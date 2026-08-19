# Step 5: render

주식 브리핑을 텔레그램 HTML 메시지로 만든다.

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 특히 "렌더링과 발송", "엣지 케이스"
- `docs/BUSINESS_RULES.md` — "렌더링 규칙"(HTML, 4096자, KST 날짜)
- `docs/ENGINEERING_NOTES.md` — "텔레그램 포맷은 MarkdownV2가 아니라 HTML을 쓴다"
- `src/secretary/tghtml.py` (step 0 산출물) — `escape`, `attr`, `text`, `pack`, `KST`, `TELEGRAM_LIMIT`
- `src/secretary/render.py` — 블록을 만들어 `pack`에 넘기는 기존 구조
- `src/secretary/stocks/models.py` — `StockBrief`, `StockEntry`, `Quote`
- `tests/test_render.py` — 이스케이프와 분할을 검증하는 방식

## 작업

### `src/secretary/stocks/render.py` 신설

```python
def render_stock_brief(brief: StockBrief) -> list[str]: ...
def render_failure(market: str, reason: str) -> str: ...
```

`tghtml`의 `escape`/`attr`/`text`/`pack`을 쓴다. **이스케이프를 직접 구현하지 않는다.**

### 메시지 구성

블록 단위로 만들어 `pack()`에 넘긴다(4096자 분할은 `pack`이 처리한다).

1. **헤더** — 시장 이름(`MARKET_LABELS`), 발송일(`generated_at`을 KST로), 기준일(`as_of`).
   `is_holiday`가 True면 휴장임을 함께 표시한다. `as_of`가 `None`이면 기준일 표기를 생략한다.
2. **지수 블록** — `brief.indices` 각 줄에 표시명·값·등락률. 비어 있으면 블록 자체를 생략한다.
3. **관심 종목 블록** — `brief.entries` 각 줄에 표시명(심볼)·값·등락률.
   비어 있으면 블록 자체를 생략한다.
4. **급등락 블록** — `comment_ko`가 있거나 `headlines`가 있는 항목만. 종목마다
   표시명·등락률, 해설 한 줄(있으면), 근거 헤드라인을 링크로 나열한다.
   대상이 하나도 없으면 블록 자체를 생략한다.

### 숫자 포맷

- 천단위 콤마를 넣는다.
- 심볼이 `^`로 시작(지수)하거나 `=X`로 끝나면(환율) → 소수 2자리
- 그 외에 통화가 `KRW`이면 → 정수 (한국 주식은 원 단위 정수로 거래된다)
- 나머지 → 소수 2자리
- 등락률은 항상 부호를 붙인 소수 2자리 (`+4.32%`, `-1.10%`)
- 방향 표시: 양수 `▲`, 음수 `▼`, 0 `–`

### 이스케이프

표시명·해설·헤드라인 제목은 **모두 `text()` 를 거친다.** 종목 표시명은 환경 변수에서,
헤드라인은 외부 RSS에서 오므로 `<`, `&`가 들어올 수 있다. 링크 URL은 `attr()` 을 쓴다.

### `render_failure`

`"⚠️ {시장 이름} 주가 브리핑을 만들지 못했습니다: {사유}"` 형태. 사유는 `text()`로 이스케이프한다.
시크릿·스택트레이스가 들어가지 않는다.

### `tests/test_stocks_render.py` 신설

최소 아래를 덮는다.

- 정상 브리핑 → 헤더에 시장 이름과 기준일이 들어간다
- `is_holiday=True` → 휴장 표기가 나타난다
- 표시명에 `<`·`&`가 있으면 이스케이프된다 (`&lt;`, `&amp;`)
- 헤드라인 제목의 특수문자가 이스케이프되고 링크가 `href="..."` 로 정상 생성된다
- 지수가 비면 지수 블록이 없고, 관심 종목이 비면 종목 블록이 없다
- 급등락 대상이 0건이면 급등락 블록이 없다
- `comment_ko=None`인 항목은 해설 줄 없이 헤드라인만 나온다
- 항목이 많아 4096자를 넘으면 **모든 조각이 `TELEGRAM_LIMIT` 이하**다
- KRW 종목은 정수로, USD 종목은 소수 2자리로 표기된다
- 등락률 부호와 방향 표시가 맞다 (양수 `▲`+`+`, 음수 `▼`+`-`)
- `render_failure`가 사유를 이스케이프한다

## Acceptance Criteria

```bash
bash scripts/verify.sh
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다.

## 금지사항

- `parse_mode=MarkdownV2`용 포맷을 쓰지 마라. 이유: 요약 문장에 흔한 `.`·`-`·`(`를 전부
  이스케이프해야 하고 한 글자만 놓쳐도 발송이 400으로 통째로 실패한다 (ENGINEERING_NOTES).
- 이스케이프 함수를 새로 구현하지 마라. `tghtml.escape`/`attr`/`text`를 쓴다. 이유: 규칙이
  둘로 갈리면 한쪽만 고쳐진다.
- `secretary/render.py`(AI 브리핑용)를 수정하지 마라. 별도 렌더러다.
- 4096자 분할 로직을 새로 짜지 마라. `tghtml.pack`을 쓴다.
- 매수·매도 의견이나 목표가를 문구로 넣지 마라.
- 발송 메시지에 환경 변수 값이나 파일 경로를 넣지 마라 (`docs/SECURITY.md`).
- spec의 "범위 제외"에 있는 것을 만들지 마라.
