"""주식 파이프라인 배선 테스트. 네트워크·LLM 호출을 전부 가짜로 바꾼다.

여기서 지키는 것은 순서와 실패 정책이다 — 특히 "LLM이 실패해도 시세는 발송한다"와
"헤드라인이 없는 종목에는 해설을 붙이지 않는다".
"""

from datetime import date, datetime, timezone

import pytest

from secretary.config import StocksConfig
from secretary.stocks import main as main_module
from secretary.stocks.models import Headline, Quote, Ticker
from secretary.telegram import TelegramError

APPLE = Ticker("AAPL", "애플")
NOW = datetime(2026, 8, 19, 21, 0, tzinfo=timezone.utc)


def make_config(**overrides) -> StocksConfig:
    values = {
        "telegram_bot_token": "token",
        "telegram_chat_id": "99",
        "gemini_api_key": "key",
        "market": "us",
        "watchlist": (APPLE,),
        "move_threshold": 5.0,
        "http_timeout": 1.0,
    }
    values.update(overrides)
    return StocksConfig(**values)


def make_quote(ticker: Ticker, change_pct: float = 1.0) -> Quote:
    return Quote(
        ticker=ticker,
        price=100.0,
        change_pct=change_pct,
        currency="USD",
        as_of=date(2026, 8, 19),
    )


def make_headline() -> Headline:
    return Headline(title="Apple ships something", url="https://example.com/a", published_at=NOW)


def patch_pipeline(
    monkeypatch,
    cfg,
    *,
    change_pct=1.0,
    quotes_fail=False,
    headlines=None,
    explain=None,
    send=None,
):
    """파이프라인 각 단계를 가짜로 대체하고 호출 순서를 기록한다."""
    calls: list[str] = []
    sent: list[list[str]] = []

    def fake_fetch_quotes(tickers, *, timeout):
        calls.append("quotes")
        if quotes_fail:
            return []
        return [make_quote(ticker, change_pct) for ticker in tickers]

    def fake_fetch_headlines_for(tickers, *, market, now, timeout):
        calls.append("news")
        found = [make_headline()] if headlines is None else headlines
        return {ticker.symbol: list(found) for ticker in tickers}

    def fake_explain_moves(client, movers):
        calls.append("explain")
        if explain is not None:
            return explain(movers)
        return {quote.ticker.symbol: "해설이다." for quote, _ in movers}

    def fake_send(config, messages):
        calls.append("send")
        sent.append(messages)
        if send is not None:
            send(messages)

    monkeypatch.setattr(
        main_module, "load_stocks_config", lambda market, *, require_secrets=True: cfg
    )
    monkeypatch.setattr(main_module, "make_client", lambda api_key: object())
    monkeypatch.setattr(main_module, "fetch_quotes", fake_fetch_quotes)
    monkeypatch.setattr(main_module, "fetch_headlines_for", fake_fetch_headlines_for)
    monkeypatch.setattr(main_module, "explain_moves", fake_explain_moves)
    monkeypatch.setattr(main_module, "send_messages", fake_send)
    return calls, sent


def test_sends_the_brief_and_exits_zero(monkeypatch):
    cfg = make_config()
    calls, sent = patch_pipeline(monkeypatch, cfg)

    assert main_module.run(["--market", "us"]) == 0

    assert calls == ["quotes", "quotes", "send"]
    assert "애플" in sent[0][0]


def test_dry_run_skips_telegram(monkeypatch, capsys):
    cfg = make_config()
    calls, _ = patch_pipeline(monkeypatch, cfg)

    assert main_module.run(["--market", "us", "--dry-run"]) == 0

    assert "send" not in calls
    assert "애플" in capsys.readouterr().out


def test_all_quotes_failed_sends_failure_notice_and_fails(monkeypatch):
    cfg = make_config()
    calls, sent = patch_pipeline(monkeypatch, cfg, quotes_fail=True)

    assert main_module.run(["--market", "us"]) == 1

    assert calls == ["quotes", "quotes", "send"]
    assert "주가 브리핑을 만들지 못했습니다" in sent[0][0]


def test_empty_watchlist_still_sends_indices(monkeypatch):
    cfg = make_config(watchlist=())
    calls, sent = patch_pipeline(monkeypatch, cfg)

    # 관심 종목이 없는 것은 실패가 아니다 — 지수만으로 브리핑이 성립한다.
    assert main_module.run(["--market", "us"]) == 0

    assert "send" in calls
    # 지수 이름의 `&`는 렌더러가 이스케이프한다.
    assert "S&amp;P 500" in sent[0][0]


def test_llm_failure_still_sends_the_quotes(monkeypatch):
    cfg = make_config()

    def boom(movers):
        raise RuntimeError("모델 응답을 읽지 못했습니다")

    calls, sent = patch_pipeline(monkeypatch, cfg, change_pct=9.0, explain=boom)

    # 시세가 본체다 — 해설만 빠지고 발송은 그대로 일어난다.
    assert main_module.run(["--market", "us"]) == 0

    assert calls == ["quotes", "quotes", "news", "explain", "send"]
    assert "해설이다." not in sent[0][0]
    assert "Apple ships something" in sent[0][0]


def test_no_movers_skips_news_and_llm(monkeypatch):
    cfg = make_config()
    calls, _ = patch_pipeline(monkeypatch, cfg, change_pct=1.0)

    assert main_module.run(["--market", "us"]) == 0

    assert "news" not in calls
    assert "explain" not in calls


def test_send_failure_does_not_send_a_failure_notice(monkeypatch):
    cfg = make_config()

    def boom(messages):
        raise TelegramError("1/1 발송 실패: HTTP 400")

    calls, _ = patch_pipeline(monkeypatch, cfg, send=boom)

    assert main_module.run(["--market", "us"]) == 1

    # 같은 채널이 죽었으므로 실패 알림을 재발송하지 않는다.
    assert calls.count("send") == 1


def test_market_is_required():
    with pytest.raises(SystemExit) as excinfo:
        main_module.run([])
    assert excinfo.value.code == 2


def test_unknown_market_is_rejected():
    with pytest.raises(SystemExit) as excinfo:
        main_module.run(["--market", "jp"])
    assert excinfo.value.code == 2


def test_entry_without_headlines_gets_no_comment(monkeypatch):
    cfg = make_config()
    # 헤드라인은 0건인데 모델이 해설을 돌려준 상황을 만든다.
    patch_pipeline(
        monkeypatch,
        cfg,
        change_pct=9.0,
        headlines=[],
        explain=lambda movers: {APPLE.symbol: "근거 없는 해설이다."},
    )

    brief = main_module.build_stock_brief(cfg, object(), now=NOW)

    entry = next(e for e in brief.entries if e.quote.ticker.symbol == APPLE.symbol)
    assert entry.headlines == []
    assert entry.comment_ko is None
