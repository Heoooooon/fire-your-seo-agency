#!/usr/bin/env python3
"""Validate Schema.org JSON-LD in a page URL or a local HTML/JSX/Vue/... file.

Standard library only. Tuned for Korean clinic sites: Dentist / MedicalClinic /
LocalBusiness required properties, FAQPage Q&A shape, Korean placeholder text.

Usage:
    python3 scripts/schema_check.py https://example-dental.co.kr/
    python3 scripts/schema_check.py app/page.tsx [--json]

Exit codes: 0 pass (warnings allowed), 1 errors found or nothing to check, 2 usage/fetch error.

Adapted from AgriciDaniel/claude-seo (MIT, Copyright (c) 2026 AgriciDaniel):
hooks/validate-schema.py (script-tag tokenizer, template detection, @graph and
deprecated-type checks). Clinic/FAQ required-property rules and Korean
placeholders were added. See NOTICE.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The attribute group treats quoted values as atomic so an embedded ">" does not
# end the tag early; the fallback class excludes both quotes to avoid
# catastrophic backtracking on unterminated tags (ReDoS fix from claude-seo).
_ATTRS_RE = r'(?:"[^"]*"|\'[^\']*\'|[^"\'>])*'
SCRIPT_TAG_RE = re.compile(r"<script\b(" + _ATTRS_RE + r")>(.*?)</script\s*>", re.DOTALL | re.IGNORECASE)
LD_JSON_TYPE_RE = re.compile(
    r"""(?:^|\s)type\s*=\s*(?:"application/ld\+json"|'application/ld\+json'|application/ld\+json(?=\s|$))""",
    re.IGNORECASE,
)
SERVER_TEMPLATE_RE = re.compile(r"^(?:<\?(?:php\b|=)|<%)")
COMPONENT_EXPRESSION_RE = re.compile(r"^(?:\{\{|\{@html\b|\$\{|\{\s*[A-Za-z_$][\w$.]*)")
COMPONENT_EXTENSIONS = (".jsx", ".tsx", ".vue", ".svelte")
CHECKED_EXTENSIONS = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs", ".astro")
SCHEMA_ORG_CONTEXTS = frozenset({"https://schema.org", "http://schema.org", "https://schema.org/", "http://schema.org/"})

PLACEHOLDERS = (
    "[Business Name]", "[City]", "[Phone]", "[Address]", "[Your", "[INSERT", "[URL]", "[Email]",
    "[병원명]", "[치과명]", "[주소]", "[전화번호]", "[원장", "[진료시간]", "[대표자", "000-0000-0000",
)
BARE_PLACEHOLDER_RE = re.compile(r"\b(?:REPLACE(?:_[A-Z]+)*|TODO|lorem ipsum)\b", re.IGNORECASE)
DEPRECATED = {
    "HowTo": "rich results removed September 2023",
    "SpecialAnnouncement": "deprecated July 31, 2025",
    "CourseInfo": "retired June 2025",
    "EstimatedSalary": "retired June 2025",
    "LearningVideo": "retired June 2025",
    "ClaimReview": "no Search rich result since June 2025",
    "VehicleListing": "retired June 2025",
}
CLINIC_TYPES = {"Dentist", "MedicalClinic", "LocalBusiness", "MedicalBusiness", "Physician", "Hospital"}
CLINIC_RECOMMENDED = ("telephone", "url", "openingHoursSpecification", "geo", "image")


def extract_ld_json_blocks(content: str) -> list:
    return [body for attrs, body in SCRIPT_TAG_RE.findall(content) if LD_JSON_TYPE_RE.search(attrs)]


def is_template_expression(block: str, filepath: str = "") -> bool:
    if SERVER_TEMPLATE_RE.match(block):
        return True
    return filepath.lower().endswith(COMPONENT_EXTENSIONS) and bool(COMPONENT_EXPRESSION_RE.match(block))


def is_schema_org_context(value) -> bool:
    if isinstance(value, str):
        return value in SCHEMA_ORG_CONTEXTS
    if isinstance(value, list):
        return any(is_schema_org_context(v) for v in value)
    if isinstance(value, dict):
        return is_schema_org_context(value.get("@vocab"))
    return False


def type_set(obj: dict) -> set:
    value = obj.get("@type")
    return {v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)}


def check_clinic(obj: dict, label: str, issues: list) -> None:
    if not str(obj.get("name") or "").strip():
        issues.append(("error", "%s: clinic is missing 'name'" % label))
    address = obj.get("address")
    if isinstance(address, dict):
        if not (address.get("streetAddress") and (address.get("addressLocality") or address.get("addressRegion"))):
            issues.append(("error", "%s: PostalAddress needs streetAddress and addressLocality/addressRegion" % label))
        country = address.get("addressCountry")
        if isinstance(country, dict):
            country = country.get("name")
        if country not in ("KR", "Korea", "대한민국"):
            issues.append(("warning", "%s: address.addressCountry should be 'KR'" % label))
    elif not (isinstance(address, str) and address.strip()):
        issues.append(("error", "%s: clinic is missing 'address'" % label))
    for key in CLINIC_RECOMMENDED:
        if not obj.get(key) and not (key == "openingHoursSpecification" and obj.get("openingHours")):
            issues.append(("warning", "%s: recommended property '%s' is missing" % (label, key)))
    for key in ("url", "logo", "image"):
        value = obj.get(key)
        if isinstance(value, str) and value and not value.startswith(("http://", "https://")):
            issues.append(("warning", "%s: '%s' should be an absolute URL (%s)" % (label, key, value)))


def check_faq(obj: dict, label: str, issues: list) -> None:
    questions = obj.get("mainEntity")
    questions = questions if isinstance(questions, list) else [questions] if isinstance(questions, dict) else []
    if not questions:
        issues.append(("error", "%s: FAQPage has no mainEntity questions" % label))
    for index, q in enumerate(questions, 1):
        answer = q.get("acceptedAnswer") if isinstance(q, dict) else None
        if not isinstance(q, dict) or "Question" not in type_set(q) or not str(q.get("name") or "").strip():
            issues.append(("error", "%s: mainEntity[%d] must be a Question with a name" % (label, index)))
        elif not isinstance(answer, dict) or not str(answer.get("text") or "").strip():
            issues.append(("error", "%s: mainEntity[%d] '%s' has no acceptedAnswer.text" % (label, index, q["name"][:40])))
    issues.append(("info", "%s: FAQPage is valid Schema.org but Google FAQ rich results ended 2026-05-07; keep the Q&A visible on the page" % label))


def check_node(obj: dict, block: int, issues: list, seen_types: set, inherited_context: bool = False) -> None:
    label = "block %d" % block
    graph = obj.get("@graph")
    if "@context" not in obj and not inherited_context:
        issues.append(("error", "%s: missing @context" % label))
    elif "@context" in obj and not is_schema_org_context(obj["@context"]):
        issues.append(("error", "%s: @context should be 'https://schema.org'" % label))
    types = type_set(obj)
    seen_types |= types
    if not types and not isinstance(graph, list):
        issues.append(("error", "%s: missing @type" % label))
    text = json.dumps({k: v for k, v in obj.items() if k != "@graph"}, ensure_ascii=False)
    for placeholder in PLACEHOLDERS:
        if placeholder.lower() in text.lower():
            issues.append(("error", "%s: contains placeholder text %s" % (label, placeholder)))
    for placeholder in BARE_PLACEHOLDER_RE.findall(text):
        issues.append(("error", "%s: contains placeholder text %s" % (label, placeholder)))
    for t in sorted(types & set(DEPRECATED)):
        issues.append(("error", "%s: @type %s is deprecated (%s)" % (label, t, DEPRECATED[t])))
    named = "%s %s" % (label, "/".join(sorted(types)))
    if types & CLINIC_TYPES:
        check_clinic(obj, named, issues)
    if "FAQPage" in types:
        check_faq(obj, named, issues)
    if "@graph" in obj:
        if not isinstance(graph, list):
            issues.append(("error", "%s: @graph must be a list" % label))
            return
        for index, item in enumerate(graph, 1):
            if isinstance(item, dict):
                check_node(item, block, issues, seen_types, inherited_context or "@context" in obj)
            else:
                issues.append(("error", "%s: @graph member %d must be an object" % (label, index)))


def validate_content(content: str, filepath: str = "") -> dict:
    blocks = extract_ld_json_blocks(content)
    issues, types, checked = [], set(), 0
    for number, raw in enumerate(blocks, 1):
        raw = raw.strip()
        if is_template_expression(raw, filepath):
            issues.append(("info", "block %d: rendered at runtime, not checked statically" % number))
            continue
        checked += 1
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(("error", "block %d: invalid JSON (%s)" % (number, exc)))
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict):
                check_node(item, number, issues, types)
            else:
                issues.append(("error", "block %d: JSON-LD root must be an object or a list of objects" % number))
    errors = [m for level, m in issues if level == "error"]
    return {
        "blocks": len(blocks),
        "checked": checked,
        "types": sorted(types),
        "errors": errors,
        "warnings": [m for level, m in issues if level == "warning"],
        "info": [m for level, m in issues if level == "info"],
        "ok": checked > 0 and not errors,
    }


def load_target(target: str) -> tuple:
    if target.startswith(("http://", "https://")):
        from seo_page import fetch

        page = fetch(target)
        if page["status"] >= 400:
            raise OSError("HTTP %d for %s" % (page["status"], target))
        return page["text"], page["final_url"]
    return Path(target).read_text(encoding="utf-8", errors="replace"), target


def render(target: str, result: dict) -> str:
    lines = ["%s %s" % ("PASS" if result["ok"] else "FAIL", target),
             "blocks=%d checked=%d types=%s" % (result["blocks"], result["checked"], ",".join(result["types"]) or "-")]
    if result["blocks"] == 0:
        lines.append("ERROR no <script type=\"application/ld+json\"> block found")
    lines += ["ERROR %s" % m for m in result["errors"]]
    lines += ["WARN  %s" % m for m in result["warnings"]]
    lines += ["INFO  %s" % m for m in result["info"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate JSON-LD structured data (clinic-aware)")
    parser.add_argument("target", help="page URL or local file")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)
    try:
        content, source = load_target(args.target)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    result = validate_content(content, source)
    print(json.dumps({"target": args.target, **result}, ensure_ascii=False, indent=2) if args.as_json else render(args.target, result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
