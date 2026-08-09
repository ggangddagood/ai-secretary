# Step 0: project-setup

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본
- `AGENTS.md`
- `scripts/verify.sh` (현재 placeholder 상태)
- `.gitignore`

## 작업

Python 프로젝트 뼈대와 검증 게이트를 만든다.

### 1. `pyproject.toml`

- 프로젝트 이름 `ai-secretary`, `requires-python = ">=3.11"`
- 런타임 의존성: `anthropic`, `httpx`, `feedparser`, `trafilatura`
- 개발 의존성(`[project.optional-dependencies].dev`): `pytest`, `ruff`
- `[tool.ruff]`: `line-length = 100`, lint rule은 기본값 + `I`(import 정렬)
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["src"]`
- 패키지는 `src/` 레이아웃 (`[tool.setuptools.packages.find] where = ["src"]` 또는 hatchling 사용 — 어느 쪽이든 무방)

### 2. `src/secretary/config.py`

```python
@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str
    github_token: str | None
    brief_item_count: int
    state_path: Path
    http_timeout: float

def load_config(*, require_secrets: bool = True) -> Config: ...
```

- spec의 "환경 변수" 표를 그대로 구현한다.
- 필수 변수가 없으면 어떤 변수가 없는지 이름을 모두 모아 한 번에 알려주는 `ConfigError`를 던진다. 하나 고칠 때마다 다시 실행하게 만들지 마라.
- `require_secrets=False`이면 필수 검사를 건너뛴다(테스트·`--dry-run` 일부 경로용). 이때 빠진 값은 빈 문자열로 둔다.
- **에러 메시지와 로그에 변수의 값을 절대 출력하지 마라. 이름만 출력한다.**

### 3. `src/secretary/models.py`

spec의 데이터 흐름에 맞춰 frozen dataclass를 정의한다:

```python
@dataclass(frozen=True)
class Item:
    title: str
    url: str
    source: str                 # "hackernews" | "geeknews" | "github" | "rss:<name>"
    score: int | None           # 소스별 인기 지표 (없으면 None)
    published_at: datetime | None
    summary_hint: str | None    # RSS description 등 소스가 제공한 짧은 설명

@dataclass(frozen=True)
class Article:
    item: Item
    body: str | None            # 본문 추출 실패 시 None

@dataclass(frozen=True)
class BriefEntry:
    title: str                  # 원문 제목(원어 유지)
    subtitle_ko: str            # 한국어 한 줄 부제
    url: str
    source: str
    axis: str                   # "tech" | "money" | "enterprise" | "marketing"
    summary_ko: list[str]       # 3줄. 본문 없으면 빈 리스트
    action_hint_ko: str | None  # 본문 없으면 None

@dataclass(frozen=True)
class Brief:
    generated_at: datetime
    entries: list[BriefEntry]
```

`AXES: Final[tuple[str, ...]] = ("tech", "money", "enterprise", "marketing")` 상수도 이 모듈에 둔다.

### 4. `src/secretary/log.py`

`logging` 기반 최소 설정 함수 `setup_logging(verbose: bool = False)` 하나. 포맷은 `%(asctime)s %(levelname)s %(name)s: %(message)s`. 외부 라이브러리 도입 금지.

### 5. `scripts/verify.sh` 채우기

placeholder 블록과 의도적 실패 부분을 삭제하고 아래로 교체한다:

```bash
ruff check .
ruff format --check .
pytest -q
```

### 6. `.gitignore` 확인

`.env`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/` 가 포함되어 있는지 확인하고 없으면 추가한다. **`state/` 는 절대 무시 목록에 넣지 마라 — 발송 기록은 커밋되어야 한다.**

### 7. `tests/test_config.py`

- 필수 변수가 모두 있으면 `Config`가 정상 생성된다
- 필수 변수가 빠지면 `ConfigError`가 나고, 메시지에 빠진 변수 이름이 **모두** 들어 있다
- `BRIEF_ITEM_COUNT` 미설정 시 기본값 5

`monkeypatch.setenv` / `delenv`로 환경을 조작한다.

## Acceptance Criteria

```bash
pip install -e ".[dev]"
bash scripts/verify.sh
python -c "from secretary.config import load_config; print('ok')"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: `verify.sh`가 exit 0으로 통과하는가 / `os.environ` 참조가 `config.py` 밖에 없는가(`grep -rn "os.environ" src/`) / 시크릿 값이 로그·에러에 출력되지 않는가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 0을 갱신한다.

## 금지사항

- 웹 프레임워크, DB 드라이버, ORM, 설정 라이브러리(pydantic-settings, dynaconf 등)를 추가하지 마라. 이유: 환경 변수 6개를 읽는 데 의존성이 필요 없다.
- `config.py` 외의 모듈에서 `os.environ`을 읽지 마라. 이유: 누락된 변수가 배치 도중 깊은 곳에서 터진다.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
