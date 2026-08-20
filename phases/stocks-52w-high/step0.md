# Step 0: quotes-52w

Yahoo 응답에서 52주 고점·저점을 읽어 하락률과 범위 내 위치를 계산한다. 표시는 아직 하지 않는다.

## 읽어야 할 파일

- `phases/stocks-52w-high/spec.md`   ← 요구 동작의 정본. 특히 "계산식"과 "엣지 케이스"
- `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙"의 등락률 계산 규칙
- `src/secretary/stocks/models.py` — `Quote` 정의
- `src/secretary/stocks/quotes.py` — `parse_chart`가 이미 `meta`를 읽고 있다
- `tests/test_stocks_quotes.py` — 가짜 응답 payload를 만드는 기존 방식

## 배경 — 계획 단계에서 실측한 사실

`meta`에 아래 키가 실재한다(추가 호출 불필요):

```
005930.KS  fiftyTwoWeekHigh=374500.0  fiftyTwoWeekLow=67500.0   (종가 271000)
AAPL       fiftyTwoWeekHigh=344.57    fiftyTwoWeekLow=223.78    (종가 317.505)
```

## 작업

### 1. `src/secretary/stocks/models.py` — `Quote`에 필드 2개 추가

```python
@dataclass(frozen=True)
class Quote:
    ticker: Ticker
    price: float
    change_pct: float
    currency: str
    as_of: date
    drawdown_pct: float | None = None   # 52주 고점 대비 %. 보통 0 이하, 신고가면 양수
    range_pct: float | None = None      # 52주 저점~고점 구간 내 위치 %. 0~100
```

**기본값 `None`으로 맨 뒤에 추가한다.** 이유: 기존 `Quote(...)` 생성 코드와 테스트가 그대로
동작해야 한다. 필드 순서를 바꾸거나 기본값을 빼면 여러 파일이 한꺼번에 깨진다.

주석으로 두 값의 의미를 남긴다. 다른 `secretary` 모듈을 import 하지 않는 규칙은 그대로다.

### 2. `src/secretary/stocks/quotes.py` — 계산 추가

`parse_chart` 안에서 `meta`를 이미 읽고 있으므로, 계산을 헬퍼로 분리하고 `Quote` 생성 시 넘긴다.

```python
def fifty_two_week(meta: dict[str, Any], price: float) -> tuple[float | None, float | None]:
    """(고점 대비 %, 범위 내 위치 %)를 돌려준다. 읽을 수 없으면 (None, None)."""
```

로직은 spec의 "계산식"과 "엣지 케이스"를 그대로 구현한다. 요점만 옮기면:

- `fiftyTwoWeekHigh` / `fiftyTwoWeekLow` 중 하나라도 없거나 `None`이면 `(None, None)`
- `float()` 변환에 실패하면(`TypeError`/`ValueError`) `(None, None)` — **예외를 올리지 않는다**
- `high <= 0`이면 `(None, None)`
- `drawdown = (price - high) / high * 100` — **클램프하지 않는다.** 양수는 "신고가"라는
  의미 있는 신호이며 step 1의 렌더가 그 값으로 분기한다
- `high == low`이면 `(drawdown, None)` — 범위 폭이 0이라 위치를 만들 수 없다
- `range_pct = min(100.0, max(0.0, (price - low) / (high - low) * 100))` — **0~100 클램프**.
  종가가 저점보다 낮거나 `low > high`인 이상 데이터를 이 클램프가 흡수한다

`parse_chart`는 이 헬퍼를 호출해 `Quote(..., drawdown_pct=..., range_pct=...)`로 넘긴다.

### 3. `tests/test_stocks_quotes.py` — 테스트 추가

기존 가짜 payload 방식을 그대로 쓴다. **네트워크에 나가지 않는다.**

최소 아래를 덮는다.

- 정상 meta → `drawdown_pct`와 `range_pct`가 계산된다. 실측값으로 검증한다:
  `price=271000, high=374500, low=67500` → `drawdown_pct ≈ -27.64`, `range_pct ≈ 66.29`
  (`pytest.approx` 사용)
- `fiftyTwoWeekHigh` 키가 없음 → 둘 다 `None`, **`Quote`는 정상 생성된다**(조회 실패가 아니다)
- `fiftyTwoWeekLow`가 `null` → 둘 다 `None`
- 값이 문자열 등 숫자가 아님 → 둘 다 `None`, 예외 없음
- `high == 0` → 둘 다 `None` (ZeroDivisionError가 나지 않는다)
- `high == low` → `drawdown_pct`는 값이 있고 `range_pct`만 `None`
- **종가 > 고점** → `drawdown_pct`가 **양수**다 (클램프되지 않는다)
- **종가 < 저점** → `range_pct == 0.0` (음수로 내려가지 않는다)
- 52주 값이 없어도 `change_pct`와 `price`는 기존과 동일하게 계산된다 — 회귀 방지

## Acceptance Criteria

```bash
bash scripts/verify.sh
python3 -c "
from secretary.stocks.quotes import fifty_two_week
print('정상   :', fifty_two_week({'fiftyTwoWeekHigh': 374500.0, 'fiftyTwoWeekLow': 67500.0}, 271000.0))
print('키없음 :', fifty_two_week({}, 100.0))
print('high=0 :', fifty_two_week({'fiftyTwoWeekHigh': 0, 'fiftyTwoWeekLow': 0}, 100.0))
print('신고가 :', fifty_two_week({'fiftyTwoWeekHigh': 100.0, 'fiftyTwoWeekLow': 50.0}, 105.0))
print('저점밑 :', fifty_two_week({'fiftyTwoWeekHigh': 100.0, 'fiftyTwoWeekLow': 50.0}, 40.0))
"
```

기대: 정상은 `(-27.6…, 66.2…)`, 키없음·high=0은 `(None, None)`, 신고가는 첫 값이 **양수**,
저점밑은 둘째 값이 **0.0**.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 exit code를 확인한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/stocks-52w-high/index.json`의 해당 step을 갱신한다:
   - 통과 → `"completed"` + `"summary"`
   - 3회 수정 후에도 실패 → `"error"` + `"error_message"`
   - 사용자 개입 필요 → `"blocked"` + `"blocked_reason"` 후 즉시 중단

## 금지사항

- `change_pct` 계산을 건드리지 마라 (CRITICAL). 여전히 `close`의 유효값 마지막 두 개로 계산하며
  `meta.chartPreviousClose`를 쓰지 않는다. 이유: 그 값은 조회 창 이전의 종가라 등락률이 틀린다.
- 52주 값을 못 읽었다고 `Quote`를 버리지 마라(`None` 반환 금지). 이유: 종가와 등락률은 이미
  유효하다. 부가 지표 때문에 시세를 통째로 잃으면 안 된다.
- `RANGE`(`"1mo"`)나 요청 파라미터를 바꾸지 마라. 이유: 52주 값은 `meta`에 이미 들어 있어
  조회 범위를 늘릴 이유가 없다. 늘리면 응답만 커지고 429 위험이 오른다.
- 52주 값을 위해 HTTP 요청을 추가하지 마라.
- `drawdown_pct`를 0 이하로 클램프하지 마라. 이유: 양수가 "신고가" 신호이고 step 1이 그것으로 분기한다.
- 렌더링 코드(`stocks/render.py`)를 건드리지 마라. step 1의 범위다.
- 테스트가 실제 네트워크에 나가게 하지 마라.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
