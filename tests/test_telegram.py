"""발송 테스트. 네트워크를 타지 않는다 — HTTP 계층을 가짜 클라이언트로 대체한다."""

import logging
from pathlib import Path

import httpx
import pytest

from secretary import telegram as telegram_module
from secretary.config import Config
from secretary.telegram import TelegramError, send_messages

TOKEN = "1234567890:AAHsuperSecretBotToken"

URL = "https://api.telegram.org/bot{token}/sendMessage"


def make_config() -> Config:
    return Config(
        telegram_bot_token=TOKEN,
        telegram_chat_id="99",
        gemini_api_key="key",
        github_token=None,
        brief_item_count=5,
        state_path=Path("state/seen.json"),
        http_timeout=1.0,
    )


def make_response(payload: dict, *, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("POST", URL.format(token=TOKEN)),
    )


def patch_http(monkeypatch, handler):
    """`make_client`를 대체한다. handler(url, json)이 응답을 주거나 예외를 던진다."""

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, url, **kwargs):
            calls.append((url, kwargs.get("json")))
            return handler(url, kwargs.get("json"))

    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(telegram_module, "make_client", lambda timeout: FakeClient())
    return calls


def test_sends_each_message_in_order_as_html(monkeypatch):
    calls = patch_http(monkeypatch, lambda url, json: make_response({"ok": True}))

    send_messages(make_config(), ["첫 번째", "두 번째"])

    assert [json["text"] for _, json in calls] == ["첫 번째", "두 번째"]
    assert all(json["parse_mode"] == "HTML" for _, json in calls)
    assert all(json["disable_web_page_preview"] is True for _, json in calls)
    assert all(json["chat_id"] == "99" for _, json in calls)


def test_ok_false_raises_even_on_http_200(monkeypatch):
    payload = {"ok": False, "description": "Bad Request: can't parse entities"}
    calls = patch_http(monkeypatch, lambda url, json: make_response(payload))

    with pytest.raises(TelegramError) as excinfo:
        send_messages(make_config(), ["첫 번째", "두 번째"])

    assert "can't parse entities" in str(excinfo.value)
    # 첫 건에서 멈춘다 — 실패를 삼키고 다음 건을 보내지 않는다.
    assert len(calls) == 1


def test_bot_token_never_appears_in_errors_or_logs(monkeypatch, caplog):
    def boom(url, json):
        # httpx 예외 메시지에는 요청 URL(=토큰)이 그대로 담긴다.
        raise httpx.ConnectError(f"connection failed for {url}")

    patch_http(monkeypatch, boom)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(TelegramError) as excinfo:
        send_messages(make_config(), ["첫 번째"])

    assert TOKEN not in str(excinfo.value)
    assert "***" in str(excinfo.value)
    assert TOKEN not in caplog.text


def test_non_json_response_raises(monkeypatch):
    response = httpx.Response(
        502,
        text="<html>bad gateway</html>",
        request=httpx.Request("POST", URL.format(token=TOKEN)),
    )
    patch_http(monkeypatch, lambda url, json: response)

    with pytest.raises(TelegramError) as excinfo:
        send_messages(make_config(), ["첫 번째"])

    assert "502" in str(excinfo.value)
