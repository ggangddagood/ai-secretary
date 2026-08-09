"""발송 기록 테스트. 파일 경로는 tmp_path로 격리한다."""

import json
import logging
from datetime import date, timedelta

from secretary.models import Item
from secretary.state import (
    filter_unseen,
    load_seen,
    mark_seen,
    normalize_url,
    prune,
    save_seen,
    url_key,
)

TODAY = date(2026, 8, 9)


def make_item(url: str) -> Item:
    return Item(
        title="title",
        url=url,
        source="rss:test",
        score=None,
        published_at=None,
        summary_hint=None,
    )


def test_url_variants_share_one_key():
    variants = [
        "http://www.Example.com/post/?utm_source=x",
        "https://example.com/post",
        "https://example.com/post/#section",
    ]

    assert len({url_key(url) for url in variants}) == 1
    assert normalize_url(variants[0]) == "https://example.com/post"


def test_query_param_order_does_not_change_key():
    assert url_key("https://example.com/p?b=2&a=1") == url_key("https://example.com/p?a=1&b=2")
    assert normalize_url("https://example.com/p?b=2&a=1") == "https://example.com/p?a=1&b=2"


def test_filter_unseen_drops_only_recorded_items():
    items = [make_item("https://example.com/a"), make_item("https://example.com/b")]
    seen = {url_key("http://www.example.com/a/?utm_source=news"): "2026-08-01"}

    assert [item.url for item in filter_unseen(items, seen)] == ["https://example.com/b"]


def test_load_seen_missing_file(tmp_path):
    assert load_seen(tmp_path / "seen.json") == {}


def test_load_seen_broken_json(tmp_path, caplog):
    path = tmp_path / "seen.json"
    path.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        assert load_seen(path) == {}

    assert caplog.records


def test_load_seen_wrong_version(tmp_path, caplog):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"version": 99, "seen": {"abc": "2026-08-09"}}), encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        assert load_seen(path) == {}

    assert caplog.records


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "nested" / "seen.json"
    seen = {"key-a": "2026-08-09", "key-b": "2026-05-01"}

    save_seen(path, seen)

    assert load_seen(path) == seen
    # 임시 파일이 남으면 원자적 쓰기가 완결되지 않은 것이다.
    assert [child.name for child in path.parent.iterdir()] == ["seen.json"]


def test_mark_seen_returns_new_dict():
    seen: dict[str, str] = {}

    updated = mark_seen(seen, [make_item("https://example.com/a")], today=TODAY)

    assert seen == {}
    assert updated == {url_key("https://example.com/a"): "2026-08-09"}


def test_prune_keeps_boundary_and_drops_older():
    seen = {
        "today": TODAY.isoformat(),
        "day-90": (TODAY - timedelta(days=90)).isoformat(),
        "day-91": (TODAY - timedelta(days=91)).isoformat(),
    }

    assert set(prune(seen, today=TODAY)) == {"today", "day-90"}
