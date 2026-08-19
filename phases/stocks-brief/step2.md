# Step 2: quotes

Yahoo Finance v8 chart 엔드포인트에서 시세를 가져와 `Quote`로 만든다.

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 특히 "시세 조회", "불변 조건", "엣지 케이스"
- `docs/STANDARDS.md` — "외부 HTTP는 `http.make_client(timeout)`을 쓴다"
- `src/secretary/http.py` — 공유 클라이언트
- `src/secretary/sources/base.py` — `describe_error` (실패 로그 포맷)
- `src/secretary/sources/hackernews.py` — JSON API 소스의 기존 구조를 참고한다
- `src/secretary/stocks/models.py` (step 1 산출물) — `Ticker`, `Quote`
- `tests/test_sources.py` — 가짜 HTTP 클라이언트로 테스트하는 기존 방식

## 배경 — 계획 단계에서 실호출로 확인한 사실

6개 심볼(`005930.KS`, `035720.KQ`, `AAPL`, `^KS11`, `^GSPC`, `USDKRW=X`)을 실제로 호출해
전부 HTTP 200을 받았다. 기존 User-Agent(`ai-secretary/0.1`)로 충분하며 브라우저 위장이 필요 없다.

## 작업

### `src/secretary/stocks/quotes.py` 신설

```python
CHART_BASE: Final[str] = "https://query1.finance.yahoo.com/v8/finance/chart/"
RANGE: Final[str] = "1mo"
INTERVAL: Final[str] = "1d"

def fetch_quotes(tickers: Sequence[Ticker], *, timeout: float) -> list[Quote]: ...
def parse_chart(payload: dict, ticker: Ticker) -> Quote | None: ...
```

- `fetch_quotes`는 `http.make_client(timeout)` 하나를 열어 심볼마다 순차 GET 한다.
  URL은 `CHART_BASE + urllib.parse.quote(ticker.symbol, safe="")` — `^`와 `=`가 인코딩되어야 한다.
  쿼리는 `{"range": RANGE, "interval": INTERVAL}`.
- 심볼 하나가 실패해도 나머지를 계속한다. 실패는 `describe_error(exc)`로 warning 로그를 남기고
  결과 목록에서 뺀다. **예외를 호출자에게 올리지 않는다.**
- 반환 순서는 입력 `tickers` 순서를 따른다.

### `parse_chart` 로직 — spec의 불변 조건을 그대로 구현한다

```
payload["chart"]["error"] 가 None이 아니면 → None (warning)
result = payload["chart"]["result"][0]
meta = result["meta"]
timestamps = result["timestamp"]
closes = result["indicators"]["quote"][0]["close"]

pairs = [(ts, c) for ts, c in zip(timestamps, closes) if c is not None]   # ← None 제거
if len(pairs) < 2 → None
latest_ts, latest = pairs[-1]
_,         prev   = pairs[-2]
if prev == 0 → None
change_pct = (latest - prev) / prev * 100
as_of = datetime.fromtimestamp(latest_ts, tz=ZoneInfo(meta["exchangeTimezoneName"])).date()
```

**CRITICAL: `meta.chartPreviousClose` 를 쓰지 마라.** 이 값은 조회 창 시작 *이전*의 종가다.
실측에서 삼성전자의 `chartPreviousClose`가 239500이었는데 실제 직전 거래일 종가는 268500이었다.
이 값으로 등락률을 계산하면 예외 없이, 그럴듯한 숫자로 틀린다.

응답 구조가 예상과 다르면(키 없음, 타입 불일치) 예외를 밖으로 던지지 말고 `None`을 돌려주며
warning 로그를 남긴다. `KeyError`/`IndexError`/`TypeError`를 잡는다.

`ZoneInfo`는 표준 라이브러리 `zoneinfo`를 쓴다(추가 의존성 없음).

### `tests/test_stocks_quotes.py` 신설

`tests/test_sources.py`의 가짜 클라이언트 방식을 따른다 — **네트워크에 나가지 않는다.**
`monkeypatch.setattr(quotes_module, "make_client", ...)`로 대체한다.

최소 아래를 덮는다.

- 정상 응답 → `price`/`change_pct`/`as_of`/`currency`가 맞다
- **`close` 배열 마지막 원소가 `None`** → 그 앞 유효값으로 계산한다 (실측 `035720.KQ` 사례)
- **`close` 중간에 `None`이 섞임** → 제거 후 마지막 두 유효값으로 계산한다
- 유효 종가가 1개뿐 → `None`
- 직전 종가가 `0` → `None` (ZeroDivisionError가 나지 않는다)
- `chart.error`가 있는 응답 → `None`
- **`chartPreviousClose`가 마지막 유효 종가와 다른 값일 때, 등락률이 `chartPreviousClose`가
  아니라 직전 유효 종가 기준으로 계산된다** — 이 회귀 테스트가 이 step의 핵심이다
- 심볼 하나가 HTTP 예외를 던져도 나머지 심볼의 결과가 돌아온다
- `^KS11` 같은 심볼이 URL 인코딩되어 요청된다 (`%5EKS11`)

## Acceptance Criteria

```bash
bash scripts/verify.sh
```

실호출 스모크 (네트워크가 되는 환경에서만, 실패해도 step 실패로 보지 않는다 — 결과를 로그로 남긴다):

```bash
python -c "
from secretary.stocks.models import Ticker
from secretary.stocks.quotes import fetch_quotes
qs = fetch_quotes([Ticker('AAPL','애플'), Ticker('005930.KS','삼성전자'), Ticker('^KS11','코스피')], timeout=20)
for q in qs: print(q.ticker.symbol, q.price, round(q.change_pct,2), q.currency, q.as_of)
print('fetched', len(qs), 'of 3')
"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다.
4. 실호출 스모크가 429나 차단으로 실패하면 그 사실을 `summary`에 적고 `docs/tracking/FINDINGS.md`에 기록한다. 단위 테스트가 통과했다면 step은 완료로 본다.

## 금지사항

- `meta.chartPreviousClose`로 등락률을 계산하지 마라. 이유: 조회 창 이전의 종가라 값이 틀린다.
- `closes[-1]`을 그대로 쓰지 마라. 이유: 마지막 원소가 `None`인 응답이 실제로 존재한다.
- `yfinance`·`pandas`를 추가하지 마라. 이유: 무거운 의존성이며 `httpx`로 충분함을 실호출로 확인했다.
- `httpx.Client`를 직접 조립하지 마라. `http.make_client(timeout)`을 쓴다 (STANDARDS).
- 브라우저 User-Agent로 위장하지 마라. 기존 UA로 200이 확인됐다.
- 재시도 로직을 넣지 마라. 이유: 하루 두 번 배치이고, 실패한 심볼은 건너뛰면 충분하다(기존 소스와 같은 정책).
- 테스트가 실제 네트워크에 나가게 하지 마라 (STANDARDS).
- spec의 "범위 제외"에 있는 것을 만들지 마라.
