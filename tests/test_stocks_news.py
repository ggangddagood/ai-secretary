"""뉴스 헤드라인 수집 테스트. 네트워크를 타지 않는다 — HTTP 계층을 가짜 클라이언트로 대체한다."""

import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from secretary.stocks import news as news_module
from secretary.stocks.models import Ticker
from secretary.stocks.news import NEWS_BASE, fetch_headlines, fetch_headlines_for

FIXTURES = Path(__file__).parent / "fixtures"

SAMSUNG = Ticker("005930.KS", "삼성전자")
NVIDIA = Ticker("NVDA", "엔비디아")

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)  # 3일 전 = 2026-08-16 12:00 UTC


def read_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FakeClient:
    """make_client 대체. 검색어(q)별로 지정된 피드 본문을 준다."""

    def __init__(self, contents: dict[str, bytes], failing: set[str] | None = None):
        self._contents = contents
        self._failing = failing or set()
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        query = kwargs["params"]["q"]
        if query in self._failing:
            raise httpx.ConnectError("연결 실패")
        return FakeResponse(self._contents[query])


def patch_client(monkeypatch, contents, failing=None) -> FakeClient:
    client = FakeClient(contents, failing)
    monkeypatch.setattr(news_module, "make_client", lambda timeout: client)
    return client


# --- fetch_headlines -----------------------------------------------------


def test_maps_title_url_and_published_at(monkeypatch):
    patch_client(monkeypatch, {"삼성전자": read_fixture("google_news.xml")})

    headlines = fetch_headlines(SAMSUNG, market="kr", now=NOW, timeout=1.0)

    assert [h.title for h in headlines] == [
        "삼성전자 주가 급등, 외국인 순매수",  # 최신순으로 정렬된다
        "삼성전자, HBM4 양산 라인 가동",
    ]
    assert headlines[0].url == "https://news.google.com/rss/articles/CBMiaGh0dHBz02"
    assert headlines[0].published_at == datetime(2026, 8, 19, 2, 30, tzinfo=timezone.utc)


def test_excludes_headlines_older_than_three_days(monkeypatch):
    patch_client(monkeypatch, {"삼성전자": read_fixture("google_news.xml")})

    headlines = fetch_headlines(SAMSUNG, market="kr", now=NOW, timeout=1.0)

    assert all("지난달" not in h.title for h in headlines)


def test_keeps_only_the_five_most_recent(monkeypatch):
    patch_client(monkeypatch, {"엔비디아": read_fixture("google_news_many.xml")})

    headlines = fetch_headlines(NVIDIA, market="kr", now=NOW, timeout=1.0)

    assert [h.title for h in headlines] == [
        "엔비디아 관련 뉴스 7",
        "엔비디아 관련 뉴스 6",
        "엔비디아 관련 뉴스 5",
        "엔비디아 관련 뉴스 4",
        "엔비디아 관련 뉴스 3",
    ]


def test_http_error_returns_empty_list(monkeypatch, caplog):
    patch_client(monkeypatch, {"삼성전자": b""}, failing={"삼성전자"})

    with caplog.at_level(logging.WARNING):
        headlines = fetch_headlines(SAMSUNG, market="kr", now=NOW, timeout=1.0)

    assert headlines == []
    assert "005930.KS" in caplog.text


def test_html_response_returns_empty_list(monkeypatch):
    """피드가 폐지되면 XML 대신 HTML이 200으로 온다 — 예외가 아니라 빈 결과다."""
    patch_client(monkeypatch, {"삼성전자": b"<html><body>cookie banner</body></html>"})

    assert fetch_headlines(SAMSUNG, market="kr", now=NOW, timeout=1.0) == []


def test_query_uses_ticker_label_not_symbol(monkeypatch):
    client = patch_client(monkeypatch, {"삼성전자": read_fixture("google_news.xml")})

    fetch_headlines(SAMSUNG, market="kr", now=NOW, timeout=1.0)

    url, kwargs = client.calls[0]
    assert url == NEWS_BASE
    assert kwargs["params"]["q"] == "삼성전자"


@pytest.mark.parametrize(
    "market,expected",
    [
        ("kr", {"hl": "ko", "gl": "KR", "ceid": "KR:ko"}),
        ("us", {"hl": "en-US", "gl": "US", "ceid": "US:en"}),
    ],
)
def test_locale_params_follow_market(monkeypatch, market, expected):
    client = patch_client(monkeypatch, {"엔비디아": read_fixture("google_news_many.xml")})

    fetch_headlines(NVIDIA, market=market, now=NOW, timeout=1.0)

    _, kwargs = client.calls[0]
    assert {k: kwargs["params"][k] for k in expected} == expected


# --- fetch_headlines_for -------------------------------------------------


def test_fetch_headlines_for_keeps_key_when_collection_fails(monkeypatch):
    client = patch_client(
        monkeypatch,
        {"삼성전자": read_fixture("google_news.xml"), "엔비디아": b""},
        failing={"엔비디아"},
    )

    result = fetch_headlines_for([SAMSUNG, NVIDIA], market="kr", now=NOW, timeout=1.0)

    assert set(result) == {"005930.KS", "NVDA"}
    assert len(result["005930.KS"]) == 2
    assert result["NVDA"] == []
    assert len(client.calls) == 2  # 클라이언트 하나로 순차 처리한다
