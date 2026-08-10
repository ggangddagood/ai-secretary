# Step 4: llm-curate-summarize

> **이 step은 재실행이다.** 앞선 실행에서 이 레이어를 Anthropic Claude API로 이미 구현했으나, 사용자가 유료 API 결제 없이 시작하기로 결정해 **LLM 제공자를 Google Gemini로 교체**한다. 기존 `src/secretary/llm.py`를 읽고 **함수 시그니처와 동작 계약은 그대로 유지한 채 제공자만 갈아끼운다.** step 5·6이 이 인터페이스에 의존하고 있으므로 시그니처를 바꾸면 그쪽이 깨진다.

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본 (4개 축, 불변 조건 1번, 확정 근거의 Gemini 항목)
- `src/secretary/llm.py` ← **기존 Claude 구현. 프롬프트와 조립 로직은 재사용하고 API 호출부만 교체한다**
- `src/secretary/config.py` (환경 변수 정의)
- `src/secretary/main.py` (클라이언트를 생성해 `curate`/`summarize`에 넘기는 부분)
- `tests/test_llm.py` (기존 가짜 클라이언트 테스트)
- `src/secretary/models.py`, `src/secretary/extract.py`

## 작업

### 1. 의존성 교체

- `pyproject.toml`: `anthropic` 제거, `google-genai` 추가. `pydantic`은 계속 쓴다.
- 설치: `pip install -e ".[dev]"`

### 2. `config.py`

- `anthropic_api_key` 필드를 `gemini_api_key`로 바꾸고, 읽는 환경 변수를 `GEMINI_API_KEY`로 바꾼다.
- 필수 변수 목록과 `tests/test_config.py`의 관련 단언도 함께 고친다.

### 3. `src/secretary/llm.py`

```python
MODEL = "gemini-3.6-flash"

def make_client(cfg: Config): ...     # genai.Client 생성. main.py가 이걸 호출한다
def curate(client, candidates: list[Item], *, count: int) -> list[Selection]: ...
def summarize(client, articles: list[Article], selections: list[Selection]) -> list[BriefEntry]: ...
```

- **Pydantic 모델(`Selection`, `SelectionResult`, `SummaryOut`, `SummaryResult`)은 기존 정의를 그대로 쓴다.**
- SDK 사용법 (공식 문서 확인 결과, 2026-08 기준):

```python
from google import genai

client = genai.Client()          # GEMINI_API_KEY 환경 변수를 읽는다

interaction = client.interactions.create(
    model=MODEL,
    system_instruction=SYSTEM_PROMPT,
    input=user_text,
    response_format={
        "type": "text",
        "mime_type": "application/json",
        "schema": SelectionResult.model_json_schema(),
    },
)
result = SelectionResult.model_validate_json(interaction.output_text)
```

- `genai.Client()`가 환경 변수를 직접 읽더라도, **키는 `config.py`를 거쳐 명시적으로 전달하라**(`genai.Client(api_key=cfg.gemini_api_key)`). 프로젝트 규칙상 다른 모듈이 환경 변수를 직접 읽으면 안 된다.
- **프롬프트에 JSON 스키마를 다시 적거나 예시 JSON을 넣지 마라.** Gemini 공식 문서가 명시적으로 경고하는 안티패턴이다 — 스키마가 중복 전달되어 출력 품질이 떨어진다. 스키마는 `response_format`으로만 전달한다.
- `max_tokens` 계열 파라미터명이 Claude와 다르다. 필요하면 설정하되, 확신이 없으면 넣지 말고 기본값을 쓴다.
- 위 호출 형태가 설치된 SDK 버전과 맞지 않으면 **추측하지 말고** `python -c "from google import genai; help(genai.Client().interactions.create)"` 로 실제 시그니처를 확인해 맞춰라.

### 4. 유지해야 할 동작 계약 (기존 구현에서 그대로 가져온다)

- `curate`: 후보를 최대 40건(`score` 상위순)으로 자른다. 각 후보는 제목·출처·URL·`summary_hint`(200자)만 전달하고 본문은 보내지 않는다. 반환된 URL이 후보에 없으면 버리고 `logger.warning`. `count` 초과 시 절단.
- `summarize`: **`article.body`가 `None`인 항목은 LLM에 보내지 않는다.** `BriefEntry(summary_ko=[], action_hint_ko=None, subtitle_ko="")`로 직접 조립한다. (spec 불변 조건 1)
- 4개 축(`tech`/`money`/`enterprise`/`marketing`) 정의와 선별 기준, 한국어 요약 지침은 기존 프롬프트를 재사용한다.
- LLM 호출 실패는 삼키지 말고 예외를 그대로 올린다. 실패 알림은 `main.py`의 책임이다.

### 5. `main.py` 배선

클라이언트 생성 부분만 `llm.make_client(cfg)` 호출로 교체한다. **파이프라인 순서·에러 정책·`save_seen` 호출 시점은 건드리지 마라.**

### 6. 테스트 `tests/test_llm.py`

기존 테스트 5건은 가짜 클라이언트를 주입하는 구조이므로 **테스트 의도를 그대로 두고 가짜 객체의 응답 형태만 Gemini 형식(`interaction.output_text`)에 맞게 고친다.** 특히 아래는 반드시 유지된다:

- `summarize`가 `body=None` 항목을 **LLM 호출 페이로드에 넣지 않는가**
- `body=None` 항목의 `summary_ko`가 `[]`, `action_hint_ko`가 `None`인가
- `curate`가 후보 밖 URL을 버리는가 / `count`로 절단하는가
- LLM이 일부 URL을 빠뜨려도 나머지가 정상 조립되는가

### 7. 잔여 참조 정리

`grep -rn "anthropic\|claude\|ANTHROPIC" src/ tests/ pyproject.toml` 결과가 비어야 한다. 문서(`docs/`)는 step 7에서 정리하므로 이 step에서는 건드리지 않는다.

## Acceptance Criteria

```bash
pip install -e ".[dev]"
bash scripts/verify.sh
grep -rn "anthropic\|ANTHROPIC" src/ tests/ pyproject.toml ; test $? -eq 1
python -c "
import inspect, secretary.llm as m
assert 'gemini-3.6-flash' in inspect.getsource(m), 'model id missing'
print('ok')
"
```

실제 API 연동 확인은 step 6의 `--dry-run` 스모크에서 한다.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: 기존 테스트 61건이 여전히 통과하는가(줄어들면 안 된다) / `body=None` 항목이 LLM 호출에서 제외되는 테스트가 통과하는가 / `curate`·`summarize`의 시그니처가 그대로라 step 5·6이 안 깨지는가 / 프롬프트에 JSON 스키마나 예시 JSON이 중복되어 있지 않은가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 4를 갱신한다.

## 금지사항

- `curate`/`summarize`의 시그니처와 반환 타입을 바꾸지 마라. 이유: step 5·6이 이미 이 인터페이스에 의존해 완성돼 있다.
- 선별과 요약을 1회 호출로 합치지 마라. 이유: 제목만 보고 요약을 지어내는 환각이 발생한다. spec 불변 조건 1 위반이다.
- 본문 없는 항목을 요약 대상에 넣지 마라. 이유: 위와 같다.
- 프롬프트 안에 JSON 스키마나 예시 출력을 넣지 마라. 이유: Gemini 문서가 경고하는 안티패턴으로 출력 품질이 떨어진다.
- LLM 예외를 모듈 안에서 삼키고 빈 결과를 반환하지 마라. 이유: 조용히 아무것도 발송되지 않는 경로가 생긴다.
- `main.py`의 파이프라인 순서나 에러 정책을 수정하지 마라. 클라이언트 생성 한 줄만 바꾼다.
