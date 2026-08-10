"""선별·요약 테스트. 실제 API를 호출하지 않는다 — 클라이언트를 가짜 객체로 대체한다."""

from datetime import datetime, timezone

from secretary.llm import (
    Selection,
    SelectionResult,
    SummaryOut,
    SummaryResult,
    curate,
    summarize,
)
from secretary.models import Article, Item


class FakeInteraction:
    def __init__(self, output_text):
        self.output_text = output_text
        self.status = "completed"


class FakeInteractions:
    def __init__(self, outputs):
        # Gemini는 구조화 출력을 JSON 텍스트로 돌려준다 — 파싱까지 포함해 흉내 낸다.
        self._outputs = [output.model_dump_json() for output in outputs]
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeInteraction(self._outputs.pop(0))


class FakeClient:
    """`client.interactions.create(...)`만 흉내 낸다."""

    def __init__(self, *outputs):
        self.interactions = FakeInteractions(outputs)


def make_item(url: str, *, title: str = "제목", score: int | None = None) -> Item:
    return Item(
        title=title,
        url=url,
        source="hackernews",
        score=score,
        published_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        summary_hint=None,
    )


def make_selection(url: str, *, axis: str = "tech") -> Selection:
    return Selection(url=url, axis=axis, reason_ko="쓸모 있다")


def make_summary(url: str) -> SummaryOut:
    return SummaryOut(
        url=url,
        subtitle_ko="한국어 부제",
        summary_ko=["첫째 줄이다.", "둘째 줄이다.", "셋째 줄이다."],
        action_hint_ko="내일 이렇게 써먹어라.",
    )


# --- curate --------------------------------------------------------------


def test_curate_drops_urls_missing_from_candidates():
    candidates = [make_item("https://example.com/1"), make_item("https://example.com/2")]
    client = FakeClient(
        SelectionResult(
            selections=[
                make_selection("https://example.com/1"),
                make_selection("https://hallucinated.example.com/x"),
            ]
        )
    )

    selections = curate(client, candidates, count=5)

    assert [selection.url for selection in selections] == ["https://example.com/1"]


def test_curate_truncates_to_count():
    candidates = [make_item(f"https://example.com/{i}") for i in range(6)]
    client = FakeClient(
        SelectionResult(selections=[make_selection(item.url) for item in candidates])
    )

    selections = curate(client, candidates, count=5)

    assert len(selections) == 5
    assert [selection.url for selection in selections] == [
        f"https://example.com/{i}" for i in range(5)
    ]


# --- summarize -----------------------------------------------------------


def test_summarize_excludes_body_less_items_from_the_llm_payload():
    with_body = Article(item=make_item("https://example.com/ok"), body="본문이 있는 글이다." * 30)
    without_body = Article(item=make_item("https://example.com/paywalled"), body=None)
    client = FakeClient(SummaryResult(summaries=[make_summary(with_body.item.url)]))

    summarize(
        client,
        [with_body, without_body],
        [make_selection(with_body.item.url), make_selection(without_body.item.url)],
    )

    assert len(client.interactions.calls) == 1
    payload = client.interactions.calls[0]["input"]
    assert "https://example.com/ok" in payload
    assert "https://example.com/paywalled" not in payload


def test_summarize_leaves_body_less_items_without_summary():
    without_body = Article(item=make_item("https://example.com/paywalled"), body=None)
    client = FakeClient()

    entries = summarize(client, [without_body], [make_selection(without_body.item.url)])

    assert client.interactions.calls == []
    assert entries[0].summary_ko == []
    assert entries[0].action_hint_ko is None
    assert entries[0].subtitle_ko == ""
    assert entries[0].title == "제목"
    assert entries[0].url == "https://example.com/paywalled"


def test_summarize_assembles_remaining_entries_when_llm_omits_a_url():
    first = Article(item=make_item("https://example.com/1"), body="본문 하나." * 40)
    second = Article(item=make_item("https://example.com/2"), body="본문 둘." * 40)
    client = FakeClient(SummaryResult(summaries=[make_summary(second.item.url)]))

    entries = summarize(
        client,
        [first, second],
        [make_selection(first.item.url), make_selection(second.item.url, axis="money")],
    )

    assert [entry.url for entry in entries] == [first.item.url, second.item.url]
    assert entries[0].summary_ko == []
    assert entries[0].action_hint_ko is None
    assert entries[1].summary_ko == ["첫째 줄이다.", "둘째 줄이다.", "셋째 줄이다."]
    assert entries[1].axis == "money"
