"""렌더링 테스트. 이스케이프와 4096자 분할이 핵심이다."""

from datetime import datetime, timezone

from secretary.models import Brief, BriefEntry
from secretary.render import TELEGRAM_LIMIT, render_brief, render_failure

GENERATED_AT = datetime(2026, 8, 9, 23, 0, tzinfo=timezone.utc)


def make_entry(
    *,
    title: str = "원문 제목",
    url: str = "https://example.com/1",
    axis: str = "tech",
    summary_ko: list[str] | None = None,
    action_hint_ko: str | None = "내일 이렇게 써먹어라.",
    subtitle_ko: str = "한국어 부제",
) -> BriefEntry:
    return BriefEntry(
        title=title,
        subtitle_ko=subtitle_ko,
        url=url,
        source="hackernews",
        axis=axis,
        summary_ko=["첫째 줄이다.", "둘째 줄이다.", "셋째 줄이다."]
        if summary_ko is None
        else summary_ko,
        action_hint_ko=action_hint_ko,
    )


def make_brief(entries: list[BriefEntry]) -> Brief:
    return Brief(generated_at=GENERATED_AT, entries=entries)


def test_entry_without_summary_shows_only_title_source_and_link():
    with_summary = make_entry(title="요약 있는 글")
    without_summary = make_entry(
        title="요약 없는 글",
        url="https://example.com/2",
        axis="money",
        summary_ko=[],
        action_hint_ko=None,
        subtitle_ko="",
    )

    (part,) = render_brief(make_brief([with_summary, without_summary]))

    header, first, second = part.split("\n\n")
    assert "AI 브리핑" in header
    assert "요약 있는 글" in first
    # 제목·축·링크 줄과 출처 줄만 남는다 — 부제·요약·힌트 줄은 없다.
    assert second.split("\n") == [
        '2. <a href="https://example.com/2">요약 없는 글</a>  ·  [수익화]',
        "<code>hackernews</code>",
    ]


def test_entry_with_summary_keeps_subtitle_summary_and_hint():
    (part,) = render_brief(make_brief([make_entry()]))

    assert "<i>한국어 부제</i>" in part
    assert "· 첫째 줄이다." in part
    assert "💡 내일 이렇게 써먹어라." in part
    assert "[기술]" in part


def test_special_characters_are_escaped():
    entry = make_entry(
        title="A <script> & B",
        url="https://example.com/x?a=1&b=2",
        summary_ko=["<b>강조</b> & 기타"],
    )

    (part,) = render_brief(make_brief([entry]))

    assert "<script>" not in part
    assert "A &lt;script&gt; &amp; B" in part
    assert "&lt;b&gt;강조&lt;/b&gt; &amp; 기타" in part
    assert 'href="https://example.com/x?a=1&amp;b=2"' in part


def test_long_brief_splits_at_entry_boundaries():
    entries = [
        make_entry(
            title=f"제목 {index}", url=f"https://example.com/{index}", summary_ko=["가" * 300] * 3
        )
        for index in range(12)
    ]

    parts = render_brief(make_brief(entries))

    assert len(parts) >= 2
    assert all(len(part) <= TELEGRAM_LIMIT for part in parts)
    # 항목이 조각 경계에서 쪼개지지 않았다 — 잘린 흔적이 없어야 한다.
    assert all(not part.endswith("…") for part in parts)


def test_single_oversized_entry_is_truncated():
    entry = make_entry(summary_ko=["가" * 500] * 30)

    parts = render_brief(make_brief([entry]))

    assert all(len(part) <= TELEGRAM_LIMIT for part in parts)
    assert parts[-1].endswith("…")


def test_render_failure_escapes_reason():
    assert render_failure("소스 <all> 실패 & 후보 0건") == (
        "⚠️ 오늘 브리핑을 만들지 못했습니다: 소스 &lt;all&gt; 실패 &amp; 후보 0건"
    )
