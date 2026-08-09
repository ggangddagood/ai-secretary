"""발송 기록(seen store).

이미 보낸 항목을 다시 보내지 않기 위해 URL 키를 JSON 파일 하나에 남긴다.
텔레그램 발송이 성공한 뒤에만 갱신한다 — 발송 실패 시 기록이 남지 않아야 다음 실행에서 재시도된다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Item

logger = logging.getLogger(__name__)

VERSION: Final[int] = 1
DEFAULT_KEEP_DAYS: Final[int] = 90

# 같은 글이 소스마다 다른 추적 파라미터를 달고 오므로 키 계산에서 뺀다.
TRACKING_PREFIXES: Final[tuple[str, ...]] = ("utm_",)
TRACKING_PARAMS: Final[frozenset[str]] = frozenset({"ref", "fbclid", "gclid"})


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PREFIXES)


def normalize_url(url: str) -> str:
    """같은 글을 다르게 보이게 하는 요소(스킴, www, 말미 /, 추적 파라미터, 프래그먼트)를 없앤다."""
    stripped = url.strip()
    split = urlsplit(stripped)
    if not split.netloc:
        # 호스트를 읽을 수 없는 값은 정규화할 근거가 없다 — 원문 그대로 키를 만든다.
        return stripped

    host = split.netloc.lower().removeprefix("www.")
    path = split.path.rstrip("/")
    params = [
        pair for pair in parse_qsl(split.query, keep_blank_values=True) if not _is_tracking(pair[0])
    ]
    return urlunsplit(("https", host, path, urlencode(sorted(params)), ""))


def url_key(url: str) -> str:
    """정규화된 URL의 sha1. 기록 파일이 원문 URL 목록으로 읽히지 않게 해시로 저장한다."""
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()


def _parse_entries(raw: object) -> dict[str, str] | None:
    """저장된 seen 맵을 검증한다. 형식이 어긋나면 None."""
    if not isinstance(raw, dict):
        return None
    entries: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None
        try:
            date.fromisoformat(value)
        except ValueError:
            return None
        entries[key] = value
    return entries


def load_seen(path: Path) -> dict[str, str]:
    """발송 기록을 읽는다. 파일이 없거나 깨졌으면 경고 후 빈 기록으로 시작한다."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        logger.warning("발송 기록 %s 읽기 실패: %s — 빈 기록으로 진행", path, exc)
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("발송 기록 %s 파싱 실패: %s — 빈 기록으로 진행", path, exc)
        return {}

    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        logger.warning("발송 기록 %s 형식이 맞지 않습니다 — 빈 기록으로 진행", path)
        return {}

    entries = _parse_entries(payload.get("seen"))
    if entries is None:
        logger.warning("발송 기록 %s 내용이 깨졌습니다 — 빈 기록으로 진행", path)
        return {}
    return entries


def save_seen(path: Path, seen: dict[str, str]) -> None:
    """발송 기록을 저장한다. 임시 파일에 쓴 뒤 rename해 중간에 죽어도 파일이 깨지지 않게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": VERSION, "seen": dict(sorted(seen.items()))}
    tmp = path.parent / f"{path.name}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def filter_unseen(items: list[Item], seen: dict[str, str]) -> list[Item]:
    """이미 발송한 항목을 후보에서 뺀다."""
    return [item for item in items if url_key(item.url) not in seen]


def mark_seen(seen: dict[str, str], items: Iterable[Item], *, today: date) -> dict[str, str]:
    """항목들을 발송 기록에 추가한 새 dict를 반환한다(입력은 변형하지 않는다)."""
    updated = dict(seen)
    stamp = today.isoformat()
    for item in items:
        updated[url_key(item.url)] = stamp
    return updated


def prune(
    seen: dict[str, str], *, today: date, keep_days: int = DEFAULT_KEEP_DAYS
) -> dict[str, str]:
    """`keep_days`보다 오래된 기록을 지운 새 dict를 반환한다."""
    cutoff = today - timedelta(days=keep_days)
    return {key: value for key, value in seen.items() if date.fromisoformat(value) >= cutoff}
