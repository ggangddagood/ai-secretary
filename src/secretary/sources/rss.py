"""지정된 RSS/Atom 피드 목록.

피드 URL은 모두 실제 요청으로 HTTP 200 + 파싱 가능을 확인한 것만 남긴다.
제외한 후보와 사유는 docs/tracking/FINDINGS.md에 기록한다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Final

from ..http import make_client
from ..models import Item
from .base import describe_error, parse_feed

logger = logging.getLogger(__name__)

RSS_FEEDS: Final[list[tuple[str, str]]] = [
    ("Simon Willison", "https://simonwillison.net/atom/everything/"),
    ("Latent Space", "https://www.latent.space/feed"),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
    ("Google AI Blog", "https://blog.google/technology/ai/rss/"),
    ("Show HN", "https://hnrss.org/show"),
    ("Lenny's Newsletter", "https://www.lennysnewsletter.com/feed"),
]


class RssSource:
    name = "rss"

    def fetch(self, *, since: datetime, timeout: float) -> list[Item]:
        items: list[Item] = []
        with make_client(timeout) as client:
            for display, url in RSS_FEEDS:
                try:
                    response = client.get(url)
                    response.raise_for_status()
                except Exception as exc:  # 피드 하나가 죽어도 나머지는 읽는다
                    logger.warning("RSS 피드 %s 실패: %s", display, describe_error(exc))
                    continue
                items.extend(parse_feed(response.content, source=f"rss:{display}", since=since))
        return items
