"""Gemini 호출 공용 — 클라이언트 생성과 구조화 출력 1회 호출.

출력 스키마는 `response_format`으로만 전달한다. 프롬프트에 스키마나 예시 JSON을 다시 적으면
스키마가 중복 전달되어 출력 품질이 떨어진다(Gemini 문서가 경고하는 안티패턴).
"""

from __future__ import annotations

from typing import Final, TypeVar

from google import genai
from pydantic import BaseModel

MODEL: Final[str] = "gemini-3.6-flash"

T = TypeVar("T", bound=BaseModel)


def make_client(api_key: str) -> genai.Client:
    """API 키를 명시적으로 넘긴다 — SDK가 환경 변수를 직접 읽게 두지 않는다."""
    return genai.Client(api_key=api_key)


def generate(client: genai.Client, system: str, user: str, expected: type[T]) -> T:
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
