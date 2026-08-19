# ai-secretary

텔레그램으로 하루치 정보를 보내 주는 개인 비서 배치 **둘**.

| 배치 | 발송 시각 (KST) | 내용 |
| --- | --- | --- |
| AI 브리핑 | 매일 08:00 | AI 활용·수익화·마케팅 정보 엄선 5건, 한국어 요약 + 실행 힌트 |
| 주가 브리핑 (미국장) | 화~토 07:00 | 관심 종목 종가·등락 + 지수·환율, 급등락 종목의 뉴스 근거 |
| 주가 브리핑 (한국장) | 월~금 16:00 | 위와 같음 (코스피·코스닥 기준) |

- 사용자는 운영자 본인 1명. 가입도 인증도 없다.
- 서버가 없다. GitHub Actions cron이 CLI를 돌리는 것이 전부다.
- DB가 없다. AI 브리핑의 발송 기록은 리포지토리 안 `state/seen.json` 하나이고,
  주가 브리핑은 상태 파일 자체가 없다.
- 두 배치는 서로를 호출하지 않는다. 같은 봇으로 각각 따로 보낸다.

## AI 브리핑

도착하는 메시지의 형태(원문 제목은 원어 그대로, 나머지는 한국어):

```
📅 AI 브리핑 · 8월 10일

1. <원문 제목>  ·  [기술]
   <이 글이 무엇에 관한 글인지 한 줄>
   · <요약 1>
   · <요약 2>
   · <요약 3>
   💡 <내일 해볼 수 있는 것 한 줄>
   rss:Simon Willison
```

```
수집 → 중복 제거 → 선별(LLM) → 본문 추출 → 요약(LLM) → 렌더 → 발송 → 상태 저장
```

- **수집**: Hacker News(Algolia), GeekNews, GitHub Search, 지정 RSS 피드에서 지난 24시간
  (GitHub는 7일) 항목. 소스 하나가 죽어도 나머지로 진행한다.
- **선별**: `tech` / `money` / `enterprise` / `marketing` 4개 축으로 5건.
- **요약**: 원문 본문을 추출해 **본문만 근거로** 3줄 요약 + 실행 힌트 1줄. 본문을 확보하지 못한
  항목은 제목·출처·링크만 싣는다 — 제목만 보고 지어내지 않는다.
- **상태 저장**: 텔레그램 발송이 성공한 뒤에만 기록한다. 실패하면 다음 실행에서 다시 시도된다.

## 주가 브리핑

```
시세 조회 → 기준일·휴장 판정 → 급등락 판정 → 뉴스 수집 → 해설(LLM) → 렌더 → 발송
```

- **시세**: Yahoo Finance v8 chart를 심볼당 한 번 호출한다. 등락률은 종가 배열의 유효값
  마지막 두 개로 계산한다 — `chartPreviousClose`는 직전 거래일 종가가 아니라서 쓰지 않는다.
- **관심 종목**: 환경 변수(`STOCKS_WATCHLIST_US` / `STOCKS_WATCHLIST_KR`)로만 주입한다.
  이 리포는 공개이므로 종목 목록을 커밋하지 않는다. 등록하지 않으면 지수·환율만 온다.
- **해설**: 등락률 절댓값이 5%(조정 가능) 이상인 종목만 Google News 헤드라인을 모아
  **헤드라인만 근거로** 한 줄 해설을 만든다. 헤드라인이 없으면 해설도 없다.
- **실패 정책**: 시세가 본체이고 해설은 부가다. 해설 생성이 실패해도 시세는 발송한다.
  시세를 한 건도 못 가져오면 실패 알림을 보내고 exit 1 — 조용히 끝나지 않는다.

투자 판단·매매 신호·목표가는 만들지 않는다. 보유 수량이나 평가손익도 다루지 않는다.

## 실행

```bash
pip install -e ".[dev]"
set -a; source .env; set +a          # .env는 자동 로드되지 않는다

python -m secretary.main --dry-run                # AI 브리핑 — 발송·기록 저장 없이 출력
python -m secretary.main                          # 실제 발송

python -m secretary.stocks --market us --dry-run  # 주가 브리핑 — --market은 필수
python -m secretary.stocks --market kr            # 실제 발송

bash scripts/verify.sh                            # 검증 단일 진입점 (ruff + pytest)
```

필요한 환경 변수는 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`
(선택: `GITHUB_TOKEN`, `BRIEF_ITEM_COUNT`, `STATE_PATH`, `HTTP_TIMEOUT`,
`STOCKS_WATCHLIST_US`, `STOCKS_WATCHLIST_KR`, `STOCKS_MOVE_THRESHOLD`).
봇 생성부터 GitHub Secrets·Variables 등록까지의 절차는 `docs/OPERATIONS.md`에 있다.

## 문서

| 파일 | 내용 |
| --- | --- |
| `AGENTS.md` / `CLAUDE.md` | 에이전트 진입점, 하드 게이트 |
| `docs/PRD.md` | 무엇을 왜 만드는가 |
| `docs/ARCHITECTURE.md` | 디렉터리 구조와 전체 흐름 |
| `docs/BUSINESS_RULES.md` | 4개 축·선별·중복·요약, 주가 등락률·급등락·해설 규칙 |
| `docs/STANDARDS.md` | 검증 게이트, 모듈 경계 |
| `docs/SECURITY.md` | 시크릿 취급과 마스킹 |
| `docs/OPERATIONS.md` | 셋업·실행·발송 시각 변경 |
| `docs/ENGINEERING_NOTES.md` | 함정과 비자명 지식 |
| `docs/DECISIONS.md` | 트레이드오프가 있었던 결정(ADR) |
| `docs/tracking/` | 진행 상황(STATUS)과 미해결 문제(FINDINGS) |

## 이 리포의 작업 방식

`/plan` → `/build` → `/review` 사이클과 `phases/`, `scripts/execute.py`를 쓰는 프레임워크 위에서
개발한다. 프레임워크 자체의 사용법은 **[`docs/WORKFLOW.md`](docs/WORKFLOW.md)** 를 본다.
