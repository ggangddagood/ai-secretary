"""텔레그램 메시지 렌더링 공용 — 이스케이프·길이 제한·4096자 분할.

포맷은 `parse_mode=HTML`이다. 도메인과 무관한 부분만 여기 둔다 — 브리핑 레이아웃은
각 파이프라인의 렌더러가 갖는다.

`KST`가 여기 있는 이유: 발송 시각이 KST라서 UTC 기준으로 날짜를 찍으면 하루 전 날짜가 나온다.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Final

TELEGRAM_LIMIT: Final[int] = 4096

# 발송 시각이 08:00 KST이므로 UTC 기준으로 날짜를 찍으면 하루 전 날짜가 나온다.
KST: Final[timezone] = timezone(timedelta(hours=9))

ELLIPSIS: Final[str] = "…"
# 한 줄이 단독으로 한도를 넘으면 태그를 살린 채 자를 수 없다. 조각마다 상한을 둔다.
MAX_FIELD_CHARS: Final[int] = 600


def escape(text: str) -> str:
    """텔레그램 HTML에서 특별한 의미를 갖는 세 글자만 이스케이프한다."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attr(value: str) -> str:
    """href 속성값 — 따옴표까지 막아야 속성이 중간에 닫히지 않는다."""
    return escape(value).replace('"', "&quot;")


def text(raw: str) -> str:
    """메시지에 넣을 텍스트 한 조각 — 길이를 제한한 뒤 이스케이프한다."""
    if len(raw) > MAX_FIELD_CHARS:
        return escape(raw[:MAX_FIELD_CHARS]) + ELLIPSIS
    return escape(raw)


def truncate(block: str) -> str:
    """한도를 넘는 항목 하나를 줄 경계에서 자른다.

    태그 중간에서 자르면 텔레그램이 HTML 파싱에 실패하므로 줄 단위로만 버린다.
    """
    kept: list[str] = []
    used = 0
    for line in block.split("\n"):
        added = len(line) + (1 if kept else 0)
        if used + added + len(ELLIPSIS) + 1 > TELEGRAM_LIMIT:
            break
        kept.append(line)
        used += added
    return "\n".join([*kept, ELLIPSIS])


def pack(blocks: list[str]) -> list[str]:
    """블록을 순서대로 이어 붙이되 한도를 넘기 전에 새 메시지로 넘긴다."""
    parts: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= TELEGRAM_LIMIT:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = block if len(block) <= TELEGRAM_LIMIT else truncate(block)
    if current:
        parts.append(current)
    return parts
