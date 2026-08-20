# Step 2: docs

새 지표의 규칙을 문서에 반영한다. 코드 변경은 없다.

## 읽어야 할 파일

- `phases/stocks-52w-high/spec.md`   ← "확정 근거"가 문서에 옮길 재료다
- `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙" 절
- `docs/tracking/STATUS.md`
- `docs/ENGINEERING_NOTES.md`
- step 0·1 산출물: `src/secretary/stocks/models.py`, `quotes.py`, `render.py`

## 작업

### 1. `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙"에 추가

기존 규칙은 건드리지 않고, "등락률 계산 규칙" 다음에 **"52주 지표 규칙"** 절을 넣는다.

- 용어: **고점 대비 하락률**(52주 최고가 대비 현재 종가가 얼마나 낮은지), **범위 내 위치**
  (52주 저점~고점 구간에서 현재 종가의 위치, 0~100%)
- 출처는 `meta.fiftyTwoWeekHigh` / `meta.fiftyTwoWeekLow`이며 **추가 조회를 하지 않는다**
- 계산식 두 개와, `range_pct`만 0~100으로 클램프한다는 것
- **52주 값을 얻지 못해도 시세 조회는 성공이다** — 종가와 등락률은 유효하다
- 종가가 52주 고점보다 높으면 `52주 신고가`로 표시한다. 우리는 종가를 쓰는데
  `fiftyTwoWeekHigh`는 장중 고가를 포함하므로 실제로 발생할 수 있다
- 표시 규칙: 하락률 소수 1자리, 범위 위치 정수, 값이 없으면 줄 자체를 생략,
  급등락 블록에는 붙이지 않는다
- "주가 브리핑 엣지 케이스" 표에 spec의 엣지 행들을 추가한다

### 2. `docs/ENGINEERING_NOTES.md` — 함정 1건 추가

증상 → 원인 → 대응 → 검증 형식으로:

- **`fiftyTwoWeekHigh`는 장중 고가라 종가보다 높을 수 있다** — 우리는 `close` 배열의 종가로
  계산하므로 `drawdown_pct`가 양수가 되는 날이 생긴다. 버그로 오해해 0으로 클램프하면
  "신고가" 정보가 사라진다. 대응: 양수를 그대로 두고 렌더가 `52주 신고가`로 분기한다.
  검증: `tests/test_stocks_quotes.py`의 종가 > 고점 케이스.

### 3. `docs/tracking/STATUS.md` 갱신

- phase `stocks-52w-high` 항목을 추가하고 step별 산출물과 검증 결과(`verify.sh` exit code,
  테스트 개수)를 적는다.
- **실제 Actions 실행으로 확인되지 않은 것을 완료로 적지 마라.** dry-run까지만 확인했다면
  그렇게 적는다.
- `phases/index.json`의 이 phase 상태는 `execute.py`가 갱신하므로 직접 건드리지 않는다.

## Acceptance Criteria

```bash
bash scripts/verify.sh
grep -c "52주" docs/BUSINESS_RULES.md
grep -c "fiftyTwoWeekHigh" docs/ENGINEERING_NOTES.md
grep -c "stocks-52w-high" docs/tracking/STATUS.md
python3 -m secretary.main --dry-run > /dev/null; echo "회귀 exit=$?"
```

`grep -c` 결과가 모두 1 이상이어야 한다.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 exit code를 확인한다.
2. 문서와 실제 코드가 일치하는지 확인한다 — 계산식, 클램프 범위, 생략 규칙이 구현과 같은가.
3. 결과에 따라 `phases/stocks-52w-high/index.json`의 해당 step을 갱신한다.

## 금지사항

- 코드를 수정하지 마라. 이번 step은 문서만이다. 문서와 코드가 어긋나면 **문서를 코드에 맞추지 말고**
  어긋난 사실을 `summary`에 적어라 — spec이 정본이므로 코드가 틀렸을 수 있다.
- `docs/BUSINESS_RULES.md`의 AI 브리핑 규칙(4개 축, 선별, 중복 판정, 요약)을 건드리지 마라.
- 확인하지 않은 것을 STATUS.md에 완료로 적지 마라.
- 문서에 시크릿 값이나 실제 관심 종목을 적지 마라. 예시는 일반적인 종목명을 쓴다.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
