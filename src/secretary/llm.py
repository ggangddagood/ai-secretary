"""Gemini API 호출 — 1단계 선별, 2단계 요약.

두 단계를 한 번의 호출로 합치지 않는다. 제목만 보고 요약하면 모델이 내용을 지어낸다.
요약의 근거는 step 3이 추출한 본문뿐이며, 본문이 없는 항목은 아예 모델에 보내지 않는다.

출력 스키마는 `response_format`으로만 전달한다. 프롬프트에 스키마나 예시 JSON을 다시 적으면
스키마가 중복 전달되어 출력 품질이 떨어진다(Gemini 문서가 경고하는 안티패턴).
"""

from __future__ import annotations

import logging
from typing import Final, Literal, TypeVar

from google import genai
from pydantic import BaseModel

from .config import Config
from .models import Article, BriefEntry, Item

logger = logging.getLogger(__name__)

MODEL: Final[str] = "gemini-3.6-flash"

MAX_CANDIDATES: Final[int] = 40
HINT_CHARS: Final[int] = 200

CURATE_SYSTEM: Final[str] = """\
너는 AI를 활용해 수익을 내려는 1인 개발자의 정보 큐레이터다.
후보 목록에서 이 독자에게 가장 쓸모 있는 항목을 고른다.

선별 축은 넷이다.
- tech: AI 기술·도구·모델·프롬프트·에이전트 활용법
- money: AI로 수익을 낸 사례, 개인/소규모 팀의 제품 출시와 매출 공개
- enterprise: 기업이 실제 업무에 AI를 도입한 사례와 방법
- marketing: 개발자·1인 제품의 마케팅, 런칭, 그로스 전략

가능하면 최소 3개 축이 포함되도록 고르되, 축을 채우려고 품질이 낮은 항목을 넣지는 마라.
우선순위는 유용성이다. 단순 뉴스 헤드라인(자금 조달, 인사, 주가)보다 독자가 실제로
따라 할 수 있는 내용을 앞에 둔다.

url은 후보 목록에 있는 값을 그대로 돌려준다. 목록에 없는 URL을 만들어내지 마라.
reason_ko는 그 항목을 고른 이유를 한국어 한 줄로 쓴다.\
"""

SUMMARIZE_SYSTEM: Final[str] = """\
너는 AI를 활용해 수익을 내려는 1인 개발자에게 글을 정리해 주는 편집자다.
주어진 본문만 근거로 삼는다.

summary_ko는 정확히 3줄이고, 각 줄은 완결된 한국어 문장이다.
본문에 없는 사실을 쓰지 마라. 배경 지식이나 일반론으로 빈 곳을 채우지 마라.
subtitle_ko는 이 글이 무엇에 관한 글인지 알려 주는 한국어 한 줄이다.
원문 제목을 번역하는 자리가 아니다.
action_hint_ko는 이 독자가 내일 무엇을 해볼 수 있는지 한 문장으로 쓴다.
url은 입력에 주어진 값을 그대로 돌려준다.\
"""


class Selection(BaseModel):
    url: str
    axis: Literal["tech", "money", "enterprise", "marketing"]
    reason_ko: str


class SelectionResult(BaseModel):
    selections: list[Selection]


class SummaryOut(BaseModel):
    url: str
    subtitle_ko: str
    summary_ko: list[str]
    action_hint_ko: str


class SummaryResult(BaseModel):
    summaries: list[SummaryOut]


T = TypeVar("T", bound=BaseModel)


def make_client(cfg: Config) -> genai.Client:
    """API 키는 config를 거쳐 명시적으로 넘긴다 — SDK가 환경 변수를 직접 읽게 두지 않는다."""
    return genai.Client(api_key=cfg.gemini_api_key)


def _generate(client: genai.Client, system: str, user: str, expected: type[T]) -> T:
    """JSON 스키마를 강제해 호출하고 응답을 파싱한다. 비어 있으면(거부·잘림 등) 예외로 알린다."""
    interaction = client.interactions.create(
        model=MODEL,
        system_instruction=system,
        input=user,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": expected.model_json_schema(),
        },
    )
    text = getattr(interaction, "output_text", None)
    if not text:
        status = getattr(interaction, "status", None)
        raise RuntimeError(f"{MODEL} 구조화 응답을 읽지 못했습니다 (status={status})")
    return expected.model_validate_json(text)


def _format_candidate(item: Item) -> str:
    lines = [f"제목: {item.title}", f"출처: {item.source}", f"URL: {item.url}"]
    if item.summary_hint:
        lines.append(f"설명: {item.summary_hint[:HINT_CHARS]}")
    return "\n".join(lines)


def curate(client: genai.Client, candidates: list[Item], *, count: int) -> list[Selection]:
    """후보 중 `count`건을 고른다. 본문은 아직 없고 제목·출처·설명만 보고 판단한다."""
    ranked = sorted(candidates, key=lambda item: item.score or 0, reverse=True)[:MAX_CANDIDATES]
    listing = "\n\n".join(_format_candidate(item) for item in ranked)

    result = _generate(
        client,
        CURATE_SYSTEM,
        f"오늘 후보 {len(ranked)}건이다. 이 중 {count}건을 골라라.\n\n{listing}",
        SelectionResult,
    )

    allowed = {item.url for item in ranked}
    selections: list[Selection] = []
    for selection in result.selections:
        if selection.url not in allowed:
            logger.warning("후보에 없는 URL이라 선별에서 제외: %s", selection.url)
            continue
        selections.append(selection)
    return selections[:count]


def _format_article(article: Article) -> str:
    item = article.item
    return "\n".join(
        [
            f"URL: {item.url}",
            f"제목: {item.title}",
            f"출처: {item.source}",
            "본문:",
            article.body or "",
        ]
    )


def _entry(article: Article, axis: str, summary: SummaryOut | None) -> BriefEntry:
    item = article.item
    if summary is None:
        # 본문이 없으면 요약하지 않는다 — 제목·출처·링크만 싣는다.
        return BriefEntry(
            title=item.title,
            subtitle_ko="",
            url=item.url,
            source=item.source,
            axis=axis,
            summary_ko=[],
            action_hint_ko=None,
        )
    return BriefEntry(
        title=item.title,
        subtitle_ko=summary.subtitle_ko,
        url=item.url,
        source=item.source,
        axis=axis,
        summary_ko=summary.summary_ko,
        action_hint_ko=summary.action_hint_ko,
    )


def summarize(
    client: genai.Client, articles: list[Article], selections: list[Selection]
) -> list[BriefEntry]:
    """본문이 있는 항목만 한 번의 호출로 요약하고 브리핑 항목을 조립한다."""
    axis_by_url = {selection.url: selection.axis for selection in selections}
    with_body = [article for article in articles if article.body is not None]

    summaries: dict[str, SummaryOut] = {}
    if with_body:
        payload = "\n\n---\n\n".join(_format_article(article) for article in with_body)
        result = _generate(
            client,
            SUMMARIZE_SYSTEM,
            f"항목 {len(with_body)}건을 요약해라.\n\n{payload}",
            SummaryResult,
        )
        summaries = {summary.url: summary for summary in result.summaries}

    entries: list[BriefEntry] = []
    for article in articles:
        # 본문 없는 항목은 모델에 보내지 않았으므로 요약도 붙이지 않는다.
        summary = summaries.get(article.item.url) if article.body is not None else None
        if article.body is not None and summary is None:
            logger.warning("요약 결과에 빠진 항목이라 요약 없이 싣는다: %s", article.item.url)
        entries.append(_entry(article, axis_by_url[article.item.url], summary))
    return entries
