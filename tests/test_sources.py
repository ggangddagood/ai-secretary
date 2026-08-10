"""수집 레이어 테스트. 네트워크를 타지 않는다 — HTTP 계층을 픽스처로 대체한다."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from secretary.config import Config
from secretary.models import Item
from secretary.sources import GITHUB_WINDOW, RECENT_WINDOW, build_sources, collect_all
from secretary.sources import geeknews as geeknews_module
from secretary.sources import github as github_module
from secretary.sources import hackernews as hackernews_module
from secretary.sources import rss as rss_module
from secretary.sources.geeknews import GeekNewsSource
from secretary.sources.github import GitHubSource
from secretary.sources.hackernews import HN_QUERIES, HackerNewsSource
from secretary.sources.rss import RSS_FEEDS, RssSource

FIXTURES = Path(__file__).parent / "fixtures"

SINCE = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)


def read_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        return None


class FakeClient:
    """make_client 대체. 모든 GET에 같은 픽스처 응답을 준다."""

    def __init__(self, content: bytes, failing_urls: set[str] | None = None):
        self._content = content
        self._failing_urls = failing_urls or set()
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url in self._failing_urls:
            raise httpx.ConnectError("연결 실패")
        return FakeResponse(self._content)


def patch_client(monkeypatch, module, content: bytes, failing_urls=None) -> FakeClient:
    client = FakeClient(content, failing_urls)
    monkeypatch.setattr(module, "make_client", lambda timeout: client)
    return client


# --- Hacker News ---------------------------------------------------------


@pytest.fixture
def hn_client(monkeypatch):
    return patch_client(monkeypatch, hackernews_module, read_fixture("hn_search.json"))


def test_hackernews_maps_hit_fields(hn_client):
    items = HackerNewsSource().fetch(since=SINCE, timeout=1.0)

    top = items[0]
    assert top.title == "Fastmail offers EU data region"
    assert top.url == "https://www.fastmail.com/blog/fastmail-offers-eu-data-region/"
    assert top.source == "hackernews"
    assert top.score == 214
    assert top.published_at == datetime(2026, 8, 9, 9, 12, 3, tzinfo=timezone.utc)


def test_hackernews_falls_back_to_permalink_when_url_missing(hn_client):
    items = HackerNewsSource().fetch(since=SINCE, timeout=1.0)

    ask = next(item for item in items if item.title.startswith("Ask HN"))
    assert ask.url == "https://news.ycombinator.com/item?id=48886741"


def test_hackernews_skips_hits_without_title_and_dedupes_queries(hn_client):
    items = HackerNewsSource().fetch(since=SINCE, timeout=1.0)

    # 프론트페이지 1회 + 키워드 쿼리마다 1회 요청하지만 응답이 같으므로 URL 기준으로 합쳐진다.
    assert len(hn_client.calls) == 1 + len(HN_QUERIES)
    assert len(items) == 2  # 제목 없는 hit은 버린다


def test_hackernews_keyword_query_filters_by_since_and_points(hn_client):
    HackerNewsSource().fetch(since=SINCE, timeout=1.0)

    front_page_params = hn_client.calls[0][1]["params"]
    keyword_params = hn_client.calls[1][1]["params"]
    assert front_page_params == {"tags": "front_page"}
    assert keyword_params["query"] == HN_QUERIES[0]
    assert keyword_params["numericFilters"] == (f"created_at_i>{int(SINCE.timestamp())},points>30")


# --- GeekNews ------------------------------------------------------------


def test_geeknews_parses_feed(monkeypatch):
    patch_client(monkeypatch, geeknews_module, read_fixture("geeknews.xml"))

    items = GeekNewsSource().fetch(since=SINCE, timeout=1.0)

    assert [item.title for item in items] == [
        "Show GN: Sift - 원클릭 복구를 지원하는 Rust 기반 로컬 파일 자동 정리 CLI",
        "LLM 에이전트를 사내 업무에 도입한 6개월 회고",
    ]
    first = items[0]
    assert first.url == "https://news.hada.io/topic?id=32300"
    assert first.source == "geeknews"
    assert first.score is None
    assert first.published_at == datetime(2026, 8, 9, 13, 54, 39, tzinfo=timezone.utc)
    # summary_hint에는 HTML 태그가 남지 않는다.
    assert first.summary_hint == "Hazel을 & 오래 썼지만 GUI가 무겁습니다"


def test_geeknews_drops_entries_older_than_since(monkeypatch):
    patch_client(monkeypatch, geeknews_module, read_fixture("geeknews.xml"))

    items = GeekNewsSource().fetch(
        since=datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc), timeout=1.0
    )

    assert [item.url for item in items] == ["https://news.hada.io/topic?id=32300"]


# --- GitHub --------------------------------------------------------------


def test_github_parses_repositories(monkeypatch):
    patch_client(monkeypatch, github_module, read_fixture("github_search.json"))

    items = GitHubSource().fetch(since=SINCE, timeout=1.0)

    assert len(items) == 2  # 쿼리 3개가 같은 응답 → URL 기준 중복 제거
    top = items[0]
    assert top.title == (
        "waiterve/wai-play — WAI Play - AI web game testing and quality evaluation platform"
    )
    assert top.url == "https://github.com/waiterve/wai-play"
    assert top.source == "github"
    assert top.score == 229
    assert top.published_at == datetime(2026, 8, 4, 7, 20, 22, tzinfo=timezone.utc)

    without_description = items[1]
    assert without_description.title == "octo-labs/agent-runtime"
    assert without_description.summary_hint is None


def test_github_sends_token_when_configured(monkeypatch):
    client = patch_client(monkeypatch, github_module, read_fixture("github_search.json"))

    GitHubSource(token="gh-token").fetch(since=SINCE, timeout=1.0)

    headers = client.calls[0][1]["headers"]
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["Authorization"] == "Bearer gh-token"


def test_github_omits_authorization_without_token(monkeypatch):
    client = patch_client(monkeypatch, github_module, read_fixture("github_search.json"))

    GitHubSource().fetch(since=SINCE, timeout=1.0)

    assert "Authorization" not in client.calls[0][1]["headers"]


# --- RSS -----------------------------------------------------------------


def test_rss_keeps_reading_after_one_feed_fails(monkeypatch, caplog):
    dead_name, dead_url = RSS_FEEDS[0]
    patch_client(monkeypatch, rss_module, read_fixture("geeknews.xml"), failing_urls={dead_url})

    with caplog.at_level(logging.WARNING):
        items = RssSource().fetch(since=SINCE, timeout=1.0)

    assert len(items) == (len(RSS_FEEDS) - 1) * 2
    assert dead_name in caplog.text
    assert all(item.source.startswith("rss:") for item in items)
    assert not any(item.source == f"rss:{dead_name}" for item in items)


# --- collect_all ---------------------------------------------------------


class StubSource:
    def __init__(self, name, *, items=None, error=None):
        self.name = name
        self._items = items or []
        self._error = error
        self.since = None

    def fetch(self, *, since, timeout):
        self.since = since
        if self._error is not None:
            raise self._error
        return list(self._items)


def make_config(**overrides) -> Config:
    defaults = {
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "gemini_api_key": "",
        "github_token": None,
        "brief_item_count": 5,
        "state_path": Path("state/seen.json"),
        "http_timeout": 1.0,
    }
    return Config(**{**defaults, **overrides})


def make_item(title, url, *, source="stub", score=None) -> Item:
    return Item(
        title=title,
        url=url,
        source=source,
        score=score,
        published_at=None,
        summary_hint=None,
    )


def use_sources(monkeypatch, *pairs):
    monkeypatch.setattr("secretary.sources.build_sources", lambda cfg: list(pairs))


def test_collect_all_continues_when_one_source_raises(monkeypatch, caplog):
    broken = StubSource("broken", error=httpx.ConnectTimeout("타임아웃"))
    healthy = StubSource("healthy", items=[make_item("살아있는 소스", "https://example.com/alive")])
    use_sources(monkeypatch, (broken, RECENT_WINDOW), (healthy, RECENT_WINDOW))

    with caplog.at_level(logging.WARNING):
        items = collect_all(make_config(), now=NOW)

    assert [item.url for item in items] == ["https://example.com/alive"]
    assert "broken" in caplog.text


def test_collect_all_returns_empty_when_every_source_fails(monkeypatch):
    use_sources(
        monkeypatch,
        (StubSource("a", error=RuntimeError("boom")), RECENT_WINDOW),
        (StubSource("b", error=RuntimeError("boom")), RECENT_WINDOW),
    )

    assert collect_all(make_config(), now=NOW) == []


def test_collect_all_merges_same_url_across_sources(monkeypatch):
    first = StubSource(
        "first",
        items=[make_item("HN 글", "https://example.com/x", source="hackernews", score=10)],
    )
    second = StubSource(
        "second",
        items=[make_item("RSS 글", "https://example.com/x", source="rss:Blog")],
    )
    use_sources(monkeypatch, (first, RECENT_WINDOW), (second, RECENT_WINDOW))

    items = collect_all(make_config(), now=NOW)

    assert len(items) == 1
    assert items[0].source == "hackernews"  # 먼저 수집된 쪽을 남긴다


def test_collect_all_sorts_by_score_with_none_last(monkeypatch):
    source = StubSource(
        "mixed",
        items=[
            make_item("점수 없음", "https://example.com/none"),
            make_item("낮은 점수", "https://example.com/low", score=5),
            make_item("높은 점수", "https://example.com/high", score=300),
        ],
    )
    use_sources(monkeypatch, (source, RECENT_WINDOW))

    items = collect_all(make_config(), now=NOW)

    assert [item.url for item in items] == [
        "https://example.com/high",
        "https://example.com/low",
        "https://example.com/none",
    ]


def test_collect_all_passes_each_source_its_own_window(monkeypatch):
    recent = StubSource("recent")
    weekly = StubSource("weekly")
    use_sources(monkeypatch, (recent, RECENT_WINDOW), (weekly, GITHUB_WINDOW))

    collect_all(make_config(), now=NOW)

    assert recent.since == NOW - timedelta(hours=24)
    assert weekly.since == NOW - timedelta(days=7)


def test_build_sources_covers_all_four_source_groups():
    names = [source.name for source, _ in build_sources(make_config())]

    assert names == ["hackernews", "geeknews", "github", "rss"]
