"""Hacker News — Algolia Search API. 인증 불필요."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

import httpx

from ..http import make_client
from ..models import Item
from .base import dedupe_by_url, get_str, parse_iso8601

SEARCH_URL: Final[str] = "https://hn.algolia.com/api/v1/search"
ITEM_URL: Final[str] = "https://news.ycombinator.com/item?id={object_id}"

HN_QUERIES: Final[tuple[str, ...]] = (
    "AI",
    "LLM",
    "Claude",
    "GPT",
    "agent",
    "indie hacker",
    "SaaS revenue",
)
MIN_POINTS: Final[int] = 30


class HackerNewsSource:
    name = "hackernews"

    def fetch(self, *, since: datetime, timeout: float) -> list[Item]:
        since_epoch = int(since.timestamp())
        items: list[Item] = []
        with make_client(timeout) as client:
            # 프론트페이지는 "지금 화제인 것"이므로 시간 필터를 걸지 않는다.
            items.extend(_search(client, {"tags": "front_page"}))
            for query in HN_QUERIES:
                items.extend(
                    _search(
                        client,
                        {
                            "query": query,
                            "tags": "story",
                            "numericFilters": (f"created_at_i>{since_epoch},points>{MIN_POINTS}"),
                        },
                    )
                )
        return dedupe_by_url(items)


def _search(client: httpx.Client, params: dict[str, str]) -> list[Item]:
    response = client.get(SEARCH_URL, params=params)
    response.raise_for_status()
    hits = response.json().get("hits", [])
    return [item for item in (_to_item(hit) for hit in hits) if item is not None]


def _to_item(hit: dict[str, Any]) -> Item | None:
    title = get_str(hit, "title")
    object_id = get_str(hit, "objectID")
    if not title or not object_id:
        return None
    return Item(
        title=title,
        # Ask HN/Show HN처럼 외부 링크가 없는 글은 HN 퍼머링크를 쓴다.
        url=get_str(hit, "url") or ITEM_URL.format(object_id=object_id),
        source="hackernews",
        score=hit.get("points"),
        published_at=parse_iso8601(hit.get("created_at")),
        summary_hint=None,
    )
