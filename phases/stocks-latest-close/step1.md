# Step 1: docs

바뀐 규칙을 문서에 반영하고, 해결된 미해결 문제를 정리한다. 코드 변경은 없다.

## 읽어야 할 파일

- `phases/stocks-latest-close/spec.md`   ← "확정 근거"가 재료다
- `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙"의 등락률 계산 규칙
- `docs/ENGINEERING_NOTES.md`
- `docs/tracking/FINDINGS.md` — "장 마감 직후가 아닌 시각에 돌리면 기준일이 하루 물러난다" 항목
- `docs/tracking/STATUS.md`
- step 0 산출물: `src/secretary/stocks/quotes.py`

## 작업

### 1. `docs/BUSINESS_RULES.md` — "등락률 계산 규칙" 갱신

현재 규칙은 "close 배열의 유효값 마지막 두 개"만 말한다. 실제 동작에 맞게 고친다.

- 최신 시세는 `meta.regularMarketPrice`, 기준일은 `meta.regularMarketTime`의 (거래소 타임존)
  날짜다.
- **직전 종가는 언제나 `close` 배열**에서 오며, **기준일보다 이전 날짜**의 마지막 유효값이다.
- `meta` 값을 읽을 수 없으면 `close` 유효값의 마지막 두 개로 폴백한다.
- **`meta.chartPreviousClose`는 여전히 쓰지 않는다** — 이 규칙을 지우지 마라. `regularMarketPrice`와
  다른 필드임을 명시한다.
- 이유를 한 줄 남긴다: 장 마감 후 `close` 배열에 최신 종가가 반영되지 않는 구간이 있어,
  그대로 두면 하루 전 데이터가 나간다.
- 엣지 케이스 표에 폴백 조건들을 추가한다.

### 2. `docs/ENGINEERING_NOTES.md` — 함정 추가

증상 → 원인 → 대응 → 검증 형식으로 쓴다.

- **장 마감 후에도 `close` 배열의 최신 bar가 `None`인 구간이 있다** — 2026-08-21 00:13 KST에
  한국장 브리핑이 이틀 전(8/19) 데이터를 싣고 "휴장"을 잘못 표시했다. 8/20 bar는 존재하지만
  `close`가 `None`이었고, 같은 응답의 `meta.regularMarketPrice`(271000)와
  `meta.regularMarketTime`(8/20 15:30:20, 정규 마감)은 정답을 갖고 있었다. 전날 22:53에는
  채워져 있었으므로 **채워졌다가 다시 비워지는 구간**이 있다. 대응: `meta`를 최신가로 쓰고
  `close`는 직전가 전용으로 쓴다. 검증: `tests/test_stocks_quotes.py`.
- **`currentTradingPeriod`로 장중 여부를 판정할 수 없다** — 이 값은 마감 후 이미 **다음**
  거래일을 가리킨다(실측: 8/20 15:30 종가인데 `currentTradingPeriod`는 8/21 09:00~15:00).
  `regularMarketTime >= end` 비교가 마감된 종가를 "장중"으로 오판한다.
- 알려진 한계 한 줄: 장중에 수동 실행하면 `regularMarketPrice`가 장중 가격이므로 "종가"가
  아니다. cron은 마감 후에만 돌아 실운영에는 영향이 없다.

### 3. `docs/tracking/FINDINGS.md` — 해결된 항목 제거

"장 마감 직후가 아닌 시각에 돌리면 기준일이 하루 물러난다" 항목을 **삭제한다.**
FINDINGS의 작성 기준이 "고쳤으면 여기 남기지 않는다 — 얻은 지식은 ENGINEERING_NOTES.md로"이므로,
위 2번에 기록한 뒤 이 항목은 지운다.

**"종목 표시명이 플랫폼·일반명사와 겹치면 뉴스 헤드라인이 오염된다" 항목은 그대로 둔다.**
그건 아직 해결되지 않았다.

### 4. `docs/tracking/STATUS.md` 갱신

- phase `stocks-latest-close` 항목을 추가한다.
- **2026-08-21 00:1x에 확인한 사실**을 검증 기록에 남긴다: 관심 종목 Variables 등록 후
  실제 Actions 실행에서 `vars` 주입이 동작했고(관심 종목 2건/1건 조회), 한국장은 급등락 2건이
  잡혀 뉴스 수집·LLM 해설까지 프로덕션에서 완주했다. 다만 그 발송은 이 phase가 고치는
  기준일 문제로 8/19 데이터였다.
- "남은 것"에서 `vars` 주입 미확인 항목을 **확인됨**으로 정리한다.
- **아직 관측하지 않은 것을 완료로 적지 마라**: 16:00 KST 정시 실행에서 기준일이 당일로
  찍히는지는 이 수정 이후에도 첫 정시 실행으로 확인해야 한다.

## Acceptance Criteria

```bash
bash scripts/verify.sh
grep -c "regularMarketPrice" docs/BUSINESS_RULES.md docs/ENGINEERING_NOTES.md
grep -c "chartPreviousClose" docs/BUSINESS_RULES.md
grep -c "기준일이 하루 물러난다" docs/tracking/FINDINGS.md || echo "OK: 해결된 항목 제거됨"
grep -c "표시명이 플랫폼" docs/tracking/FINDINGS.md
python3 -m secretary.main --dry-run > /dev/null; echo "회귀 exit=$?"
```

- 앞의 두 `grep -c`는 1 이상이어야 한다(`chartPreviousClose` 금지 규칙이 남아 있어야 한다).
- `기준일이 하루 물러난다`는 **0건**이어야 한다(삭제됨).
- `표시명이 플랫폼`은 **1 이상**이어야 한다(미해결이므로 남아 있어야 한다).

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 exit code를 확인한다.
2. 문서와 step 0의 실제 코드가 일치하는지 확인한다 — 폴백 조건, `prev`의 출처, 기준일 정의.
3. 결과에 따라 `phases/stocks-latest-close/index.json`의 해당 step을 갱신한다.

## 금지사항

- 코드를 수정하지 마라. 문서만이다. 문서와 코드가 어긋나면 문서를 코드에 맞추지 말고 그 사실을
  `summary`에 적어라 — spec이 정본이므로 코드가 틀렸을 수 있다.
- `chartPreviousClose` 금지 규칙을 지우지 마라. 여전히 유효하다.
- 미해결 상태인 "뉴스 헤드라인 오염" 항목을 FINDINGS에서 지우지 마라.
- 확인하지 않은 것을 STATUS.md에 완료로 적지 마라.
- AI 브리핑 규칙을 건드리지 마라.
