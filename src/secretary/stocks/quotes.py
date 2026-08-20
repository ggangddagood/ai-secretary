"""Yahoo Finance v8 chart 엔드포인트에서 시세를 읽는다.

인증이 없고 한국·미국 종목과 지수·환율을 한 소스로 커버한다. 재시도하지 않는다 —
하루 두 번 배치이므로 실패한 심볼은 건너뛰면 충분하다(기존 소스와 같은 정책).
"""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

import httpx

from ..http import make_client
from ..sources.base import describe_error
from .models import Quote, Ticker

logger = logging.getLogger(__name__)

CHART_BASE: Final[str] = "https://query1.finance.yahoo.com/v8/finance/chart/"
# 5d는 연휴에 유효 거래일이 2개 미만이 될 수 있다. 1mo는 22~23 거래일을 준다.
RANGE: Final[str] = "1mo"
INTERVAL: Final[str] = "1d"


def fetch_quotes(tickers: Sequence[Ticker], *, timeout: float) -> list[Quote]:
    """심볼마다 순차 조회한다. 실패한 심볼은 경고 로그를 남기고 결과에서 뺀다.

    반환 순서는 입력 순서를 따른다. 예외를 호출자에게 올리지 않는다.
    """
    quotes: list[Quote] = []
    with make_client(timeout) as client:
        for ticker in tickers:
            quote = _fetch_one(client, ticker)
            if quote is not None:
                quotes.append(quote)
    return quotes


def _fetch_one(client: httpx.Client, ticker: Ticker) -> Quote | None:
    # `^GSPC`, `USDKRW=X`처럼 심볼에 URL 예약 문자가 들어간다.
    url = CHART_BASE + urllib.parse.quote(ticker.symbol, safe="")
    try:
        response = client.get(url, params={"range": RANGE, "interval": INTERVAL})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("시세 조회 실패 %s: %s", ticker.symbol, describe_error(exc))
        return None
    return parse_chart(payload, ticker)


def parse_chart(payload: dict[str, Any], ticker: Ticker) -> Quote | None:
    """chart 응답에서 최신 종가와 등락률을 뽑는다. 읽을 수 없으면 None.

    등락률은 `close` 배열에서 None을 제거한 유효값의 마지막 두 개로 계산한다.
    `meta.chartPreviousClose`는 조회 창 시작 *이전*의 종가라 직전 거래일 종가가 아니다 —
    쓰면 예외 없이 그럴듯한 숫자로 틀린다.
    """
    try:
        chart = payload["chart"]
        if chart.get("error") is not None:
            logger.warning("시세 조회 실패 %s: chart.error=%s", ticker.symbol, chart["error"])
            return None
        result = chart["result"][0]
        meta = result["meta"]
        pairs = [
            (ts, close)
            for ts, close in zip(result["timestamp"], result["indicators"]["quote"][0]["close"])
            if close is not None
        ]
        if len(pairs) < 2:
            logger.warning("유효 종가가 부족합니다 %s: %d건", ticker.symbol, len(pairs))
            return None
        (latest_ts, latest), (_, prev) = pairs[-1], pairs[-2]
        if prev == 0:
            logger.warning("직전 종가가 0입니다 %s", ticker.symbol)
            return None
        as_of = datetime.fromtimestamp(latest_ts, tz=ZoneInfo(meta["exchangeTimezoneName"])).date()
        drawdown_pct, range_pct = fifty_two_week(meta, float(latest))
        return Quote(
            ticker=ticker,
            price=float(latest),
            change_pct=(float(latest) - float(prev)) / float(prev) * 100,
            currency=meta["currency"],
            as_of=as_of,
            drawdown_pct=drawdown_pct,
            range_pct=range_pct,
        )
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("시세 응답을 읽을 수 없습니다 %s: %s", ticker.symbol, describe_error(exc))
        return None


def fifty_two_week(meta: dict[str, Any], price: float) -> tuple[float | None, float | None]:
    """(52주 고점 대비 %, 52주 범위 내 위치 %)를 돌려준다. 읽을 수 없으면 (None, None).

    값은 `meta`에 이미 들어 있다 — 추가 조회도, RANGE 변경도 하지 않는다.
    고점 대비는 클램프하지 않는다: 양수는 "신고가"라는 신호이고 렌더가 그것으로 분기한다.
    범위 내 위치만 0~100으로 클램프해 이상 데이터(저점 밑 종가, low > high)를 흡수한다.
    """
    raw_high, raw_low = meta.get("fiftyTwoWeekHigh"), meta.get("fiftyTwoWeekLow")
    if raw_high is None or raw_low is None:
        return (None, None)
    try:
        high, low = float(raw_high), float(raw_low)
    except (TypeError, ValueError):
        return (None, None)
    if high <= 0:
        return (None, None)
    drawdown_pct = (price - high) / high * 100
    if high == low:
        return (drawdown_pct, None)
    range_pct = min(100.0, max(0.0, (price - low) / (high - low) * 100))
    return (drawdown_pct, range_pct)
