import pytest

from secretary.config import REQUIRED_VARS, ConfigError, load_stocks_config, parse_watchlist

STOCKS_VARS = (
    "STOCKS_WATCHLIST_US",
    "STOCKS_WATCHLIST_KR",
    "STOCKS_MOVE_THRESHOLD",
    "HTTP_TIMEOUT",
)


@pytest.fixture
def clean_env(monkeypatch):
    """주식 파이프라인이 읽는 환경 변수를 모두 제거한 상태에서 시작한다."""
    for name in (*REQUIRED_VARS, *STOCKS_VARS):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def set_required(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("GEMINI_API_KEY", "api-key")


def test_parse_watchlist_reads_symbol_and_label():
    tickers = parse_watchlist("AAPL:애플,NVDA:엔비디아")

    assert [(t.symbol, t.label) for t in tickers] == [("AAPL", "애플"), ("NVDA", "엔비디아")]


def test_parse_watchlist_without_label_uses_symbol():
    (ticker,) = parse_watchlist("AAPL")

    assert ticker.symbol == "AAPL"
    assert ticker.label == "AAPL"


def test_parse_watchlist_splits_on_first_colon_only():
    (ticker,) = parse_watchlist("005930.KS:삼성전자:우선주")

    assert ticker.symbol == "005930.KS"
    assert ticker.label == "삼성전자:우선주"


def test_parse_watchlist_strips_spaces_and_skips_empty_entries():
    tickers = parse_watchlist(" AAPL : 애플 , , NVDA ")

    assert [(t.symbol, t.label) for t in tickers] == [("AAPL", "애플"), ("NVDA", "NVDA")]


def test_parse_watchlist_skips_entry_without_symbol():
    assert parse_watchlist(":애플") == ()


def test_parse_watchlist_empty_string_gives_empty_tuple():
    assert parse_watchlist("") == ()


def test_load_stocks_config_reads_only_the_requested_market(clean_env):
    set_required(clean_env)
    clean_env.setenv("STOCKS_WATCHLIST_US", "AAPL:애플")
    clean_env.setenv("STOCKS_WATCHLIST_KR", "005930.KS:삼성전자")

    config = load_stocks_config("us")

    assert config.market == "us"
    assert [t.symbol for t in config.watchlist] == ["AAPL"]


def test_unknown_market_raises(clean_env):
    set_required(clean_env)

    with pytest.raises(ConfigError) as excinfo:
        load_stocks_config("jp")

    assert "jp" in str(excinfo.value)


def test_missing_required_vars_raise_without_leaking_values(clean_env):
    clean_env.setenv("TELEGRAM_CHAT_ID", "super-secret-chat")

    with pytest.raises(ConfigError) as excinfo:
        load_stocks_config("us")

    message = str(excinfo.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "GEMINI_API_KEY" in message
    assert "super-secret-chat" not in message


def test_require_secrets_false_skips_validation(clean_env):
    config = load_stocks_config("kr", require_secrets=False)

    assert config.telegram_bot_token == ""
    assert config.gemini_api_key == ""
    assert config.watchlist == ()


def test_move_threshold_defaults_to_5(clean_env):
    set_required(clean_env)

    assert load_stocks_config("us").move_threshold == 5.0


def test_optional_vars_override_defaults(clean_env):
    set_required(clean_env)
    clean_env.setenv("STOCKS_MOVE_THRESHOLD", "3.5")
    clean_env.setenv("HTTP_TIMEOUT", "7.5")

    config = load_stocks_config("us")

    assert config.move_threshold == 3.5
    assert config.http_timeout == 7.5
