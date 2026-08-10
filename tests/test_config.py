from pathlib import Path

import pytest

from secretary.config import REQUIRED_VARS, Config, ConfigError, load_config

OPTIONAL_VARS = ("GITHUB_TOKEN", "BRIEF_ITEM_COUNT", "STATE_PATH", "HTTP_TIMEOUT")


@pytest.fixture
def clean_env(monkeypatch):
    """이 프로젝트가 읽는 환경 변수를 모두 제거한 상태에서 시작한다."""
    for name in (*REQUIRED_VARS, *OPTIONAL_VARS):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def set_required(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("GEMINI_API_KEY", "api-key")


def test_load_config_with_required_vars(clean_env):
    set_required(clean_env)

    config = load_config()

    assert isinstance(config, Config)
    assert config.telegram_bot_token == "bot-token"
    assert config.telegram_chat_id == "12345"
    assert config.gemini_api_key == "api-key"
    assert config.github_token is None
    assert config.state_path == Path("state/seen.json")
    assert config.http_timeout == 20.0


def test_missing_required_vars_are_all_reported(clean_env):
    clean_env.setenv("TELEGRAM_CHAT_ID", "12345")

    with pytest.raises(ConfigError) as excinfo:
        load_config()

    message = str(excinfo.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "GEMINI_API_KEY" in message
    assert "TELEGRAM_CHAT_ID" not in message


def test_error_message_does_not_leak_values(clean_env):
    clean_env.setenv("TELEGRAM_CHAT_ID", "super-secret-chat")

    with pytest.raises(ConfigError) as excinfo:
        load_config()

    assert "super-secret-chat" not in str(excinfo.value)


def test_brief_item_count_defaults_to_5(clean_env):
    set_required(clean_env)

    assert load_config().brief_item_count == 5


def test_optional_vars_override_defaults(clean_env):
    set_required(clean_env)
    clean_env.setenv("GITHUB_TOKEN", "gh-token")
    clean_env.setenv("BRIEF_ITEM_COUNT", "3")
    clean_env.setenv("STATE_PATH", "tmp/seen.json")
    clean_env.setenv("HTTP_TIMEOUT", "5.5")

    config = load_config()

    assert config.github_token == "gh-token"
    assert config.brief_item_count == 3
    assert config.state_path == Path("tmp/seen.json")
    assert config.http_timeout == 5.5


def test_require_secrets_false_skips_validation(clean_env):
    config = load_config(require_secrets=False)

    assert config.telegram_bot_token == ""
    assert config.telegram_chat_id == ""
    assert config.gemini_api_key == ""
    assert config.brief_item_count == 5


def test_non_numeric_brief_item_count_raises(clean_env):
    set_required(clean_env)
    clean_env.setenv("BRIEF_ITEM_COUNT", "many")

    with pytest.raises(ConfigError) as excinfo:
        load_config()

    assert "BRIEF_ITEM_COUNT" in str(excinfo.value)
    assert "many" not in str(excinfo.value)
