"""원문 본문 추출.

여기서 확보한 본문이 요약의 유일한 근거다. 확보하지 못하면 `None`을 남겨
이후 단계가 "요약 없음"으로 처리하게 한다 — 제목이나 소스 설명으로 대신하지 않는다.
"""

from __future__ import annotations

import logging
from typing import Final

import trafilatura

from .http import make_client
from .models import Article, Item
from .sources.base import describe_error

logger = logging.getLogger(__name__)

MAX_BODY_CHARS: Final[int] = 8000
# 짧은 조각으로 요약하면 모델이 나머지를 지어낸다. 이 미만은 추출 실패로 본다.
MIN_BODY_CHARS: Final[int] = 300

_HTML_TYPES: Final[frozenset[str]] = frozenset({"text/html", "application/xhtml+xml"})


def _is_html(content_type: str) -> bool:
    return content_type.split(";")[0].strip().lower() in _HTML_TYPES


def fetch_body(url: str, *, timeout: float) -> str | None:
    """원문 본문을 추출한다. 실패하면 사유를 로그로 남기고 `None`을 반환한다.

    호출자에게 예외를 던지지 않는다 — 추출 실패는 정상적인 결과다.
    """
    try:
        with make_client(timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if not _is_html(content_type):
                logger.info("본문 건너뜀 %s: content-type=%s", url, content_type or "(없음)")
                return None
            html = response.text
        body = trafilatura.extract(html, include_comments=False, include_tables=False)
    except Exception as exc:
        logger.info("본문 추출 실패 %s: %s", url, describe_error(exc))
        return None

    if body is None:
        logger.info("본문 추출 실패 %s: 추출된 본문 없음", url)
        return None
    body = body.strip()
    if len(body) < MIN_BODY_CHARS:
        logger.info("본문 추출 실패 %s: 본문이 %d자로 너무 짧음", url, len(body))
        return None
    return body[:MAX_BODY_CHARS]


def extract_articles(items: list[Item], *, timeout: float) -> list[Article]:
    """각 항목의 본문을 추출한다.

    실패한 항목도 목록에 남긴다 — 제목·링크만이라도 브리핑에 실려야 한다.
    `Item.summary_hint`(예: GitHub 레포 description)는 본문 대용으로 쓰지 않는다.
    """
    return [Article(item=item, body=fetch_body(item.url, timeout=timeout)) for item in items]
