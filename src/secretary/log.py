"""로깅 설정."""

from __future__ import annotations

import logging
import re
from typing import Final

LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# 요청 URL을 통째로 찍는 라이브러리들. 텔레그램 봇 토큰은 URL 경로에 들어가므로
# 이들의 INFO 로그를 그대로 두면 토큰이 평문으로 남는다. verbose에서도 올리지 않는다.
_URL_LOGGING_LIBRARIES: Final[tuple[str, ...]] = (
    "httpx",
    "httpcore",
    "urllib3",
    "google_genai",
    "google.genai",
)

# 텔레그램 봇 토큰 형태(`bot<숫자>:<영숫자>`).
_BOT_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}")


class SecretRedactingFilter(logging.Filter):
    """어느 로거가 남기든 토큰 형태 문자열을 마스킹한다.

    라이브러리 로그 레벨을 낮추는 것만으로는 부족하다 — 새 의존성이 늘거나
    누군가 레벨을 되돌리면 다시 새기 때문에, 출력 직전에 한 번 더 지운다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _BOT_TOKEN_RE.sub("bot***", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(verbose: bool = False) -> None:
    # force=True — basicConfig는 루트에 핸들러가 이미 있으면 조용히 무시된다.
    # 그러면 레벨도 필터도 적용되지 않아 토큰 마스킹이 통째로 빠진다.
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        force=True,
    )
    redactor = SecretRedactingFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redactor)
    for name in _URL_LOGGING_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)
