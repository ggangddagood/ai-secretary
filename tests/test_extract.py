"""본문 추출 테스트. 네트워크를 타지 않는다 — HTTP 계층을 픽스처로 대체한다."""

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from secretary import extract as extract_module
from secretary.extract import MAX_BODY_CHARS, extract_articles, fetch_body
from secretary.models import Item

FIXTURES = Path(__file__).parent / "fixtures"

URL = "https://example.com/post"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_response(
    text: str, *, content_type: str = "text/html; charset=utf-8", status: int = 200
) -> httpx.Response:
    return httpx.Response(
        status,
        text=text,
        headers={"content-type": content_type},
        request=httpx.Request("GET", URL),
    )


def patch_http(monkeypatch, handler):
    """`make_client`를 대체한다. handler(url)이 응답을 주거나 예외를 던진다."""

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def get(self, url, **kwargs):
            calls.append(url)
            return handler(url)

    calls: list[str] = []
    monkeypatch.setattr(extract_module, "make_client", lambda timeout: FakeClient())
    return calls


def patch_response(monkeypatch, response: httpx.Response) -> list[str]:
    return patch_http(monkeypatch, lambda url: response)


def make_item(url: str, *, summary_hint: str | None = None) -> Item:
    return Item(
        title="제목",
        url=url,
        source="github",
        score=None,
        published_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        summary_hint=summary_hint,
    )


# --- fetch_body ----------------------------------------------------------


def test_fetch_body_extracts_article_text(monkeypatch):
    patch_response(monkeypatch, make_response(read_fixture("article.html")))

    body = fetch_body(URL, timeout=1.0)

    assert body is not None
    assert "distribution is a product decision" in body
    # 네비게이션·스크립트·푸터 텍스트는 섞이지 않는다.
    assert "NAV_ARCHIVE_LINK" not in body
    assert "SCRIPT_TRACKER_BEACON" not in body
    assert "FOOTER_COPYRIGHT_NOTICE" not in body


def test_fetch_body_returns_none_when_body_too_short(monkeypatch):
    patch_response(monkeypatch, make_response(read_fixture("article_thin.html")))

    assert fetch_body(URL, timeout=1.0) is None


def test_fetch_body_returns_none_for_non_html_content_type(monkeypatch):
    calls = patch_response(
        monkeypatch, make_response("%PDF-1.7 ...", content_type="application/pdf")
    )

    assert fetch_body(URL, timeout=1.0) is None
    assert calls == [URL]


def test_fetch_body_returns_none_on_http_error(monkeypatch):
    patch_response(monkeypatch, make_response("서버 오류", status=500))

    assert fetch_body(URL, timeout=1.0) is None


@pytest.mark.parametrize(
    "exc",
    [
        httpx.TimeoutException("시간 초과"),
        httpx.ConnectError("연결 실패"),
    ],
)
def test_fetch_body_returns_none_on_transport_exception(monkeypatch, exc):
    def raise_exc(url):
        raise exc

    patch_http(monkeypatch, raise_exc)

    assert fetch_body(URL, timeout=1.0) is None


def test_fetch_body_truncates_long_body(monkeypatch):
    paragraphs = "".join(
        f"<p>문단 {i}. 이 문장은 본문 길이를 늘리기 위해 반복되는 충분히 긴 한국어 문장이다.</p>"
        for i in range(400)
    )
    patch_response(
        monkeypatch, make_response(f"<html><body><article>{paragraphs}</article></body></html>")
    )

    body = fetch_body(URL, timeout=1.0)

    assert body is not None
    assert len(body) == MAX_BODY_CHARS


# --- extract_articles ----------------------------------------------------


def test_extract_articles_keeps_failed_items(monkeypatch):
    ok_html = read_fixture("article.html")

    def handler(url):
        if url == "https://example.com/2":
            raise httpx.TimeoutException("시간 초과")
        return make_response(ok_html)

    patch_http(monkeypatch, handler)
    items = [make_item(f"https://example.com/{i}") for i in (1, 2, 3)]

    articles = extract_articles(items, timeout=1.0)

    assert [article.item for article in articles] == items
    assert articles[0].body is not None
    assert articles[1].body is None
    assert articles[2].body is not None


def test_extract_articles_does_not_promote_summary_hint(monkeypatch):
    patch_http(monkeypatch, lambda url: make_response("", status=404))
    item = make_item("https://github.com/acme/agent", summary_hint="An agent framework")

    articles = extract_articles([item], timeout=1.0)

    assert articles[0].body is None
