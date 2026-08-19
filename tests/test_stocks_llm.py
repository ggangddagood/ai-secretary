"""급등락 해설 테스트. 실제 API를 호출하지 않는다 — 클라이언트를 가짜 객체로 대체한다."""

from datetime import date, datetime, timezone

from secretary.stocks.llm import CommentOut, CommentResult, explain_moves
from secretary.stocks.models import Headline, Quote, Ticker


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


def make_quote(symbol: str, label: str, *, change_pct: float = 7.5) -> Quote:
    return Quote(
        ticker=Ticker(symbol, label),
        price=100.0,
        change_pct=change_pct,
        currency="USD",
        as_of=date(2026, 8, 19),
    )


def make_headline(title: str) -> Headline:
    return Headline(
        title=title,
        url="https://news.example.com/1",
        published_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )


def test_ticker_without_headlines_is_not_sent_to_the_model():
    client = FakeClient(
        CommentResult(comments=[CommentOut(symbol="NVDA", comment_ko="신제품 발표가 있었다.")])
    )
    movers = [
        (make_quote("NVDA", "엔비디아"), [make_headline("Nvidia unveils new chip")]),
        (make_quote("TSLA", "테슬라"), []),
    ]

    comments = explain_moves(client, movers)

    assert comments == {"NVDA": "신제품 발표가 있었다."}
    sent = client.interactions.calls[0]["input"]
    assert "NVDA" in sent
    assert "TSLA" not in sent
    assert "테슬라" not in sent


def test_no_headlines_at_all_skips_the_call():
    client = FakeClient()
    movers = [(make_quote("NVDA", "엔비디아"), []), (make_quote("TSLA", "테슬라"), [])]

    assert explain_moves(client, movers) == {}
    assert client.interactions.calls == []


def test_comment_for_symbol_not_in_prompt_is_dropped(caplog):
    client = FakeClient(
        CommentResult(
            comments=[
                CommentOut(symbol="NVDA", comment_ko="신제품 발표가 있었다."),
                CommentOut(symbol="AAPL", comment_ko="지어낸 해설이다."),
            ]
        )
    )
    movers = [(make_quote("NVDA", "엔비디아"), [make_headline("Nvidia unveils new chip")])]

    comments = explain_moves(client, movers)

    assert comments == {"NVDA": "신제품 발표가 있었다."}
    assert "AAPL" in caplog.text


def test_returns_symbol_to_comment_mapping():
    client = FakeClient(
        CommentResult(
            comments=[
                CommentOut(symbol="NVDA", comment_ko="신제품 발표가 있었다."),
                CommentOut(symbol="005930.KS", comment_ko="실적 발표가 있었다."),
            ]
        )
    )
    movers = [
        (make_quote("NVDA", "엔비디아"), [make_headline("Nvidia unveils new chip")]),
        (make_quote("005930.KS", "삼성전자"), [make_headline("삼성전자 실적 발표")]),
    ]

    comments = explain_moves(client, movers)

    assert comments == {"NVDA": "신제품 발표가 있었다.", "005930.KS": "실적 발표가 있었다."}
    # 종목마다 호출하지 않는다 — 한 번에 묶는다.
    assert len(client.interactions.calls) == 1


def test_missing_ticker_in_response_leaves_the_rest_intact():
    client = FakeClient(
        CommentResult(comments=[CommentOut(symbol="NVDA", comment_ko="신제품 발표가 있었다.")])
    )
    movers = [
        (make_quote("NVDA", "엔비디아"), [make_headline("Nvidia unveils new chip")]),
        (make_quote("TSLA", "테슬라"), [make_headline("Tesla recalls cars")]),
    ]

    comments = explain_moves(client, movers)

    assert comments == {"NVDA": "신제품 발표가 있었다."}
