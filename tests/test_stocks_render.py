"""주식 브리핑 렌더링 테스트. 이스케이프·숫자 포맷·4096자 분할이 핵심이다."""

from datetime import date, datetime, timezone

from secretary.stocks.models import Headline, Quote, StockBrief, StockEntry, Ticker
from secretary.stocks.render import render_failure, render_stock_brief
from secretary.tghtml import TELEGRAM_LIMIT

GENERATED_AT = datetime(2026, 8, 19, 21, 0, tzinfo=timezone.utc)  # 8월 20일 06:00 KST
AS_OF = date(2026, 8, 19)


def make_quote(
    symbol: str = "AAPL",
    label: str = "애플",
    *,
    price: float = 226.34,
    change_pct: float = 1.2,
    currency: str = "USD",
) -> Quote:
    return Quote(
        ticker=Ticker(symbol, label),
        price=price,
        change_pct=change_pct,
        currency=currency,
        as_of=AS_OF,
    )


def make_headline(title: str = "Apple ships something", url: str = "https://news.example.com/1"):
    return Headline(title=title, url=url, published_at=datetime(2026, 8, 19, tzinfo=timezone.utc))


def make_entry(
    quote: Quote | None = None,
    *,
    headlines: list[Headline] | None = None,
    comment_ko: str | None = None,
) -> StockEntry:
    return StockEntry(
        quote=quote if quote is not None else make_quote(),
        headlines=headlines if headlines is not None else [],
        comment_ko=comment_ko,
    )


def make_brief(
    *,
    market: str = "us",
    as_of: date | None = AS_OF,
    is_holiday: bool = False,
    indices: list[Quote] | None = None,
    entries: list[StockEntry] | None = None,
) -> StockBrief:
    return StockBrief(
        market=market,
        generated_at=GENERATED_AT,
        as_of=as_of,
        is_holiday=is_holiday,
        indices=indices if indices is not None else [make_quote("^GSPC", "S&P 500", price=6466.58)],
        entries=entries if entries is not None else [make_entry()],
    )


def test_header_shows_market_label_and_as_of_date():
    (part,) = render_stock_brief(make_brief())

    header = part.split("\n\n")[0]
    assert "미국장" in header
    # 발송일은 KST 기준이다 — UTC로 찍으면 하루 전 날짜가 나온다.
    assert "8월 20일" in header
    assert "기준일 2026-08-19" in header
    assert "휴장" not in header


def test_holiday_is_marked_in_header():
    (part,) = render_stock_brief(make_brief(market="kr", is_holiday=True))

    header = part.split("\n\n")[0]
    assert "한국장" in header
    assert "휴장" in header


def test_header_omits_as_of_when_unknown():
    (part,) = render_stock_brief(make_brief(as_of=None, is_holiday=True))

    header = part.split("\n\n")[0]
    assert "기준일" not in header
    assert "휴장" not in header


def test_special_characters_in_labels_are_escaped():
    quote = make_quote("<TICK>", "A & B <주>")

    (part,) = render_stock_brief(make_brief(indices=[], entries=[make_entry(quote)]))

    assert "<주>" not in part
    assert "A &amp; B &lt;주&gt; (&lt;TICK&gt;)" in part


def test_headline_title_is_escaped_and_link_is_built():
    entry = make_entry(
        headlines=[make_headline("Q&A: <b>why</b>", "https://news.example.com/x?a=1&b=2")],
        comment_ko="신제품 발표가 있었다.",
    )

    (part,) = render_stock_brief(make_brief(entries=[entry]))

    assert 'href="https://news.example.com/x?a=1&amp;b=2"' in part
    assert "Q&amp;A: &lt;b&gt;why&lt;/b&gt;" in part
    assert "<b>why</b>" not in part


def test_empty_indices_and_entries_drop_their_blocks():
    (part,) = render_stock_brief(make_brief(indices=[], entries=[]))

    assert "지수" not in part
    assert "관심 종목" not in part
    assert "미국장" in part


def test_movers_block_is_omitted_when_no_ticker_has_news_or_comment():
    (part,) = render_stock_brief(make_brief(entries=[make_entry(), make_entry()]))

    assert "급등락" not in part


def test_entry_without_comment_shows_headlines_only():
    entry = make_entry(headlines=[make_headline("Apple ships something")], comment_ko=None)

    (part,) = render_stock_brief(make_brief(entries=[entry]))

    mover = part.split("🔎 급등락</b>\n")[1]
    assert mover.split("\n") == [
        "<b>애플</b>  ▲ +1.20%",
        '· <a href="https://news.example.com/1">Apple ships something</a>',
    ]


def test_long_brief_splits_below_the_limit():
    entries = [
        make_entry(
            make_quote(f"SYM{index}", f"종목 {index}"),
            headlines=[make_headline("가" * 200, f"https://news.example.com/{index}")] * 5,
            comment_ko="나" * 200,
        )
        for index in range(12)
    ]

    parts = render_stock_brief(make_brief(entries=entries))

    assert len(parts) >= 2
    assert all(len(part) <= TELEGRAM_LIMIT for part in parts)


def test_krw_prices_are_integers_and_usd_prices_keep_two_decimals():
    krw = make_entry(make_quote("005930.KS", "삼성전자", price=71800.0, currency="KRW"))
    usd = make_entry(make_quote("AAPL", "애플", price=226.34, currency="USD"))

    (part,) = render_stock_brief(make_brief(indices=[], entries=[krw, usd]))

    assert "삼성전자 (005930.KS)  71,800  " in part
    assert "애플 (AAPL)  226.34  " in part


def test_index_and_fx_keep_two_decimals_even_in_krw():
    indices = [
        make_quote("^KS11", "코스피", price=3210.4, currency="KRW"),
        make_quote("USDKRW=X", "원달러", price=1389.5, currency="KRW"),
    ]

    (part,) = render_stock_brief(make_brief(market="kr", indices=indices, entries=[]))

    assert "코스피  3,210.40  " in part
    assert "원달러  1,389.50  " in part


def test_change_sign_and_direction_marker_match():
    indices = [
        make_quote("^GSPC", "오름", change_pct=4.321),
        make_quote("^IXIC", "내림", change_pct=-1.1),
        make_quote("USDKRW=X", "보합", change_pct=0.0),
    ]

    (part,) = render_stock_brief(make_brief(indices=indices, entries=[]))

    assert "오름  226.34  ▲ +4.32%" in part
    assert "내림  226.34  ▼ -1.10%" in part
    assert "보합  226.34  – +0.00%" in part


def test_render_failure_escapes_reason():
    assert render_failure("kr", "시세 조회 <all> 실패 & 0건") == (
        "⚠️ 한국장 주가 브리핑을 만들지 못했습니다: 시세 조회 &lt;all&gt; 실패 &amp; 0건"
    )
