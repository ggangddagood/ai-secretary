"""주식 브리핑을 텔레그램 메시지로 렌더링한다.

포맷은 `parse_mode=HTML`이다. 이스케이프와 4096자 분할은 `tghtml`이 갖는다 —
규칙이 둘로 갈리면 한쪽만 고쳐진다.

종목 표시명은 환경 변수에서, 헤드라인 제목은 외부 RSS에서 온다. 둘 다 `<`·`&`가 들어올 수
있으므로 사람이 읽는 문자열은 전부 `text()`를, 링크 URL은 `attr()`을 거친다.
"""

from __future__ import annotations

from typing import Final

from ..tghtml import KST, attr, pack, text
from .models import MARKET_LABELS, Quote, StockBrief, StockEntry

INDEX_HEADING: Final[str] = "<b>📊 지수</b>"
WATCHLIST_HEADING: Final[str] = "<b>📈 관심 종목</b>"
MOVERS_HEADING: Final[str] = "<b>🔎 급등락</b>"


def _format_price(quote: Quote) -> str:
    symbol = quote.ticker.symbol
    # 지수(`^GSPC`)와 환율(`USDKRW=X`)은 통화와 무관하게 소수점을 살린다.
    if symbol.startswith("^") or symbol.endswith("=X"):
        return f"{quote.price:,.2f}"
    # 한국 주식은 원 단위 정수로 거래된다 — 소수점을 붙이면 없는 정밀도가 생긴다.
    if quote.currency == "KRW":
        return f"{quote.price:,.0f}"
    return f"{quote.price:,.2f}"


def _format_change(change_pct: float) -> str:
    if change_pct > 0:
        arrow = "▲"
    elif change_pct < 0:
        arrow = "▼"
    else:
        arrow = "–"
    return f"{arrow} {change_pct:+.2f}%"


def _render_header(brief: StockBrief) -> str:
    local = brief.generated_at.astimezone(KST)
    label = MARKET_LABELS.get(brief.market, brief.market)
    line = f"📅 <b>{text(label)} 주가 브리핑 · {local.month}월 {local.day}일</b>"
    # 조회가 전부 실패해 기준일을 모르면 날짜를 지어내지 않는다.
    if brief.as_of is None:
        return line
    holiday = " · 휴장" if brief.is_holiday else ""
    return f"{line}\n<i>기준일 {brief.as_of.isoformat()}{holiday}</i>"


def _format_52w(quote: Quote) -> str | None:
    """52주 지표 줄. 표시할 값이 없으면 None — 호출자가 줄 자체를 생략한다.

    고정 문구와 우리가 만든 숫자뿐이라 `text()`를 거치지 않는다.
    """
    if quote.drawdown_pct is None:
        return None
    # 신고가면 범위 내 위치가 100%로 자명하다 — 덧붙이면 중복이다.
    if quote.drawdown_pct >= 0:
        return "   52주 신고가"
    # drawdown_pct는 음수이므로 :.1f가 부호를 만든다.
    line = f"   52주 고점 대비 {quote.drawdown_pct:.1f}%"
    if quote.range_pct is None:
        return line
    return f"{line}  (범위 내 {quote.range_pct:.0f}%)"


def _render_index(quote: Quote) -> str:
    line = f"{text(quote.ticker.label)}  {_format_price(quote)}  {_format_change(quote.change_pct)}"
    fifty_two = _format_52w(quote)
    return f"{line}\n{fifty_two}" if fifty_two else line


def _render_entry(entry: StockEntry) -> str:
    quote = entry.quote
    label = f"{text(quote.ticker.label)} ({text(quote.ticker.symbol)})"
    line = f"{label}  {_format_price(quote)}  {_format_change(quote.change_pct)}"
    fifty_two = _format_52w(quote)
    return f"{line}\n{fifty_two}" if fifty_two else line


def _render_mover(entry: StockEntry) -> str:
    quote = entry.quote
    lines = [
        f"<b>{text(quote.ticker.label)}</b>  {_format_change(quote.change_pct)}",
    ]
    # 해설이 없으면 헤드라인만 싣는다 — 근거 없는 해설을 만들지 않는다는 규칙의 표시면이다.
    if entry.comment_ko:
        lines.append(text(entry.comment_ko))
    lines.extend(
        f'· <a href="{attr(headline.url)}">{text(headline.title)}</a>'
        for headline in entry.headlines
    )
    return "\n".join(lines)


def render_stock_brief(brief: StockBrief) -> list[str]:
    """주식 브리핑을 발송할 메시지 목록으로 만든다. 한도를 넘으면 블록 경계에서 나눈다."""
    blocks = [_render_header(brief)]
    if brief.indices:
        blocks.append("\n".join([INDEX_HEADING, *(_render_index(q) for q in brief.indices)]))
    if brief.entries:
        blocks.append("\n".join([WATCHLIST_HEADING, *(_render_entry(e) for e in brief.entries)]))

    movers = [entry for entry in brief.entries if entry.comment_ko or entry.headlines]
    if movers:
        mover_blocks = [_render_mover(entry) for entry in movers]
        # 헤딩을 첫 종목에 붙인다 — 조각이 나뉠 때 헤딩만 남는 메시지가 생기지 않게.
        mover_blocks[0] = f"{MOVERS_HEADING}\n{mover_blocks[0]}"
        blocks.extend(mover_blocks)
    return pack(blocks)


def render_failure(market: str, reason: str) -> str:
    """실패 알림. `reason`에는 사람이 읽을 짧은 사유만 담는다 — 시크릿·스택트레이스 금지."""
    label = MARKET_LABELS.get(market, market)
    return f"⚠️ {text(label)} 주가 브리핑을 만들지 못했습니다: {text(reason)}"
