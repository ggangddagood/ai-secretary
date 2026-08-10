"""환경 변수 로딩과 검증.

이 모듈이 `os.environ`을 읽는 유일한 곳이다. 다른 모듈은 `Config`를 주입받아 쓴다.
에러 메시지에는 변수 이름만 담는다 — 값은 시크릿일 수 있으므로 절대 출력하지 않는다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REQUIRED_VARS: Final[tuple[str, ...]] = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GEMINI_API_KEY",
)

DEFAULT_BRIEF_ITEM_COUNT: Final[int] = 5
DEFAULT_STATE_PATH: Final[str] = "state/seen.json"
DEFAULT_HTTP_TIMEOUT: Final[float] = 20.0


class ConfigError(Exception):
    """환경 변수가 없거나 형식이 잘못됐을 때."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    gemini_api_key: str
    github_token: str | None
    brief_item_count: int
    state_path: Path
    http_timeout: float


def _get(name: str) -> str:
    return os.environ.get(name, "").strip()


def _int_env(name: str, default: int) -> int:
    raw = _get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name}: 정수로 읽을 수 없습니다") from None


def _float_env(name: str, default: float) -> float:
    raw = _get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name}: 실수로 읽을 수 없습니다") from None


def load_config(*, require_secrets: bool = True) -> Config:
    """환경 변수에서 설정을 읽는다.

    `require_secrets=False`이면 필수 변수 검사를 건너뛰고 빠진 값은 빈 문자열로 둔다.
    """
    if require_secrets:
        missing = [name for name in REQUIRED_VARS if not _get(name)]
        if missing:
            raise ConfigError("필수 환경 변수가 없습니다: " + ", ".join(missing))

    return Config(
        telegram_bot_token=_get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_get("TELEGRAM_CHAT_ID"),
        gemini_api_key=_get("GEMINI_API_KEY"),
        github_token=_get("GITHUB_TOKEN") or None,
        brief_item_count=_int_env("BRIEF_ITEM_COUNT", DEFAULT_BRIEF_ITEM_COUNT),
        state_path=Path(_get("STATE_PATH") or DEFAULT_STATE_PATH),
        http_timeout=_float_env("HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT),
    )
