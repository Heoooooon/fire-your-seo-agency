#!/usr/bin/env python3
"""Fetch a public page and extract the SEO elements the other scripts compare.

Standard library only. Shared by seo_drift.py, schema_check.py and geo_check.py.

Adapted from AgriciDaniel/claude-seo (MIT, Copyright (c) 2026 AgriciDaniel):
scripts/fetch_page.py, scripts/parse_html.py and scripts/url_safety.py were
reduced to a urllib + html.parser implementation. See NOTICE.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

USER_AGENT = "Mozilla/5.0 (compatible; fire-your-seo-agency/1.0; +https://github.com/Heoooooon/fire-your-seo-agency)"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 20
MAX_REDIRECTS = 5


class UnsafeURLError(ValueError):
    pass


def assert_public_url(url: str) -> None:
    """Reject non-http(s) schemes and hosts resolving to private/reserved IPs (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURLError("only http/https URLs with a host are accepted: %s" % url)
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeURLError("cannot resolve host %s: %s" % (parsed.hostname, exc)) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURLError("host %s resolves to non-public address %s" % (parsed.hostname, ip))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url: str, timeout: int = TIMEOUT) -> dict:
    """GET a URL, following redirects manually so every hop passes the SSRF guard.

    Returns {"url", "final_url", "status", "headers", "text", "redirects"}.
    4xx/5xx responses are returned, not raised: the status is itself a tracked field.
    """
    current = url
    redirects = []
    for _ in range(MAX_REDIRECTS + 1):
        assert_public_url(current)
        request = urllib.request.Request(current, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"})
        try:
            response = _OPENER.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        status = response.getcode()
        headers = {k.lower(): v for k, v in response.headers.items()}
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            redirects.append({"status": status, "from": current})
            response.close()
            current = urljoin(current, headers["location"])
            continue
        body = response.read(MAX_BYTES + 1)
        response.close()
        if len(body) > MAX_BYTES:
            body = body[:MAX_BYTES]
        charset = response.headers.get_content_charset() or "utf-8"
        return {
            "url": url,
            "final_url": current,
            "status": status,
            "headers": headers,
            "text": body.decode(charset, errors="replace"),
            "redirects": redirects,
        }
    raise UnsafeURLError("too many redirects (>%d) starting at %s" % (MAX_REDIRECTS, url))


class _SEOParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data = {
            "title": None,
            "meta_description": None,
            "meta_robots": None,
            "canonical": None,
            "h1": [],
            "h2": [],
            "h3": [],
            "open_graph": {},
            "verification": {},
            "jsonld_raw": [],
            "paragraphs": [],
            "lang": None,
        }
        self._capture = None
        self._buffer = []
        self._script_ld = False
        self._skip_depth = 0
        self.visible_chars = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.data["lang"] = a["lang"]
        if tag == "meta":
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            content = a.get("content", "").strip()
            if name == "description" and self.data["meta_description"] is None:
                self.data["meta_description"] = content
            elif name in ("robots", "googlebot", "yeti") and content:
                tokens = [t for t in (self.data["meta_robots"] or "").split(", ") if t]
                tokens += [t.strip() for t in content.split(",") if t.strip() and t.strip() not in tokens]
                self.data["meta_robots"] = ", ".join(tokens)
            elif name in ("naver-site-verification", "google-site-verification", "msvalidate.01"):
                self.data["verification"][name] = content
            if prop.startswith("og:") and content:
                self.data["open_graph"][prop] = content
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.data["canonical"] = a.get("href") or None
        elif tag == "script":
            if a.get("type", "").strip().lower() == "application/ld+json":
                self._script_ld = True
                self._buffer = []
            else:
                self._skip_depth += 1
        elif tag in ("style", "noscript", "template"):
            self._skip_depth += 1
        elif tag in ("title", "h1", "h2", "h3", "p") and self._capture is None:
            self._capture = tag
            self._buffer = []

    def handle_endtag(self, tag):
        if tag == "script":
            if self._script_ld:
                self.data["jsonld_raw"].append("".join(self._buffer))
                self._script_ld = False
                self._buffer = []
            elif self._skip_depth:
                self._skip_depth -= 1
        elif tag in ("style", "noscript", "template") and self._skip_depth:
            self._skip_depth -= 1
        elif tag == self._capture:
            text = " ".join("".join(self._buffer).split())
            if tag == "title":
                if self.data["title"] is None:
                    self.data["title"] = text
            elif tag == "p":
                if text:
                    self.data["paragraphs"].append(text)
            elif text:
                self.data[tag].append(text)
            self._capture = None
            self._buffer = []

    def handle_data(self, data):
        if self._script_ld or self._capture:
            self._buffer.append(data)
        if not self._skip_depth and not self._script_ld:
            self.visible_chars += len(data.strip())


def parse_jsonld(raw_blocks: list) -> tuple:
    parsed, errors = [], []
    for index, raw in enumerate(raw_blocks, 1):
        try:
            parsed.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            errors.append("block %d: invalid JSON (%s)" % (index, exc))
    return parsed, errors


def parse_html(html: str, base_url: str = "") -> dict:
    parser = _SEOParser()
    parser.feed(html)
    parser.close()
    data = parser.data
    if data["canonical"] and base_url:
        data["canonical"] = urljoin(base_url, data["canonical"])
    data["schema"], data["schema_errors"] = parse_jsonld(data["jsonld_raw"])
    data["visible_text_chars"] = parser.visible_chars
    return data


def load_page(url: str) -> dict:
    """Fetch + parse. X-Robots-Tag is merged into meta_robots so noindex in a header is not missed."""
    page = fetch(url)
    parsed = parse_html(page["text"], page["final_url"])
    header_robots = page["headers"].get("x-robots-tag")
    if header_robots:
        parsed["meta_robots"] = (parsed["meta_robots"] + ", " if parsed["meta_robots"] else "") + header_robots
    parsed["x_robots_tag"] = header_robots
    return {**page, "parsed": parsed}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: seo_page.py <url>", file=sys.stderr)
        return 2
    try:
        page = load_page(argv[0])
    except (UnsafeURLError, urllib.error.URLError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    parsed = dict(page["parsed"])
    parsed.pop("jsonld_raw", None)
    parsed["paragraphs"] = parsed["paragraphs"][:5]
    print(json.dumps({"status": page["status"], "final_url": page["final_url"], **parsed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
