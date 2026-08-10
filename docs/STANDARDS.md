# 표준과 규칙

> 작성 기준: 위반하면 무언가 깨지는 규칙만 (빌드 실패, 테스트 실패, 런타임 에러, 구조 파손). 위반 여부를 판정할 수 없는 문장은 규칙이 아니다. 취향("~하면 좋다")은 쓰지 않는다. 이유는 규칙이 직관에 반할 때만 덧붙인다.

## 검증 게이트

- 머지 전: `bash scripts/verify.sh` exit 0 (`ruff check .` + `ruff format --check .` + `pytest -q`)
- 새 기능은 테스트를 먼저 작성하고 통과시킨다. 외부 HTTP·LLM 호출은 monkeypatch로 대체한다 —
  테스트가 네트워크에 나가면 안 된다.
- 소스·발송·시크릿 취급을 바꿨으면 `python -m secretary.main --dry-run` exit 0까지 확인한다.
  단위 테스트는 실제 피드가 죽은 것을 잡지 못한다.

## 모듈 경계

- `sources/`는 `llm`, `telegram`, `render`, `extract`, `main`을 import 하지 않는다. 수집은 아래
  단계를 몰라야 하고, 항목을 걸러내지도 않는다 — 선별은 LLM 단계의 책임이다.
- 반대 방향은 허용한다. `extract`·`telegram`이 `sources.base.describe_error`를 쓰는 것은 정상이다.
- `os.environ`을 읽는 모듈은 `config.py` 하나다. 다른 모듈은 `Config`를 인자로 받는다 —
  이유: 어디서 무엇을 읽는지 흩어지면 누락된 변수가 실행 한참 뒤에 터진다.
- SDK가 환경 변수를 직접 읽게 두지 않는다. Gemini 클라이언트는 `make_client(cfg)`로 키를 주입한다.
- `main.py`는 순서와 실패 정책만 정한다. 도메인 로직을 여기 두지 않는다.
- 외부 HTTP는 `http.make_client(timeout)`을 쓴다. 모듈마다 `httpx.Client`를 새로 조립하지 않는다.

## 실패 처리

- 소스 하나의 실패는 `collect_all`이 warning으로 흡수한다. 전체 실행을 중단시키지 않는다.
- 본문 추출 실패는 예외가 아니라 `None`이다. `fetch_body`는 호출자에게 예외를 던지지 않는다.
- 발송 기록 저장은 `send_messages`가 성공으로 반환한 뒤에만 호출한다.
- 실패로 끝나는 모든 경로는 사용자에게 메시지를 보낸다. 예외는 텔레그램 발송 실패 하나뿐이다
  (같은 채널이 죽었으므로 보낼 곳이 없다).

## 시크릿

- 시크릿 값을 코드·워크플로 파일·문서·테스트에 하드코딩하지 않는다. 이름만 적는다.
- 예외 메시지와 로그에 요청 URL을 그대로 남기지 않는다. 텔레그램 URL에는 봇 토큰이 들어 있다.
- 상세는 `SECURITY.md`.

## 커밋/브랜치

- 커밋 메시지는 conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`)
- 작업은 `feat-<task>` 브랜치에서 한다. `main` 직접 커밋 금지.
- 워크플로가 만드는 상태 커밋은 `chore: update seen state` 하나뿐이다.

## 네이밍/구조

- 소스 클래스는 `<이름>Source`, 클래스 속성 `name`과 `fetch(*, since, timeout)`을 갖는다.
  등록은 `sources/__init__.py`의 `build_sources()` 한 곳에서만 한다.
- 모듈 밖으로 나가는 상수는 `typing.Final`로 선언한다.
- 데이터 구조는 `models.py`의 frozen dataclass다. LLM 입출력 스키마만 Pydantic 모델을 쓴다.
- 한국어 필드는 `_ko` 접미사를 붙인다(`summary_ko`, `action_hint_ko`).
