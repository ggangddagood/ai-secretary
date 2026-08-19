# Step 6: pipeline-cli

앞의 모듈들을 배선하고 CLI를 만든다. 이 파일은 **순서와 실패 정책만** 정한다.

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 특히 "외부 인터페이스", "엣지 케이스" 전체
- `docs/STANDARDS.md` — "실패 처리", "`main.py`는 순서와 실패 정책만 정한다"
- `docs/DECISIONS.md` — 철학("조용히 죽지 않는다")
- `src/secretary/main.py` — 실패 정책과 CLI 구조의 기존 패턴. **이 파일을 그대로 따른다**
- step 1~5 산출물 전부:
  - `src/secretary/config.py` (`load_stocks_config`, `StocksConfig`)
  - `src/secretary/stocks/models.py` (`MARKET_INDICES`, `MARKET_TZ`, `FX_SYMBOL`, `MARKETS`)
  - `src/secretary/stocks/quotes.py` (`fetch_quotes`)
  - `src/secretary/stocks/news.py` (`fetch_headlines_for`)
  - `src/secretary/stocks/llm.py` (`explain_moves`)
  - `src/secretary/stocks/render.py` (`render_stock_brief`, `render_failure`)
- `src/secretary/gemini.py` (`make_client`), `src/secretary/telegram.py` (`send_messages`)
- `tests/test_main.py` — monkeypatch로 전 단계를 대체하는 방식

## 작업

### `src/secretary/stocks/main.py` 신설

```python
class StocksPipelineError(Exception): ...

def build_stock_brief(
    cfg: StocksConfig, client: genai.Client, *, now: datetime
) -> StockBrief: ...

def run(argv: list[str] | None = None) -> int: ...
```

### 흐름

```
1. 시세 조회   fetch_quotes(MARKET_INDICES[market])  → 지수·환율
               fetch_quotes(cfg.watchlist)           → 관심 종목
               둘 다 0건이면 StocksPipelineError
               관심 종목 목록이 비어 있으면 warning만 남기고 계속한다(실패 아님)
2. 기준일 판정 환율(FX_SYMBOL)을 제외한 Quote들의 as_of 중 최댓값 = brief.as_of
               brief.is_holiday = (as_of != now를 MARKET_TZ[market]로 변환한 날짜)
               환율만 남았다면 as_of=None, is_holiday=False
3. 급등락 판정 관심 종목 중 abs(change_pct) >= cfg.move_threshold 인 것
4. 뉴스 수집   급등락 종목이 있을 때만 fetch_headlines_for(...)  — 실패는 흡수된다
5. 해설       explain_moves(...) — 실패하면 warning 후 해설 없이 진행
6. 조립       StockEntry 목록. 헤드라인이 없는 종목의 comment_ko는 반드시 None
7. 렌더       render_stock_brief
8. 발송       send_messages
→ exit 0
```

### 실패 정책 — spec의 "엣지 케이스"가 정본이다

- 1~7 중 실패하면 `render_failure(market, describe_error(exc))`를 텔레그램으로 보내고 exit 1.
  트레이스백은 stderr 로그에만 남기고 발송 메시지에는 예외 타입과 한 줄 요약만 담는다.
- **8(발송)에서 실패하면 실패 알림을 보내지 않는다.** 같은 채널이 죽었으므로 보낼 곳이 없다. exit 1.
- **LLM 실패는 발송을 막지 않는다.** `explain_moves`를 `try/except`로 감싸 warning 로그를
  남기고 해설 없이 진행한다. 이유: 시세가 본체이고 해설은 부가다. (기존 `secretary.main`은
  LLM 실패 시 exit 1이지만, 거기서는 요약이 산출물의 본체이므로 정책이 다르다.)
- 실패 알림 발송마저 실패하면 로그만 남긴다.
- **발송 기록을 저장하지 않는다.** 이 파이프라인에 상태 파일은 없다.

### CLI

```
python -m secretary.stocks --market {us|kr} [--dry-run] [--verbose]
```

- `--market`은 `required=True`, `choices=MARKETS`. 기본값을 두지 않는다 — 잘못된 시장으로
  조용히 도는 것보다 exit 2로 즉시 실패하는 편이 낫다.
- `--dry-run`은 렌더링 결과를 stdout에 출력하고 exit 0. 발송하지 않는다.
- `--dry-run`일 때 설정 로딩은 `require_secrets=False`로 하되, `GEMINI_API_KEY`가 없으면
  `ConfigError`를 낸다 (기존 `secretary.main._load_config`와 같은 규칙).
- `--verbose`는 DEBUG 로깅. `setup_logging(args.verbose)`를 **반드시 먼저** 호출한다
  (봇 토큰 마스킹 필터가 여기서 붙는다).

### `src/secretary/stocks/__main__.py` 신설

`secretary/__main__.py`와 같은 형태로 `sys.exit(run())`.

### `tests/test_stocks_main.py` 신설

`tests/test_main.py`의 monkeypatch 방식을 따른다. **네트워크·API 호출이 없다.**

최소 아래를 덮는다.

- 정상 경로: 조회 → 렌더 → 발송, exit 0
- `--dry-run`: `send_messages`가 **호출되지 않고** exit 0
- 시세가 전부 0건 → 실패 알림이 발송되고 exit 1
- 관심 종목 목록이 비어도 지수만으로 발송되고 exit 0 (실패가 아니다)
- **`explain_moves`가 예외를 던져도 발송이 일어나고 exit 0** (해설만 빠진다)
- 급등락 종목이 없으면 `fetch_headlines_for`와 `explain_moves`가 **호출되지 않는다**
- 텔레그램 발송 실패 → exit 1이고 **실패 알림이 추가로 발송되지 않는다**
- `--market` 없이 실행하면 `SystemExit(2)`
- `--market jp` → `SystemExit(2)`
- 헤드라인이 없는 종목의 `comment_ko`가 `None`이다

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -m secretary.stocks --market us --dry-run; echo "exit=$?"
python -m secretary.stocks --market kr --dry-run; echo "exit=$?"
python -m secretary.stocks 2>/dev/null; echo "no-market exit=$? (2를 기대)"
python -m secretary.main --dry-run > /dev/null; echo "regression exit=$?"
```

- dry-run 두 개는 `exit=0`이어야 한다. `GEMINI_API_KEY`가 필요하다.
- 마지막 명령은 **기존 AI 브리핑이 깨지지 않았다는 회귀 확인**이다.
- 관심 종목 없이 돌리면 지수만 출력된다. 종목까지 보려면 아래처럼 임시 주입한다(커밋하지 않는다):

```bash
STOCKS_WATCHLIST_US="AAPL:애플,TSLA:테슬라" python -m secretary.stocks --market us --dry-run
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 **exit code를 캡처해 보고한다.**
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. dry-run 출력에서 확인한다: 등락률이 상식적인 범위인가, 기준일이 맞는가, 휴장 표시가 적절한가.
4. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다.
5. `GEMINI_API_KEY`가 없어 dry-run을 평가할 수 없으면 `"blocked"` + `blocked_reason`으로 남기고
   중단한다. **실행하지 못한 검사를 통과로 추론하지 마라.**

## 금지사항

- `state/seen.json`을 읽거나 쓰지 마라 (CRITICAL). 이 파이프라인에 상태는 없다.
- `secretary/main.py`를 수정하지 마라. 별도 진입점이다.
- 텔레그램 발송 실패 시 실패 알림을 보내려 하지 마라. 이유: 같은 채널이 죽은 상황이라
  재시도해도 같은 결과다.
- LLM 실패로 전체를 실패시키지 마라. 이유: 시세만으로 브리핑이 성립한다.
- `--market`에 기본값을 두지 마라.
- 도메인 로직을 `main.py`에 넣지 마라. 순서와 실패 정책만 정한다 (STANDARDS).
- `setup_logging` 호출을 빠뜨리거나 뒤로 미루지 마라. 이유: 봇 토큰 마스킹 필터가 여기서 붙는다.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
