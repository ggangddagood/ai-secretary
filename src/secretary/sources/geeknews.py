"""GeekNews — Atom 피드. 인증 불필요."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ..http import make_client
from ..models import Item
from .base import parse_feed

FEED_URL: Final[str] = "https://news.hada.io/rss/news"


class GeekNewsSource:
    name = "geeknews"

    def fetch(self, *, since: datetime, timeout: float) -> list[Item]:
        with make_client(timeout) as client:
            response = client.get(FEED_URL)
            response.raise_for_status()
            body = response.content
        return parse_feed(body, source=self.name, since=since)
