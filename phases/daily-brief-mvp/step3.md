# Step 3: extract

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본 (특히 불변 조건 1번)
- `src/secretary/models.py` (step 0 — `Item`, `Article`)
- `src/secretary/http.py` (step 1)
- `src/secretary/config.py` (step 0)

## 작업

선별된 항목의 원문 본문을 추출한다. 이 본문이 요약의 유일한 근거가 된다.

### `src/secretary/extract.py`

```python
MAX_BODY_CHARS = 8000

def fetch_body(url: str, *, timeout: float) -> str | None: ...
def extract_articles(items: list[Item], *, timeout: float) -> list[Article]: ...
```

- `fetch_body`:
  - `httpx`로 GET, `follow_redirects=True`.
  - `Content-Type`이 `text/html` 계열이 아니면 `None` 반환(PDF·이미지 등).
  - `trafilatura.extract(html, include_comments=False, include_tables=False)`로 본문 추출.
  - 결과가 `None`이거나 공백 제거 후 **300자 미만이면 `None`을 반환한다.** 짧은 조각으로 요약하면 환각이 생긴다.
  - `MAX_BODY_CHARS` 초과 시 앞부분만 남기고 자른다(토큰 비용 상한).
  - 어떤 예외(타임아웃, HTTP 에러, 파싱 실패)도 밖으로 던지지 않는다. `logger.info`로 URL과 사유를 남기고 `None`을 반환한다.
- `extract_articles`: 각 `Item`을 `Article(item=..., body=fetch_body(...))`로 변환. 실패는 `body=None`으로 남긴다. **실패했다고 목록에서 빼지 마라** — 제목·링크만이라도 브리핑에 실려야 한다.
- GitHub 저장소 항목은 `Item.summary_hint`(레포 description)만 있고 본문 추출이 실패하기 쉽다. 이 경우 `summary_hint`를 body로 승격하지 마라 — `None`으로 두고 step 4가 요약 없이 처리하게 한다.

### 테스트 `tests/test_extract.py`

**네트워크를 타지 않는다.** `tests/fixtures/`에 HTML 샘플을 두고 HTTP 계층을 monkeypatch한다:

- 정상 HTML → 본문 문자열 반환, 네비게이션/스크립트 텍스트가 섞이지 않음
- 본문이 거의 없는 HTML(300자 미만) → `None`
- `Content-Type: application/pdf` → `None`
- HTTP 500 / 타임아웃 예외 → `None` (예외가 밖으로 새지 않음)
- 8000자 초과 본문 → 잘려서 반환
- `extract_articles`: 3건 중 1건이 실패해도 결과 길이가 3이고, 실패 건의 `body`가 `None`인가

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
from secretary.extract import fetch_body
body = fetch_body('https://simonwillison.net/', timeout=20)
print('len =', len(body) if body else None)
assert body is None or len(body) >= 300
print('ok')
"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: `extract.py`의 어떤 경로에서도 예외가 호출자에게 전파되지 않는가 / spec 불변 조건 1(본문 없으면 요약 금지)을 위해 실패가 `None`으로 명확히 구분되는가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 3을 갱신한다.

## 금지사항

- Playwright, Selenium 등 헤드리스 브라우저를 도입하지 마라. 이유: JS 렌더링 페이지 몇 건을 위해 CI 실행 시간과 의존성이 몇 배가 된다. 추출 실패는 정상적인 결과다.
- 추출 실패 시 제목이나 `summary_hint`를 본문 대용으로 쓰지 마라. 이유: spec 불변 조건 1을 우회하는 경로가 된다.
- 요약이나 번역을 이 모듈에서 하지 마라. LLM은 step 4의 책임이다.
