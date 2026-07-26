# phases/ — 작업 계획과 실행 상태

`/plan`이 생성하고, `/build`(세션 내) 또는 `scripts/execute.py`(무인)가 실행한다.
파일 형식의 정의는 `.claude/commands/plan.md`에 있다.

## 구조

```
phases/
├── index.json            # 전체 task 목록과 상태
└── <task-name>/
    ├── spec.md           # 요구 동작의 정본
    ├── index.json        # step 목록과 상태 (pending/completed/error/blocked)
    ├── step0.md …        # step별 자기완결 실행 지시
    └── stepN-output.json # execute.py 실행 로그
```

## 상태 복구

- **error**: `<task-name>/index.json`에서 해당 step의 status를 `"pending"`으로 되돌리고 `error_message`를 삭제한 뒤 재실행
- **blocked**: `blocked_reason`의 사유를 해결한 뒤 동일하게 재실행
