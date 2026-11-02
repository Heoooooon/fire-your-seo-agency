# schema — 구조화 데이터(JSON-LD) 검사

치과 페이지의 JSON-LD가 문법·필수 속성·자리표시자 기준을 통과하는지 확인한다. 운영 페이지 URL과
로컬 소스 파일(.html·.tsx·.vue 등)을 모두 받는다. 화면에 없는 사실을 JSON-LD에 넣지 않는다는
원칙은 [AEO](aeo.md)와 같다.

## 1. 실행

```bash
python3 scripts/schema_check.py https://example-dental.co.kr/      # 운영 페이지
python3 scripts/schema_check.py app/page.tsx --json                # 로컬 파일, JSON 출력
```

종료 코드는 0 통과(경고 허용), 1 오류 또는 검사할 블록 없음, 2 사용법·수집 오류다.
`tests/fixtures/broken-dentist.html`이 일부러 깨 둔 예시다.

## 2. 치과 페이지 최소 조건

| 대상 | 오류(실패) | 경고 |
|---|---|---|
| 모든 블록 | JSON 문법 오류, @context·@type 누락, 자리표시자([치과명]·000-0000-0000 등), 폐지 타입(HowTo 등) | — |
| Dentist·MedicalClinic·LocalBusiness | name 누락, address 누락 또는 streetAddress·addressLocality 없음 | telephone·url·openingHoursSpecification·geo·image 누락, 상대 URL, addressCountry가 KR 아님 |
| FAQPage | 질문 없음, Question에 name 없음, acceptedAnswer.text 없음 | — (구글 FAQ 리치 결과는 2026-05-07 종료. 정보로만 알림) |

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

위 예시의 전화번호·주소·플레이스 ID는 실제 값으로 바꾼다. 네이버 플레이스와 같은 이름·주소·전화를 쓴다.

## 3. 저장 시 자동 검사 (Claude Code 훅)

Claude Code 플러그인으로 설치하면 `hooks/hooks.json`이 Edit·Write 직후 `hooks/validate-schema.py`를
실행한다. 오류가 있으면 종료 코드 2와 함께 내용을 Claude에게 돌려주고, 경고만 있으면 참고 문맥으로 넘긴다.
JSX의 `{JSON.stringify(schema)}`처럼 실행 중에 만들어지는 블록은 건너뛴다. OmO/Senpi에는 훅이 없으므로
파일을 고친 뒤 `schema_check.py`를 직접 실행한다.

## 4. 판정 기준

- 통과는 "문법과 필수 속성이 맞다"는 뜻이다. 리치 결과 노출 보장이 아니다
- 구글 리치 결과 테스트와 네이버 서치어드바이저의 구조화 데이터 리포트로 한 번 더 확인한다
- 후기·별점(AggregateRating)은 페이지에 실제로 보이는 후기만 넣는다. 의료광고 심의 대상인지도 먼저 확인한다
