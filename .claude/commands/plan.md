새 작업의 실행 계획을 만든다. 인자: 작업 설명(아이디어 한 줄, 문서 경로, 또는 비어 있음 — 비어 있으면 무엇을 만들거나 바꿀지 먼저 묻는다).

이 커맨드는 계획만 만든다. **사용자가 승인하기 전에는 구현 코드를 작성하지 않는다.**

## 원칙

- **입력은 검토할 재료이지 확정된 사실이 아니다.** 문서가 자세하다는 이유로 옳다고 가정하지 않는다. 입력 안의 사실/선호/제안/모순을 분리해서 다룬다.
- **파생 가능한 결정은 묻지 않는다.** 확정된 목표·제약·코드 사실·docs/에서 답을 도출할 수 있으면 스스로 확정하고 근거를 spec에 남긴다.
- **다음만 사용자에게 묻는다:**
  1. 답에 따라 결과가 달라지는 제품/도메인/정책 미결정 — 그 지점을 정확히 짚어서
  2. 트레이드오프가 큰 기술 결정 — 선택지 + 장단점 + 추천안 형태로
- 결과를 바꾸지 않는 구현 튜닝은 실행 단계 재량에 맡긴다.
- 질문은 한 번에 4개 이하, 각 질문에 추천안을 붙인다. **미결정이 남은 채 spec을 쓰지 않는다** — 입력이 짧을수록 확정할 것이 많다.
- 제품 의도는 나중에 코드만 보고 복원할 수 없다. 애매하면 spec에 남기는 쪽을 택한다.

## 절차

### A. 탐색

1. AGENTS.md, docs/tracking/STATUS.md, 작업과 관련된 docs/(ARCHITECTURE, BUSINESS_RULES, STANDARDS 등)를 읽는다.
2. 기존 코드가 있으면 영향 범위의 코드를 읽는다. 필요시 Explore 에이전트를 병렬로 쓴다.
3. `scripts/verify.sh`가 실제 동작하는지 확인한다. placeholder 상태면 검증 게이트 부재 자체를 결정 사항으로 다룬다 — 어떤 명령으로 검증할지 확정하고, verify.sh를 채우는 작업을 계획에 포함한다.
4. **첫 사이클**(docs/가 대부분 placeholder)이면: 이번 작업만이 아니라 프로젝트 기반 — 제품 목표(PRD), 핵심 도메인 규칙, 스택과 아키텍처 — 도 함께 확정한다. 승인 후 docs/의 해당 문서를 채우는 것까지가 첫 사이클의 범위다.

### B. 결정 확정

위 원칙대로 결정을 분류해 처리한다. 사용자 답변까지 반영해 결과를 좌우하는 모든 결정이 확정되면 다음으로.

### C. spec 작성 — `phases/<task-name>/spec.md`

확정된 의도의 정본. step과 spec이 충돌하면 spec이 우선한다.

```markdown
# Spec: {작업 이름}

## 목표
{한 줄}

## 요구 동작
- {검증 가능한 문장으로. "~가 동작한다"가 아니라 "조건 A에서 B를 하면 C가 된다"}

## 불변 조건
- {구현 중 절대 깨지면 안 되는 것}

## 범위 제외
- {이번에 안 만드는 것 — 실행자가 요청 없이 만들지 않는다}

## 엣지 케이스
- {각 엣지의 구체적 처리. "적절히 처리" 금지}

## 외부 인터페이스
- {API/이벤트/CLI 등 소비자와의 계약. 입력·출력·에러. 없으면 "없음"}

## 확정 근거
- {스스로 확정한 결정과 그 근거 / 사용자가 답해서 확정된 결정}

## 필수 검증
- bash scripts/verify.sh
- {추가 검증 — 예: 런타임 스모크 방법}
```

### D. step 분해

설계 원칙:

1. **Scope 최소화** — step 하나는 하나의 레이어 또는 모듈만 다룬다. 여러 모듈을 동시에 수정해야 하면 쪼갠다.
2. **자기완결성** — 각 step은 독립된 세션에서 실행된다. "이전 대화에서 논의한 대로" 같은 외부 참조 금지. 필요한 정보는 전부 step 파일과 spec 안에 적는다.
3. **사전 준비 강제** — 읽어야 할 문서 경로와 이전 step에서 생성/수정된 파일 경로를 명시한다.
4. **시그니처 수준 지시** — 함수/클래스 인터페이스만 제시하고 내부 구현은 재량에 맡긴다. 단, 벗어나면 안 되는 핵심 규칙(멱등성, 보안, 데이터 무결성)은 반드시 명시한다.
5. **AC는 실행 가능한 커맨드** — "~가 동작해야 한다"가 아니라 `bash scripts/verify.sh` 같은 실제 실행 명령.
6. **주의사항은 구체적으로** — "조심해라" 대신 "X를 하지 마라. 이유: Y".
7. **네이밍** — step 이름은 kebab-case slug (예: project-setup, api-layer, auth-flow).

초안을 사용자에게 보여 피드백을 받는다.

### E. 파일 생성 (피드백 반영 후)

#### E-1. `phases/index.json` — 전체 현황 (없으면 생성, 있으면 항목 추가)

```json
{
  "phases": [
    { "dir": "0-mvp", "status": "pending" }
  ]
}
```

- status: `"pending"` | `"completed"` | `"error"` | `"blocked"`
- 타임스탬프는 execute.py가 자동 기록한다. 생성 시 넣지 않는다.

#### E-2. `phases/<task-name>/index.json` — task 상세

```json
{
  "project": "<프로젝트명 — AGENTS.md 참조>",
  "phase": "<task-name>",
  "steps": [
    { "step": 0, "name": "project-setup", "status": "pending" },
    { "step": 1, "name": "api-layer", "status": "pending" }
  ]
}
```

- `step`: 0부터 순번. `name`: kebab-case. 초기 status는 모두 `"pending"`.
- 상태 전이 시 실행 주체가 기록하는 필드:
  - → `completed`: `summary` — 산출물 한 줄 요약. 다음 step 프롬프트에 누적 전달되므로 생성 파일·핵심 결정을 담는다.
  - → `error`: `error_message` — 구체적 에러 내용
  - → `blocked`: `blocked_reason` — 구체적 사유
- 타임스탬프(`started_at`, `completed_at`, `failed_at`, `blocked_at`, `created_at`)는 execute.py가 자동 기록한다.

#### E-3. `phases/<task-name>/step{N}.md` — step마다 1개

```markdown
# Step {N}: {이름}

## 읽어야 할 파일

먼저 아래를 읽고 설계 의도를 파악하라:

- `phases/<task-name>/spec.md`   ← 요구 동작의 정본
- `/docs/ARCHITECTURE.md`
- {이 step과 관련된 docs 경로}
- {이전 step에서 생성/수정된 파일 경로}

## 작업

{구체적 지시. 파일 경로, 클래스/함수 시그니처, 로직 설명.
코드는 인터페이스/시그니처 수준만 제시하고 구현체는 재량에 맡긴다.
단, 벗어나면 안 되는 핵심 규칙은 명확히 박아넣는다.}

## Acceptance Criteria

```bash
bash scripts/verify.sh
{추가 검증 명령}
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. 확인한다: ARCHITECTURE.md 구조를 따르는가 / AGENTS.md CRITICAL 규칙 위반이 없는가 / spec의 불변 조건이 유지되는가.
3. 결과에 따라 `phases/<task-name>/index.json`의 해당 step을 갱신한다:
   - 통과 → `"completed"` + `"summary"`
   - 3회 수정 후에도 실패 → `"error"` + `"error_message"`
   - 사용자 개입 필요(API 키, 인증, 수동 설정) → `"blocked"` + `"blocked_reason"` 후 즉시 중단

## 금지사항

- {X를 하지 마라. 이유: Y}
- spec의 "범위 제외"에 있는 것을 만들지 마라
- 기존 테스트를 깨뜨리지 마라
```

### F. 자가 점검 후 승인 요청

- spec의 모든 요구 동작이 최소 1개 step에 매핑된다 (빠짐 없음)
- 모든 step이 spec의 요구에 근거한다 (고아 step 없음)
- 모든 AC가 실제 실행 가능한 명령이다

통과하면 계획 요약(질문으로 확정된 결정 포함)을 제시하고 승인을 요청한다. 승인되면 안내한다:

- 같은 세션에서 실행: `/build <task-name>`
- 무인 실행: `python3 scripts/execute.py <task-name>`
