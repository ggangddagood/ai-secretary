# 엔지니어링 노트

> 작성 기준: 모르면 당하는 것만. 코드만 읽어서 알 수 있는 것은 쓰지 않는다. 각 항목은 증상 → 원인 → 대응. 체크리스트는 "X를 하라"에서 끝내지 말고 "Y로 검증하라"까지. 첫 사이클엔 얇아도 된다 — 발견할 때마다 쌓는다.

## 함정

### 죽은 RSS 피드는 예외가 아니라 빈 결과로 나타난다

- 증상: 피드 URL이 HTTP 200을 주는데 수집 항목이 0건이다. `raise_for_status()`도 통과한다.
- 원인: 사이트가 피드를 폐지하면 XML 대신 HTML 페이지(쿠키 배너 등)를 200으로 준다. feedparser는 이때 예외를 던지지 않고 `bozo=1` + `entries=[]`를 돌려준다.
- 대응: `sources/base.py:parse_feed`가 `feed.bozo`를 경고 로그로 남긴다. 피드를 추가할 때는 HTTP 상태가 아니라 `feedparser.parse(...).entries` 길이로 검증한다.

### 저빈도 피드는 24시간 창에서 대부분 0건이다

- 증상: RSS 그룹은 20건 넘게 모으는데 그중 대부분이 Show HN이고, OpenAI/Google AI/Latent Space는 0건인 날이 많다.
- 원인: 24시간 수집 창(`sources.RECENT_WINDOW`)보다 발행 주기가 길다. 피드가 죽은 것이 아니다.
- 대응: 0건을 고장으로 오해하지 않는다. 특정 피드가 정말 죽었는지는 위 항목의 `bozo` 경고로 판단한다.

### `secretary/http.py`는 표준 라이브러리 `http`를 가리지 않는다

- 증상: 패키지 안에 `http.py`가 있으면 stdlib `http`를 덮어쓸 것처럼 보인다.
- 원인: Python 3는 절대 임포트가 기본이라 `import http`는 항상 stdlib를 찾고, 이 모듈은 `secretary.http`로만 접근된다.
- 대응: 패키지 안에서는 `from ..http import make_client`처럼 상대 임포트로만 쓴다. 이 규칙을 지키는 한 httpx 내부의 `import http`도 정상 동작한다.

## 반복 작업 체크리스트

### RSS 피드 추가/교체

1. 후보 URL을 실제로 GET → 검증: HTTP 200이면서 `feedparser.parse(r.content).entries`가 1건 이상
2. `sources/rss.py`의 `RSS_FEEDS`에 `(표시명, URL)` 추가 → 검증: `bash scripts/verify.sh` exit 0 (`test_rss_keeps_reading_after_one_feed_fails`가 피드 수에 연동됨)
3. 제외한 후보가 있으면 사유를 `docs/tracking/FINDINGS.md`에 기록
