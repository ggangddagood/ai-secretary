# AI 작업 사이클

Claude Code / Codex로 이 프로젝트를 작업하는 방법. 프레임워크 자체에 대한 설명은 이 파일 하나뿐이며, 나머지 `docs/`는 전부 프로젝트 자신을 설명한다.

## 한눈에

```
새 작업:            /plan → 사용자 승인 → /build → /review → 머지
무인 실행:          /plan 으로 계획 승인 후 → python3 scripts/execute.py <task-name>
기존 프로젝트 도입:  /onboard (docs/ 하네스 구축) → 이후 일반 사이클
```

## 왜 이렇게 하나

- 가장 큰 낭비는 잘못된 방향으로 만든 뒤 되돌리는 작업이다. 중요한 결정은 구현 전(`/plan`)에 확정한다.
- 세션이 끝나면 대화는 사라진다. 남아야 할 것은 spec(`phases/`)과 문서(`docs/`)에 쓴다.
- 에이전트의 "됐습니다"는 증거가 아니다. 완료는 검증 명령 + exit code로 판단한다.

## 단계별

### 1. /plan — 계획

입력(아이디어 한 줄, 요구사항 문서, 메모)을 재료로 받아:

- 코드/문서에서 파생 가능한 결정은 스스로 확정하고
- 답에 따라 결과가 달라지는 제품/도메인 미결정만 질문한 뒤
- `phases/<task>/`에 `spec.md` + step 파일 + `index.json`을 만든다.

승인 전에는 구현하지 않는다.

### 2. /build — 실행 (또는 execute.py 무인 실행)

승인된 step을 순서대로 구현한다. step마다 AC(실행 가능한 검증 명령)를 통과해야 다음으로 넘어간다.

- 실패: 3회까지 자가 수정, 그래도 실패면 `error` 기록 후 중단
- 사용자 개입 필요(API 키, 인증 등): `blocked` 기록 후 즉시 중단
- 전체 완료 후: `bash scripts/verify.sh` 통과 + 서버가 있으면 런타임 스모크(기동→요청 1건→2xx 확인)
- 마무리로 docs/ 갱신: `STATUS.md`(매번), `ENGINEERING_NOTES.md`/`DECISIONS.md`/영향받은 문서(해당 시)

### 3. /review — 리뷰

spec 준수, 하드 게이트 위반, 테스트 존재, verify 통과를 증거와 함께 표로 보고한다.

## 무인 실행 (execute.py)

```bash
python3 scripts/execute.py <task-name>                  # 순차 실행 (기본: claude)
python3 scripts/execute.py <task-name> --agent codex    # Codex로 실행
python3 scripts/execute.py <task-name> --push           # 완료 후 push
```

- `feat-<task>` 브랜치에서 step을 순차 실행하고 step마다 커밋한다
- 가드레일(AGENTS.md + docs/ + spec.md)을 매 step 프롬프트에 주입한다
- 완료된 step의 summary를 다음 step에 누적 전달한다
- 실패 시 에러 메시지를 피드백하며 3회 재시도한다

복구:

- **error**: `phases/<task>/index.json`에서 해당 step의 status를 `"pending"`으로 되돌리고 `error_message`를 삭제한 뒤 재실행
- **blocked**: `blocked_reason`의 사유를 해결한 뒤 동일하게 재실행

## Codex에서

- 대화형: "`.claude/commands/plan.md`를 읽고 그 워크플로로 진행해" (build/review/onboard 동일)
- 무인: `python3 scripts/execute.py <task> --agent codex`
- 프로젝트 지침(`AGENTS.md`)은 Codex가 자동으로 읽는다.

## 작업 크기 조절

작은 기계적 수정(오타, 한 줄 변경)에 전체 사이클은 과하다. 바로 고치되 `verify.sh`는 통과시킨다.
단, 입력이 짧다고 spec을 얇게 만들지 않는다 — 입력이 모호할수록 `/plan`에서 확정해야 할 것이 많다.

반대 방향도 마찬가지다: `/plan` 없이 큰 변경을 요청받아도 에이전트는 AGENTS.md의 **자동 전환 규칙**(새 기능, 스키마/인터페이스/인증 변경, 다중 모듈, 모호한 요구)에 따라 계획부터 만든다. 사용자가 "계획 없이 바로 해"라고 명시한 경우에만 예외다.
