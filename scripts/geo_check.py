#!/usr/bin/env python3
"""GEO / AI-citation readiness check for one public page (Naver + AI search).

Standard library only, no paid APIs. Reports what a crawler sees without
JavaScript: AI and search crawler access in robots.txt (search vs training
reported separately), llms.txt presence (no weight), SSR text, entity markup,
question headings, freshness and Naver signals.

Usage:
    python3 scripts/geo_check.py https://example-dental.co.kr/ [--json]

Exit codes: 0 report printed (even with FAIL items), 2 fetch error.

Adapted from AgriciDaniel/claude-seo (MIT, Copyright (c) 2026 AgriciDaniel):
skills/seo-geo/SKILL.md criteria (crawler table, citability, structure,
authority, technical accessibility). DataForSEO checks were dropped; Naver
Yeti and naver-site-verification checks were added. See NOTICE.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seo_page import UnsafeURLError, fetch, load_page  # noqa: E402

SEARCH_CRAWLERS = {
    "Googlebot": "Google Search, AI Overviews, AI Mode",
    "Yeti": "Naver search and AI Briefing",
    "Bingbot": "Bing, Copilot",
    "OAI-SearchBot": "ChatGPT Search citations",
    "Claude-SearchBot": "Claude search citations",
    "PerplexityBot": "Perplexity search",
    "Applebot": "Siri, Spotlight, Safari",
}
TRAINING_CRAWLERS = {
    "GPTBot": "OpenAI model training",
    "ClaudeBot": "Anthropic model training",
    "Google-Extended": "Gemini/Vertex training and grounding (not Google Search)",
    "Applebot-Extended": "Apple Intelligence training opt-out",
    "CCBot": "Common Crawl",
}
CLINIC_TYPES = {"Dentist", "MedicalClinic", "LocalBusiness", "MedicalBusiness", "Physician", "Hospital"}
QUESTION_RE = re.compile(r"(\?|？|나요|가요|까요|인가요|있나요|되나요|무엇|어떻게|언제|얼마|왜)\s*$")
SAMEAS_HINTS = ("naver.com", "naver.me", "youtube.com", "instagram.com", "kakao.com", "pf.kakao.com", "facebook.com")


def walk_nodes(blocks):
    stack = list(blocks)
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            yield node
            stack.extend(v for v in node.values() if isinstance(v, (dict, list)))


def node_types(node: dict) -> set:
    value = node.get("@type")
    return {v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)}


def robots_report(page_url: str) -> dict:
    robots_url = urljoin(page_url, "/robots.txt")
    try:
        response = fetch(robots_url)
    except (UnsafeURLError, urllib.error.URLError, OSError) as exc:
        return {"url": robots_url, "status": None, "error": str(exc), "search": {}, "training": {}}
    parser = urllib.robotparser.RobotFileParser()
    if response["status"] >= 400:
        parser.parse([])
    else:
        parser.parse(response["text"].splitlines())
    path = urlparse(page_url).path or "/"
    return {
        "url": robots_url,
        "status": response["status"],
        "search": {bot: parser.can_fetch(bot, path) for bot in SEARCH_CRAWLERS},
        "training": {bot: parser.can_fetch(bot, path) for bot in TRAINING_CRAWLERS},
    }


def llms_report(page_url: str) -> dict:
    url = urljoin(page_url, "/llms.txt")
    try:
        response = fetch(url)
    except (UnsafeURLError, urllib.error.URLError, OSError) as exc:
        return {"url": url, "present": False, "error": str(exc)}
    is_html = "html" in response["headers"].get("content-type", "") or response["text"].lstrip()[:15].lower().startswith(("<!doctype", "<html"))
    return {"url": url, "status": response["status"], "present": response["status"] == 200 and not is_html,
            "bytes": len(response["text"].encode("utf-8"))}


def check(items: list, name: str, level: str, detail: str) -> None:
    items.append({"check": name, "level": level, "detail": detail})


def analyze(url: str) -> dict:
    page = load_page(url)
    parsed = page["parsed"]
    nodes = list(walk_nodes(parsed["schema"]))
    types = set().union(*(node_types(n) for n in nodes)) if nodes else set()
    items = []

    check(items, "http_status", "pass" if page["status"] == 200 else "fail", "HTTP %d at %s" % (page["status"], page["final_url"]))
    robots = (parsed["meta_robots"] or "").lower()
    check(items, "indexable", "fail" if "noindex" in robots else "pass", "robots: %s" % (parsed["meta_robots"] or "(none)"))
    chars = parsed["visible_text_chars"]
    check(items, "ssr_text", "pass" if chars >= 1500 else "warn" if chars >= 300 else "fail",
          "%d visible text characters without JavaScript (many AI crawlers do not run JS)" % chars)
    check(items, "h1", "pass" if len(parsed["h1"]) == 1 else "warn", "%d H1: %s" % (len(parsed["h1"]), " | ".join(parsed["h1"][:2])))

    headings = parsed["h2"] + parsed["h3"]
    questions = [h for h in headings if QUESTION_RE.search(h)]
    check(items, "question_headings", "pass" if questions else "warn",
          "%d of %d H2/H3 are questions%s" % (len(questions), len(headings), (": " + " | ".join(questions[:3])) if questions else ""))
    answers = [p for p in parsed["paragraphs"] if 40 <= len(p) <= 400]
    check(items, "answer_paragraphs", "pass" if len(answers) >= 3 else "warn",
          "%d self-contained paragraphs of 40-400 chars (quotable answer blocks)" % len(answers))
    faq_answers = sum(1 for n in nodes if "Question" in node_types(n) and isinstance(n.get("acceptedAnswer"), dict))
    check(items, "faq_qa", "pass" if faq_answers else "warn", "%d Q&A pairs in JSON-LD (keep the same Q&A visible on the page)" % faq_answers)

    clinic = [n for n in nodes if node_types(n) & CLINIC_TYPES]
    check(items, "entity_schema", "pass" if clinic else "warn" if nodes else "fail",
          "JSON-LD types: %s" % (", ".join(sorted(types)) or "none"))
    same_as = []
    for n in clinic:
        value = n.get("sameAs") or []
        same_as += value if isinstance(value, list) else [value]
    linked = sorted({h for h in SAMEAS_HINTS for s in same_as if isinstance(s, str) and h in s})
    check(items, "entity_sameas", "pass" if linked else "warn",
          "%d sameAs links (%s); link Naver Place/Blog, YouTube, Instagram" % (len(same_as), ", ".join(linked) or "none"))
    people = [n for n in nodes if node_types(n) & {"Person", "Physician"}]
    check(items, "author_or_doctor", "pass" if people else "warn", "%d Person/Physician nodes (doctor credentials support E-E-A-T)" % len(people))
    dated = any(n.get("dateModified") or n.get("datePublished") for n in nodes) or "article:modified_time" in parsed["open_graph"]
    check(items, "freshness", "pass" if dated else "warn", "dateModified/datePublished %s" % ("present" if dated else "missing"))

    check(items, "naver_verification", "pass" if parsed["verification"].get("naver-site-verification") else "warn",
          "naver-site-verification meta %s" % ("present" if parsed["verification"].get("naver-site-verification") else "missing"))
    og = parsed["open_graph"]
    check(items, "open_graph", "pass" if {"og:title", "og:image"} <= set(og) else "warn", "%d og: tags (KakaoTalk/Naver share preview)" % len(og))

    robots_txt = robots_report(page["final_url"])
    blocked_search = [b for b, ok in robots_txt["search"].items() if not ok]
    check(items, "robots_search_crawlers", "fail" if blocked_search else "pass" if robots_txt["search"] else "warn",
          ("blocked: " + ", ".join(blocked_search)) if blocked_search else robots_txt.get("error") or "all search/citation crawlers allowed")
    blocked_training = [b for b, ok in robots_txt["training"].items() if not ok]
    check(items, "robots_training_crawlers", "info",
          ("blocked: " + ", ".join(blocked_training)) if blocked_training else "training crawlers allowed (licensing choice, not a visibility factor)")
    llms = llms_report(page["final_url"])
    check(items, "llms_txt", "info", "%s (%s). Google ignores llms.txt; no score weight" % ("present" if llms["present"] else "missing", llms["url"]))

    scored = [i for i in items if i["level"] in ("pass", "warn", "fail")]
    return {
        "url": url,
        "final_url": page["final_url"],
        "title": parsed["title"],
        "score": {"pass": sum(i["level"] == "pass" for i in scored), "total": len(scored),
                  "warn": sum(i["level"] == "warn" for i in scored), "fail": sum(i["level"] == "fail" for i in scored)},
        "checks": items,
        "robots": robots_txt,
        "llms_txt": llms,
    }


def render(report: dict) -> str:
    s = report["score"]
    lines = ["GEO readiness %s" % report["final_url"], "title: %s" % report["title"],
             "score: %d/%d pass, %d warn, %d fail (unweighted checklist)" % (s["pass"], s["total"], s["warn"], s["fail"]), ""]
    for item in report["checks"]:
        lines.append("%-5s %-25s %s" % (item["level"].upper(), item["check"], item["detail"]))
    lines.append("")
    lines.append("crawler access for %s:" % report["robots"]["url"])
    for group, names in (("search", SEARCH_CRAWLERS), ("training", TRAINING_CRAWLERS)):
        for bot, purpose in names.items():
            allowed = report["robots"][group].get(bot)
            lines.append("  %-8s %-18s %-8s %s" % (group, bot, {True: "allowed", False: "BLOCKED", None: "unknown"}[allowed], purpose))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GEO / AI-citation readiness check (Naver-aware)")
    parser.add_argument("url")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.url)
    except (UnsafeURLError, urllib.error.URLError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
