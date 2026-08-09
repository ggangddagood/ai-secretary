"""브리핑을 텔레그램 메시지로 렌더링한다.

포맷은 `parse_mode=HTML`이다. MarkdownV2는 요약 문장에 흔한 `.`, `-`, `(`까지 전부
이스케이프해야 하고 한 글자만 놓쳐도 발송이 400으로 실패한다. HTML은 `&`, `<`, `>` 셋뿐이다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

from .models import Brief, BriefEntry

TELEGRAM_LIMIT: Final[int] = 4096

# 발송 시각이 08:00 KST이므로 UTC 기준으로 날짜를 찍으면 하루 전 날짜가 나온다.
KST: Final[timezone] = timezone(timedelta(hours=9))

AXIS_LABELS: Final[dict[str, str]] = {
    "tech": "기술",
    "money": "수익화",
    "enterprise": "기업 사례",
    "marketing": "마케팅",
}

ELLIPSIS: Final[str] = "…"
# 한 줄이 단독으로 한도를 넘으면 태그를 살린 채 자를 수 없다. 조각마다 상한을 둔다.
MAX_FIELD_CHARS: Final[int] = 600


def _escape(text: str) -> str:
    """텔레그램 HTML에서 특별한 의미를 갖는 세 글자만 이스케이프한다."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attr(value: str) -> str:
    """href 속성값 — 따옴표까지 막아야 속성이 중간에 닫히지 않는다."""
    return _escape(value).replace('"', "&quot;")


def _text(raw: str) -> str:
    """메시지에 넣을 텍스트 한 조각 — 길이를 제한한 뒤 이스케이프한다."""
    if len(raw) > MAX_FIELD_CHARS:
        return _escape(raw[:MAX_FIELD_CHARS]) + ELLIPSIS
    return _escape(raw)


def _render_header(generated_at: datetime) -> str:
    local = generated_at.astimezone(KST)
    return f"📅 <b>AI 브리핑 · {local.month}월 {local.day}일</b>"


def _render_entry(index: int, entry: BriefEntry) -> str:
    axis = AXIS_LABELS.get(entry.axis, entry.axis)
    lines = [f'{index}. <a href="{_attr(entry.url)}">{_text(entry.title)}</a>  ·  [{_text(axis)}]']
    # 요약이 없는 항목은 부제·힌트도 없다. 본문 없이 쓸 수 있는 줄이 아니다.
    if entry.summary_ko:
        if entry.subtitle_ko:
            lines.append(f"<i>{_text(entry.subtitle_ko)}</i>")
        lines.extend(f"· {_text(line)}" for line in entry.summary_ko)
        if entry.action_hint_ko:
            lines.append(f"💡 {_text(entry.action_hint_ko)}")
    lines.append(f"<code>{_text(entry.source)}</code>")
    return "\n".join(lines)


def _truncate(block: str) -> str:
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


def _pack(blocks: list[str]) -> list[str]:
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
        current = block if len(block) <= TELEGRAM_LIMIT else _truncate(block)
    if current:
        parts.append(current)
    return parts


def render_brief(brief: Brief) -> list[str]:
    """브리핑을 발송할 메시지 목록으로 만든다. 한도를 넘으면 항목 경계에서 나눈다."""
    blocks = [_render_entry(index, entry) for index, entry in enumerate(brief.entries, start=1)]
    return _pack([_render_header(brief.generated_at), *blocks])


def render_failure(reason: str) -> str:
    """실패 알림. `reason`에는 사람이 읽을 짧은 사유만 담는다 — 시크릿·스택트레이스 금지."""
    return f"⚠️ 오늘 브리핑을 만들지 못했습니다: {_text(reason)}"
