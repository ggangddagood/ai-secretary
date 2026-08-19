# 현재 상태

> 작성 기준: 매 사이클 갱신. "완료"는 검증된 상태만 — 테스트 없는 구현은 "구현됨, 미검증"으로 구분해서 적는다. "남은 것"은 막연한 개선("성능 개선 필요")이 아니라 구체적 항목.

기준 시점: 2026-08-20 / 브랜치 `feat-stocks-brief` / phase `stocks-brief` **코드·문서 완료, 운영 검증 미완**

리포: https://github.com/ggangddagood/ai-secretary (공개)

- phase `daily-brief-mvp` (AI 브리핑) — **완료**. 매일 08:00 KST 자동 발송 가동 중
- phase `stocks-brief` (주가 브리핑) — step 0~7 구현·문서 완료. **아직 머지되지 않았고 실제
  Actions 실행으로 검증되지 않았다**

## phase daily-brief-mvp (AI 브리핑) — 완료

- **step 0 project-setup** — pyproject(src 레이아웃, ruff+pytest 게이트), `config`/`models`/`log` 뼈대 — 테스트 통과 (2026-08-09)
- **step 1 sources** — HN(Algolia) / GeekNews / GitHub Search / RSS 4개 소스 + 공유 httpx 클라이언트, 소스별 실패 흡수 — 테스트 통과 + 실제 수집 108건 확인 (2026-08-09)
- **step 2 state-dedupe** — URL 정규화·sha1 키, `seen.json` 원자적 저장, 90일 prune — 테스트 통과 + **실제 중복 제거 확인**(2회차 실행에서 135건 중 기발송 5건 제외 → 132건) (2026-08-11)
- **step 3 extract** — trafilatura 본문 추출, 300자 미만·모든 예외는 `None`, 8000자 상한 — 테스트 통과 + 실제 사이트 추출 확인 (2026-08-09)
- **step 4 llm-curate-summarize** — Gemini `gemini-3.6-flash`로 선별·요약(JSON Schema 강제), 본문 없는 항목은 모델에 미전송 — 테스트 통과 + 실제 호출 확인 (2026-08-10)
- **step 5 delivery** — 텔레그램 HTML 렌더링·4096자 분할, `sendMessage` 발송, 봇 토큰 마스킹 — 테스트 통과 + **실제 발송 성공** (2026-08-11)
- **step 6 pipeline** — `main.py` 전체 배선, 발송 성공 후에만 기록 갱신 — 테스트 통과 + 실제 `--dry-run` exit 0(수집 143건 → 선별 5건 → 본문 4/5) (2026-08-10)
- **step 7 ops-docs** — `.github/workflows/daily.yml`, `AGENTS.md`·`docs/`·`README.md` 작성 + **GitHub Actions 실행 검증 완료** (2026-08-11)
- **로그 토큰 마스킹 수정** — httpx의 INFO 요청 로그가 봇 토큰을 평문으로 남기던 문제. URL 로깅 라이브러리 WARNING 고정 + 출력 직전 마스킹 필터 + `basicConfig(force=True)` — 회귀 테스트 6건, 공개 Actions 로그에서 `bot***` 확인 (2026-08-11)

### 운영 검증 기록 (실제 실행)

| 항목 | 결과 |
| --- | --- |
| 로컬 실발송 (2026-08-11) | 수집 144 → 선별 5 → 본문 3/5 → 발송 성공, 기록 5건 |
| GitHub Actions 수동 실행 (run 31500137637) | conclusion **success**. 수집 135 → 중복 제거 132 → 선별 5 → 본문 5/5 → 발송 성공, 기록 10건 |
| 공개 Actions 로그 시크릿 노출 | 없음 (`bot***`로 마스킹 확인) |
| 상태 파일 자동 커밋 | `chore: update seen state` 커밋이 리포에 반영됨 |
| GitHub Secrets | `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 등록 완료 |

## phase stocks-brief (주가 브리핑) — 구현·문서 완료

`bash scripts/verify.sh` exit **0** (ruff check + ruff format --check + pytest **128 passed**).
`tests/test_stocks_*.py` 6개 파일에 주가 테스트 61건이 있다
(config 12 · quotes 12 · news 9 · llm 5 · render 13 · main 10 — pytest 수집 기준).

- **step 0 shared-foundation** — 공용 모듈 `tghtml.py`(이스케이프·4096자 분할·KST)와
  `gemini.py`(MODEL·make_client·generate) 추출. `render.py`·`llm.py`는 위임만 하고
  `telegram.send_messages`는 `TelegramTarget` Protocol을 받는다 — 기존 67건 그대로 통과(동작 불변)
- **step 1 stocks-config-models** — `stocks/models.py`(Ticker/Quote/Headline/StockEntry/StockBrief
  + 시장 상수)와 `config.py`의 `StocksConfig`/`parse_watchlist`/`load_stocks_config` — 79건 통과
- **step 2 quotes** — Yahoo v8 chart 조회. `close`의 `None` 제거 후 유효값 마지막 두 개로 등락률
  계산(`chartPreviousClose` 미사용) — 12건 신설(91건), **실호출 스모크 3/3 성공**
- **step 3 news** — Google News RSS 헤드라인(최근 3일·최신순 최대 5건, 본문 미추출), 모든 실패는
  warning 후 빈 리스트 — 9건 신설(100건), **실호출 스모크 2종목 각 5건 확인**
- **step 4 llm** — `explain_moves`. 헤드라인 있는 종목만 1회 호출로 묶고, 헤드라인 0건이면 호출
  자체를 하지 않는다. 투자 판단 금지 시스템 프롬프트 — 5건 신설(105건)
- **step 5 render** — 헤더(시장명·KST 발송일·기준일+휴장), 지수/관심 종목/급등락 블록,
  숫자 포맷(KRW 정수 / 지수·환율 소수 2자리), 방향 표시 `▲▼–` — 13건 신설(118건)
- **step 6 pipeline-cli** — `build_stock_brief` 배선 + 실패 정책(생성 실패는 알림 후 exit 1,
  LLM 실패는 warning 후 해설 없이 발송, 발송 실패는 알림 없이 exit 1) + CLI(`--market` 필수) —
  10건 신설(128건)
- **step 7 ops-docs** — `.github/workflows/stocks-us.yml`·`stocks-kr.yml` 신설(`contents: read`,
  상태 커밋 없음), `AGENTS.md`·`README.md`·`docs/` 7개 파일 갱신, ADR-007~009 추가

### 검증 기록 (실제 실행, 2026-08-20)

| 항목 | 결과 |
| --- | --- |
| `bash scripts/verify.sh` | exit **0** — 128 passed |
| `python -m secretary.stocks --market us --dry-run` | exit **0**. 지수 3건 + 관심 종목 2건 조회, 급등락 0건, 조각 1개 |
| `python -m secretary.stocks --market kr --dry-run` | exit **0**. 지수 3건 + 관심 종목 2건 조회, 급등락 0건, 조각 1개. 기준일이 로컬 날짜와 달라 **휴장** 표기가 실제로 붙는 것을 확인 |
| 급등락 해설 경로 (`STOCKS_MOVE_THRESHOLD=2`, kr) | exit **0**. 급등락 2건 → 종목별 헤드라인 5건씩 수집 → Gemini 해설 1회 → 렌더까지 **실데이터로 완주**. 삼성전자 해설이 실제 뉴스(파운드리 가격 인상·DX 적자 대응)에 근거함을 확인 |
| 관심 종목 미등록 상태 dry-run (us/kr) | exit **0**. `관심 종목 목록이 비어 있습니다` warning 후 지수 3건만으로 브리핑 생성 — 빈 목록이 실패가 아니라는 규칙을 실측으로 확인 |
| 기존 파이프라인 회귀 `python -m secretary.main --dry-run` | exit **0**. 수집 138 → 중복 제거 후 138 → 선별 5 → 본문 5/5 → 조각 1개 |
| 워크플로 파일 | `stocks-us.yml`(`0 22 * * 1-5`) / `stocks-kr.yml`(`0 7 * * 1-5`) 생성. `contents: write` 없음, `vars.STOCKS_WATCHLIST_*` 참조 확인 |
| `daily.yml` | 이번 phase에서 **수정하지 않음**(git diff 없음) |

관심 종목을 넣은 dry-run에는 문서 예시 종목(`AAPL`, `NVDA`, `005930.KS`, `035720.KQ`)을 환경
변수로 주입해 썼다. 실제 관심 종목이 아니다.

회귀 실행에서 Gemini 선별 호출이 약 6분 걸렸다(수집 완료 00:17:42 → 선별 완료 00:23:49).
실패는 아니지만 워크플로 `timeout-minutes` 를 넘길 여지가 있다 — 아래 "남은 것" 참고.

## 남은 것 (우선순위 순)

1. **`STOCKS_WATCHLIST_US` / `STOCKS_WATCHLIST_KR` 등록** — 아직 등록하지 않았다. 등록 전에는
   지수·환율만 발송된다. 절차는 `docs/OPERATIONS.md` "4. 관심 종목 등록"
   (**Secrets 탭이 아니라 Variables 탭**).
2. **실제 GitHub Actions 실행 검증** — 아직 하지 않았다. `workflow_dispatch`는 워크플로 파일이
   기본 브랜치에 있어야 목록에 뜨므로(`ENGINEERING_NOTES.md`), **머지 후에** `gh workflow run
   stocks-us` / `stocks-kr` 로 수동 실행해 다음을 확인한다.
   - conclusion success, 텔레그램에 메시지 도착
   - 공개 Actions 로그에 봇 토큰이 `bot***`로 마스킹되는지
   - `vars.STOCKS_WATCHLIST_*`가 주입돼 관심 종목이 실제로 조회되는지
   - 상태 커밋이 **생기지 않는지**(주가 워크플로는 상태를 쓰지 않는다)
   - **기준일이 당일로 찍히는지** — 자정 dry-run에서 한국장 기준일이 하루 물러나고 "휴장"이 잘못 붙은 사례가 있다(`docs/tracking/FINDINGS.md`)
3. **뉴스 검색어 오염 대응** — 해설 경로 자체는 2026-08-20에 `STOCKS_MOVE_THRESHOLD=2` 로
   낮춰 **실데이터로 완주시켰다**(위 표). 다만 표시명이 플랫폼 이름과 겹치는 종목(`NAVER`)에서
   무관한 헤드라인만 모이는 것을 확인했다 — `docs/tracking/FINDINGS.md` 참조. LLM이 이유를
   지어내지 않고 "직접 다룬 뉴스 없음"이라고 답해 환각으로 번지지는 않았다. 종목을 몇 개 더
   넣어 보고 표시명 조정(`NAVER` → `네이버`)만으로 충분한지부터 판단한다.
4. **LLM 호출 지연 관측** — 2026-08-20 회귀 실행에서 AI 브리핑의 선별 호출 하나가 약 6분
   걸렸다. `daily.yml` 은 `timeout-minutes: 15`, 주가 워크플로는 `10` 이다. 주가 해설 호출도
   같은 지연을 겪으면 10분을 넘길 수 있는데, 그때는 job이 죽어 **실패 알림조차 못 보낸다**.
   같은 날 두 번째 회귀 실행에서는 선별이 **25초**였다(수집 00:30:51 → 선별 00:31:16).
   6분은 상시가 아니라 편차로 보이며, 그래서 더 관측이 필요하다.
   며칠 실행 시간을 보고 필요하면 `timeout-minutes` 를 올리거나 LLM 호출에 타임아웃을 건다.
5. **미국장 cron 요일 실측** — `0 22 * * 1-5`가 KST 화~토에 도는 것은 계산이지 관측이 아니다.
   머지 후 첫 주에 실제 도착 요일을 확인한다. 특히 **토요일 아침 도착이 정상**임을 잊지 않는다.
6. **`docs/PRD.md` 갱신 여부 판단** — PRD는 여전히 AI 브리핑만 제품 범위로 적고 있다. 주가
   브리핑은 step 7 범위에 PRD가 포함되지 않아 손대지 않았다. 두 배치를 한 제품으로 볼지,
   PRD를 나눌지는 제품 결정이라 사용자 확인이 필요하다.
7. **소스 편중 관측**(AI 브리핑) — 1회차 선별 5건 중 4건이 GitHub 저장소였다. 축은 4개가 모두
   채워졌으므로 축 편중이 아니라 **소스** 쏠림이다. 며칠 받아보고도 같으면 소스별 상한(예: 한
   소스 최대 2건)을 검토한다. 표본이 부족해 지금 손대지 않는다.
8. **본문 추출 실패율 관측**(AI 브리핑) — 1회차 2/5 실패(Docker 403, 본문 170자), 2회차 0/5.
   설계대로 제목·링크만 나가므로 치명적이지 않지만, 실패율이 계속 높으면 User-Agent 조정이나
   소스별 처리를 검토한다.

## 블로커

없음.
