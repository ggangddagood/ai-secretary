# Step 4: llm-curate-summarize

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본 (4개 축, 불변 조건 1번)
- `src/secretary/models.py` (step 0 — `Item`, `Article`, `BriefEntry`, `AXES`)
- `src/secretary/extract.py` (step 3)
- `src/secretary/config.py` (step 0)

## 작업

Claude API를 2단계로 호출한다. **1단계 선별 → (step 3의 본문 추출) → 2단계 요약.** 이 순서를 합치지 마라.

### `src/secretary/llm.py`

```python
MODEL = "claude-opus-5"

class Selection(BaseModel):          # pydantic
    url: str
    axis: Literal["tech", "money", "enterprise", "marketing"]
    reason_ko: str                    # 왜 골랐는지 한 줄 (로그용)

class SelectionResult(BaseModel):
    selections: list[Selection]

class SummaryOut(BaseModel):
    url: str
    subtitle_ko: str                  # 한국어 한 줄 부제
    summary_ko: list[str]             # 정확히 3줄
    action_hint_ko: str               # "너라면 이렇게 써먹어라" 한 줄

class SummaryResult(BaseModel):
    summaries: list[SummaryOut]

def curate(client, candidates: list[Item], *, count: int) -> list[Selection]: ...
def summarize(client, articles: list[Article], selections: list[Selection]) -> list[BriefEntry]: ...
```

- Anthropic SDK의 구조화 출력을 쓴다: `client.messages.parse(model=MODEL, max_tokens=..., messages=[...], output_config={"format": <schema>})` 형태로 호출하고 `response.parsed_output`을 읽는다. 자유 텍스트를 정규식으로 파싱하지 마라.
- `MODEL`은 모듈 상수로 두고 하드코딩 위치를 한 곳으로 제한한다.
- `max_tokens`는 넉넉히 잡는다(선별 8000, 요약 16000). `claude-opus-5`는 thinking이 기본 on이고 `max_tokens`가 thinking+응답을 함께 제한하므로 빠듯하게 잡으면 응답이 잘린다.

#### `curate` (1단계)

- 후보를 최대 40건으로 자른다(`score` 상위순). 각 후보는 `제목 / 출처 / URL / summary_hint(있으면 200자)` 만 전달한다. 본문은 아직 없다.
- 시스템 프롬프트에 담을 것:
  - 독자는 AI를 활용해 수익을 내려는 1인 개발자다.
  - 4개 축(`tech`, `money`, `enterprise`, `marketing`)의 정의는 spec "요구 동작"의 정의를 그대로 쓴다.
  - **가능하면 최소 3개 축이 포함되도록 고르되, 축을 채우려고 품질이 낮은 항목을 넣지는 마라.** 우선순위는 유용성이다.
  - 단순 뉴스 헤드라인(자금 조달, 인사, 주가)보다 실제로 따라 할 수 있는 내용을 우선한다.
  - 반드시 후보 목록에 있는 URL만 반환한다.
- 반환된 URL이 후보에 없으면 그 항목은 버리고 `logger.warning`을 남긴다. 결과가 `count`를 초과하면 앞에서부터 자른다.

#### `summarize` (2단계)

- 입력은 step 3이 만든 `Article` 목록.
- **`article.body`가 `None`인 항목은 LLM에 보내지 않는다.** `BriefEntry(summary_ko=[], action_hint_ko=None, subtitle_ko="")`로 직접 만든다. (spec 불변 조건 1)
- 본문이 있는 항목만 한 번의 호출로 묶어 요약한다.
- 요약 지침:
  - 3줄 각각은 완결된 한국어 문장. 본문에 없는 사실을 쓰지 마라.
  - `action_hint_ko`는 "이 독자가 내일 뭘 해볼 수 있는지" 한 문장.
  - 원문 제목은 번역하지 않는다(`BriefEntry.title`은 `Item.title` 그대로). `subtitle_ko`가 한국어 설명 역할을 한다.
- 반환 항목을 URL로 매칭해 `BriefEntry`를 조립한다. LLM이 빠뜨린 URL은 본문 없음과 동일하게 처리한다.

### 에러 정책

- SDK는 429/5xx를 기본 재시도한다. 그 이후에도 실패하면 예외를 그대로 올린다. **여기서 삼키지 마라** — step 6의 파이프라인이 실패 알림 발송을 책임진다.

### 테스트 `tests/test_llm.py`

**실제 API를 호출하지 않는다.** Anthropic 클라이언트를 가짜 객체로 주입한다(그래서 `curate`/`summarize`는 `client`를 인자로 받는다):

- `curate`: 가짜 응답이 후보에 없는 URL을 섞어 반환하면 그 항목이 걸러지는가
- `curate`: 반환 개수가 `count`를 넘으면 잘리는가
- `summarize`: `body=None`인 항목이 **LLM 호출 페이로드에 포함되지 않는가** ← 이 테스트는 반드시 있어야 한다 (불변 조건 1)
- `summarize`: `body=None`인 항목의 `BriefEntry.summary_ko`가 `[]`이고 `action_hint_ko`가 `None`인가
- `summarize`: LLM이 일부 URL을 빠뜨려도 나머지 항목이 정상 조립되는가

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
import inspect, secretary.llm as m
src = inspect.getsource(m)
assert 'claude-opus-5' in src, 'model id missing'
print('ok')
"
```

실제 API 연동 확인은 step 6의 `--dry-run` 스모크에서 한다.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: `body=None` 항목이 LLM 호출에서 제외되는 테스트가 실제로 통과하는가 / 자유 텍스트 파싱(정규식, `json.loads` 후처리 루프)이 없는가 / 프롬프트에 시크릿이나 사용자 식별 정보가 들어가지 않는가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 4를 갱신한다.

## 금지사항

- 선별과 요약을 1회 호출로 합치지 마라. 이유: 제목만 보고 요약을 지어내는 환각이 발생한다. spec 불변 조건 1 위반이다.
- 본문 없는 항목을 요약 대상에 넣지 마라. 이유: 위와 같다.
- 모델을 더 저렴한 등급으로 바꾸지 마라. 이유: 하루 1회 호출이라 절약 효과가 미미하고, 모델 선택은 사용자 결정 사항이다.
- LLM 예외를 모듈 안에서 삼키고 빈 결과를 반환하지 마라. 이유: 조용히 아무것도 발송되지 않는 경로가 생긴다.
- 프롬프트를 파일 밖(예: DB, 외부 설정)으로 빼지 마라. 이유: 요청되지 않은 유연성이다.
