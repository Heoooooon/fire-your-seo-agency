#!/usr/bin/env python3
"""SEO drift monitor: baseline -> compare -> history for one URL.

Standard library only. Storage: SQLite at ~/.cache/fire-your-seo-agency/drift/baselines.db
(override with --db or SEO_DRIFT_DB).

Usage:
    python3 scripts/seo_drift.py baseline <url>
    python3 scripts/seo_drift.py compare <url> [--baseline-id N]
    python3 scripts/seo_drift.py history <url> [--limit N]

Exit codes: 0 ok, 1 error, 3 compare found CRITICAL drift.

Adapted from AgriciDaniel/claude-seo (MIT, Copyright (c) 2026 AgriciDaniel):
scripts/drift_baseline.py, drift_compare.py, drift_history.py. Changes: the
PageSpeed/CWV rules (needs an API key) were removed, X-Robots-Tag is folded
into the noindex rule, and a Naver/Google site-verification rule was added.
See NOTICE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import urllib.error
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seo_page import UnsafeURLError, load_page  # noqa: E402

DEFAULT_DB = Path.home() / ".cache" / "fire-your-seo-agency" / "drift" / "baselines.db"
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "n_media", "n_query"}
RETIRED_RICH_RESULT_TYPES = {"FAQPage", "HowTo", "Dataset"}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = "%s:%d" % (host, port) if port else host
    query = parse_qs(parsed.query, keep_blank_values=True)
    kept = {k: v for k, v in sorted(query.items()) if k not in TRACKING_PARAMS}
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", urlencode(kept, doseq=True), ""))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            snapshot_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_baselines_url ON baselines(url);
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            baseline_id INTEGER NOT NULL REFERENCES baselines(id),
            timestamp TEXT NOT NULL,
            critical INTEGER NOT NULL,
            warning INTEGER NOT NULL,
            info INTEGER NOT NULL,
            result_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_comparisons_url ON comparisons(url);
        """
    )
    return conn


def snapshot(page: dict) -> dict:
    parsed = page["parsed"]
    schema = parsed["schema"]
    return {
        "status_code": page["status"],
        "final_url": page["final_url"],
        "title": parsed["title"],
        "meta_description": parsed["meta_description"],
        "canonical": parsed["canonical"],
        "robots": parsed["meta_robots"],
        "h1": parsed["h1"],
        "h2": parsed["h2"],
        "h3": parsed["h3"],
        "open_graph": parsed["open_graph"],
        "verification": parsed["verification"],
        "schema_types": schema_types(schema),
        "schema_count": len(schema),
        "schema_hash": sha256(json.dumps(schema, sort_keys=True, ensure_ascii=False)) if schema else None,
        "html_hash": sha256(page["text"]),
    }


def schema_types(blocks: list) -> list:
    found = set()

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            value = node.get("@type")
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, str) and item:
                    found.add(item.rsplit("/", 1)[-1])
            if isinstance(node.get("@graph"), list):
                walk(node["@graph"])

    walk(blocks)
    return sorted(found)


def finding(rule: str, severity: str, triggered: bool, old, new, message: str) -> dict:
    return {"rule": rule, "severity": severity, "triggered": bool(triggered), "old": old, "new": new, "message": message}


def first(items: list):
    return items[0] if items else None


def compare_snapshots(old: dict, new: dict) -> list:
    rules = []
    old_types = old.get("schema_types") or []
    removed = old.get("schema_count", 0) > 0 and new.get("schema_count", 0) == 0
    retired_only = bool(old_types) and all(t in RETIRED_RICH_RESULT_TYPES for t in old_types)
    rules.append(finding(
        "schema_removed", "WARNING" if retired_only else "CRITICAL", removed,
        old_types, [],
        "All JSON-LD removed (%s). Restore Dentist/LocalBusiness markup before Naver/Google recrawl." % ", ".join(old_types),
    ))
    oc, nc = old.get("canonical"), new.get("canonical")
    rules.append(finding("canonical_changed", "CRITICAL", bool(oc and nc and oc != nc), oc, nc,
                         "Canonical URL changed; ranking signals move to the new URL."))
    rules.append(finding("canonical_removed", "CRITICAL", bool(oc and not nc), oc, nc,
                         "Canonical tag removed; search engines will guess the canonical."))
    orb, nrb = (old.get("robots") or "").lower(), (new.get("robots") or "").lower()
    rules.append(finding("noindex_added", "CRITICAL", "noindex" not in orb and "noindex" in nrb,
                         old.get("robots"), new.get("robots"),
                         "noindex added (meta robots or X-Robots-Tag); the page will drop out of Naver/Google."))
    oh1, nh1 = first(old.get("h1") or []), first(new.get("h1") or [])
    rules.append(finding("h1_removed", "CRITICAL", bool(oh1 and not nh1), oh1, nh1, "H1 removed."))
    ratio = SequenceMatcher(None, oh1 or "", nh1 or "").ratio() if oh1 and nh1 else 1.0
    rules.append(finding("h1_changed", "CRITICAL", ratio < 0.5, oh1, nh1,
                         "H1 changed significantly (similarity %d%%)." % round(ratio * 100)))
    ot, nt = (old.get("title") or "").strip(), (new.get("title") or "").strip()
    rules.append(finding("title_removed", "CRITICAL", bool(ot and not nt), ot, nt, "Title tag removed."))
    os_, ns = old.get("status_code"), new.get("status_code")
    rules.append(finding("status_code_error", "CRITICAL", bool(os_ and os_ < 400 and ns and ns >= 400), os_, ns,
                         "Page now returns HTTP %s (was %s)." % (ns, os_)))
    lost = sorted(k for k in (old.get("verification") or {}) if k not in (new.get("verification") or {}))
    rules.append(finding("site_verification_removed", "CRITICAL", bool(lost), lost, [],
                         "Site verification meta removed (%s); Naver Search Advisor / Search Console ownership can lapse." % ", ".join(lost)))

    rules.append(finding("title_changed", "WARNING", bool(ot and nt and ot != nt), ot, nt,
                         "Title changed; watch CTR in Search Advisor / Search Console for 2 weeks."))
    om, nm = (old.get("meta_description") or "").strip(), (new.get("meta_description") or "").strip()
    rules.append(finding("meta_description_changed", "WARNING", bool(om and nm and om != nm), om, nm,
                         "Meta description changed."))
    rules.append(finding("og_tags_removed", "WARNING", bool(old.get("open_graph")) and not new.get("open_graph"),
                         sorted(old.get("open_graph") or {}), [],
                         "All Open Graph tags removed; KakaoTalk/Naver share previews break."))
    osh, nsh = old.get("schema_hash"), new.get("schema_hash")
    rules.append(finding("schema_modified", "WARNING", bool(osh and nsh and osh != nsh),
                         old_types, new.get("schema_types"),
                         "JSON-LD content changed; run scripts/schema_check.py on the page."))

    rules.append(finding("schema_added", "INFO", old.get("schema_count", 0) == 0 and new.get("schema_count", 0) > 0,
                         [], new.get("schema_types"), "New JSON-LD added; validate it."))
    rules.append(finding("h2_structure_changed", "INFO", (old.get("h2") or []) != (new.get("h2") or []),
                         len(old.get("h2") or []), len(new.get("h2") or []), "H2 structure changed."))
    rules.append(finding("content_hash_changed", "INFO", old.get("html_hash") != new.get("html_hash"),
                         (old.get("html_hash") or "")[:12], (new.get("html_hash") or "")[:12],
                         "HTML changed (catch-all; dynamic tokens also trigger this)."))
    return rules


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_baseline(conn, url: str) -> dict:
    page = load_page(url)
    snap = snapshot(page)
    norm = normalize_url(url)
    cur = conn.execute("INSERT INTO baselines (url, timestamp, snapshot_json) VALUES (?, ?, ?)",
                       (norm, now_iso(), json.dumps(snap, ensure_ascii=False)))
    conn.commit()
    return {"status": "ok", "baseline_id": cur.lastrowid, "url": norm, "snapshot": {
        **{k: snap[k] for k in ("status_code", "title", "canonical", "robots", "schema_types", "verification")},
        "h1": first(snap["h1"]), "h2_count": len(snap["h2"]), "og_tags": len(snap["open_graph"]),
    }}


def cmd_compare(conn, url: str, baseline_id=None) -> dict:
    norm = normalize_url(url)
    if baseline_id is None:
        row = conn.execute("SELECT * FROM baselines WHERE url = ? ORDER BY id DESC LIMIT 1", (norm,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM baselines WHERE url = ? AND id = ?", (norm, baseline_id)).fetchone()
    if row is None:
        return {"error": "no baseline for %s; run `seo_drift.py baseline %s` first" % (norm, url)}
    new = snapshot(load_page(url))
    rules = compare_snapshots(json.loads(row["snapshot_json"]), new)
    hit = [r for r in rules if r["triggered"]]
    counts = {s.lower(): sum(1 for r in hit if r["severity"] == s) for s in ("CRITICAL", "WARNING", "INFO")}
    result = {"status": "ok", "url": norm, "baseline_id": row["id"], "baseline_timestamp": row["timestamp"],
              "compared_at": now_iso(), "summary": {"rules": len(rules), "triggered": len(hit), **counts},
              "triggered": hit, "passed": [r["rule"] for r in rules if not r["triggered"]]}
    conn.execute("INSERT INTO comparisons (url, baseline_id, timestamp, critical, warning, info, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (norm, row["id"], result["compared_at"], counts["critical"], counts["warning"], counts["info"],
                  json.dumps(result, ensure_ascii=False)))
    conn.commit()
    return result


def cmd_history(conn, url: str, limit: int) -> dict:
    norm = normalize_url(url)
    baselines = [dict(id=r["id"], timestamp=r["timestamp"]) for r in conn.execute(
        "SELECT id, timestamp FROM baselines WHERE url = ? ORDER BY id DESC LIMIT ?", (norm, limit))]
    comparisons = [dict(r) for r in conn.execute(
        "SELECT id, baseline_id, timestamp, critical, warning, info FROM comparisons WHERE url = ? ORDER BY id DESC LIMIT ?",
        (norm, limit))]
    return {"status": "ok", "url": norm, "baselines": baselines, "comparisons": comparisons}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SEO drift monitor (baseline / compare / history)")
    parser.add_argument("command", choices=["baseline", "compare", "history"])
    parser.add_argument("url")
    parser.add_argument("--baseline-id", type=int)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--db", default=os.environ.get("SEO_DRIFT_DB", str(DEFAULT_DB)))
    args = parser.parse_args(argv)
    conn = connect(Path(args.db).expanduser())
    try:
        if args.command == "baseline":
            result = cmd_baseline(conn, args.url)
        elif args.command == "compare":
            result = cmd_compare(conn, args.url, args.baseline_id)
        else:
            result = cmd_history(conn, args.url, args.limit)
    except (UnsafeURLError, urllib.error.URLError, OSError) as exc:
        result = {"error": str(exc)}
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("error"):
        return 1
    if args.command == "compare" and result["summary"]["critical"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
