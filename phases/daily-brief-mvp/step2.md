# Step 2: state-dedupe

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본
- `src/secretary/models.py` (step 0)
- `src/secretary/config.py` (step 0 — `state_path`)
- `src/secretary/sources/__init__.py` (step 1 — `collect_all` 출력 형태)

## 작업

이미 발송한 항목을 다시 보내지 않기 위한 발송 기록(seen store)을 만든다.

### `src/secretary/state.py`

```python
def normalize_url(url: str) -> str: ...
def url_key(url: str) -> str: ...
def load_seen(path: Path) -> dict[str, str]: ...
def save_seen(path: Path, seen: dict[str, str]) -> None: ...
def filter_unseen(items: list[Item], seen: dict[str, str]) -> list[Item]: ...
def mark_seen(seen: dict[str, str], items: Iterable[Item], *, today: date) -> dict[str, str]: ...
def prune(seen: dict[str, str], *, today: date, keep_days: int = 90) -> dict[str, str]: ...
```

- `normalize_url`: 스킴을 https로 통일, 호스트 소문자화, `www.` 제거, 말미 `/` 제거, 쿼리에서 `utm_*` / `ref` / `fbclid` / `gclid` 제거 후 남은 쿼리는 키 정렬. 프래그먼트(`#...`) 제거.
- `url_key`: `normalize_url` 결과의 sha1 hexdigest.
- 저장 형식 (`state/seen.json`):

```json
{ "version": 1, "seen": { "<sha1>": "2026-08-09" } }
```

- `save_seen`은 부모 디렉터리를 만들고, **임시 파일에 쓴 뒤 원자적으로 rename** 한다. 배치가 중간에 죽어도 파일이 깨지지 않게 한다.
- `load_seen`: 파일이 없으면 빈 dict. JSON 파싱 실패나 `version` 불일치면 `logger.warning` 후 빈 dict를 반환하고 예외를 던지지 않는다. (spec 엣지 케이스)
- `prune`: `keep_days`보다 오래된 항목 제거. `save_seen` 직전에 호출한다.
- `mark_seen`은 **새 dict를 반환**한다(입력을 변형하지 않는다).

### 초기 상태 파일

`state/seen.json`을 `{"version": 1, "seen": {}}` 내용으로 생성해 커밋한다. GitHub Actions가 이 파일을 갱신·푸시할 것이다.

### 테스트 `tests/test_state.py`

- `normalize_url`: 아래가 모두 같은 키로 정규화되는가
  - `http://www.Example.com/post/?utm_source=x`
  - `https://example.com/post`
  - `https://example.com/post/#section`
- 쿼리 파라미터 순서가 달라도 같은 키가 나오는가 (`?b=2&a=1` vs `?a=1&b=2`)
- `filter_unseen`: seen에 있는 항목만 제외되는가
- `load_seen`: 파일 없음 / 깨진 JSON / 잘못된 version — 세 경우 모두 예외 없이 빈 dict인가
- `save_seen` → `load_seen` 왕복이 동일한 내용을 주는가
- `prune`: `keep_days` 경계 동작 (정확히 90일 된 항목은 유지, 91일은 제거)

`tmp_path` fixture로 파일 경로를 격리한다.

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
from secretary.state import normalize_url, url_key
a = normalize_url('http://www.Example.com/post/?utm_source=news&b=2&a=1#top')
b = normalize_url('https://example.com/post?a=1&b=2')
print(a); print(b)
assert url_key(a) == url_key(b), 'normalization mismatch'
print('ok')
"
test -f state/seen.json
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: `state/seen.json`이 존재하고 `.gitignore`에 걸리지 않는가(`git check-ignore state/seen.json` 이 아무것도 출력하지 않아야 함) / `save_seen`이 원자적 쓰기를 쓰는가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 2를 갱신한다.

## 금지사항

- SQLite나 외부 DB를 쓰지 마라. 이유: 하루 수십 건 기록에 DB는 과하고, JSON은 사람이 읽고 git으로 되돌릴 수 있다.
- `save_seen`을 파이프라인 중간에서 호출하지 마라. 발송 성공 이후에만 호출한다(step 6에서 배선). 이유: 발송 실패 시 항목이 영영 유실된다.
- 제목 유사도 기반 중복 제거를 넣지 마라. 이유: 요청되지 않았고, URL 정규화로 충분하다.
