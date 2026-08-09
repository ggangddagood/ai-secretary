"""모든 소스가 공유하는 HTTP 클라이언트.

재시도하지 않는다 — 하루 1회 배치이므로 실패한 소스는 `collect_all`이 건너뛰면 충분하다.
"""

from __future__ import annotations

from typing import Final

import httpx

USER_AGENT: Final[str] = "ai-secretary/0.1"


def make_client(timeout: float) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
