"""수집 레이어 진입점.

여기서는 항목을 걸러내지 않는다 — 선별은 LLM 단계의 책임이다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Final

from ..config import Config
from ..models import Item
from .base import Source, dedupe_by_url, describe_error
from .geeknews import GeekNewsSource
from .github import GitHubSource
from .hackernews import HackerNewsSource
from .rss import RssSource

logger = logging.getLogger(__name__)

RECENT_WINDOW: Final[timedelta] = timedelta(hours=24)
GITHUB_WINDOW: Final[timedelta] = timedelta(days=7)


def build_sources(cfg: Config) -> list[tuple[Source, timedelta]]:
    """(소스, 조회 기간) 목록."""
    return [
        (HackerNewsSource(), RECENT_WINDOW),
        (GeekNewsSource(), RECENT_WINDOW),
        (GitHubSource(token=cfg.github_token), GITHUB_WINDOW),
        (RssSource(), RECENT_WINDOW),
    ]


def collect_all(cfg: Config, *, now: datetime) -> list[Item]:
    """모든 소스를 수집해 URL 중복을 제거하고 score 내림차순(None은 뒤)으로 반환한다.

    소스 하나가 실패해도 경고만 남기고 나머지 소스의 결과로 진행한다.
    """
    items: list[Item] = []
    for source, window in build_sources(cfg):
        try:
            fetched = source.fetch(since=now - window, timeout=cfg.http_timeout)
        except Exception as exc:
            logger.warning("소스 %s 수집 실패: %s", source.name, describe_error(exc))
            continue
        logger.info("소스 %s: %d건", source.name, len(fetched))
        items.extend(fetched)

    unique = dedupe_by_url(items)
    logger.info("수집 %d건 (중복 제거 전 %d건)", len(unique), len(items))
    return sorted(unique, key=lambda item: (item.score is None, -(item.score or 0)))
