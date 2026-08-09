"""로깅 설정."""

from __future__ import annotations

import logging
from typing import Final

LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
    )
