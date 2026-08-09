"""파이프라인이 주고받는 데이터 구조.

수집(Item) → 본문 추출(Article) → 브리핑(BriefEntry, Brief) 순으로 흐른다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

AXES: Final[tuple[str, ...]] = ("tech", "money", "enterprise", "marketing")


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    source: str  # "hackernews" | "geeknews" | "github" | "rss:<name>"
    score: int | None  # 소스별 인기 지표 (없으면 None)
    published_at: datetime | None
    summary_hint: str | None  # RSS description 등 소스가 제공한 짧은 설명


@dataclass(frozen=True)
class Article:
    item: Item
    body: str | None  # 본문 추출 실패 시 None


@dataclass(frozen=True)
class BriefEntry:
    title: str  # 원문 제목(원어 유지)
    subtitle_ko: str  # 한국어 한 줄 부제
    url: str
    source: str
    axis: str  # AXES 중 하나
    summary_ko: list[str]  # 3줄. 본문 없으면 빈 리스트
    action_hint_ko: str | None  # 본문 없으면 None


@dataclass(frozen=True)
class Brief:
    generated_at: datetime
    entries: list[BriefEntry]
