# Spec: stocks-latest-close

## 목표

장 마감 후 `close` 배열에 최신 종가가 아직 반영되지 않아도, `meta`가 가진 확정 종가를 써서
**최신 거래일 기준으로** 시세와 등락률을 만든다.

## 배경 — 실측으로 확인한 문제

2026-08-21 00:13 KST 실행에서 한국장 브리핑이 **이틀 전(8/19) 데이터**를 싣고 "휴장"을 잘못
표시했다. 원인은 Yahoo 응답의 불일치다.

```
005930.KS   close 배열의 8/20 bar  = None      ← 현재 로직이 보는 곳
            meta.regularMarketPrice = 271000.0  ← 실제 8/20 종가
            meta.regularMarketTime  = 2026-08-20 15:30:20 KST (정규 마감)
```

8/20 장은 정상 마감했고 종가도 확정됐는데 `close` 배열에만 반영되지 않았다. 현재 로직은
설계대로 `None`을 걷어내고 8/19 값을 썼다 — **버그가 아니라 설계가 이 경우를 몰랐다.**

같은 날 22:53에는 8/20 값이 채워져 있었다. 즉 채워졌다가 다시 비워지는 구간이 있다.

## 요구 동작

- `meta.regularMarketPrice`와 `meta.regularMarketTime`을 읽을 수 있으면 그것을 **최신 시세**로 쓴다.
  - `as_of` = `regularMarketTime`을 `meta.exchangeTimezoneName` 타임존으로 변환한 **날짜**
  - `price` = `regularMarketPrice`
  - `prev` = `close` 배열의 유효값 중 **`as_of`보다 이전 날짜**의 마지막 값
- 위 경로로 `prev`를 찾지 못하면(또는 `meta` 값을 읽을 수 없으면) **기존 방식으로 폴백한다**:
  `close`에서 `None`을 제거한 유효값의 마지막 두 개.
- 등락률은 어느 경로에서든 `(price - prev) / prev * 100`이다.
- 52주 지표는 위에서 정해진 `price`를 기준으로 계산한다.

### 실측 기대값 (회귀 기준)

| 심볼 | price | prev | change_pct | as_of |
| --- | --- | --- | --- | --- |
| `005930.KS` | 271000 (meta) | 247500 (8/19 close) | **+9.49%** | 2026-08-20 |
| `QQQ` | 712.105 (meta) | 716.08 (8/19 close) | -0.55% | 2026-08-20 |

## 불변 조건

- **CRITICAL: `meta.chartPreviousClose`를 쓰지 않는다.** 이 규칙은 그대로다 — 그 값은 조회 창
  시작 *이전*의 종가라 직전 거래일 종가가 아니다. `regularMarketPrice`는 별개 필드다.
- **직전 종가(`prev`)는 언제나 `close` 배열에서 온다.** `meta`에서 직전가를 가져오지 않는다.
- `meta` 값을 읽을 수 없어도 시세 조회가 실패하지 않는다 — 기존 방식으로 폴백한다.
- 폴백 경로의 동작은 지금과 완전히 같아야 한다. 기존 테스트가 그대로 통과한다.
- `price`와 `prev`가 **같은 날짜에서 오지 않는다.** 같은 날 값으로 등락률을 계산하면 항상 0이 된다.
- `prev == 0`이면 조회 실패로 본다(0으로 나누지 않는다).
- 렌더링·CLI·워크플로·환경 변수에 변경이 없다.

## 범위 제외

- 휴장 판정 규칙 변경 — 지금은 "기준일 ≠ 실행 시각의 시장 로컬 날짜"다. 장 열리기 전에
  실행하면 휴장으로 표시되는 문제가 있으나 이번 범위가 아니다(cron은 마감 후에만 돈다)
- 장중 실행 시 "장중"임을 표시하는 기능
- `range`·`interval` 변경, 재시도, 다른 데이터 소스 추가
- 52주 지표 계산식 변경

## 엣지 케이스

| 상황 | 처리 |
| --- | --- |
| `regularMarketPrice` 또는 `regularMarketTime`이 없음/`None` | 폴백(기존 방식) |
| 두 값이 숫자로 변환되지 않음 | 폴백. 예외를 올리지 않는다 |
| `regularMarketTime`이 타임스탬프로 변환되지 않음(`OSError`/`ValueError`) | 폴백 |
| `as_of`보다 이전 날짜의 유효 종가가 하나도 없음 | 폴백 |
| 폴백해도 유효값이 2개 미만 | 조회 실패(`None` 반환). 지금과 같다 |
| `prev == 0` | 조회 실패. 0으로 나누지 않는다 |
| `close` 배열에 이미 최신 종가가 있음(미국장 등) | `meta` 경로가 그대로 쓰이며 결과가 같다. `prev`는 그 이전 날짜에서 오므로 등락률이 어긋나지 않는다 |
| 장중 실행이라 `regularMarketPrice`가 장중 가격 | 그 값을 쓴다. cron은 마감 후에만 돌므로 실운영에는 영향이 없다. 이 한계를 문서에 적는다 |
| `regularMarketTime`의 날짜가 `close` 배열 마지막 bar보다 과거 | `as_of` 이전 유효값을 찾는 규칙이 그대로 적용된다. 별도 분기를 두지 않는다 |

## 외부 인터페이스

변경 없음. `Quote` 구조도 그대로다(`price`·`change_pct`·`as_of`의 **출처**만 바뀐다).

## 확정 근거

- **`meta.regularMarketPrice`를 최신가로 채택** — 실측에서 이 값이 `regularMarketTime`
  15:30:20(정규 마감)과 함께 확정 종가를 담고 있었다. `close` 배열이 비어 있어도 정답을 안다.
- **`prev`는 여전히 `close` 배열에서** — `meta`에는 직전 거래일 종가에 해당하는 신뢰할 수 있는
  필드가 없다. `chartPreviousClose`는 조회 창 이전 값이라 쓰면 안 된다(기존 CRITICAL 규칙).
- **`as_of` 이전 날짜로 `prev`를 거른다** — 단순히 "마지막 유효값"을 쓰면, `close`에 최신
  종가가 이미 있는 미국장에서 `price`와 `prev`가 같은 날이 되어 등락률이 0이 된다.
- **폴백을 남긴다** — `meta` 구조가 바뀌거나 필드가 빠져도 조용히 실패하지 않게 한다.
- **`currentTradingPeriod`로 장중 여부를 판정하지 않는다** — 실측에서 이 값이 이미 **다음**
  거래일(8/21 09:00~15:00)을 가리켜, 8/20 15:30 종가를 "장중"으로 오판했다. 쓸 수 없다.

## 필수 검증

- `bash scripts/verify.sh`
- `python3 -m secretary.stocks --market kr --dry-run` exit 0 — 기준일이 **마지막 개장일**이고,
  삼성전자 등락률이 8/19 종가 대비로 나온다
- `python3 -m secretary.stocks --market us --dry-run` exit 0
- `python3 -m secretary.main --dry-run` exit 0 (기존 AI 브리핑 회귀)
