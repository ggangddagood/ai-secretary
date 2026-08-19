# Step 0: shared-foundation

주식 파이프라인이 복제 없이 재사용할 수 있도록, 텔레그램 HTML 렌더링과 Gemini 호출을 공용
모듈로 추출한다. **이번 step은 리팩터링이며 동작은 전혀 바뀌지 않는다.**

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← 요구 동작의 정본
- `docs/ARCHITECTURE.md`
- `docs/STANDARDS.md` — 특히 "모듈 경계"
- `docs/DECISIONS.md` — ADR-005(모델 교체 시 손댈 파일은 `llm.py` 하나)
- `src/secretary/render.py`, `src/secretary/llm.py`, `src/secretary/telegram.py`
- `tests/test_render.py`, `tests/test_llm.py`, `tests/test_main.py`, `tests/test_telegram.py`

## 왜 이 step이 필요한가

주식 브리핑도 텔레그램 HTML을 만들고 Gemini를 호출한다. 복제하면 두 가지가 깨진다.

- 텔레그램 HTML 이스케이프 규칙은 `docs/BUSINESS_RULES.md`가 정본인데, 구현이 둘로 갈리면
  한쪽만 고쳐진다.
- ADR-005는 "모델 교체가 필요하면 손댈 파일은 `llm.py` 하나"라고 약속했다. 복제하면 그 약속이 깨진다.

## 작업

### 1. `src/secretary/tghtml.py` 신설

텔레그램 메시지를 만들 때 도메인과 무관하게 공용으로 쓰는 상수와 헬퍼를 담는다.
`render.py`에서 아래를 **그대로 옮긴다**. 언더스코어 접두만 떼고 로직은 한 글자도 바꾸지 않는다.

| 이동 전 (`render.py`) | 이동 후 (`tghtml.py`) |
| --- | --- |
| `TELEGRAM_LIMIT` | `TELEGRAM_LIMIT` |
| `ELLIPSIS` | `ELLIPSIS` |
| `MAX_FIELD_CHARS` | `MAX_FIELD_CHARS` |
| `KST` | `KST` |
| `_escape` | `escape` |
| `_attr` | `attr` |
| `_text` | `text` |
| `_truncate` | `truncate` |
| `_pack` | `pack` |

모듈 docstring에 "텔레그램 메시지 렌더링 공용 — 이스케이프·길이 제한·4096자 분할"과,
`KST`가 여기 있는 이유(발송 시각이 KST라 UTC로 날짜를 찍으면 하루 전이 나온다)를 적는다.

### 2. `src/secretary/render.py` 수정

- 위 표의 심볼을 삭제하고 `from .tghtml import KST, attr, escape, pack, text` 로 가져온다.
- `AXIS_LABELS`, `_render_header`, `_render_entry`, `render_brief`, `render_failure` 는
  `render.py`에 그대로 남긴다. 호출하는 이름만 `_escape` → `escape` 식으로 바꾼다.
- 모듈 docstring은 유지한다.

### 3. `src/secretary/gemini.py` 신설

`llm.py`에서 아래를 옮긴다.

- `MODEL: Final[str] = "gemini-3.6-flash"`
- `T = TypeVar("T", bound=BaseModel)`
- `_generate` → `generate(client, system, user, expected)` — 로직 불변
- **신설**: `make_client(api_key: str) -> genai.Client` — 키를 문자열로 직접 받는다.
  `llm.make_client`(`Config`를 받는다)와 시그니처가 다르다는 점에 주의한다.

모듈 docstring에 "출력 스키마는 `response_format`으로만 전달한다. 프롬프트에 스키마를 다시
적으면 중복 전달되어 품질이 떨어진다"는 기존 주의를 옮겨 적는다.

### 4. `src/secretary/llm.py` 수정

- `MODEL`, `_generate`, `T` 를 삭제하고 `from .gemini import generate` 로 가져온다.
- **`make_client(cfg: Config) -> genai.Client` 는 이름도 시그니처도 그대로 유지한다.**
  내부만 `return gemini_make_client(cfg.gemini_api_key)` 로 위임한다. 이름 충돌을 피하려면
  `from .gemini import make_client as make_gemini_client` 형태로 가져온다.
- `curate`, `summarize`, Pydantic 모델들은 그대로 둔다. `_generate(` 호출을 `generate(` 로만 바꾼다.

### 5. `src/secretary/telegram.py` 수정 — 타입 힌트만

`StocksConfig`도 받을 수 있도록 파라미터 타입을 Protocol로 넓힌다. **런타임 동작은 불변이다.**

```python
class TelegramTarget(Protocol):
    telegram_bot_token: str
    telegram_chat_id: str
    http_timeout: float
```

`send_messages(cfg: TelegramTarget, messages: list[str]) -> None` 로 바꾸고, 쓰이지 않게 된
`from .config import Config` import를 제거한다(남기면 ruff F401).

### 6. `tests/test_render.py` import 1줄 조정

`TELEGRAM_LIMIT`의 출처가 바뀌었으므로 import만 고친다.

```python
from secretary.render import render_brief, render_failure
from secretary.tghtml import TELEGRAM_LIMIT
```

**assertion은 한 줄도 바꾸지 않는다.** 테스트 개수도 그대로다.

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "from secretary.tghtml import TELEGRAM_LIMIT, escape, attr, text, pack, truncate, KST; print('tghtml ok')"
python -c "from secretary.gemini import MODEL, generate, make_client; print('gemini ok')"
python -c "from secretary.llm import make_client; import inspect; print(inspect.signature(make_client))"
pytest -q 2>&1 | tail -3
```

- `pytest`가 **67 passed** 여야 한다. 개수가 줄면 테스트를 지운 것이고, 늘면 이번 step의 범위를 넘은 것이다.
- 마지막 명령의 출력이 `(cfg: 'Config') -> 'genai.Client'` 형태여야 한다 — `make_client`가 여전히
  `Config`를 받는다는 증거다.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다:
   - 통과 → `"completed"` + `"summary"`
   - 3회 수정 후에도 실패 → `"error"` + `"error_message"`
   - 사용자 개입 필요 → `"blocked"` + `"blocked_reason"` 후 즉시 중단

## 금지사항

- 함수 내부 로직을 바꾸지 마라. 이번 step은 **이동뿐**이다. 이유: 동작이 바뀌면 기존 67건이
  그것을 잡아 줘야 하는데, 커버되지 않는 미묘한 변경이 조용히 들어갈 수 있다.
- `llm.make_client(cfg)`의 시그니처를 바꾸지 마라. 이유: `tests/test_main.py`가
  `monkeypatch.setattr(main_module, "make_client", lambda config: object())`로 패치한다. 시그니처가
  바뀌면 그 테스트가 실제 코드와 어긋난 채 통과한다.
- `AXIS_LABELS`·`_render_entry`·`_render_header`를 `tghtml.py`로 옮기지 마라. 이유: AI 브리핑
  도메인이며 주식 브리핑은 전혀 다른 레이아웃을 쓴다.
- `src/secretary/stocks/` 를 만들지 마라. 이번 step의 범위가 아니다 (step 1부터).
- 기존 테스트의 assertion을 바꾸지 마라. 허용되는 수정은 `tests/test_render.py`의 import 경로 한 곳뿐이다.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
