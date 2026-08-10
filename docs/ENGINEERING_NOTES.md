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

### (anthropic SDK 한정) `messages.parse()`에 `output_config`만 주면 `parsed_output`이 조용히 `None`이다

- 적용 범위: step 4에서 LLM을 Gemini로 바꿔 현재 코드에 anthropic SDK는 없다. 되돌리거나 병행할 때만 유효한 지식이다.
- 증상: `client.messages.parse(..., output_config={"format": 스키마})`로 호출하면 API는 정상 응답하는데 `response.parsed_output`이 항상 `None`이다. 에러도 경고도 없다.
- 원인: anthropic SDK(0.121.0)의 `parse()`는 `output_format=` 인자로 받은 타입으로만 응답 텍스트를 검증한다. `output_config`는 요청 본문에 그대로 실려 가지만 응답 파싱에는 관여하지 않는다.
- 대응: `parse()`를 쓸 때는 Pydantic 모델을 `output_format=`으로 넘긴다. 원시 JSON 스키마를 직접 넘겨야 하면 `messages.create(output_config=...)` + 직접 파싱이지, `parse()`가 아니다.

### httpx 예외 메시지에는 요청 URL이 그대로 들어간다 — 텔레그램 URL은 봇 토큰이다

- 증상: 발송이 실패하면 로그나 스택트레이스에 `https://api.telegram.org/bot<진짜토큰>/sendMessage`가 찍힌다. `raise_for_status()`가 던지는 `HTTPStatusError`가 대표적이다.
- 원인: 텔레그램은 인증을 헤더가 아니라 경로에 담는다. URL을 남기는 모든 경로(예외 메시지, `__context__`로 이어진 원인 예외, 로그)가 토큰 유출 경로가 된다.
- 대응: `secretary/telegram.py`는 `raise_for_status()`를 쓰지 않고 응답 JSON의 `ok`를 직접 본다. httpx 예외는 `TelegramError`로 감싸 `from None`으로 원인을 끊고, 메시지에 토큰 문자열을 `***`로 치환한다. 로그에는 상수 `MASKED_URL`만 남긴다. 검증: `tests/test_telegram.py::test_bot_token_never_appears_in_errors_or_logs`

### 텔레그램 포맷은 MarkdownV2가 아니라 HTML을 쓴다

- 증상: MarkdownV2로 보내면 요약 문장 하나 때문에 `400 Bad Request: can't parse entities`로 발송이 통째로 실패한다. 어느 글자가 문제인지는 응답에 나오지 않는다.
- 원인: MarkdownV2는 `_ * [ ] ( ) ~ \` > # + - = | { } . !` 를 전부 이스케이프해야 한다. 요약 문장에 흔한 마침표·하이픈·괄호가 전부 여기 들어간다. 한 글자만 놓쳐도 실패다.
- 대응: `parse_mode=HTML`을 쓴다. 이스케이프 대상이 `&`, `<`, `>` 셋(링크 속성값은 `"`까지)뿐이라 놓칠 여지가 없다. `render.py:_escape`/`_attr`가 담당한다. 검증: `tests/test_render.py::test_special_characters_are_escaped`

### 전달 채널로 카카오톡을 쓰지 않은 이유는 취향이 아니라 제약이다

- 증상: "나에게 보내기"로 만들면 브리핑이 잘려 도착하고, 몇 주 뒤 배치가 조용히 실패하기 시작한다.
- 원인: 카카오톡 기본 텍스트 템플릿은 200자 제한이다(브리핑 1건도 못 담는다). 그리고 access token 6시간 / refresh token 약 2개월마다 재인증이 필요해, 무인 배치는 사람이 다시 로그인해 줄 때까지 멈춘다.
- 대응: 텔레그램 봇을 쓴다. 토큰 하나, 만료 없음, 메시지 4096자, HTML 포맷. 카카오톡을 다시 검토한다면 200자 제한과 토큰 갱신 방법부터 확인한다.

### Threads/X/Reddit은 "안 만든 것"이 아니라 "승인 없이 못 만드는 것"이다

- 증상: 수집 소스에 소셜이 없어 커버리지가 얇아 보인다. 추가하려 들면 며칠이 사라진다.
- 원인: Threads 키워드 검색은 Meta App Review + 비즈니스 인증을 요구한다. Reddit은 신규 OAuth 앱이 수동 승인 대기에 걸린다는 보고가 반복된다. 둘 다 코드 문제가 아니라 심사 문제다.
- 대응: 승인 없이 즉시 동작하는 소스만 쓴다(HN Algolia, GeekNews, GitHub Search, 공개 RSS). 소셜을 추가하려면 심사 소요를 별도 작업으로 잡는다.

### 확인된 죽은/제외 피드

추가 후보를 검토할 때 다시 시도하지 않도록 남긴다. 판단 근거는 위 "죽은 RSS 피드" 항목의 검증법.

| 피드 | 상태 |
| --- | --- |
| `https://www.indiehackers.com/feed.xml` | HTTP 200 + HTML(쿠키 배너). `entries=0`. 폐지된 것으로 보임 |
| `https://www.indiehackers.com/rss` | 위와 동일 |

대체로 Lenny's Newsletter(`https://www.lennysnewsletter.com/feed`)를 넣었다. 마케팅 축이 계속 얇으면 TLDR Marketing(`https://tldr.tech/api/rss/marketing`, 20건 확인)이 다음 후보다.

### `.env`는 자동으로 로드되지 않는다

- 증상: `.env`에 키를 채웠는데 로컬 실행이 "필수 환경 변수가 없습니다"로 죽는다.
- 원인: python-dotenv를 쓰지 않는다. `config.py`는 `os.environ`만 읽고, GitHub Actions는 워크플로 `env`로 주입하므로 배치 경로에는 `.env`가 필요 없다.
- 대응: 로컬에서는 `set -a; source .env; set +a`로 직접 export한 뒤 실행한다.

### `workflow_dispatch`는 워크플로 파일이 기본 브랜치에 있어야 뜬다

- 증상: 기능 브랜치에 `daily.yml`을 만들고 push했는데 `gh workflow run daily-brief`가 워크플로를 찾지 못한다.
- 원인: GitHub은 `workflow_dispatch` 대상 목록을 기본 브랜치의 워크플로 파일에서 만든다. 다른 브랜치의 파일은 목록에 없다(`--ref`로 실행 대상 ref를 고르는 것과 별개다).
- 대응: 수동 실행으로 검증하려면 워크플로 파일을 먼저 기본 브랜치에 머지한다.

## 반복 작업 체크리스트

### RSS 피드 추가/교체

1. 후보 URL을 실제로 GET → 검증: HTTP 200이면서 `feedparser.parse(r.content).entries`가 1건 이상
2. `sources/rss.py`의 `RSS_FEEDS`에 `(표시명, URL)` 추가 → 검증: `bash scripts/verify.sh` exit 0 (`test_rss_keeps_reading_after_one_feed_fails`가 피드 수에 연동됨)
3. 제외한 후보가 있으면 사유를 `docs/tracking/FINDINGS.md`에 기록
