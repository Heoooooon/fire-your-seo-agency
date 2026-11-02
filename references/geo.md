# GEO — 생성엔진 최적화 (ChatGPT · Perplexity · Claude)

생성 AI가 브라우징·검색 도구로 웹을 읽을 때 **당신을 1차 소스로 인용**하게 만드는 레인.
답변엔진(AEO)과 겹치지만, 생성엔진은 ① 크롤러 정책이 다르고 ② llms.txt를 읽으며
③ "원출처"를 더 강하게 우대한다.

## 1. llms.txt

사이트 루트에 `/llms.txt` — AI에게 주는 사이트 안내서다. 형식은 마크다운:

```markdown
# 서비스명

> 한 문장 설명 (무엇의 1차 소스인지 명시)

## 핵심 페이지
- [실적 캘린더](https://example.com/earnings): 국내 상장사 실적 발표 일정
- [종목 데이터](https://example.com/stocks): 공시 기반 재무·밸류에이션

## 데이터 정책
- 출처: 공식 전자공시 기반 자체 산출, 매일 갱신
- 인용 시 표기: example.com
```

- [ ] `/llms.txt` (안내서) + 여력이 되면 `/llms-full.txt` (핵심 데이터 전문)
- [ ] 신뢰 신호를 담아라: 데이터 출처, 갱신 주기, 무엇의 원출처인지
- [ ] 앱 라우트로 서빙해도 된다(정적 파일일 필요 없음) — 항상 최신이 되게

## 2. AI 크롤러 정책 결정

AI 크롤러는 **용도가 세 종류**고, robots.txt 정책은 용도별로 나눠 짜야 한다.
기본 무정책 = 우연에 맡기는 것:

| 용도 | 대표 User-agent | 막으면 잃는 것 |
|---|---|---|
| **학습** (모델 훈련 데이터 수집) | GPTBot, ClaudeBot, Google-Extended, CCBot, Applebot-Extended | 미래 모델의 브랜드 인지 (LLMO) |
| **검색 색인** (AI 검색의 자체 인덱스) | OAI-SearchBot, Claude-SearchBot, PerplexityBot | ChatGPT·Claude·Perplexity 검색 인용 |
| **실시간 fetch** (사용자 질문 시 페이지 열람) | ChatGPT-User, Perplexity-User, Claude-User | 답변 시점의 직접 인용·트래픽 |

```
# 인용 유입이 목표라면 전부 Allow가 기본값
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: Claude-User
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Perplexity-User
Allow: /
```

콘텐츠가 자산이라 **학습만** 막고 싶다면 첫 행(학습용)만 Disallow — 검색·fetch를 같이
막으면 인용 유입 자체가 죽는다. 명단은 변한다 — 각사 크롤러 문서를 분기마다 확인하라.

- [ ] **Bing 색인 확인**: ChatGPT 검색은 자체 크롤러에 더해 Bing 색인에 의존한다.
      Bing Webmaster Tools 등록이 안 돼 있으면 `references/aeo.md`의 0번부터 하라

## 3. 1차 소스 되기 — GEO의 본체

생성엔진은 "어디서 이 숫자가 시작됐나"를 추적한다. 남의 데이터를 요약한 페이지는
원출처에게 인용을 뺏긴다.

- [ ] 우리만 계산·수집하는 숫자가 무엇인지 정의하라 (자체 산출 지표·집계·관측)
- [ ] 그 숫자에 이름을 붙이고 항상 같은 페이지에서 서빙하라 (안정 URL = 인용 주소)
- [ ] 문단 단위 인용 가능성: 각 문단이 [주어 + 수치 + 기준일 + 산출 방식]을 갖추면
      그 문단째로 인용된다 — 실측으로 네이버 AI 브리핑·Perplexity 모두 이 단위로 잘라 간다

## 4. 검증

- Perplexity·ChatGPT(검색 모드)에 실제 질문을 던져 출처 목록에 도메인이 뜨는지 확인
- 안 뜨면: llms.txt 존재 → 크롤러 허용 → 해당 페이지 SSR 여부 → 경쟁 원출처 존재 순 점검

## 5. 자동 점검 스크립트

```bash
python3 scripts/geo_check.py https://example-dental.co.kr/          # 사람이 읽는 표
python3 scripts/geo_check.py https://example-dental.co.kr/ --json   # 보고서·비교용
```

- 자바스크립트 없이 받은 HTML 기준으로 SSR 본문 양, H1, 질문형 소제목, 인용 가능한 문단, JSON-LD의 Q&A·Dentist 엔티티·sameAs(네이버 플레이스·블로그·유튜브), 의료진(Person/Physician), 갱신일, naver-site-verification, OG 태그를 본다
- robots.txt는 검색·인용 크롤러(Googlebot·Yeti·Bingbot·OAI-SearchBot·Claude-SearchBot·PerplexityBot·Applebot)와 학습 크롤러(GPTBot·ClaudeBot·Google-Extended 등)를 따로 판정한다. 학습만 막은 것은 실패가 아니다
- llms.txt는 있는지만 알린다. 구글은 쓰지 않는다고 밝혔으므로 점수에 넣지 않는다
- 점수는 가중치 없는 체크리스트 개수다. AI 답변에 실제로 인용되는지는 4번의 실제 질문으로 확인한다
- 원본(claude-seo seo-geo)의 DataForSEO 연동은 유료라 뺐다
