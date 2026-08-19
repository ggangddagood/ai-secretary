"""주식 브리핑 배치 오케스트레이션.

시세 조회 → 기준일 판정 → 급등락 판정 → 뉴스 수집 → 해설 → 렌더링 → 발송 순으로 배선한다.
도메인 로직은 각 모듈에 있고, 이 파일은 순서와 실패 정책만 정한다.

`secretary.main`(AI 브리핑)과 실패 정책이 두 곳에서 갈린다.
- 발송 기록이 없다. 직전 종가는 API가 응답에 담아 주므로 실행 간에 남길 상태가 없다.
- LLM 실패가 발송을 막지 않는다. 시세가 산출물의 본체이고 해설은 부가다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from google import genai

from ..config import ConfigError, StocksConfig, load_stocks_config
from ..gemini import make_client
from ..log import setup_logging
from ..sources.base import describe_error
from ..telegram import send_messages
from .llm import explain_moves
from .models import (
    FX_SYMBOL,
    MARKET_INDICES,
    MARKET_TZ,
    MARKETS,
    Headline,
    Quote,
    StockBrief,
    StockEntry,
)
from .news import fetch_headlines_for
from .quotes import fetch_quotes
from .render import render_failure, render_stock_brief

logger = logging.getLogger(__name__)


class StocksPipelineError(Exception):
    """브리핑을 만들 수 없어 실패 알림으로 끝나야 하는 상태."""


def _resolve_as_of(
    quotes: Sequence[Quote], *, market: str, now: datetime
) -> tuple[date | None, bool]:
    """기준일과 휴장 여부를 판정한다.

    환율은 24시간 거래라 시장이 쉬는 날에도 갱신된다 — 판정에 넣으면 휴장이 잡히지 않는다.
    환율만 남았다면 시장 기준일을 알 수 없으므로 날짜를 지어내지 않고 None으로 둔다.
    """
    dates = [quote.as_of for quote in quotes if quote.ticker.symbol != FX_SYMBOL]
    if not dates:
        return None, False
    as_of = max(dates)
    local_today = now.astimezone(ZoneInfo(MARKET_TZ[market])).date()
    return as_of, as_of != local_today


def _build_entry(
    quote: Quote, headlines: dict[str, list[Headline]], comments: dict[str, str]
) -> StockEntry:
    found = headlines.get(quote.ticker.symbol, [])
    # 헤드라인이 없으면 해설도 없다 — 근거 없는 해설은 환각이다(spec 불변 조건).
    comment = comments.get(quote.ticker.symbol) if found else None
    return StockEntry(quote=quote, headlines=found, comment_ko=comment)


def build_stock_brief(cfg: StocksConfig, client: genai.Client, *, now: datetime) -> StockBrief:
    """시세와 해설을 모아 브리핑을 만든다. 발송은 호출자가 한다."""
    market = cfg.market
    indices = fetch_quotes(MARKET_INDICES[market], timeout=cfg.http_timeout)
    if not cfg.watchlist:
        # 관심 종목이 없어도 지수만으로 브리핑이 성립한다. 실패가 아니다.
        logger.warning("관심 종목 목록이 비어 있습니다 — 시장 지표만 싣습니다")
    watchlist = fetch_quotes(cfg.watchlist, timeout=cfg.http_timeout)
    logger.info("시세 조회: 지수 %d건, 관심 종목 %d건", len(indices), len(watchlist))
    if not indices and not watchlist:
        raise StocksPipelineError("시세를 한 건도 조회하지 못했습니다")

    as_of, is_holiday = _resolve_as_of(indices + watchlist, market=market, now=now)

    # 급등락 판정 대상은 관심 종목뿐이다 — 지수는 해설하지 않는다.
    movers = [quote for quote in watchlist if abs(quote.change_pct) >= cfg.move_threshold]
    logger.info("급등락 %d건 (기준 %.1f%%)", len(movers), cfg.move_threshold)

    headlines: dict[str, list[Headline]] = {}
    comments: dict[str, str] = {}
    if movers:
        headlines = fetch_headlines_for(
            [quote.ticker for quote in movers],
            market=market,
            now=now,
            timeout=cfg.http_timeout,
        )
        try:
            comments = explain_moves(
                client,
                [(quote, headlines.get(quote.ticker.symbol, [])) for quote in movers],
            )
        except Exception as exc:
            # 시세가 본체이고 해설은 부가다 — 해설이 없다고 발송까지 막지 않는다.
            logger.warning("해설 생성 실패, 해설 없이 진행: %s", describe_error(exc))

    return StockBrief(
        market=market,
        generated_at=now,
        as_of=as_of,
        is_holiday=is_holiday,
        indices=indices,
        entries=[_build_entry(quote, headlines, comments) for quote in watchlist],
    )


def _load_config(market: str, *, dry_run: bool) -> StocksConfig:
    """dry-run은 텔레그램으로 보내지 않으므로 봇 토큰 없이도 돈다. Gemini 키는 여전히 필요하다."""
    cfg = load_stocks_config(market, require_secrets=not dry_run)
    if dry_run and not cfg.gemini_api_key:
        raise ConfigError("필수 환경 변수가 없습니다: GEMINI_API_KEY")
    return cfg


def _notify_failure(cfg: StocksConfig, reason: str, *, dry_run: bool) -> None:
    """실패 사실을 사용자에게 알린다.

    이 발송마저 실패하면 로그로만 남긴다 — 같은 채널이 죽은 상황이라 재시도할 곳이 없다.
    """
    message = render_failure(cfg.market, reason)
    if dry_run:
        print(message)
        return
    try:
        send_messages(cfg, [message])
    except Exception as exc:
        logger.error("실패 알림 발송도 실패: %s", describe_error(exc))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="secretary.stocks",
        description="관심 종목의 종가·등락과 시장 지표를 텔레그램으로 보낸다.",
    )
    # 기본값을 두지 않는다 — 잘못된 시장으로 조용히 도는 것보다 exit 2로 즉시 실패하는 편이 낫다.
    parser.add_argument("--market", required=True, choices=MARKETS, help="브리핑할 시장")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="텔레그램 발송 없이 브리핑을 stdout에 출력한다",
    )
    parser.add_argument("--verbose", action="store_true", help="DEBUG 로깅")
    return parser.parse_args(argv)


def _run(cfg: StocksConfig, args: argparse.Namespace) -> int:
    client = make_client(cfg.gemini_api_key)
    now = datetime.now(timezone.utc)

    try:
        brief = build_stock_brief(cfg, client, now=now)
        parts = render_stock_brief(brief)
    except Exception as exc:
        # 트레이스백은 로그(stderr)에만 남기고, 발송 메시지에는 예외 타입과 한 줄 요약만 담는다.
        logger.exception("주가 브리핑 생성 실패")
        _notify_failure(cfg, describe_error(exc), dry_run=args.dry_run)
        return 1

    logger.info("발송 조각 %d개", len(parts))
    if args.dry_run:
        print("\n\n".join(parts))
        logger.info("dry-run: 발송을 건너뜁니다")
        return 0

    try:
        send_messages(cfg, parts)
    except Exception as exc:
        # 실패 알림을 보내지 않는다. 같은 채널이 죽었으므로 재시도해도 같은 결과다.
        logger.error("텔레그램 발송 실패: %s", describe_error(exc))
        return 1
    return 0


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    # 반드시 먼저 부른다 — 봇 토큰 마스킹 필터가 여기서 루트 핸들러에 붙는다.
    setup_logging(args.verbose)

    try:
        cfg = _load_config(args.market, dry_run=args.dry_run)
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
