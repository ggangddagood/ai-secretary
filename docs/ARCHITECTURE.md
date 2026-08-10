# 아키텍처

> 작성 기준: 시스템 수준만 — 컴포넌트가 무엇이고 어떻게 연결되는지. 도메인 규칙은 BUSINESS_RULES.md에, 코드 컨벤션은 STANDARDS.md에 쓴다. "모던한 아키텍처를 쓴다" 같은 수식어가 아니라 A → B → C의 구체적 연결과 프로토콜을 적는다.

## 디렉토리 구조

```
src/secretary/
├── main.py            # 배치 오케스트레이션 (순서 + 실패 정책). CLI 진입점
├── __main__.py        # `python -m secretary` 진입점
├── config.py          # 환경 변수 로딩·검증. os.environ을 읽는 유일한 곳
├── models.py          # Item / Article / BriefEntry / Brief
├── http.py            # 공유 httpx 클라이언트 (타임아웃, User-Agent, 리다이렉트)
├── log.py             # 로깅 설정
├── sources/           # 수집
│   ├── __init__.py    #   collect_all — 소스별 실패 흡수 + URL 중복 제거 + score 정렬
│   ├── base.py        #   Source 프로토콜, 피드/시각 파싱 헬퍼, describe_error
│   ├── hackernews.py  #   Algolia Search API
│   ├── geeknews.py    #   news.hada.io RSS
│   ├── github.py      #   GitHub Search API
│   └── rss.py         #   지정 RSS 피드 목록
├── state.py           # 발송 기록 (URL 정규화, sha1 키, 원자적 저장, 90일 prune)
├── extract.py         # 원문 본문 추출 (trafilatura)
├── llm.py             # Gemini 호출 — curate(선별) / summarize(요약)
├── render.py          # 텔레그램 HTML 렌더링 + 4096자 분할
└── telegram.py        # sendMessage 발송 + 봇 토큰 마스킹

state/seen.json        # 발송 기록 (리포지토리에 커밋된다)
tests/                 # pytest. 외부 호출은 monkeypatch로 대체
.github/workflows/daily.yml  # cron 실행 + seen.json 커밋
```

## 컴포넌트와 연결

- 실행 주체는 GitHub Actions cron 하나다. 서버도, 상주 프로세스도, 수신 엔드포인트도 없다.
- 배치는 나가는 HTTP만 쓴다: Algolia(HN) · news.hada.io · api.github.com · 각 RSS 피드 ·
  기사 원문 사이트 · Gemini API(`google-genai` SDK) · api.telegram.org.
- 상태는 파일 하나(`state/seen.json`)다. 실행이 끝나면 워크플로가 변경분을 리포지토리에 커밋한다.
- 시크릿은 GitHub Secrets → 워크플로 `env` → `config.py` 경로로만 들어온다.

## 대표 흐름 1개

이 배치에는 흐름이 하나뿐이다 — 하루치 브리핑 발송(`secretary.main.run`).

```
cron(0 23 * * *) → python -m secretary.main
  1. 수집       sources.collect_all — 4개 소스 병렬 아닌 순차 조회, 실패한 소스는 warning 후 건너뜀
                 → URL 중복 제거 → score 내림차순 정렬
  2. 중복 제거   state.load_seen + filter_unseen — 발송 기록에 있는 URL 키 제외
                 → 후보 0건이면 PipelineError
  3. 선별       llm.curate — 상위 40건만 모델에 전달, count건 선택(축 + 선정 이유)
                 → 후보 목록에 없는 URL은 폐기
  4. 본문 추출   extract.extract_articles — 항목별 GET → trafilatura
                 → 실패하면 body=None으로 목록에 남긴다
  5. 요약       llm.summarize — body가 있는 항목만 1회 호출로 요약
                 → body 없는 항목은 요약 없이 BriefEntry 조립
  6. 렌더       render.render_brief — 텔레그램 HTML, 4096자 초과 시 항목 경계에서 분할
  7. 발송       telegram.send_messages — 조각을 순서대로 sendMessage
  8. 상태 저장   state.mark_seen → prune(90일) → save_seen (발송 성공 뒤에만)
  → exit 0
```

실패 경로: 1~6 중 어디서 실패해도 `render_failure` 메시지를 텔레그램으로 보내고 exit 1.
7에서 실패하면 발송 기록을 갱신하지 않고 exit 1 — 실패 알림도 보내지 않는다(같은 채널이 죽었다).
`--dry-run`은 6까지 하고 stdout에 출력한 뒤 exit 0. 7·8을 건너뛴다.

## 패턴

- 각 소스는 `Source` 프로토콜(`name`, `fetch(since, timeout)`)만 만족하면 된다. 등록 지점은
  `sources/build_sources()` 한 곳.
- LLM 출력은 Pydantic 모델을 JSON Schema로 강제한다(`response_format`). 자유 텍스트 파싱 없음.
- 실패는 계층별로 다르게 다룬다: 소스 실패는 흡수(warning), 본문 추출 실패는 정상 결과(`None`),
  선별·요약·발송 실패는 예외로 올려 `main`이 정책을 적용한다.

## 상태 관리

- 런타임 상태는 없다. 프로세스가 시작할 때 `state/seen.json`을 읽고, 성공하면 다시 쓴다.
- 저장은 임시 파일 → `os.replace`로 원자적으로 한다. 중간에 죽어도 파일이 깨지지 않는다.
- 기록은 URL의 sha1 키 → 발송 날짜 맵이다. 90일이 지난 항목은 저장 시점에 지운다.
