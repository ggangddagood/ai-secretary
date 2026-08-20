# Step 1: render-52w

계산된 52주 지표를 텔레그램 메시지에 표시한다.

## 읽어야 할 파일

- `phases/stocks-52w-high/spec.md`   ← 특히 "요구 동작"의 표시 형식과 "엣지 케이스"
- `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙"의 렌더링 규칙
- `src/secretary/stocks/render.py` — `_render_index`, `_render_entry`, `_format_change`
- `src/secretary/stocks/models.py` (step 0에서 `Quote`에 `drawdown_pct`·`range_pct` 추가됨)
- `src/secretary/tghtml.py` — `text`, `attr`, `pack`
- `tests/test_stocks_render.py` — `Quote`를 만드는 헬퍼와 검증 방식

## 작업

### `src/secretary/stocks/render.py`

52주 줄을 만드는 헬퍼를 추가한다.

```python
def _format_52w(quote: Quote) -> str | None:
    """52주 지표 줄. 표시할 값이 없으면 None."""
```

규칙(spec이 정본):

- `quote.drawdown_pct is None` → `None` 을 돌려준다. **호출자는 줄을 아예 넣지 않는다.**
  빈 괄호나 `-` 같은 자리표시자를 남기지 않는다.
- `drawdown_pct >= 0` → `   52주 신고가` (범위 내 위치를 덧붙이지 않는다. 신고가면 100%로 자명해 중복이다)
- 그 외 → `   52주 고점 대비 {drawdown_pct:.1f}%  (범위 내 {range_pct:.0f}%)`
- `range_pct is None`인데 `drawdown_pct`는 있는 경우 → `   52주 고점 대비 {drawdown_pct:.1f}%`
  (괄호 부분만 생략)

`drawdown_pct`는 음수이므로 `:.1f`가 `-27.6`을 만든다 — 부호를 따로 붙이지 않는다.
줄 앞의 들여쓰기는 공백 3칸이다.

이 문자열은 우리가 만든 숫자와 고정 문구뿐이므로 `text()`를 거칠 필요가 없다.
**사람이 입력한 문자열(표시명·헤드라인)은 기존대로 `text()`를 거친다** — 그 규칙을 약화시키지 마라.

### 적용 지점

`_render_index`(지수·환율)와 `_render_entry`(관심 종목) **둘 다** 시세 줄 다음에 52주 줄을
붙인다. 각 함수가 여러 줄 문자열을 돌려주게 된다.

```
코스피  6,869.83  ▼ -1.55%
   52주 고점 대비 -8.2%  (범위 내 74%)
```

`_render_mover`(급등락 블록)에는 **붙이지 않는다** — spec의 "범위 제외"에 있다.

### `tests/test_stocks_render.py` — 테스트 추가

최소 아래를 덮는다.

- 정상 값 → `52주 고점 대비 -27.6%` 와 `(범위 내 66%)` 가 출력에 있다
- `drawdown_pct=None` → 출력에 `52주` 문자열이 **없다** (줄 자체가 생략된다)
- `drawdown_pct >= 0` → `52주 신고가` 가 있고 `범위 내` 는 **없다**
- `range_pct=None`, `drawdown_pct`는 있음 → 하락률은 있고 `범위 내` 는 없다
- 지수 줄에도 52주 줄이 붙는다
- 급등락 블록에는 52주 줄이 **붙지 않는다**
- 52주 줄이 붙어도 모든 조각이 `TELEGRAM_LIMIT` 이하다
- 소수 자릿수: 하락률 1자리, 범위 위치 정수

## Acceptance Criteria

```bash
bash scripts/verify.sh
python3 -c "
from datetime import date, datetime, timezone
from secretary.stocks.models import Quote, StockBrief, StockEntry, Ticker
from secretary.stocks.render import render_stock_brief
q = Quote(Ticker('005930.KS','삼성전자'), 271000.0, 11.07, 'KRW', date(2026,8,20), -27.64, 66.29)
hi = Quote(Ticker('AAPL','애플'), 105.0, 1.0, 'USD', date(2026,8,20), 0.5, 100.0)
no = Quote(Ticker('^KS11','코스피'), 6869.83, -1.55, 'KRW', date(2026,8,20))
b = StockBrief('kr', datetime(2026,8,20,7,0,tzinfo=timezone.utc), date(2026,8,20), False,
               [no], [StockEntry(q, [], None), StockEntry(hi, [], None)])
print('\n'.join(render_stock_brief(b)))
"
```

기대 출력: 삼성전자 줄 아래 `52주 고점 대비 -27.6%  (범위 내 66%)`, 애플 줄 아래 `52주 신고가`,
코스피 줄 아래에는 **52주 줄이 없다**.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 exit code를 확인한다.
2. 출력을 눈으로 확인한다 — 들여쓰기, 소수 자릿수, 생략이 spec대로인가.
3. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
4. 결과에 따라 `phases/stocks-52w-high/index.json`의 해당 step을 갱신한다.

## 금지사항

- 이스케이프 함수를 새로 만들지 마라. 표시명·헤드라인은 기존대로 `tghtml.text()`/`attr()`를 쓴다.
- 4096자 분할 로직을 새로 만들지 마라. `tghtml.pack`이 이미 처리한다.
- `_render_mover`(급등락 블록)에 52주 줄을 넣지 마라. 이유: 같은 종목이 관심 종목 블록에 이미
  나오므로 중복이다. spec의 "범위 제외"에 있다.
- `drawdown_pct`가 `None`일 때 `-`나 `N/A` 같은 자리표시자를 넣지 마라. 줄 자체를 생략한다.
- 52주 고점·저점의 **원본 값**을 표시하지 마라. 하락률과 위치만 쓴다.
- `secretary/render.py`(AI 브리핑용)를 건드리지 마라.
- 기존 시세 줄의 형식(가격 포맷, `▲▼–`, 등락률 소수 2자리)을 바꾸지 마라.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
