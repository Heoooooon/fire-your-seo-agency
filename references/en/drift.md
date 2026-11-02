# drift — SEO change detection before and after a deploy

Store a clinic homepage's SEO elements as a baseline before a deploy, fetch the same page
again afterwards and judge what changed rule by rule. The goal is to catch "noindex shipped
with the deploy" or "the redesign dropped the Dentist JSON-LD" before crawlers do.

## 1. When to use it

- Right before and right after a homepage redesign or deploy (baseline → compare on one URL)
- When Naver Search Advisor or Search Console impressions drop suddenly
- Acceptance check after an outside agency touched the site

## 2. Run it

```bash
python3 scripts/seo_drift.py baseline https://example-dental.co.kr/   # before the deploy
python3 scripts/seo_drift.py compare  https://example-dental.co.kr/   # after the deploy
python3 scripts/seo_drift.py history  https://example-dental.co.kr/   # baselines and comparisons
```

Standard library only. Baselines go to `~/.cache/fire-your-seo-agency/drift/baselines.db` (SQLite);
override with `--db` or `SEO_DRIFT_DB`. compare exits 3 when any CRITICAL rule fires, so it can
gate a deploy script. Private IPs and localhost are refused (SSRF guard).

## 3. Rules

| Rule | Severity | Change caught |
|---|---|---|
| `schema_removed` | CRITICAL | All JSON-LD removed (WARNING when only FAQPage/HowTo existed) |
| `canonical_changed` | CRITICAL | Canonical URL changed |
| `canonical_removed` | CRITICAL | Canonical tag removed |
| `noindex_added` | CRITICAL | noindex appeared in meta robots or X-Robots-Tag |
| `h1_removed` | CRITICAL | H1 removed |
| `h1_changed` | CRITICAL | H1 text similarity below 50% |
| `title_removed` | CRITICAL | Title removed |
| `status_code_error` | CRITICAL | A 2xx/3xx page now returns 4xx/5xx |
| `site_verification_removed` | CRITICAL | naver-site-verification or another ownership meta removed |
| `title_changed` | WARNING | Title text changed |
| `meta_description_changed` | WARNING | Meta description changed |
| `og_tags_removed` | WARNING | All og: tags removed (KakaoTalk/Naver share previews) |
| `schema_modified` | WARNING | JSON-LD content changed |
| `schema_added` | INFO | New JSON-LD added |
| `h2_structure_changed` | INFO | H2 list changed |
| `content_hash_changed` | INFO | HTML changed (catch-all) |

## 4. Reading the result

- CRITICAL: roll back or fix now. noindex, canonical and ownership meta hit Naver and Google immediately
- WARNING: confirm it was intended; after a title/description change watch CTR for two weeks
- INFO: awareness only. Next.js and similar change the HTML hash every build, so `content_hash_changed` alone is normal
- If JSON-LD changed, run the [schema check](schema.md) next

## 5. Limits

- The two Core Web Vitals rules from claude-seo need a PageSpeed API key and were dropped; measure speed in the [measurement loop](measure.md)
- Only HTML fetched without JavaScript is checked. Client-only elements are invisible to crawlers too, so that is the right view
