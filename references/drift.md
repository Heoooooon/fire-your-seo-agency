# drift — 배포 전후 SEO 변경 감지

치과 홈페이지를 배포하기 전에 SEO 요소를 기준선으로 저장하고, 배포 후 같은 페이지를 다시 받아
무엇이 바뀌었는지 규칙별로 판정한다. "배포했더니 noindex가 따라 나갔다", "리뉴얼하면서 Dentist
JSON-LD가 빠졌다" 같은 사고를 수집 전에 잡는 것이 목적이다.

## 1. 언제 쓰나

- 홈페이지 리뉴얼·배포 직전과 직후 (같은 URL로 baseline → compare)
- 네이버 서치어드바이저·Search Console에서 노출이 갑자기 떨어졌을 때 무엇이 바뀌었는지 확인
- 외주 제작사가 손댄 뒤 인수 확인

## 2. 실행

```bash
python3 scripts/seo_drift.py baseline https://example-dental.co.kr/   # 배포 전 기준선
python3 scripts/seo_drift.py compare  https://example-dental.co.kr/   # 배포 후 비교
python3 scripts/seo_drift.py history  https://example-dental.co.kr/   # 기준선·비교 이력
```

표준 라이브러리만 쓴다. 기준선은 `~/.cache/fire-your-seo-agency/drift/baselines.db`(SQLite)에 쌓이며
`--db` 또는 `SEO_DRIFT_DB`로 위치를 바꾼다. compare는 CRITICAL이 하나라도 있으면 종료 코드 3을
돌려주므로 배포 스크립트의 게이트로 걸 수 있다. 사설 IP·localhost는 거부한다(SSRF 방지).

## 3. 규칙

| 규칙 | 등급 | 잡는 변화 |
|---|---|---|
| `schema_removed` | CRITICAL | JSON-LD가 전부 사라짐 (FAQPage·HowTo만 있었으면 WARNING) |
| `canonical_changed` | CRITICAL | canonical 주소가 바뀜 |
| `canonical_removed` | CRITICAL | canonical 태그가 사라짐 |
| `noindex_added` | CRITICAL | meta robots·X-Robots-Tag에 noindex가 생김 |
| `h1_removed` | CRITICAL | H1이 사라짐 |
| `h1_changed` | CRITICAL | H1 문구 유사도 50% 미만 |
| `title_removed` | CRITICAL | title이 사라짐 |
| `status_code_error` | CRITICAL | 정상 응답이 4xx·5xx로 바뀜 |
| `site_verification_removed` | CRITICAL | naver-site-verification 등 소유 확인 메타가 사라짐 |
| `title_changed` | WARNING | title 문구가 바뀜 |
| `meta_description_changed` | WARNING | meta description이 바뀜 |
| `og_tags_removed` | WARNING | og: 태그가 전부 사라짐 (카톡·네이버 공유 미리보기) |
| `schema_modified` | WARNING | JSON-LD 내용이 바뀜 |
| `schema_added` | INFO | JSON-LD가 새로 생김 |
| `h2_structure_changed` | INFO | H2 목록이 바뀜 |
| `content_hash_changed` | INFO | HTML이 바뀜 (모든 변경을 잡는 마지막 규칙) |

## 4. 결과 읽기

- CRITICAL: 배포를 되돌리거나 즉시 고친다. noindex·canonical·소유 확인 메타는 네이버와 구글 모두에 바로 영향이 간다
- WARNING: 의도한 변경인지 확인하고, 제목·설명이 바뀌었으면 2주간 클릭률을 본다
- INFO: 참고용이다. Next.js 등은 빌드마다 HTML 해시가 바뀌므로 `content_hash_changed`만 뜨면 정상이다
- JSON-LD가 바뀌었으면 [schema 검사](schema.md)를 이어서 돌린다

## 5. 한계

- 원본(claude-seo)의 Core Web Vitals 규칙 2개는 PageSpeed API 키가 필요해 뺐다. 속도는 [측정 루프](measure.md)에서 따로 잰다
- 자바스크립트를 실행하지 않은 HTML만 본다. 클라이언트에서만 그려지는 요소는 크롤러에게도 안 보이므로 이 판정이 맞다
