# Step 1: sources

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본
- `src/secretary/models.py` (step 0에서 생성 — `Item` 정의)
- `src/secretary/config.py` (step 0에서 생성)
- `src/secretary/log.py` (step 0에서 생성)

## 작업

외부 소스에서 `Item` 목록을 수집하는 레이어를 만든다. **이 step에서는 LLM, 본문 추출, 발송을 건드리지 않는다.**

### 1. `src/secretary/sources/base.py`

```python
class Source(Protocol):
    name: str
    def fetch(self, *, since: datetime, timeout: float) -> list[Item]: ...
```

### 2. `src/secretary/sources/hackernews.py`

Algolia HN Search API (인증 불필요):

- 프론트페이지: `GET https://hn.algolia.com/api/v1/search?tags=front_page`
- AI 키워드 검색: `GET https://hn.algolia.com/api/v1/search?query=<kw>&tags=story&numericFilters=created_at_i>{since_epoch},points>{MIN_POINTS}`
  - 키워드는 모듈 상수 `HN_QUERIES`로 둔다. 시작값: `("AI", "LLM", "Claude", "GPT", "agent", "indie hacker", "SaaS revenue")`
  - `MIN_POINTS = 30`
- 응답의 `hits[]`에서 `title`, `url`(없으면 `https://news.ycombinator.com/item?id={objectID}`), `points`→`score`, `created_at`→`published_at`을 매핑.
- 여러 쿼리 결과는 URL 기준으로 중복 제거한다.

### 3. `src/secretary/sources/geeknews.py`

`https://news.hada.io/rss/news` 를 `feedparser`로 파싱. `title`, `link`, `published`, `summary`(→`summary_hint`) 매핑. `score`는 `None`.

### 4. `src/secretary/sources/github.py`

GitHub Search API (`https://api.github.com/search/repositories`):

- 쿼리 예: `q=created:>{7일전} topic:ai&sort=stars&order=desc&per_page=15`
- 모듈 상수 `GITHUB_QUERIES`로 2~3개 쿼리를 둔다 (예: `topic:ai`, `topic:llm`, `topic:agent`).
- `Accept: application/vnd.github+json` 헤더. `config.github_token`이 있으면 `Authorization: Bearer <token>` 추가.
- `full_name` + `description`을 합쳐 `title`, `html_url`→`url`, `stargazers_count`→`score`, `created_at`→`published_at`, `description`→`summary_hint`.

### 5. `src/secretary/sources/rss.py`

여러 RSS 피드를 읽는 범용 소스. 피드 목록은 모듈 상수 `RSS_FEEDS: list[tuple[str, str]]`(표시명, URL)로 둔다.

**아래는 후보 목록이지 확정 목록이 아니다. 각 URL을 실제로 요청해서 HTTP 200과 파싱 가능한 피드를 반환하는지 확인하고, 실패하는 항목은 목록에서 제거한 뒤 `docs/tracking/FINDINGS.md`에 "제외한 피드와 사유"를 기록하라.**

후보:
- Simon Willison — `https://simonwillison.net/atom/everything/`
- Latent Space — `https://www.latent.space/feed`
- OpenAI Blog — `https://openai.com/blog/rss.xml`
- Google AI Blog — `https://blog.google/technology/ai/rss/`
- Hacker News Show HN — `https://hnrss.org/show`
- Indie Hackers — `https://www.indiehackers.com/feed.xml`

최소 3개 이상이 살아남아야 한다. 3개 미만이면 대체 피드를 찾아 채운다. `source` 필드는 `f"rss:{표시명}"` 형식.

### 6. `src/secretary/sources/__init__.py`

```python
def collect_all(cfg: Config, *, now: datetime) -> list[Item]: ...
```

- 모든 소스를 순회하며 `fetch`를 호출한다.
- **각 소스 호출을 개별적으로 try/except로 감싼다. 한 소스가 예외를 던지면 `logger.warning`으로 소스명과 사유를 남기고 다음 소스로 넘어간다.** (spec 불변 조건)
- 전체 결과를 URL 기준으로 중복 제거하고, `score` 내림차순(None은 뒤)으로 정렬해 반환한다.
- HN/GeekNews/RSS는 `since = now - 24h`, GitHub는 `now - 7d`를 적용한다.

### 7. HTTP 클라이언트

`src/secretary/http.py`에 `httpx.Client` 생성 헬퍼를 두고 모든 소스가 공유한다. 타임아웃은 `config.http_timeout`, `User-Agent`는 `ai-secretary/0.1`, 재시도는 하지 않는다(하루 1회 배치이므로 실패한 소스는 건너뛰면 충분).

### 8. 테스트 `tests/test_sources.py`

**네트워크를 타지 않는다.** 각 소스의 응답 샘플을 `tests/fixtures/` 에 저장하고, HTTP 계층을 monkeypatch해서 파싱 로직만 검증한다:

- HN JSON 픽스처 → `Item` 필드가 올바르게 매핑되는가 (특히 `url`이 없는 Ask HN 항목이 HN 퍼머링크로 대체되는가)
- GeekNews RSS 픽스처 → 파싱되는가
- GitHub JSON 픽스처 → 파싱되는가
- `collect_all`: 소스 하나가 예외를 던져도 나머지 소스 결과가 반환되는가 ← **이 테스트는 반드시 있어야 한다**
- `collect_all`: 서로 다른 소스가 같은 URL을 주면 1건으로 합쳐지는가

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
from datetime import datetime, timezone
from secretary.config import load_config
from secretary.sources import collect_all
items = collect_all(load_config(require_secrets=False), now=datetime.now(timezone.utc))
print(f'collected={len(items)}')
assert len(items) > 0, 'no items collected'
for i in items[:5]: print(i.source, '|', i.title[:70])
"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다. 마지막 명령은 실제 네트워크를 사용하므로 소스별 응답을 눈으로 확인하라.
2. 확인한다: 4개 소스군이 모두 최소 1건 이상 반환하는가(0건인 소스가 있으면 원인을 파악해 고치거나 FINDINGS.md에 기록) / 소스 하나를 강제로 실패시켜도 `collect_all`이 예외 없이 반환하는가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 1을 갱신한다.

## 금지사항

- 인증이 필요한 소스(Reddit, Threads, X)를 추가하지 마라. 이유: spec의 범위 제외 항목이며 MVP를 몇 주 지연시킨다.
- HTML 스크래핑으로 GitHub Trending 페이지를 파싱하지 마라. 이유: 공식 API가 아니라 마크업 변경에 그대로 깨진다. Search API를 쓴다.
- 테스트에서 실제 네트워크를 호출하지 마라. 이유: CI가 외부 서비스 가용성에 묶인다.
- 수집 단계에서 항목을 LLM으로 필터링하지 마라. 선별은 step 4의 책임이다.
