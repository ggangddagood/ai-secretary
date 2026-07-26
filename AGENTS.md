# {프로젝트명}

## 개요

{무엇을 하는 서비스이고, 누가 쓰고, 어느 규모인지 2~3줄.
예: 소상공인용 재고 관리 SaaS. 웹 대시보드 + REST API. 1인이 운영하는 소규모 서비스 — 과한 인프라 금지.}

## 기술 스택

- {프레임워크 (예: Next.js 15, App Router)}
- {언어 (예: TypeScript strict mode)}
- {데이터 (예: PostgreSQL + Drizzle)}
- {스타일링 (예: Tailwind CSS)}

## 하드 게이트 (CRITICAL)

위반하면 안 되는 최상위 규칙 3~5개만 여기에. 전체 규칙은 `docs/STANDARDS.md`.

- CRITICAL: {예: 모든 DB 접근은 services/ 레이어를 통해서만. 라우트 핸들러에서 직접 쿼리 금지}
- CRITICAL: {예: 클라이언트 컴포넌트에서 외부 API 직접 호출 금지}
- CRITICAL: 새 기능은 테스트를 먼저 작성하고 통과시킨다 (TDD)

## 명령어

```bash
bash scripts/verify.sh    # 검증 단일 진입점 (lint + typecheck + test + build)
{npm run dev              # 개발 서버}
```

## 문서 내비게이션

```
AGENTS.md / CLAUDE.md        ← 진입점 (이 파일)
docs/
├── WORKFLOW.md              ← AI 작업 사이클 사용법
├── PRD.md                   ← 제품 요구사항 — 무엇을 왜 만드는가
├── ARCHITECTURE.md          ← 시스템 구조와 데이터 흐름
├── BUSINESS_RULES.md        ← 도메인 규칙의 정본 (불변 조건, 상태 전이, 엣지)
├── STANDARDS.md             ← 규칙 전체 (위반 판정 가능한 것만)
├── SECURITY.md              ← 인증/인가/민감 정보
├── UI_GUIDE.md              ← UI 디자인 규칙 + 금지 패턴
├── OPERATIONS.md            ← 셋업/빌드/배포 절차
├── ENGINEERING_NOTES.md     ← 함정과 비자명 지식 (증상→원인→대응)
├── DECISIONS.md             ← 트레이드오프가 있었던 결정 기록 (ADR)
└── tracking/
    ├── STATUS.md            ← 현재 진행 상황 (완료/남은 것/블로커)
    └── FINDINGS.md          ← 미해결 문제
phases/                      ← 작업 계획과 실행 상태 (spec + step)
```

## 작업 전 체크리스트

1. `docs/tracking/STATUS.md` — 현재 위치 파악
2. `docs/STANDARDS.md` + `docs/ENGINEERING_NOTES.md` — 규칙과 함정
3. 작업 영역의 문서 — 도메인 로직이면 `BUSINESS_RULES.md`, UI면 `UI_GUIDE.md`
4. {위험 작업별 필수 선행 읽기 — 예: 인증을 건드리기 전 SECURITY.md의 인가 모델}

## 워크플로

- 새 기능/큰 변경: `/plan`(계획·승인) → `/build`(실행) → `/review`(검증). 상세: `docs/WORKFLOW.md`
- **자동 전환 규칙**: 사용자가 `/plan`을 명시하지 않았더라도, 요청이 아래 기준에 하나라도 해당하면 바로 구현하지 말고 `.claude/commands/plan.md`의 워크플로를 따른다. 전환할 때는 "계획부터 만들겠다"고 한 줄 알리고 시작한다:
  - 새 기능 또는 새 도메인 엔티티 추가
  - DB 스키마, 외부 인터페이스(API 계약), 인증/인가를 건드리는 변경
  - 여러 모듈에 걸치거나 파일 3개 이상 수정이 예상되는 변경
  - 요구사항이 모호해서 제품/도메인 결정이 먼저 필요한 경우
- 작은 기계적 수정(오타, 한 줄 변경, 원인이 명확한 버그 픽스): 전체 사이클 없이 바로 수정하되, 완료 전 `bash scripts/verify.sh` 통과 필수
- Codex 사용 시: 슬래시 커맨드 대신 해당 파일을 읽고 따른다 — 예: "`.claude/commands/plan.md`를 읽고 그 워크플로로 진행해". 자동 전환 규칙은 Codex에도 동일하게 적용된다.

## 작업 원칙

1. **추측하지 않는다.** 제품/도메인 결정이 불명확하면 구현 전에 질문한다. 결과가 달라지지 않는 구현 세부는 스스로 판단한다.
2. **spec이 정본이다.** `phases/<task>/spec.md`가 요구 동작을 정하고, 코드는 현재 구현 사실일 뿐이다. spec이 잘못돼 보이면 편한 해석으로 바꾸지 말고 사용자에게 확인한다.
3. **완료는 증거로 판단한다.** 검증 명령의 exit code를 캡처해서 보고한다. 평가하지 못한 검사는 실패로 취급한다 — 명령이 assertion에 도달하기 전에 죽었으면 성공을 추론하지 않는다.
4. **외과적으로 변경한다.** 요청과 무관한 코드/주석/포맷을 건드리지 않는다. 변경된 모든 줄이 요청으로 추적 가능해야 한다.
5. **지식을 하네스에 남긴다.** 작업 중 알게 된 비자명한 사실(함정, 메커니즘)은 `docs/ENGINEERING_NOTES.md`에, 트레이드오프 결정은 `docs/DECISIONS.md`에 기록한다. 세션 대화는 사라진다.

## 문제 라우팅

- {프로젝트 치명 조건 — 예: 데이터 격리 위반, 인가 우회, 마이그레이션 손상} 발견 → 즉시 사용자에게 보고하고 중단
- 그 외 당장 못 고치는 문제 → `docs/tracking/FINDINGS.md`에 기록 (증상→영향→왜 지금 못 고치나)
