"""로그에 시크릿이 남지 않는지 검증한다.

httpx는 요청 URL을 INFO로 찍는데 텔레그램 봇 토큰이 URL 경로에 들어간다.
실제로 토큰이 평문으로 남은 적이 있어 회귀 테스트로 고정한다.
"""

from __future__ import annotations

import logging

from secretary.log import SecretRedactingFilter, setup_logging

# 실제 토큰을 픽스처로 쓰지 마라. 테스트 파일은 커밋되고 리포는 공개다.
# 아래는 형식만 맞춘 가짜 값이다(텔레그램 토큰은 `<숫자>:<영숫자>` 형태).
FAKE_TOKEN = "1234567890:FAKEfakeFAKEfakeFAKEfakeFAKEfake123"
FAKE_URL = f"HTTP Request: POST https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord("httpx", logging.INFO, __file__, 1, message, None, None)


def test_redacts_bot_token_from_a_url():
    record = _record(FAKE_URL)

    assert SecretRedactingFilter().filter(record) is True

    text = record.getMessage()
    assert FAKE_TOKEN.split(":")[1] not in text
    assert FAKE_TOKEN.split(":")[0] not in text
    assert "bot***" in text


def test_redacts_token_passed_as_a_log_argument():
    record = logging.LogRecord("httpx", logging.INFO, __file__, 1, "요청 %s", (FAKE_URL,), None)

    SecretRedactingFilter().filter(record)

    assert FAKE_TOKEN.split(":")[1] not in record.getMessage()


def test_leaves_ordinary_messages_untouched():
    record = _record("수집 144건")

    SecretRedactingFilter().filter(record)

    assert record.getMessage() == "수집 144건"


def test_url_logging_libraries_stay_at_warning():
    setup_logging()

    for name in ("httpx", "httpcore", "urllib3"):
        assert logging.getLogger(name).level == logging.WARNING, name


def test_verbose_does_not_re_enable_url_logging():
    """--verbose는 우리 로거만 DEBUG로 내린다. httpx가 URL을 다시 찍으면 안 된다."""
    setup_logging(verbose=True)

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger().level == logging.DEBUG


def test_root_handlers_carry_the_redactor():
    setup_logging()

    handlers = logging.getLogger().handlers
    assert handlers, "루트 핸들러가 없으면 필터가 적용될 곳도 없다"
    assert any(any(isinstance(f, SecretRedactingFilter) for f in h.filters) for h in handlers)
