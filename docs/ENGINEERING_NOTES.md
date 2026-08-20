# 엔지니어링 노트

> 작성 기준: 모르면 당하는 것만. 코드만 읽어서 알 수 있는 것은 쓰지 않는다. 각 항목은 증상 → 원인 → 대응. 체크리스트는 "X를 하라"에서 끝내지 말고 "Y로 검증하라"까지. 첫 사이클엔 얇아도 된다 — 발견할 때마다 쌓는다.

## 함정

### httpx의 INFO 로그가 텔레그램 봇 토큰을 평문으로 남긴다

- 증상: `telegram.py`가 URL을 `bot***`로 마스킹해 로그를 남기는데도, 바로 다음 줄에 `INFO httpx: HTTP Request: POST https://api.telegram.org/bot<봇ID>:<토큰>/sendMessage` 가 토큰을 통째로 찍는다. 실제로 한 번 유출됐고 봇 토큰을 폐기·재발급해야 했다.
- 원인: 텔레그램은 봇 토큰을 **URL 경로**에 넣는다(헤더가 아니다). httpx는 모든 요청 URL을 INFO로 남기므로 `logging.basicConfig(level=INFO)`를 부르는 순간 우리 마스킹과 무관하게 원본 URL이 로그에 들어간다. GitHub Actions는 등록된 Secret을 자동 마스킹하지만 로컬 실행에는 그 보호가 없다.
- 대응: `log.py`가 두 겹으로 막는다. (1) `_URL_LOGGING_LIBRARIES`(httpx/httpcore/urllib3/google_genai)를 `--verbose`에서도 WARNING으로 고정한다. (2) `SecretRedactingFilter`가 루트 핸들러에 붙어 출력 직전에 `bot<숫자>:<영숫자>` 패턴을 `bot***`로 치환한다. 레벨만 낮추는 1번만으로는 새 의존성이 늘거나 누가 레벨을 되돌리면 다시 샌다.
- 검증: `tests/test_log.py` 6건. 새 HTTP 라이브러리를 추가하면 `_URL_LOGGING_LIBRARIES`에 이름을 넣고, 실제 호출 후 로그에 토큰이 없는지 확인한다.

### `logging.basicConfig()`는 핸들러가 이미 있으면 조용히 무시된다

- 증상: `setup_logging(verbose=True)`를 불렀는데 루트 로거 레벨이 INFO 그대로다. 예외도 경고도 없다.
- 원인: `basicConfig()`는 루트에 핸들러가 하나라도 있으면 아무 일도 하지 않고 반환한다. 테스트에서 두 번 호출하거나, pytest·다른 라이브러리가 먼저 로깅을 구성한 뒤라면 레벨도 포맷도 적용되지 않는다. 위의 마스킹 필터도 함께 빠지므로 보안 문제로 이어진다.
- 대응: `force=True`를 준다. 기존 핸들러를 제거하고 다시 구성하므로 몇 번을 불러도 같은 결과가 된다.

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

### `meta.chartPreviousClose` 는 직전 거래일 종가가 아니다

- 증상: 등락률이 예외도 경고도 없이 틀린다. 숫자가 그럴듯해서 브리핑을 읽어도 눈치채기 어렵다.
- 원인: Yahoo v8 chart의 `meta.chartPreviousClose` 는 **조회 창이 시작되기 이전**의 종가다.
  `range=1mo` 로 부르면 한 달 전 근처의 값이 온다. 실측에서 삼성전자(`005930.KS`)의
  `chartPreviousClose` 는 239500이었는데 실제 직전 거래일 종가는 268500이었다 — 이 값으로
  계산하면 등락률이 +12%로 나간다.
- 대응: `indicators.quote[0].close` 배열에서 `None` 을 제거한 **유효값의 마지막 두 개**로만
  계산한다(`stocks/quotes.py:parse_chart`). `meta` 에서는 타임존과 통화만 읽는다.
- 검증: `tests/test_stocks_quotes.py::test_change_pct_ignores_chart_previous_close` 가 실측값
  그대로(`chartPreviousClose=239500`, 직전 종가 268500) 회귀를 잡는다. 새 필드를 `meta` 에서
  읽고 싶어지면 그 값이 조회 창의 **안**을 가리키는지부터 확인한다.

### Yahoo chart의 `close` 배열에는 `None` 이 섞인다 — 마지막 원소에도 들어온다

- 증상: `closes[-1]` 로 최신 종가를 읽는 코드가 `TypeError` 로 죽거나, 등락률이 `None` 이 된다.
- 원인: 거래가 없었거나 데이터가 아직 채워지지 않은 구간이 `None` 으로 온다. 중간에만 오는 것이
  아니다 — 실측에서 `USDKRW=X` 는 배열 중간에, `035720.KQ`(코스닥)는 **마지막 원소**가
  `None` 이었다. 길이는 `timestamp` 배열과 같으므로 인덱스로 짝지으려면 `None` 위치를 알아야 한다.
- 대응: `(timestamp, close)` 를 짝지은 뒤 `close is None` 인 쌍을 버리고, 남은 유효값이 2개
  이상일 때만 등락률을 만든다. 2개 미만이면 그 심볼은 조회 실패로 처리한다. 기준일도 버리기
  전 인덱스가 아니라 **살아남은 마지막 쌍의 timestamp** 로 잡는다.
- 검증: `tests/test_stocks_quotes.py::test_parse_chart_skips_trailing_none_close` (마지막 원소),
  `::test_parse_chart_skips_none_in_the_middle` (중간),
  `::test_parse_chart_returns_none_with_single_valid_close` (유효값 부족).

### `fiftyTwoWeekHigh` 는 장중 고가라 종가보다 높을 수 있다

- 증상: 52주 고점 대비 하락률(`drawdown_pct`)이 **양수**로 나온다. 정의상 0 이하여야 할 값이라
  버그로 보이고, 0으로 클램프하고 싶어진다.
- 원인: 우리는 `close` 배열의 **종가**로 계산하는데 `meta.fiftyTwoWeekHigh` 는 **장중 고가**를
  포함한 값이다. 기준이 다르므로 종가가 52주 고점을 넘는 날이 실제로 생긴다 — 데이터 오류가
  아니다.
- 대응: 양수를 그대로 둔다. `stocks/quotes.py:fifty_two_week` 는 `range_pct` 만 0~100으로
  클램프하고 `drawdown_pct` 는 손대지 않으며, `stocks/render.py:_format_52w` 가
  `drawdown_pct >= 0` 을 **"52주 신고가"** 로 분기한다. 클램프하면 이 신호가 `-0.0%` 로 뭉개져
  사라진다.
- 검증: `tests/test_stocks_quotes.py::test_fifty_two_week_keeps_positive_drawdown_above_high`
  (종가 105 > 고점 100 → `drawdown_pct` 가 `+5.0`),
  `tests/test_stocks_render.py::test_new_high_replaces_the_range_position` (표시면).

### Yahoo v8 chart는 이 프로젝트의 User-Agent를 거부하지 않는다

- 증상: 시세 API를 붙일 때 "브라우저 User-Agent로 위장해야 한다"는 조언을 먼저 만나게 된다.
- 원인: 그 조언은 대부분 `v7/finance/quote` 엔드포인트 이야기다. 그쪽은 실제로 크리덴셜(crumb)과
  브라우저 헤더를 요구하도록 막혔다. `v8/finance/chart` 는 아직 그렇지 않다.
- 대응: 계획 단계에서 6개 심볼(미국 주식·한국 주식·지수·환율)을 기본 User-Agent
  `ai-secretary/0.1` 로 호출해 전부 HTTP 200을 받았다. 그래서 `http.make_client` 를 그대로 쓴다 —
  위장 헤더를 넣지 않는다. v7/quote로 갈아타지 않는다.
- 검증: 막힌 것 같으면 헤더를 바꾸기 전에 `curl -s -o /dev/null -w '%{http_code}'
  'https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=1mo&interval=1d'` 로 상태
  코드부터 본다. 429면 차단이지 UA 문제가 아니다.

### 미국장 워크플로의 cron 요일은 KST 요일과 하루 어긋난다

- 증상: `stocks-us.yml` 의 `0 22 * * 1-5` 를 보고 "월~금 발송"으로 읽는다. 토요일 아침에 도착한
  브리핑을 보고 cron이 잘못됐다고 판단해 고치려 든다.
- 원인: cron의 요일 필드도 **UTC** 기준이다. 미국장은 KST 새벽 05~06시에 마감하므로 UTC 22:00은
  이미 KST 다음 날 07:00이다. `0 22 * * 1-5`(UTC 월~금)는 **KST 화~토 07:00**에 돌고, 각 실행이
  다루는 것은 그 전날 미국장 종가다. UTC 금요일 실행이 KST 토요일에 미국 금요일장을 보내는 것이
  정상 동작이다. (한국장 `stocks-kr.yml` 의 `0 7 * * 1-5` 는 KST 월~금 16:00으로 요일이 같다 —
  두 파일이 같은 규칙일 것이라고 넘겨짚으면 안 된다.)
- 대응: 두 워크플로의 cron 위에 UTC↔KST 요일 대응을 주석으로 남겨 뒀다. 요일 필드를 KST 기준으로
  고치면 미국 금요일장 브리핑이 통째로 사라진다.
- 검증: `docs/OPERATIONS.md` 의 "발송 시각 변경" 표가 세 워크플로의 UTC cron과 KST 실행 시각을
  나란히 적고 있다. cron을 바꾸면 그 표도 함께 고친다.

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

### 관심 종목 추가/교체

1. Yahoo Finance에서 종목을 검색해 URL의 심볼을 확인한다(한국은 코스피 `.KS` / 코스닥 `.KQ`)
   → 검증: v8 chart를 실제로 호출해 HTTP 200이고 `close` 유효값이 2개 이상인지 본다

   ```bash
   python3 -c "
   import httpx
   sym = '005930.KS'
   r = httpx.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}',
                 params={'range': '1mo', 'interval': '1d'}, timeout=20)
   res = r.json()['chart']['result'][0]
   closes = [c for c in res['indicators']['quote'][0]['close'] if c is not None]
   print(r.status_code, res['meta']['currency'], '유효 종가', len(closes), closes[-2:])
   "
   ```

2. `gh variable set STOCKS_WATCHLIST_US --body "..."` (Secrets가 아니라 Variables다)
   → 검증: `gh variable list` 에 이름과 값이 보인다
3. 검증: `STOCKS_WATCHLIST_US="심볼:표시명" python -m secretary.stocks --market us --dry-run`
   exit 0 이고, 출력에 그 종목이 보인다
4. 표시명은 급등락 해설의 **뉴스 검색어**로 쓰인다. 너무 일반적인 단어(예: `애플`)면 무관한
   기사가 섞일 수 있다 — 급등락이 실제로 잡힌 날 헤드라인이 그 종목 이야기인지 확인한다
