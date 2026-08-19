"""급등락 해설 생성 — 수집한 헤드라인만을 근거로 삼는다.

헤드라인이 없는 종목은 아예 프롬프트에 넣지 않는다. 근거 없이 "왜 올랐나"를 물으면 모델이
이유를 지어내고, 그럴듯한 거짓 해설은 이 파이프라인에서 가장 치명적인 실패다.
본문 없는 항목을 모델에 보내지 않는 `secretary.llm.summarize`와 같은 구조적 방어다.

호출 실패는 흡수하지 않고 그대로 올린다 — 해설 없이 발송할지는 `main`이 정한다.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from google import genai
from pydantic import BaseModel

from ..gemini import generate
from .models import Headline, Quote

logger = logging.getLogger(__name__)

EXPLAIN_SYSTEM: Final[str] = """\
너는 한국 개인 투자자에게 그날의 주가 움직임을 설명해 주는 편집자다.
주어진 헤드라인만 근거로 삼는다.

헤드라인에 없는 사실을 쓰지 마라. 배경 지식이나 일반론으로 빈 곳을 채우지 마라.
헤드라인이 등락의 이유를 설명하지 못하면, 이유를 지어내지 말고 헤드라인이 전하는 소식을
그대로 한 줄로 요약해라.

comment_ko는 한국어 한 문장이다.
매수·매도 의견, 목표가, 투자 판단을 쓰지 마라.
symbol은 입력에 주어진 값을 그대로 돌려준다.\
"""


class CommentOut(BaseModel):
    symbol: str
    comment_ko: str


class CommentResult(BaseModel):
    comments: list[CommentOut]


def _format_mover(quote: Quote, headlines: list[Headline]) -> str:
    lines = [
        f"심볼: {quote.ticker.symbol}",
        f"종목: {quote.ticker.label}",
        f"등락률: {quote.change_pct:+.2f}%",
        "헤드라인:",
    ]
    lines.extend(f"- {headline.title}" for headline in headlines)
    return "\n".join(lines)


def explain_moves(
    client: genai.Client,
    movers: Sequence[tuple[Quote, list[Headline]]],
) -> dict[str, str]:
    """헤드라인이 있는 종목만 한 번의 호출로 해설한다. `{심볼: 해설}`을 돌려준다.

    해설을 받지 못한 심볼은 키가 없다. 헤드라인이 있는 종목이 하나도 없으면 호출하지 않는다.
    """
    grounded = [(quote, headlines) for quote, headlines in movers if headlines]
    if not grounded:
        return {}

    payload = "\n\n---\n\n".join(_format_mover(quote, headlines) for quote, headlines in grounded)
    result = generate(
        client,
        EXPLAIN_SYSTEM,
        f"종목 {len(grounded)}건의 움직임을 설명해라.\n\n{payload}",
        CommentResult,
    )

    allowed = {quote.ticker.symbol for quote, _ in grounded}
    comments: dict[str, str] = {}
    for comment in result.comments:
        if comment.symbol not in allowed:
            # 프롬프트에 없던 심볼이다 — 근거가 없으므로 모델이 만들어낸 해설이다.
            logger.warning("근거 없는 심볼의 해설이라 폐기: %s", comment.symbol)
            continue
        comments[comment.symbol] = comment.comment_ko
    return comments
