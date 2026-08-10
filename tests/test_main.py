"""파이프라인 배선 테스트. 네트워크·LLM·파일 저장을 전부 가짜로 바꾼다.

여기서 지키는 것은 순서와 실패 정책이다 — 특히 "발송이 성공한 뒤에만 발송 기록을 저장한다".
"""

from datetime import datetime, timezone
from pathlib import Path

from secretary import main as main_module
from secretary.config import Config
from secretary.llm import Selection
from secretary.models import Article, BriefEntry, Item
from secretary.telegram import TelegramError


def make_config(tmp_path: Path) -> Config:
    return Config(
        telegram_bot_token="token",
        telegram_chat_id="99",
        gemini_api_key="key",
        github_token=None,
        brief_item_count=5,
        state_path=tmp_path / "seen.json",
        http_timeout=1.0,
    )


def make_item(url: str) -> Item:
    return Item(
        title="Example Post",
        url=url,
        source="hackernews",
        score=100,
        published_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        summary_hint=None,
    )


def make_entry(url: str) -> BriefEntry:
    return BriefEntry(
        title="Example Post",
        subtitle_ko="한국어 부제",
        url=url,
        source="hackernews",
        axis="tech",
        summary_ko=["첫째 줄이다.", "둘째 줄이다.", "셋째 줄이다."],
        action_hint_ko="내일 이렇게 써먹어라.",
    )


URL = "https://example.com/post"


def patch_pipeline(monkeypatch, cfg, *, items=None, summarize=None, send=None):
    """파이프라인 각 단계를 가짜로 대체하고 호출 순서를 기록한다."""
    calls: list[str] = []
    saved: dict[str, dict[str, str]] = {}
    candidates = [make_item(URL)] if items is None else items

    def fake_summarize(client, articles, selections):
        calls.append("summarize")
        if summarize is not None:
            return summarize(articles, selections)
        return [make_entry(article.item.url) for article in articles]

    def fake_send(config, messages):
        calls.append("send")
        if send is not None:
            send(messages)

    def fake_save_seen(path, seen):
        calls.append("save_seen")
        saved["seen"] = seen

    monkeypatch.setattr(main_module, "load_config", lambda *, require_secrets=True: cfg)
    monkeypatch.setattr(main_module, "make_client", lambda config: object())
    monkeypatch.setattr(main_module, "collect_all", lambda config, *, now: list(candidates))
    monkeypatch.setattr(main_module, "load_seen", lambda path: {})
    monkeypatch.setattr(
        main_module,
        "curate",
        lambda client, cands, *, count: [
            Selection(url=item.url, axis="tech", reason_ko="쓸모 있다") for item in cands[:count]
        ],
    )
    monkeypatch.setattr(
        main_module,
        "extract_articles",
        lambda selected, *, timeout: [
            Article(item=item, body="본문이다." * 60) for item in selected
        ],
    )
    monkeypatch.setattr(main_module, "summarize", fake_summarize)
    monkeypatch.setattr(main_module, "send_messages", fake_send)
    monkeypatch.setattr(main_module, "save_seen", fake_save_seen)
    return calls, saved


def test_saves_seen_only_after_a_successful_send(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    calls, saved = patch_pipeline(monkeypatch, cfg)

    assert main_module.run([]) == 0

    # 순서가 핵심이다 — save_seen이 send보다 먼저면 발송 실패 시 항목이 유실된다.
    assert calls == ["summarize", "send", "save_seen"]
    assert len(saved["seen"]) == 1


def test_no_candidates_sends_failure_notice_and_fails(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    sent: list[list[str]] = []
    calls, _ = patch_pipeline(monkeypatch, cfg, items=[], send=sent.append)

    assert main_module.run([]) == 1

    assert calls == ["send"]
    assert "브리핑을 만들지 못했습니다" in sent[0][0]
    assert "save_seen" not in calls


def test_summarize_failure_sends_failure_notice_and_skips_state(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    sent: list[list[str]] = []

    def boom(articles, selections):
        raise RuntimeError("모델 응답을 읽지 못했습니다")

    calls, _ = patch_pipeline(monkeypatch, cfg, summarize=boom, send=sent.append)

    assert main_module.run([]) == 1

    assert calls == ["summarize", "send"]
    assert "save_seen" not in calls
    # 사유는 예외 타입과 한 줄 요약까지만 — 트레이스백은 로그로만 남는다.
    assert "RuntimeError" in sent[0][0]


def test_send_failure_does_not_save_seen(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)

    def boom(messages):
        raise TelegramError("1/1 발송 실패: HTTP 400")

    calls, saved = patch_pipeline(monkeypatch, cfg, send=boom)

    assert main_module.run([]) == 1

    # 기록을 남기지 않아야 다음 실행에서 같은 항목을 다시 시도한다.
    assert "save_seen" not in calls
    assert saved == {}
    # 실패 알림을 같은 채널로 재발송하지 않는다.
    assert calls.count("send") == 1


def test_dry_run_skips_telegram_and_state(monkeypatch, tmp_path, capsys):
    cfg = make_config(tmp_path)
    calls, saved = patch_pipeline(monkeypatch, cfg)

    assert main_module.run(["--dry-run"]) == 0

    assert calls == ["summarize"]
    assert saved == {}
    assert "Example Post" in capsys.readouterr().out
