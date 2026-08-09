"""배치 오케스트레이션.

수집 → 중복 제거 → 선별 → 본문 추출 → 요약 → 렌더링 → 발송 → 발송 기록 순으로 배선한다.
도메인 로직은 각 모듈에 있고, 이 파일은 순서와 실패 정책만 정한다.

실패 정책의 축은 둘이다.
- 어느 단계에서 무너지든 사용자에게는 결과가 도달한다. 조용히 아무것도 보내지 않고 끝내지 않는다.
- 발송 기록은 텔레그램 발송이 성공한 뒤에만 저장한다. 실패 시 기록이 없어야 다음 실행에서 재시도된다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timezone

from anthropic import Anthropic

from .config import Config, ConfigError, load_config
from .extract import extract_articles
from .llm import curate, summarize
from .log import setup_logging
from .models import Brief, Item
from .render import render_brief, render_failure
from .sources import collect_all
from .sources.base import describe_error
from .state import filter_unseen, load_seen, mark_seen, prune, save_seen
from .telegram import send_messages

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """브리핑을 만들 수 없어 실패 알림으로 끝나야 하는 상태."""


def build_brief(
    cfg: Config, client: Anthropic, *, now: datetime, limit: int
) -> tuple[Brief, list[Item]]:
    """브리핑과 거기 실린 원본 항목 목록을 만든다.

    항목 목록은 발송 성공 후 발송 기록에 남길 대상이다 — 여기서 기록을 갱신하지 않는다.
    """
    items = collect_all(cfg, now=now)
    logger.info("수집 %d건", len(items))

    seen = load_seen(cfg.state_path)
    candidates = filter_unseen(items, seen)
    logger.info("중복 제거 후 %d건 (발송 기록 %d건)", len(candidates), len(seen))
    if not candidates:
        raise PipelineError(f"수집 {len(items)}건 중 새 항목이 없습니다")

    selections = curate(client, candidates, count=limit)
    logger.info("선별 %d건", len(selections))
    if not selections:
        # 항목이 하나도 없는 브리핑을 보내는 것은 아무것도 안 보내는 것과 같다.
        raise PipelineError(f"후보 {len(candidates)}건에서 한 건도 선별되지 않았습니다")

    item_by_url = {item.url: item for item in candidates}
    selected = [item_by_url[selection.url] for selection in selections]

    articles = extract_articles(selected, timeout=cfg.http_timeout)
    extracted = sum(1 for article in articles if article.body is not None)
    logger.info("본문 추출 성공 %d건 / 실패 %d건", extracted, len(articles) - extracted)

    entries = summarize(client, articles, selections)
    return Brief(generated_at=now, entries=entries), selected


def _load_config(*, dry_run: bool) -> Config:
    """dry-run은 텔레그램으로 보내지 않으므로 봇 토큰 없이도 돈다. Claude 키는 여전히 필요하다."""
    cfg = load_config(require_secrets=not dry_run)
    if dry_run and not cfg.anthropic_api_key:
        raise ConfigError("필수 환경 변수가 없습니다: ANTHROPIC_API_KEY")
    return cfg


def _notify_failure(cfg: Config, reason: str, *, dry_run: bool) -> None:
    """실패 사실을 사용자에게 알린다.

    이 발송마저 실패하면 로그로만 남긴다 — 같은 채널이 죽은 상황이라 재시도할 곳이 없다.
    """
    message = render_failure(reason)
    if dry_run:
        print(message)
        return
    try:
        send_messages(cfg, [message])
    except Exception as exc:
        logger.error("실패 알림 발송도 실패: %s", describe_error(exc))


def _record_sent(cfg: Config, items: list[Item], *, today: date) -> None:
    """발송 기록을 갱신한다. 발송이 성공한 뒤에만 호출한다."""
    # 발송 전에 읽은 기록을 다시 읽는다 — 발송이 실패했다면 여기까지 오지 않으므로,
    # 기록을 들고 다니는 것보다 저장 직전에 읽는 편이 순서 실수를 만들 여지가 적다.
    seen = load_seen(cfg.state_path)
    updated = prune(mark_seen(seen, items, today=today), today=today)
    save_seen(cfg.state_path, updated)
    logger.info("발송 기록 저장: 신규 %d건, 총 %d건", len(items), len(updated))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="secretary",
        description="AI 브리핑을 수집·요약해 텔레그램으로 보낸다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="텔레그램 발송과 발송 기록 저장 없이 브리핑을 stdout에 출력한다",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="브리핑 항목 수 (기본: BRIEF_ITEM_COUNT)",
    )
    parser.add_argument("--verbose", action="store_true", help="DEBUG 로깅")
    return parser.parse_args(argv)


def _run(cfg: Config, args: argparse.Namespace) -> int:
    client = Anthropic(api_key=cfg.anthropic_api_key)
    now = datetime.now(timezone.utc)
    limit = args.limit if args.limit is not None else cfg.brief_item_count

    try:
        brief, selected = build_brief(cfg, client, now=now, limit=limit)
        parts = render_brief(brief)
    except Exception as exc:
        # 트레이스백은 로그(stderr)에만 남기고, 발송 메시지에는 예외 타입과 한 줄 요약만 담는다.
        logger.exception("브리핑 생성 실패")
        _notify_failure(cfg, describe_error(exc), dry_run=args.dry_run)
        return 1

    logger.info("발송 조각 %d개", len(parts))
    if args.dry_run:
        print("\n\n".join(parts))
        logger.info("dry-run: 발송과 발송 기록 저장을 건너뜁니다")
        return 0

    try:
        send_messages(cfg, parts)
    except Exception as exc:
        # 발송 기록을 남기지 않는다 — 남기면 실패한 항목이 다음 실행에서도 후보로 잡히지 않는다.
        # 실패 알림도 보내지 않는다. 같은 채널이 죽었으므로 재시도해도 같은 결과다.
        logger.error("텔레그램 발송 실패: %s", describe_error(exc))
        return 1

    _record_sent(cfg, selected, today=now.date())
    return 0


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    setup_logging(args.verbose)

    try:
        cfg = _load_config(dry_run=args.dry_run)
    except ConfigError as exc:
        # 설정이 없으면 알릴 채널도 없다. 로그만 남기고 실패로 끝낸다.
        logger.error("설정 오류: %s", exc)
        return 1

    try:
        return _run(cfg, args)
    except Exception as exc:
        logger.exception("예상치 못한 실패")
        _notify_failure(cfg, describe_error(exc), dry_run=args.dry_run)
        return 1


if __name__ == "__main__":
    sys.exit(run())
