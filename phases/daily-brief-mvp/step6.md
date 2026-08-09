# Step 6: pipeline

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본 (엣지 케이스 표 전체, 불변 조건 전체)
- `src/secretary/sources/__init__.py` (step 1 — `collect_all`)
- `src/secretary/state.py` (step 2)
- `src/secretary/extract.py` (step 3)
- `src/secretary/llm.py` (step 4)
- `src/secretary/render.py`, `src/secretary/telegram.py` (step 5)

## 작업

지금까지의 레이어를 하나의 배치로 배선한다. 이 step에서 새 도메인 로직을 만들지 마라 — 오케스트레이션과 에러 정책만 담당한다.

### `src/secretary/main.py`

```python
def build_brief(cfg, client, *, now, limit) -> tuple[Brief, list[Item]]: ...
def run(argv: list[str] | None = None) -> int: ...
```

파이프라인 순서:

1. `collect_all(cfg, now=now)` → 후보 수집
2. `load_seen(cfg.state_path)` → `filter_unseen(items, seen)`
3. 후보가 0건이면 → 실패 경로 (아래 참조)
4. `curate(client, candidates, count=limit)` → 선별
5. 선별된 `Item`들에 `extract_articles(...)` → 본문 추출
6. `summarize(client, articles, selections)` → `BriefEntry` 목록
7. `Brief` 조립 → `render_brief(brief)`
8. `send_messages(cfg, parts)` → 발송
9. **발송 성공 이후에만** `mark_seen` → `prune` → `save_seen`

### 에러 정책 (spec 엣지 케이스 표를 그대로 구현)

| 상황 | 동작 |
| --- | --- |
| 후보 0건 (수집 실패 또는 전부 중복) | `render_failure` 메시지 발송 → return 1 |
| `curate`/`summarize` 예외 | 사유를 짧게 담아 `render_failure` 발송 → return 1 |
| `send_messages` 예외 | 로그만 남기고 return 1. **발송 기록 저장 금지, 실패 알림 재발송 시도 금지**(어차피 같은 채널이다) |
| 그 외 예상치 못한 예외 | 최상위에서 잡아 `render_failure` 시도 후 return 1 |

`render_failure`에 넣는 사유는 예외 타입과 한 줄 요약까지만. 전체 트레이스백은 로그(stderr)로만 남긴다.

### CLI

```
python -m secretary.main [--dry-run] [--limit N] [--verbose]
```

- `--dry-run`: 텔레그램 발송과 `save_seen`을 **모두** 건너뛰고 렌더링 결과를 stdout에 출력한다. LLM 호출은 실제로 한다(품질 확인이 목적이므로).
- `--limit N`: 기본값은 `cfg.brief_item_count`.
- `--verbose`: DEBUG 로깅.
- `if __name__ == "__main__": sys.exit(run())` 그리고 `src/secretary/__main__.py`도 만들어 `python -m secretary` 로도 실행되게 한다.

### 로깅

각 단계 끝에 한 줄씩 남긴다: 수집 건수, 중복 제거 후 건수, 선별 건수, 본문 추출 성공/실패 건수, 발송 조각 수. 배치가 실패했을 때 어느 단계에서 무너졌는지 로그만 보고 알 수 있어야 한다.

### 테스트 `tests/test_main.py`

가짜 소스·가짜 LLM 클라이언트·가짜 텔레그램으로 `build_brief`와 `run`을 검증한다:

- 정상 흐름: 발송이 1회 호출되고 `save_seen`이 그 **뒤에** 호출되는가 (호출 순서 검증)
- 후보 0건: `render_failure`가 발송되고 return 1인가
- `summarize`가 예외: 실패 메시지 발송 + return 1 + `save_seen` 미호출
- `send_messages`가 예외: return 1 + `save_seen` 미호출 ← **이 테스트는 반드시 있어야 한다** (불변 조건)
- `--dry-run`: 텔레그램과 `save_seen`이 모두 호출되지 않고 return 0

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -m secretary.main --dry-run --limit 5
echo "exit=$?"
```

마지막 명령은 실제 소스 + 실제 Claude API를 사용한다. `ANTHROPIC_API_KEY`가 필요하다. exit 0이어야 하고, 브리핑 5건(또는 후보가 적으면 그 이하)이 stdout에 출력되어야 한다.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다. `--dry-run` 출력의 요약 3줄이 실제 원문 내용과 맞는지 링크 1~2개를 열어 눈으로 검증하라. 요약이 본문과 무관하면 step 4의 프롬프트 문제다.
2. 확인한다: 발송 실패 시 `save_seen`이 호출되지 않는 테스트가 통과하는가 / 실패 경로에서도 항상 사용자에게 메시지가 가는가 / 로그만으로 실패 단계를 특정할 수 있는가.
3. `ANTHROPIC_API_KEY`가 없어 AC를 실행할 수 없으면 step을 `blocked`로 표시하고 즉시 중단한다.
4. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 6을 갱신한다.

## 금지사항

- 발송 전에 `save_seen`을 호출하지 마라. 이유: 발송 실패 시 항목이 영영 유실된다. spec 불변 조건이다.
- 실패 알림 발송이 또 실패했을 때 재귀적으로 재시도하지 마라. 이유: 같은 채널이 죽은 상황이라 무한 루프만 남는다.
- `--dry-run`에서 LLM 호출을 건너뛰지 마라. 이유: dry-run의 목적이 요약 품질 확인이다.
- 이 step에서 수집/추출/요약 로직을 새로 작성하지 마라. 기존 모듈을 호출만 한다.
