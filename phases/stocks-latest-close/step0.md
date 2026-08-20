# Step 0: latest-close

`meta.regularMarketPrice`를 최신 시세로 쓰도록 `parse_chart`를 고친다. 렌더링은 건드리지 않는다.

## 읽어야 할 파일

- `phases/stocks-latest-close/spec.md`   ← 요구 동작의 정본. "배경"과 "엣지 케이스"를 반드시 읽어라
- `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙"의 등락률 계산 규칙
- `docs/ENGINEERING_NOTES.md` — `chartPreviousClose` 함정
- `src/secretary/stocks/quotes.py` — `parse_chart`, `fifty_two_week`
- `src/secretary/stocks/models.py` — `Quote`
- `tests/test_stocks_quotes.py` — 가짜 payload를 만드는 기존 방식

## 배경 — 실측 데이터

```
005930.KS  close 8/20 = None,  meta.regularMarketPrice = 271000.0,
           meta.regularMarketTime = 2026-08-20 15:30:20 KST,  close 8/19 = 247500.0
QQQ        close 8/20 = 712.105(있음), meta.regularMarketPrice = 712.105,
           meta.regularMarketTime = 2026-08-20 11:14 ET,      close 8/19 = 716.08
```

## 작업

### `src/secretary/stocks/quotes.py`

최신가·직전가·기준일을 정하는 로직을 헬퍼로 분리한다.

```python
def latest_and_previous(
    meta: dict[str, Any],
    timestamps: list[int],
    closes: list[float | None],
    tz: ZoneInfo,
) -> tuple[date, float, float] | None:
    """(기준일, 최신가, 직전 종가). 정할 수 없으면 None."""
```

**우선 경로 — `meta` 사용:**

1. `meta.regularMarketPrice`와 `meta.regularMarketTime`을 읽는다. 없거나 `None`이면 폴백.
2. `as_of = datetime.fromtimestamp(regularMarketTime, tz=tz).date()`,
   `price = float(regularMarketPrice)`. 변환에 실패하면(`TypeError`/`ValueError`/`OSError`) 폴백.
3. `close` 배열의 유효값 중 **날짜가 `as_of`보다 이전인 것**들만 남기고, 그 마지막 값을 `prev`로 쓴다.
   하나도 없으면 폴백.
4. `(as_of, price, prev)` 반환.

**폴백 경로 — 기존 방식 그대로:**

- `close`에서 `None`을 제거한 유효값이 2개 미만이면 `None`.
- 마지막 두 유효값을 `(price, prev)`로, 최신 값의 타임스탬프 날짜를 `as_of`로 쓴다.

`parse_chart`는 이 헬퍼를 부르고, 결과가 `None`이면 지금처럼 warning 후 `None`을 돌려준다.
`prev == 0` 검사와 `fifty_two_week(meta, price)` 호출은 그대로 유지한다.

**3번이 이 step의 핵심이다.** 단순히 "마지막 유효값"을 `prev`로 쓰면, `close`에 최신 종가가
이미 들어 있는 미국장에서 `price`와 `prev`가 같은 날이 되어 등락률이 항상 0이 된다.

### `tests/test_stocks_quotes.py` — 테스트 추가

기존 가짜 payload 방식을 쓴다. **네트워크에 나가지 않는다.**

최소 아래를 덮는다.

- **`close` 마지막이 `None` + `meta`에 종가 있음** → `price`는 `meta` 값, `prev`는 그 이전 날짜의
  close, `as_of`는 `regularMarketTime`의 날짜. 실측 재현:
  `regularMarketPrice=271000`, `regularMarketTime`=8/20, `close` 8/19=247500
  → `price==271000`, `change_pct≈+9.49`, `as_of==date(2026,8,20)`
- **`close`에 최신 종가가 이미 있음** → `price`와 `prev`가 **다른 날짜**에서 오고 등락률이 0이 아니다
  (`regularMarketPrice`와 마지막 close가 같은 값이어도 `prev`는 그 전날에서 온다)
- `regularMarketPrice`가 없음 → 폴백. 기존과 같은 결과
- `regularMarketTime`이 없음 → 폴백
- 두 값이 숫자가 아님(문자열 등) → 폴백, 예외 없음
- `as_of` 이전 유효 종가가 없음(모든 bar가 같은 날이거나 이후) → 폴백
- 폴백해도 유효값 2개 미만 → `None`
- `prev == 0` → `None`
- 52주 지표가 **`meta` 경로의 `price`** 기준으로 계산된다

## Acceptance Criteria

```bash
bash scripts/verify.sh
python3 -c "
from datetime import date
from zoneinfo import ZoneInfo
from secretary.stocks.quotes import latest_and_previous
tz = ZoneInfo('Asia/Seoul')
# 8/18, 8/19, 8/20(=None) bar. meta는 8/20 15:30 종가 271000을 안다.
ts = [1787011200, 1787097600, 1787184000]  # KST 2026-08-18, 08-19, 08-20 09:00
meta = {'regularMarketPrice': 271000.0, 'regularMarketTime': 1787207400}  # 08-20 15:30 KST
print('meta경로:', latest_and_previous(meta, ts, [268500.0, 247500.0, None], tz))
print('폴백  :', latest_and_previous({}, ts, [268500.0, 247500.0, None], tz))
"
```

`meta경로`의 최신가는 `271000.0`, 직전가는 `247500.0`이어야 한다.
`폴백`은 최신가 `247500.0`, 직전가 `268500.0`이어야 한다(기존 동작).

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 exit code를 확인한다.
2. 확인한다: spec의 불변 조건이 유지되는가 — 특히 `prev`가 항상 `close` 배열에서 오는가,
   `price`와 `prev`가 같은 날짜에서 오지 않는가.
3. 결과에 따라 `phases/stocks-latest-close/index.json`의 해당 step을 갱신한다.

## 금지사항

- `meta.chartPreviousClose`를 쓰지 마라 (CRITICAL). 조회 창 이전의 종가라 등락률이 틀린다.
  `regularMarketPrice`와 혼동하지 마라 — 다른 필드다.
- `prev`(직전 종가)를 `meta`에서 가져오지 마라. 언제나 `close` 배열에서 온다.
- 폴백 경로의 동작을 바꾸지 마라. 기존 테스트가 그대로 통과해야 한다.
- `price`와 `prev`가 같은 날짜에서 오게 두지 마라. 등락률이 0이 된다.
- `currentTradingPeriod`로 장중 여부를 판정하지 마라. 실측에서 이 값이 **다음** 거래일을 가리켜
  마감된 종가를 "장중"으로 오판했다.
- `RANGE`·`INTERVAL`을 바꾸거나 HTTP 요청을 추가하지 마라.
- 렌더링(`stocks/render.py`)·휴장 판정(`stocks/main.py`)을 건드리지 마라. spec의 "범위 제외"다.
- 테스트가 실제 네트워크에 나가게 하지 마라.
