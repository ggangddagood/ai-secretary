"""GitHub — Search API로 최근 생성된 AI 관련 저장소를 찾는다.

Trending 페이지 HTML을 긁지 않는다. 공식 API가 아니라 마크업이 바뀌면 그대로 깨진다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

import httpx

from ..http import make_client
from ..models import Item
from .base import clean_text, dedupe_by_url, get_str, parse_iso8601

SEARCH_URL: Final[str] = "https://api.github.com/search/repositories"

GITHUB_QUERIES: Final[tuple[str, ...]] = ("topic:ai", "topic:llm", "topic:agent")
PER_PAGE: Final[int] = 15


class GitHubSource:
    name = "github"

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    def fetch(self, *, since: datetime, timeout: float) -> list[Item]:
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        created_since = since.date().isoformat()
        items: list[Item] = []
        with make_client(timeout) as client:
            for query in GITHUB_QUERIES:
                items.extend(_search(client, query, created_since, headers))
        return dedupe_by_url(items)


def _search(
    client: httpx.Client, query: str, created_since: str, headers: dict[str, str]
) -> list[Item]:
    response = client.get(
        SEARCH_URL,
        headers=headers,
        params={
            "q": f"created:>{created_since} {query}",
            "sort": "stars",
            "order": "desc",
            "per_page": PER_PAGE,
        },
    )
    response.raise_for_status()
    repos = response.json().get("items", [])
    return [item for item in (_to_item(repo) for repo in repos) if item is not None]


def _to_item(repo: dict[str, Any]) -> Item | None:
    full_name = get_str(repo, "full_name")
    url = get_str(repo, "html_url")
    if not full_name or not url:
        return None
    description = clean_text(repo.get("description"))
    return Item(
        title=f"{full_name} — {description}" if description else full_name,
        url=url,
        source="github",
        score=repo.get("stargazers_count"),
        published_at=parse_iso8601(repo.get("created_at")),
        summary_hint=description,
    )
