# Step 1: stocks-config-models

주식 파이프라인의 설정 로딩과 데이터 구조를 만든다. 아직 네트워크 호출은 없다.

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 특히 "환경 변수", "관심 종목 목록 형식", "시세 조회"
- `docs/STANDARDS.md` — "모듈 경계"(`os.environ`은 `config.py`에서만)
- `docs/SECURITY.md` — 에러 메시지에 값을 넣지 않는 규칙
- `src/secretary/config.py` — 기존 `Config`/`load_config` 패턴을 그대로 따른다
- `src/secretary/models.py` — frozen dataclass 스타일과 `AXES` 상수 배치를 참고한다
- `tests/test_config.py` — 기존 테스트 스타일

## 작업

### 1. `src/secretary/stocks/__init__.py` 신설

패키지 docstring만 둔다. 여기서 하위 모듈을 import 하지 않는다(순환과 불필요한 로딩을 만든다).

### 2. `src/secretary/stocks/models.py` 신설

**이 모듈은 다른 `secretary` 모듈을 import 하지 않는다.** `config.py`가 이 모듈을 import 하므로,
반대 방향 의존이 생기면 순환한다.

```python
Market = Literal["us", "kr"]

MARKETS: Final[tuple[str, ...]] = ("us", "kr")

@dataclass(frozen=True)
class Ticker:
    symbol: str   # Yahoo 심볼. 예: "AAPL", "005930.KS", "^KS11", "USDKRW=X"
    label: str    # 표시명이자 뉴스 검색어. 예: "애플", "삼성전자"

@dataclass(frozen=True)
class Quote:
    ticker: Ticker
    price: float
    change_pct: float
    currency: str          # "USD" | "KRW" 등 meta.currency 원문
    as_of: date            # 최신 유효 종가의 거래일 (거래소 타임존 기준)

@dataclass(frozen=True)
class Headline:
    title: str
    url: str
    published_at: datetime

@dataclass(frozen=True)
class StockEntry:
    quote: Quote
    headlines: list[Headline]   # 급등락이 아니거나 수집 실패면 빈 리스트
    comment_ko: str | None      # 해설. 헤드라인이 없으면 반드시 None

@dataclass(frozen=True)
class StockBrief:
    market: str
    generated_at: datetime
    as_of: date | None          # 시장 기준일. 조회 결과가 없으면 None
    is_holiday: bool            # 기준일이 그 시장 로컬 날짜와 다르면 True
    indices: list[Quote]
    entries: list[StockEntry]
```

시장 지표는 코드 상수로 둔다(관심 종목과 달리 사적 정보가 아니다). 심볼은 계획 단계에서
실호출로 검증했다.

```python
MARKET_INDICES: Final[dict[str, tuple[Ticker, ...]]] = {
    "us": (Ticker("^GSPC", "S&P 500"), Ticker("^IXIC", "나스닥"), Ticker("USDKRW=X", "원달러")),
    "kr": (Ticker("^KS11", "코스피"), Ticker("^KQ11", "코스닥"), Ticker("USDKRW=X", "원달러")),
}

# 24시간 거래라 휴장 판정에서 제외한다.
FX_SYMBOL: Final[str] = "USDKRW=X"

# 시장 로컬 날짜 판정에 쓰는 타임존.
MARKET_TZ: Final[dict[str, str]] = {"us": "America/New_York", "kr": "Asia/Seoul"}

MARKET_LABELS: Final[dict[str, str]] = {"us": "미국장", "kr": "한국장"}
```

### 3. `src/secretary/config.py` 에 추가

기존 `Config`/`load_config`는 **건드리지 않는다**. 아래를 덧붙인다.

```python
DEFAULT_MOVE_THRESHOLD: Final[float] = 5.0

@dataclass(frozen=True)
class StocksConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    gemini_api_key: str
    market: str
    watchlist: tuple[Ticker, ...]
    move_threshold: float
    http_timeout: float

def parse_watchlist(raw: str) -> tuple[Ticker, ...]: ...

def load_stocks_config(market: str, *, require_secrets: bool = True) -> StocksConfig: ...
```

- `load_stocks_config`는 `market`에 따라 `STOCKS_WATCHLIST_US` / `STOCKS_WATCHLIST_KR` 중
  하나를 읽는다. `market`이 `MARKETS`에 없으면 `ConfigError`를 올린다.
- 필수 변수 검사는 기존 `REQUIRED_VARS`와 같은 세 개(`TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`)다. `require_secrets=False`면 건너뛴다.
- `move_threshold`는 기존 `_float_env` 헬퍼를 재사용한다.
- `http_timeout`도 기존 `_float_env("HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT)`을 쓴다.

`parse_watchlist` 규칙 (spec "관심 종목 목록 형식"이 정본):

- 쉼표로 나눈다. 각 항목은 `심볼:표시명`.
- **첫 콜론에서만** 나눈다 (`split(":", 1)`). 표시명에 콜론이 들어갈 수 있다.
- 콜론이 없으면 심볼을 표시명으로 쓴다.
- 심볼·표시명 앞뒤 공백을 제거한다.
- 심볼이 빈 문자열인 항목은 건너뛴다(경고 로그).
- 표시명이 빈 문자열이면 심볼을 표시명으로 쓴다.
- 입력이 빈 문자열이면 빈 튜플을 돌려준다.

### 4. `tests/test_stocks_config.py` 신설

최소 아래를 덮는다.

- `parse_watchlist("AAPL:애플,NVDA:엔비디아")` → 2건, label이 한글
- `parse_watchlist("AAPL")` → label == "AAPL"
- `parse_watchlist("005930.KS:삼성전자:우선주")` → label == "삼성전자:우선주" (첫 콜론에서만 분리)
- `parse_watchlist(" AAPL : 애플 , , NVDA ")` → 공백 제거 + 빈 항목 무시 → 2건
- `parse_watchlist(":애플")` → 심볼이 비어 건너뜀 → 0건
- `parse_watchlist("")` → 빈 튜플
- `load_stocks_config("us", ...)`가 `STOCKS_WATCHLIST_US`를 읽고 `STOCKS_WATCHLIST_KR`은 읽지 않는다
- `load_stocks_config("jp")` → `ConfigError`
- `require_secrets=True`인데 변수가 없으면 `ConfigError`이고, **에러 메시지에 값이 들어가지 않는다**
- `STOCKS_MOVE_THRESHOLD` 미설정 시 기본 5.0

환경 변수는 `monkeypatch.setenv` / `monkeypatch.delenv`로 다룬다.

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
from secretary.config import parse_watchlist
print(parse_watchlist('AAPL:애플,005930.KS:삼성전자'))
print(parse_watchlist(''))
"
python -c "from secretary.stocks.models import MARKET_INDICES, MARKET_TZ, FX_SYMBOL; print(MARKET_INDICES['kr'])"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다 (통과 → `"completed"` + `"summary"`).

## 금지사항

- `secretary/stocks/models.py`에서 다른 `secretary` 모듈을 import 하지 마라. 이유: `config.py`가
  이 모듈을 import 하므로 순환이 생긴다.
- 기존 `Config`/`load_config`/`REQUIRED_VARS`를 수정하지 마라. AI 브리핑 파이프라인이 쓰고 있다.
- `os.environ`을 `config.py` 밖에서 읽지 마라 (CRITICAL).
- 에러 메시지에 환경 변수 **값**을 넣지 마라. 이름만 넣는다 (`docs/SECURITY.md`).
- 관심 종목 기본값을 코드에 박지 마라. 리포지토리가 공개이므로 종목은 환경 변수로만 들어온다.
- 네트워크 호출 코드를 작성하지 마라 (step 2부터).
- spec의 "범위 제외"에 있는 것을 만들지 마라.
