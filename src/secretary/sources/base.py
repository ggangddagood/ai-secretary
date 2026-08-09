"""소스 공통 인터페이스와 파싱 헬퍼."""

from __future__ import annotations

import calendar
import html
import logging
import re
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any, Final, Protocol

import feedparser

from ..models import Item

logger = logging.getLogger(__name__)

# summary_hint는 이후 LLM 프롬프트에 그대로 들어가므로 장문을 남기지 않는다.
MAX_HINT_CHARS: Final[int] = 500

_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]+>")
_WS_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


class Source(Protocol):
    name: str

    def fetch(self, *, since: datetime, timeout: float) -> list[Item]: ...


def parse_iso8601(raw: str | None) -> datetime | None:
    """`2026-08-09T13:56:41.000Z` 형식을 aware datetime으로. 읽을 수 없으면 None."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def from_struct_time(value: time.struct_time | None) -> datetime | None:
    """feedparser의 `*_parsed`(UTC struct_time)를 aware datetime으로."""
    if value is None:
        return None
    return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)


def clean_text(raw: str | None) -> str | None:
    """HTML 태그·엔티티를 걷어내고 공백을 정리한 뒤 길이를 제한한다."""
    if not raw:
        return None
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", raw))).strip()
    return text[:MAX_HINT_CHARS] or None


def dedupe_by_url(items: Iterable[Item]) -> list[Item]:
    """URL이 같은 항목은 먼저 나온 것만 남긴다."""
    seen: set[str] = set()
    unique: list[Item] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def parse_feed(body: bytes, *, source: str, since: datetime) -> list[Item]:
    """RSS/Atom 본문을 Item 목록으로 바꾼다.

    발행 시각을 읽을 수 없는 항목은 최신 여부를 판단할 수 없으므로 제외한다.
    """
    feed = feedparser.parse(body)
    if feed.bozo:
        # feedparser는 피드가 아닌 응답(예: HTML 에러 페이지)에도 예외 대신 빈 결과를 준다.
        logger.warning("피드 %s 파싱 경고: %s", source, feed.get("bozo_exception"))

    items: list[Item] = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue
        published_at = from_struct_time(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )
        if published_at is None or published_at < since:
            continue
        items.append(
            Item(
                title=title,
                url=url,
                source=source,
                score=None,
                published_at=published_at,
                summary_hint=clean_text(entry.get("summary")),
            )
        )
    return items


def describe_error(exc: BaseException) -> str:
    """로그용 짧은 실패 사유. 예외 타입과 메시지만 남긴다."""
    return f"{type(exc).__name__}: {exc}"


def get_str(payload: dict[str, Any], key: str) -> str:
    return (payload.get(key) or "").strip()
