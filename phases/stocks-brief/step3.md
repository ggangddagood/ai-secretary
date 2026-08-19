# Step 3: news

급등락 종목의 근거가 될 뉴스 헤드라인을 Google News RSS에서 수집한다. **본문은 추출하지 않는다.**

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 특히 "급등락 해설", "엣지 케이스"
- `docs/STANDARDS.md` — 모듈 경계
- `docs/ENGINEERING_NOTES.md` — "죽은 RSS 피드는 예외가 아니라 빈 결과로 나타난다"
- `src/secretary/sources/base.py` — `parse_feed`, `describe_error`
- `src/secretary/sources/rss.py` — RSS를 가져오는 기존 구조
- `src/secretary/stocks/models.py` — `Ticker`, `Headline`
- `tests/test_sources.py` — 픽스처로 피드를 테스트하는 방식

`sources/base.py`의 헬퍼를 쓰는 것은 STANDARDS가 허용한다("반대 방향은 허용한다").

## 작업

### `src/secretary/stocks/news.py` 신설

```python
NEWS_BASE: Final[str] = "https://news.google.com/rss/search"
LOCALE: Final[dict[str, dict[str, str]]] = {
    "us": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "kr": {"hl": "ko",    "gl": "KR", "ceid": "KR:ko"},
}
RECENT_DAYS: Final[int] = 3
MAX_HEADLINES: Final[int] = 5

def fetch_headlines(
    ticker: Ticker, *, market: str, now: datetime, timeout: float
) -> list[Headline]: ...

def fetch_headlines_for(
    tickers: Sequence[Ticker], *, market: str, now: datetime, timeout: float
) -> dict[str, list[Headline]]: ...
```

- 검색어는 `ticker.label`이다(심볼이 아니다). 표시명이 뉴스에서 검색되는 이름이다.
- 쿼리 파라미터: `q=<label>` + `LOCALE[market]`. `q`는 URL 인코딩한다.
- `since = now - timedelta(days=RECENT_DAYS)` 를 `parse_feed`에 넘겨 최근 것만 남긴다.
- `parse_feed(body, source=f"news:{ticker.symbol}", since=since)` 로 `Item` 목록을 얻고
  `Headline(title=item.title, url=item.url, published_at=item.published_at)` 로 변환한다.
  `parse_feed`는 발행 시각을 못 읽는 항목을 이미 제외하므로 `published_at`은 `None`이 아니다.
- 최신순으로 정렬해 최대 `MAX_HEADLINES`건까지 자른다.
- **실패는 흡수한다.** 타임아웃·HTTP 에러·파싱 실패 시 warning 로그를 남기고 빈 리스트를 돌려준다.
  뉴스는 부가 정보이므로 전체 실행을 실패시키지 않는다.
- `fetch_headlines_for`는 클라이언트 하나로 여러 종목을 순차 처리하고 `{심볼: [Headline]}`을 돌려준다.
  헤드라인이 0건인 종목도 키는 존재하되 빈 리스트다.

### `tests/test_stocks_news.py` 신설

`tests/test_sources.py`의 픽스처 방식을 따른다. **네트워크에 나가지 않는다.**
RSS 픽스처는 `tests/fixtures/` 에 최소한의 유효 RSS XML로 새로 만든다(기존 픽스처를 수정하지 않는다).

최소 아래를 덮는다.

- 정상 RSS → `Headline` 목록, 제목·URL·시각이 맞다
- 3일보다 오래된 항목이 제외된다
- 5건을 넘으면 최신 5건만 남는다
- HTTP 예외 → 빈 리스트 (예외가 밖으로 나가지 않는다)
- 피드가 HTML을 돌려주는 경우(bozo) → 빈 리스트, 예외 없음
- 시장에 따라 `hl`/`gl`/`ceid` 파라미터가 달라진다 (`us` vs `kr`)
- 검색어로 `ticker.label`이 쓰인다 (심볼이 아니다)

## Acceptance Criteria

```bash
bash scripts/verify.sh
```

실호출 스모크 (선택, 실패해도 step 실패 아님):

```bash
python -c "
from datetime import datetime, timezone
from secretary.stocks.models import Ticker
from secretary.stocks.news import fetch_headlines
hs = fetch_headlines(Ticker('005930.KS','삼성전자'), market='kr', now=datetime.now(timezone.utc), timeout=20)
for h in hs: print(h.published_at.date(), h.title[:60])
print('headlines:', len(hs))
"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다.

## 금지사항

- 기사 **본문**을 추출하지 마라. `extract.py`를 부르지 마라. 이유: spec의 "범위 제외"에 있다.
  헤드라인까지만 쓴다.
- 뉴스 수집 실패를 예외로 올리지 마라. 이유: 시세가 본체이고 해설은 부가다. 뉴스 때문에 시세
  발송이 실패하면 안 된다.
- `sources/` 아래에 새 소스 클래스를 만들지 마라. 이유: `sources/`는 AI 브리핑의 수집 계층이고
  `build_sources()`에 등록되면 AI 브리핑에 주식 뉴스가 섞인다.
- 급등락이 아닌 종목의 뉴스를 가져오지 마라. 이유: 불필요한 외부 호출이다. 호출자가 대상을 정한다.
- 테스트가 실제 네트워크에 나가게 하지 마라.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
