"""Offline tests for the ported check scripts (scripts/seo_drift.py, schema_check.py, geo_check.py)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import geo_check  # noqa: E402
import schema_check  # noqa: E402
import seo_drift  # noqa: E402
import seo_page  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "broken-dentist.html"
VALID_PAGE = """<html lang="ko"><head>
<title>OO치과 | 임플란트</title>
<meta name="description" content="OO치과 진료 안내">
<meta name="robots" content="index, follow">
<meta name="naver-site-verification" content="abc123">
<meta property="og:title" content="OO치과"><meta property="og:image" content="https://example-dental.co.kr/og.png">
<link rel="canonical" href="/">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Dentist", "name": "OO치과의원",
 "url": "https://example-dental.co.kr/", "telephone": "031-000-1234", "image": "https://example-dental.co.kr/a.jpg",
 "geo": {"@type": "GeoCoordinates", "latitude": 37.1, "longitude": 126.9},
 "openingHours": "Mo-Fr 10:00-18:30",
 "sameAs": ["https://blog.naver.com/example"],
 "address": {"@type": "PostalAddress", "streetAddress": "OO로 12", "addressLocality": "화성시", "addressCountry": "KR"}}
</script></head>
<body><h1>OO치과</h1><h2>임플란트는 얼마나 걸리나요?</h2><p>%s</p></body></html>
""" % ("임플란트 치료 기간은 뼈 상태에 따라 다르며 보통 3개월에서 6개월이 걸립니다. " * 30)


def page_dict(html: str, status: int = 200, headers=None) -> dict:
    url = "https://example-dental.co.kr/"
    page = {"url": url, "final_url": url, "status": status, "headers": headers or {}, "text": html, "redirects": []}
    parsed = seo_page.parse_html(html, url)
    return {**page, "parsed": parsed}


class DriftTests(unittest.TestCase):
    def test_identical_page_triggers_nothing_but_hash(self):
        snap = seo_drift.snapshot(page_dict(VALID_PAGE))
        hits = [r["rule"] for r in seo_drift.compare_snapshots(snap, dict(snap)) if r["triggered"]]
        self.assertEqual(hits, [])

    def test_noindex_and_lost_naver_verification_are_critical(self):
        old = seo_drift.snapshot(page_dict(VALID_PAGE))
        broken = VALID_PAGE.replace('content="index, follow"', 'content="noindex, nofollow"').replace(
            '<meta name="naver-site-verification" content="abc123">', "")
        new = seo_drift.snapshot(page_dict(broken))
        critical = {r["rule"] for r in seo_drift.compare_snapshots(old, new) if r["triggered"] and r["severity"] == "CRITICAL"}
        self.assertEqual(critical, {"noindex_added", "site_verification_removed"})

    def test_x_robots_tag_header_counts_as_noindex(self):
        page = page_dict(VALID_PAGE, headers={"x-robots-tag": "noindex"})
        page["parsed"]["meta_robots"] += ", " + page["headers"]["x-robots-tag"]
        old = seo_drift.snapshot(page_dict(VALID_PAGE))
        hits = {r["rule"] for r in seo_drift.compare_snapshots(old, seo_drift.snapshot(page)) if r["triggered"]}
        self.assertIn("noindex_added", hits)

    def test_removing_only_faq_schema_is_warning(self):
        faq = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[]}</script>'
        old = seo_drift.snapshot(page_dict("<html><head>%s</head><body><h1>a</h1></body></html>" % faq))
        new = seo_drift.snapshot(page_dict("<html><body><h1>a</h1></body></html>"))
        rule = next(r for r in seo_drift.compare_snapshots(old, new) if r["rule"] == "schema_removed")
        self.assertTrue(rule["triggered"])
        self.assertEqual(rule["severity"], "WARNING")

    def test_normalize_url_drops_tracking_and_trailing_slash(self):
        self.assertEqual(
            seo_drift.normalize_url("HTTPS://Example-Dental.co.kr:443/about/?utm_source=naver&b=2&a=1"),
            "https://example-dental.co.kr/about?a=1&b=2",
        )

    def test_baseline_compare_history_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "drift.db"
            pages = iter([page_dict(VALID_PAGE), page_dict(VALID_PAGE.replace("OO치과 | 임플란트", "OO치과"))])
            with mock.patch.object(seo_drift, "load_page", lambda url: next(pages)):
                conn = seo_drift.connect(db)
                seo_drift.cmd_baseline(conn, "https://example-dental.co.kr/")
                result = seo_drift.cmd_compare(conn, "https://example-dental.co.kr/")
                history = seo_drift.cmd_history(conn, "https://example-dental.co.kr/", 5)
                conn.close()
        self.assertEqual([r["rule"] for r in result["triggered"]], ["title_changed", "content_hash_changed"])
        self.assertEqual((len(history["baselines"]), len(history["comparisons"])), (1, 1))


class SchemaTests(unittest.TestCase):
    def test_broken_fixture_fails_with_each_problem(self):
        result = schema_check.validate_content(FIXTURE.read_text(encoding="utf-8"), str(FIXTURE))
        errors = "\n".join(result["errors"])
        self.assertFalse(result["ok"])
        for expected in ("[치과명]", "missing 'address'", "acceptedAnswer.text", "HowTo", "invalid JSON"):
            self.assertIn(expected, errors)

    def test_valid_dentist_passes(self):
        result = schema_check.validate_content(VALID_PAGE)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["types"], ["Dentist"])

    def test_page_without_jsonld_is_not_a_pass(self):
        self.assertFalse(schema_check.validate_content("<html><body>no schema</body></html>")["ok"])

    def test_jsx_expression_is_skipped_not_reported_invalid(self):
        jsx = '<script type="application/ld+json" dangerouslySetInnerHTML>{JSON.stringify(schema)}</script>'
        result = schema_check.validate_content(jsx, "app/page.tsx")
        self.assertEqual((result["checked"], result["errors"]), (0, []))

    def test_hook_blocks_broken_file_and_allows_valid_file(self):
        hook = ROOT / "hooks" / "validate-schema.py"
        with tempfile.TemporaryDirectory() as tmp:
            valid = Path(tmp) / "index.html"
            valid.write_text(VALID_PAGE, encoding="utf-8")
            codes = []
            for path in (FIXTURE, valid):
                event = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})
                proc = subprocess.run([sys.executable, str(hook)], input=event, capture_output=True, text=True, timeout=30)
                codes.append(proc.returncode)
        self.assertEqual(codes, [2, 0])


class PageAndGeoTests(unittest.TestCase):
    def test_private_and_non_http_urls_are_refused(self):
        for url in ("http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd"):
            with self.assertRaises(seo_page.UnsafeURLError):
                seo_page.assert_public_url(url)

    def test_geo_flags_blocked_naver_yeti_but_not_training_blocks(self):
        robots = "User-agent: Yeti\nDisallow: /\n\nUser-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"

        def fake_fetch(url, timeout=20):
            text = robots if url.endswith("/robots.txt") else ""
            return {"url": url, "final_url": url, "status": 200 if text else 404, "headers": {}, "text": text, "redirects": []}

        with mock.patch.object(geo_check, "load_page", lambda url: page_dict(VALID_PAGE)), \
                mock.patch.object(geo_check, "fetch", fake_fetch):
            report = geo_check.analyze("https://example-dental.co.kr/")
        levels = {c["check"]: (c["level"], c["detail"]) for c in report["checks"]}
        self.assertEqual(levels["robots_search_crawlers"], ("fail", "blocked: Yeti"))
        self.assertEqual(levels["robots_training_crawlers"][0], "info")
        self.assertEqual(levels["question_headings"][0], "pass")
        self.assertFalse(report["llms_txt"]["present"])


if __name__ == "__main__":
    unittest.main()
