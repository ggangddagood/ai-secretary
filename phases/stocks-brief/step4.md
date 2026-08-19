# Step 4: llm

수집한 헤드라인만을 근거로 급등락 해설을 만든다. **근거 없는 해설은 만들지 않는다.**

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 특히 "급등락 해설", "불변 조건", "엣지 케이스"
- `docs/BUSINESS_RULES.md` — "요약 규칙"(본문 없으면 모델에 보내지 않는다)의 정신을 따른다
- `docs/DECISIONS.md` — ADR-004(근거 없는 요약을 만들지 않기 위해 호출을 나눈 이유)
- `src/secretary/gemini.py` (step 0 산출물) — `generate`, `make_client(api_key)`, `MODEL`
- `src/secretary/llm.py` — 프롬프트 작성과 Pydantic 스키마 강제 방식
- `src/secretary/stocks/models.py` — `Quote`, `Headline`
- `tests/test_llm.py` — `FakeClient`로 `client.interactions.create`를 흉내 내는 방식

## 작업

### `src/secretary/stocks/llm.py` 신설

```python
class CommentOut(BaseModel):
    symbol: str
    comment_ko: str

class CommentResult(BaseModel):
    comments: list[CommentOut]

def explain_moves(
    client: genai.Client,
    movers: Sequence[tuple[Quote, list[Headline]]],
) -> dict[str, str]: ...
```

- **헤드라인이 빈 종목은 프롬프트에 넣지 않는다.** 이것이 이 step의 CRITICAL 규칙이다.
  근거 없이 "왜 올랐나"를 쓰게 하면 모델이 지어낸다. 기존 파이프라인이 본문 없는 항목을
  아예 모델에 보내지 않는 것과 같은 구조적 방어다.
- 헤드라인이 있는 종목이 하나도 없으면 **호출하지 않고** 빈 dict를 돌려준다.
- 한 번의 호출로 전체를 처리한다(종목마다 호출하지 않는다).
- 응답 중 프롬프트에 넣지 않은 심볼의 해설은 폐기한다(warning 로그). 모델이 만들어낸 것이다.
- 반환은 `{심볼: 해설}`이며, 해설을 받지 못한 심볼은 키가 없다.
- 호출 실패는 **예외를 그대로 올린다.** 정책(해설 없이 발송)은 step 6의 `main`이 정한다
  — STANDARDS의 "선별·요약 실패는 예외로 올려 `main`이 정책을 적용한다"와 같다.

### 프롬프트

시스템 프롬프트에 담을 것:

- 역할: 한국 개인 투자자에게 그날의 주가 움직임을 설명하는 편집자
- **주어진 헤드라인만 근거로 삼는다. 헤드라인에 없는 사실을 쓰지 마라. 배경 지식으로 빈 곳을 채우지 마라.**
- 헤드라인이 등락의 이유를 설명하지 못하면, 이유를 지어내지 말고 헤드라인이 전하는 소식을
  그대로 한 줄로 요약해라.
- `comment_ko`는 한국어 한 문장이다.
- **매수·매도 의견, 목표가, 투자 판단을 쓰지 마라.**
- `symbol`은 입력에 주어진 값을 그대로 돌려준다.

사용자 메시지에는 종목마다 심볼·표시명·등락률과 헤드라인 제목 목록을 넣는다.

`llm.py`의 기존 주의를 지킨다: **프롬프트에 JSON 스키마나 예시 JSON을 다시 적지 않는다.**
스키마는 `generate(...)`의 `expected` 인자로만 전달된다.

### `tests/test_stocks_llm.py` 신설

`tests/test_llm.py`의 `FakeClient` 방식을 그대로 쓴다. **실제 API를 호출하지 않는다.**

최소 아래를 덮는다.

- 헤드라인이 있는 종목만 프롬프트에 들어간다 — `client.interactions.calls`에 기록된 입력 문자열에
  헤드라인 없는 종목의 심볼이 **나타나지 않는다**
- 모든 종목의 헤드라인이 비면 **호출 자체가 일어나지 않고** 빈 dict가 돌아온다
  (`calls`가 비어 있는지로 검증한다)
- 프롬프트에 없던 심볼의 해설이 응답에 오면 폐기된다
- 정상 응답 → `{심볼: 해설}` 매핑이 맞다
- 응답에 일부 종목이 빠져도 예외 없이 나머지가 돌아온다

## Acceptance Criteria

```bash
bash scripts/verify.sh
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. **특히 확인한다**: 헤드라인 없는 종목이 어떤 경로로도 프롬프트에 들어가지 않는가.
4. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다.

## 금지사항

- 헤드라인이 없는 종목을 프롬프트에 넣지 마라 (CRITICAL). 이유: 모델이 등락 이유를 지어낸다.
  이 파이프라인에서 가장 치명적인 실패다.
- 모델에게 투자 의견·목표가·매매 판단을 요청하지 마라.
- 종목마다 따로 호출하지 마라. 이유: 호출 수가 종목 수만큼 늘어난다. 한 번에 묶는다.
- 프롬프트에 JSON 스키마나 예시 JSON을 적지 마라. 이유: `response_format`과 중복 전달되어
  출력 품질이 떨어진다 (`llm.py` 모듈 docstring 참조).
- LLM 실패를 여기서 흡수하지 마라. 예외를 올린다. 정책은 step 6의 `main`이 정한다.
- 테스트가 실제 API를 호출하게 하지 마라.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
