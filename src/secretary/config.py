"""환경 변수 로딩과 검증.

이 모듈이 `os.environ`을 읽는 유일한 곳이다. 다른 모듈은 `Config`를 주입받아 쓴다.
에러 메시지에는 변수 이름만 담는다 — 값은 시크릿일 수 있으므로 절대 출력하지 않는다.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .stocks.models import MARKETS, Ticker

logger = logging.getLogger(__name__)

REQUIRED_VARS: Final[tuple[str, ...]] = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GEMINI_API_KEY",
)

DEFAULT_BRIEF_ITEM_COUNT: Final[int] = 5
DEFAULT_STATE_PATH: Final[str] = "state/seen.json"
DEFAULT_HTTP_TIMEOUT: Final[float] = 20.0
DEFAULT_MOVE_THRESHOLD: Final[float] = 5.0


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


@dataclass(frozen=True)
class StocksConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    gemini_api_key: str
    market: str
    watchlist: tuple[Ticker, ...]
    move_threshold: float
    http_timeout: float


def parse_watchlist(raw: str) -> tuple[Ticker, ...]:
    """`심볼:표시명` 쉼표 목록을 파싱한다.

    표시명에 콜론이 들어갈 수 있으므로 첫 콜론에서만 나눈다.
    심볼이 없는 항목은 건너뛴다 — 표시명만으로는 시세를 조회할 수 없다.
    """
    tickers: list[Ticker] = []
    for chunk in raw.split(","):
        entry = chunk.strip()
        if not entry:
            continue
        symbol, _, label = entry.partition(":")
        symbol = symbol.strip()
        label = label.strip()
        if not symbol:
            logger.warning("관심 종목 항목에 심볼이 없어 건너뜁니다")
            continue
        tickers.append(Ticker(symbol=symbol, label=label or symbol))
    return tuple(tickers)


def load_stocks_config(market: str, *, require_secrets: bool = True) -> StocksConfig:
    """주식 브리핑 설정을 읽는다.

    관심 종목은 시장별 환경 변수(`STOCKS_WATCHLIST_US` / `STOCKS_WATCHLIST_KR`)로만 들어온다 —
    리포지토리가 공개이므로 코드에 기본값을 두지 않는다.
    """
    if market not in MARKETS:
        raise ConfigError(f"지원하지 않는 시장입니다: {market}")

    if require_secrets:
        missing = [name for name in REQUIRED_VARS if not _get(name)]
        if missing:
            raise ConfigError("필수 환경 변수가 없습니다: " + ", ".join(missing))

    return StocksConfig(
        telegram_bot_token=_get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_get("TELEGRAM_CHAT_ID"),
        gemini_api_key=_get("GEMINI_API_KEY"),
        market=market,
        watchlist=parse_watchlist(_get(f"STOCKS_WATCHLIST_{market.upper()}")),
        move_threshold=_float_env("STOCKS_MOVE_THRESHOLD", DEFAULT_MOVE_THRESHOLD),
        http_timeout=_float_env("HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT),
    )
