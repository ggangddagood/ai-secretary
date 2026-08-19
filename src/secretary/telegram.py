"""텔레그램 발송.

sendMessage 하나만 쓰므로 봇 프레임워크를 들이지 않는다.
요청 URL에 봇 토큰이 들어 있다 — 로그와 예외 메시지에 URL을 그대로 남기지 않는다.
"""

from __future__ import annotations

import logging
from typing import Final, Protocol

import httpx

from .http import make_client
from .sources.base import describe_error

logger = logging.getLogger(__name__)

API_BASE: Final[str] = "https://api.telegram.org"
MASKED_URL: Final[str] = f"{API_BASE}/bot***/sendMessage"


class TelegramTarget(Protocol):
    """발송에 필요한 설정만 요구한다 — `Config`와 `StocksConfig`가 모두 만족한다."""

    telegram_bot_token: str
    telegram_chat_id: str
    http_timeout: float


class TelegramError(Exception):
    """발송 실패. 메시지에 봇 토큰이 들어가지 않는다."""


def _mask(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def _failure(response: httpx.Response) -> str | None:
    """실패 사유를 돌려준다. 성공이면 None.

    HTTP 200이어도 `ok: false`면 발송되지 않은 것이다.
    """
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("ok") is True:
        return None
    description = payload.get("description") if isinstance(payload, dict) else None
    return f"HTTP {response.status_code}: {description or '응답을 읽지 못했습니다'}"


def send_messages(cfg: TelegramTarget, messages: list[str]) -> None:
    """메시지를 순서대로 발송한다. 하나라도 실패하면 예외를 올린다.

    중간에 실패해도 성공으로 처리하지 않는다 — 발송 기록이 갱신되면 실패한 항목이
    다음 실행에서도 후보로 잡히지 않아 영영 유실된다.
    """
    url = f"{API_BASE}/bot{cfg.telegram_bot_token}/sendMessage"
    total = len(messages)
    with make_client(cfg.http_timeout) as client:
        for index, message in enumerate(messages, start=1):
            logger.info("텔레그램 발송 %d/%d → %s", index, total, MASKED_URL)
            try:
                response = client.post(
                    url,
                    json={
                        "chat_id": cfg.telegram_chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
            except httpx.HTTPError as exc:
                # httpx 예외 메시지에는 요청 URL(=토큰)이 담긴다. 원인 예외도 잇지 않는다.
                raise TelegramError(
                    _mask(
                        f"{index}/{total} 발송 실패: {describe_error(exc)}",
                        cfg.telegram_bot_token,
                    )
                ) from None

            reason = _failure(response)
            if reason is not None:
                raise TelegramError(
                    _mask(f"{index}/{total} 발송 실패: {reason}", cfg.telegram_bot_token)
                )
