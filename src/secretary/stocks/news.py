"""급등락 종목의 근거가 될 헤드라인을 Google News RSS에서 모은다.

제목·링크·발행 시각까지만 쓴다 — 기사 본문은 추출하지 않는다(spec "범위 제외").
어떤 실패도 호출자에게 올리지 않는다. 시세가 브리핑의 본체이고 해설은 부가이므로,
뉴스 수집이 실패했다고 시세 발송까지 멈추면 안 된다.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

import httpx

from ..http import make_client
from ..sources.base import describe_error, parse_feed
from .models import Headline, Ticker

logger = logging.getLogger(__name__)

NEWS_BASE: Final[str] = "https://news.google.com/rss/search"
LOCALE: Final[dict[str, dict[str, str]]] = {
    "us": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "kr": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
}
RECENT_DAYS: Final[int] = 3
MAX_HEADLINES: Final[int] = 5


def fetch_headlines(
    ticker: Ticker, *, market: str, now: datetime, timeout: float
) -> list[Headline]:
    """종목 하나의 최근 헤드라인을 최신순으로 최대 MAX_HEADLINES건 돌려준다."""
    with make_client(timeout) as client:
        return _fetch(client, ticker, market=market, now=now)


def fetch_headlines_for(
    tickers: Sequence[Ticker], *, market: str, now: datetime, timeout: float
) -> dict[str, list[Headline]]:
    """여러 종목을 클라이언트 하나로 순차 수집해 `{심볼: [Headline]}`을 돌려준다.

    0건인 종목도 키는 남긴다 — 호출자가 "수집했지만 없음"을 알 수 있어야 한다.
    """
    with make_client(timeout) as client:
        return {ticker.symbol: _fetch(client, ticker, market=market, now=now) for ticker in tickers}


def _fetch(client: httpx.Client, ticker: Ticker, *, market: str, now: datetime) -> list[Headline]:
    # 검색어는 심볼이 아니라 표시명이다 — 뉴스에서 검색되는 이름은 그쪽이다.
    params = {"q": ticker.label, **LOCALE[market]}
    since = now - timedelta(days=RECENT_DAYS)
    try:
        response = client.get(NEWS_BASE, params=params)
        response.raise_for_status()
        items = parse_feed(response.content, source=f"news:{ticker.symbol}", since=since)
    except Exception as exc:  # 뉴스는 부가 정보다. 전체 실행을 실패시키지 않는다
        logger.warning("뉴스 수집 실패 %s: %s", ticker.symbol, describe_error(exc))
        return []

    # parse_feed가 발행 시각을 못 읽는 항목을 이미 제외하므로 published_at은 None이 아니다.
    headlines = [
        Headline(title=item.title, url=item.url, published_at=item.published_at) for item in items
    ]
    headlines.sort(key=lambda headline: headline.published_at, reverse=True)
    return headlines[:MAX_HEADLINES]
