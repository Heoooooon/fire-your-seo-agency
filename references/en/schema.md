# schema — structured data (JSON-LD) check

Check that a clinic page's JSON-LD passes syntax, required-property and placeholder rules.
Accepts a live page URL or a local source file (.html, .tsx, .vue, ...). The rule that JSON-LD
never states facts the page does not show is the same as in [AEO](aeo.md).

## 1. Run it

```bash
python3 scripts/schema_check.py https://example-dental.co.kr/      # live page
python3 scripts/schema_check.py app/page.tsx --json                # local file, JSON output
```

Exit codes: 0 pass (warnings allowed), 1 errors or nothing to check, 2 usage/fetch error.
`tests/fixtures/broken-dentist.html` is a deliberately broken example.

## 2. Minimum for a clinic page

| Target | Error (fail) | Warning |
|---|---|---|
| Every block | Invalid JSON, missing @context/@type, placeholders ([치과명], 000-0000-0000, ...), retired types (HowTo, ...) | — |
| Dentist · MedicalClinic · LocalBusiness | Missing name, missing address or no streetAddress/addressLocality | Missing telephone/url/openingHoursSpecification/geo/image, relative URLs, addressCountry not KR |
| FAQPage | No questions, Question without name, no acceptedAnswer.text | — (Google FAQ rich results ended 2026-05-07; reported as info) |

```json
{
  "@context": "https://schema.org",
  "@type": ["Dentist", "MedicalClinic"],
  "name": "OO치과의원",
  "url": "https://example-dental.co.kr/",
  "telephone": "031-000-1234",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "향남읍 OO로 12, 3층",
    "addressLocality": "화성시",
    "addressRegion": "경기도",
    "addressCountry": "KR"
  },
  "openingHoursSpecification": [
    {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Thursday", "Friday"], "opens": "10:00", "closes": "18:30"}
  ],
  "sameAs": ["https://map.naver.com/p/entry/place/0000000000", "https://blog.naver.com/example"]
}
```

Replace the phone, address and Place ID with real values, using the same name/address/phone as Naver Place.

## 3. Check on save (Claude Code hook)

Installed as a Claude Code plugin, `hooks/hooks.json` runs `hooks/validate-schema.py` right after
Edit/Write. Errors go back to Claude with exit code 2; warnings only are passed as context.
Blocks built at runtime, such as JSX `{JSON.stringify(schema)}`, are skipped. OmO/Senpi has no
hook, so run `schema_check.py` yourself after editing.

## 4. What a pass means

- Pass means "syntax and required properties are right", not a rich-result guarantee
- Confirm once more with Google's Rich Results Test and Naver Search Advisor's structured data report
- Reviews and ratings (AggregateRating) only for reviews actually visible on the page; check medical-advertising review rules first
