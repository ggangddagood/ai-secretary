"""브리핑을 텔레그램 메시지로 렌더링한다.

포맷은 `parse_mode=HTML`이다. MarkdownV2는 요약 문장에 흔한 `.`, `-`, `(`까지 전부
이스케이프해야 하고 한 글자만 놓쳐도 발송이 400으로 실패한다. HTML은 `&`, `<`, `>` 셋뿐이다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from .models import Brief, BriefEntry
from .tghtml import KST, attr, pack, text

AXIS_LABELS: Final[dict[str, str]] = {
    "tech": "기술",
    "money": "수익화",
    "enterprise": "기업 사례",
    "marketing": "마케팅",
}


def _render_header(generated_at: datetime) -> str:
    local = generated_at.astimezone(KST)
    return f"📅 <b>AI 브리핑 · {local.month}월 {local.day}일</b>"


def _render_entry(index: int, entry: BriefEntry) -> str:
    axis = AXIS_LABELS.get(entry.axis, entry.axis)
    lines = [f'{index}. <a href="{attr(entry.url)}">{text(entry.title)}</a>  ·  [{text(axis)}]']
    # 요약이 없는 항목은 부제·힌트도 없다. 본문 없이 쓸 수 있는 줄이 아니다.
    if entry.summary_ko:
        if entry.subtitle_ko:
            lines.append(f"<i>{text(entry.subtitle_ko)}</i>")
        lines.extend(f"· {text(line)}" for line in entry.summary_ko)
        if entry.action_hint_ko:
            lines.append(f"💡 {text(entry.action_hint_ko)}")
    lines.append(f"<code>{text(entry.source)}</code>")
    return "\n".join(lines)


def render_brief(brief: Brief) -> list[str]:
    """브리핑을 발송할 메시지 목록으로 만든다. 한도를 넘으면 항목 경계에서 나눈다."""
    blocks = [_render_entry(index, entry) for index, entry in enumerate(brief.entries, start=1)]
    return pack([_render_header(brief.generated_at), *blocks])


def render_failure(reason: str) -> str:
    """실패 알림. `reason`에는 사람이 읽을 짧은 사유만 담는다 — 시크릿·스택트레이스 금지."""
    return f"⚠️ 오늘 브리핑을 만들지 못했습니다: {text(reason)}"
