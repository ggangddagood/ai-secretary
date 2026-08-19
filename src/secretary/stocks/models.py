"""주식 브리핑이 주고받는 데이터 구조와 시장 상수.

시세 조회(Quote) → 뉴스 수집(Headline) → 브리핑(StockEntry, StockBrief) 순으로 흐른다.

이 모듈은 다른 `secretary` 모듈을 import 하지 않는다 — `config.py`가 여기서 `Ticker`를
가져가므로, 반대 방향 의존이 생기면 순환한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal

Market = Literal["us", "kr"]

MARKETS: Final[tuple[str, ...]] = ("us", "kr")


@dataclass(frozen=True)
class Ticker:
    symbol: str  # Yahoo 심볼. 예: "AAPL", "005930.KS", "^KS11", "USDKRW=X"
    label: str  # 표시명이자 뉴스 검색어. 예: "애플", "삼성전자"


@dataclass(frozen=True)
class Quote:
    ticker: Ticker
    price: float
    change_pct: float
    currency: str  # meta.currency 원문. 예: "USD", "KRW"
    as_of: date  # 최신 유효 종가의 거래일 (거래소 타임존 기준)


@dataclass(frozen=True)
class Headline:
    title: str
    url: str
    published_at: datetime


@dataclass(frozen=True)
class StockEntry:
    quote: Quote
    headlines: list[Headline]  # 급등락이 아니거나 수집 실패면 빈 리스트
    comment_ko: str | None  # 해설. 헤드라인이 없으면 반드시 None


@dataclass(frozen=True)
class StockBrief:
    market: str
    generated_at: datetime
    as_of: date | None  # 시장 기준일. 조회 결과가 없으면 None
    is_holiday: bool  # 기준일이 그 시장 로컬 날짜와 다르면 True
    indices: list[Quote]
    entries: list[StockEntry]


# 시장 지표는 코드 상수다 — 관심 종목과 달리 사적 정보가 아니다.
MARKET_INDICES: Final[dict[str, tuple[Ticker, ...]]] = {
    "us": (Ticker("^GSPC", "S&P 500"), Ticker("^IXIC", "나스닥"), Ticker("USDKRW=X", "원달러")),
    "kr": (Ticker("^KS11", "코스피"), Ticker("^KQ11", "코스닥"), Ticker("USDKRW=X", "원달러")),
}

# 24시간 거래라 휴장 판정에서 제외한다.
FX_SYMBOL: Final[str] = "USDKRW=X"

# 시장 로컬 날짜 판정에 쓰는 타임존.
MARKET_TZ: Final[dict[str, str]] = {"us": "America/New_York", "kr": "Asia/Seoul"}

MARKET_LABELS: Final[dict[str, str]] = {"us": "미국장", "kr": "한국장"}
