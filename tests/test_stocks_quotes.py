"""시세 조회 테스트. 네트워크를 타지 않는다 — HTTP 계층을 가짜 클라이언트로 대체한다."""

import urllib.parse
from datetime import date, datetime, timezone

import httpx
import pytest

from secretary.stocks import quotes as quotes_module
from secretary.stocks.models import Ticker
from secretary.stocks.quotes import fetch_quotes, parse_chart

APPLE = Ticker("AAPL", "애플")
SAMSUNG = Ticker("005930.KS", "삼성전자")
KOSPI = Ticker("^KS11", "코스피")

# 2026-08-17/18 16:00 America/New_York
DAY1 = int(datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc).timestamp())
DAY2 = int(datetime(2026, 8, 18, 20, 0, tzinfo=timezone.utc).timestamp())
DAY3 = int(datetime(2026, 8, 19, 20, 0, tzinfo=timezone.utc).timestamp())
DAY4 = int(datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc).timestamp())


def chart_payload(
    *,
    timestamps,
    closes,
    tz="America/New_York",
    currency="USD",
    previous_close=None,
):
    meta = {"exchangeTimezoneName": tz, "currency": currency}
    if previous_close is not None:
        meta["chartPreviousClose"] = previous_close
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": meta,
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ],
        }
    }


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeClient:
    """make_client 대체. 심볼별로 지정된 페이로드를 준다."""

    def __init__(self, payloads: dict, failing: set[str] | None = None):
        self._payloads = payloads
        self._failing = failing or set()
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        symbol = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        if symbol in self._failing:
            raise httpx.ConnectError("연결 실패")
        return FakeResponse(self._payloads[symbol])


def patch_client(monkeypatch, payloads, failing=None) -> FakeClient:
    client = FakeClient(payloads, failing)
    monkeypatch.setattr(quotes_module, "make_client", lambda timeout: client)
    return client


# --- parse_chart ---------------------------------------------------------


def test_parse_chart_reads_price_change_and_as_of():
    payload = chart_payload(timestamps=[DAY1, DAY2], closes=[100.0, 110.0])

    quote = parse_chart(payload, APPLE)

    assert quote is not None
    assert quote.ticker is APPLE
    assert quote.price == 110.0
    assert quote.change_pct == pytest.approx(10.0)
    assert quote.currency == "USD"
    assert quote.as_of == date(2026, 8, 18)


def test_parse_chart_uses_market_timezone_for_as_of():
    # 06:30 UTC = 15:30 KST 같은 날, 뉴욕 기준으로는 전날이다.
    close_ts = int(datetime(2026, 8, 18, 6, 30, tzinfo=timezone.utc).timestamp())
    payload = chart_payload(
        timestamps=[close_ts - 86400, close_ts],
        closes=[268500.0, 271000.0],
        tz="Asia/Seoul",
        currency="KRW",
    )

    quote = parse_chart(payload, SAMSUNG)

    assert quote is not None
    assert quote.as_of == date(2026, 8, 18)
    assert quote.currency == "KRW"


def test_parse_chart_skips_trailing_none_close():
    """실측에서 035720.KQ의 close 배열 마지막 원소가 None이었다."""
    payload = chart_payload(timestamps=[DAY1, DAY2, DAY3], closes=[100.0, 110.0, None])

    quote = parse_chart(payload, APPLE)

    assert quote is not None
    assert quote.price == 110.0
    assert quote.change_pct == pytest.approx(10.0)
    assert quote.as_of == date(2026, 8, 18)


def test_parse_chart_skips_none_in_the_middle():
    payload = chart_payload(timestamps=[DAY1, DAY2, DAY3, DAY4], closes=[100.0, None, 120.0, 132.0])

    quote = parse_chart(payload, APPLE)

    assert quote is not None
    assert quote.price == 132.0
    assert quote.change_pct == pytest.approx(10.0)


def test_parse_chart_returns_none_with_single_valid_close():
    payload = chart_payload(timestamps=[DAY1, DAY2], closes=[None, 100.0])

    assert parse_chart(payload, APPLE) is None


def test_parse_chart_returns_none_when_previous_close_is_zero():
    payload = chart_payload(timestamps=[DAY1, DAY2], closes=[0.0, 100.0])

    assert parse_chart(payload, APPLE) is None


def test_parse_chart_returns_none_on_chart_error():
    payload = {"chart": {"error": {"code": "Not Found"}, "result": None}}

    assert parse_chart(payload, APPLE) is None


def test_parse_chart_returns_none_on_unexpected_shape():
    assert parse_chart({"chart": {"error": None, "result": []}}, APPLE) is None
    assert parse_chart({}, APPLE) is None


def test_change_pct_ignores_chart_previous_close():
    """chartPreviousClose는 조회 창 이전의 종가다. 실측 삼성전자 239500 vs 실제 직전 268500."""
    payload = chart_payload(
        timestamps=[DAY1, DAY2],
        closes=[268500.0, 271000.0],
        tz="Asia/Seoul",
        currency="KRW",
        previous_close=239500.0,
    )

    quote = parse_chart(payload, SAMSUNG)

    assert quote is not None
    assert quote.change_pct == pytest.approx((271000.0 - 268500.0) / 268500.0 * 100)
    assert quote.change_pct != pytest.approx((271000.0 - 239500.0) / 239500.0 * 100)


# --- fetch_quotes --------------------------------------------------------


def test_fetch_quotes_encodes_symbol_in_url(monkeypatch):
    client = patch_client(
        monkeypatch,
        {"^KS11": chart_payload(timestamps=[DAY1, DAY2], closes=[100.0, 110.0])},
    )

    fetch_quotes([KOSPI], timeout=1.0)

    (url, kwargs) = client.calls[0]
    assert url.endswith("%5EKS11")
    assert kwargs["params"] == {"range": "1mo", "interval": "1d"}


def test_fetch_quotes_keeps_going_after_one_symbol_fails(monkeypatch):
    payload = chart_payload(timestamps=[DAY1, DAY2], closes=[100.0, 110.0])
    patch_client(
        monkeypatch,
        {"AAPL": payload, "005930.KS": payload, "^KS11": payload},
        failing={"005930.KS"},
    )

    quotes = fetch_quotes([APPLE, SAMSUNG, KOSPI], timeout=1.0)

    assert [q.ticker.symbol for q in quotes] == ["AAPL", "^KS11"]


def test_fetch_quotes_drops_unparsable_symbol(monkeypatch):
    patch_client(
        monkeypatch,
        {
            "AAPL": chart_payload(timestamps=[DAY1, DAY2], closes=[100.0, 110.0]),
            "^KS11": {"chart": {"error": {"code": "Not Found"}}},
        },
    )

    quotes = fetch_quotes([APPLE, KOSPI], timeout=1.0)

    assert [q.ticker.symbol for q in quotes] == ["AAPL"]
