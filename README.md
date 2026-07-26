# ai-framework

Claude Code와 Codex로 서비스를 만들고 유지보수하기 위한 프로젝트 템플릿.

핵심 아이디어는 세 가지 출처를 융합한 것이다:

- [jha0313/harness_framework](https://github.com/jha0313/harness_framework) — step 단위 실행 계획(`phases/`), 무인 자동 실행기(`scripts/execute.py`), 안전 훅, UI 가이드
- [fn-opt/dryforge](https://github.com/fn-opt/dryforge) — bounded autonomy: 판단 권한 분리, spec 정본, 증거 기반 검증, 지속되는 문서 하네스
- AI 코딩 베스트 프랙티스 — 구현 전 계획 확정, TDD, 외과적 변경, 자기완결적 작업 단위

## 핵심 원칙

1. **의도는 사용자가 정한다.** 에이전트는 제품/도메인 결정을 추측하는 대신 구현 전에 질문한다. 파생 가능한 결정은 스스로 확정하고 근거를 남긴다.
2. **spec이 정본이다.** 요구 동작은 승인된 spec(`phases/<task>/spec.md`)이 정하고, 코드는 현재 구현 사실일 뿐이다.
3. **완료는 증거다.** "됐습니다"가 아니라 검증 명령 + exit code. 평가하지 못한 검사는 실패로 취급한다.
4. **외과적 변경.** 변경된 모든 줄이 요청으로 추적 가능해야 한다.
5. **지식은 하네스에 남긴다.** 세션이 끝나면 대화는 사라진다. 남아야 할 것은 `docs/`에 쓴다.

## 구조

```
ai-framework/
├── AGENTS.md                    ← 에이전트 진입점 (프로젝트 지침의 단일 소스)
├── CLAUDE.md                    ← Claude Code용 진입점 (AGENTS.md를 import)
├── docs/
│   ├── WORKFLOW.md              ← AI 작업 사이클 사용법 (프로젝트와 함께 이동)
│   ├── PRD.md                   ← 제품 요구사항
│   ├── ARCHITECTURE.md          ← 시스템 구조
│   ├── BUSINESS_RULES.md        ← 도메인 규칙의 정본
│   ├── STANDARDS.md             ← 규칙 (위반 판정 가능한 것만)
│   ├── SECURITY.md              ← 인증/인가/민감 정보
│   ├── UI_GUIDE.md              ← UI 규칙 + AI 슬롭 안티패턴
│   ├── OPERATIONS.md            ← 셋업/빌드/배포
│   ├── ENGINEERING_NOTES.md     ← 함정과 비자명 지식
│   ├── DECISIONS.md             ← ADR (트레이드오프 있는 결정만)
│   └── tracking/
│       ├── STATUS.md            ← 진행 현황
│       └── FINDINGS.md          ← 미해결 문제
├── .claude/
│   ├── settings.json            ← 위험 명령 차단 훅
│   └── commands/
│       ├── plan.md              ← /plan — 의도 확정 → spec + step 생성
│       ├── build.md             ← /build — 승인된 계획 실행 + 문서 갱신
│       ├── review.md            ← /review — 증거 기반 리뷰
│       └── onboard.md           ← /onboard — 기존 프로젝트에 하네스 구축
├── phases/                      ← 작업 계획과 실행 상태 (spec + step)
└── scripts/
    ├── verify.sh                ← 검증 단일 진입점 (프로젝트별로 채움)
    ├── execute.py               ← 무인 step 실행기 (claude / codex)
    ├── new-project.sh           ← 새 프로젝트 부트스트랩
    └── hooks/block_dangerous.py ← 파괴적 명령 차단 훅
```

## 새 프로젝트 시작

```bash
bash scripts/new-project.sh ~/projects/my-service "my-service"
cd ~/projects/my-service
claude          # Claude Code 실행 후 /plan 으로 첫 작업 시작
```

첫 `/plan` 사이클에서 제품 목표·도메인 규칙·스택까지 함께 확정하고 docs/의 placeholder를 채운다.
`scripts/verify.sh`에 검증 명령을 채우는 것도 첫 사이클에 포함된다.

## 기존 프로젝트에 도입 (유지보수)

```bash
cd <기존-프로젝트>
F=~/Documents/ai-framework
rsync -a "$F/.claude" "$F/scripts" "$F/phases" .
rsync -a --ignore-existing "$F/docs/" docs/
[ -f AGENTS.md ] || cp "$F/AGENTS.md" .
[ -f CLAUDE.md ] || cp "$F/CLAUDE.md" .
```

그 다음 Claude Code에서 `/onboard` 실행 — 코드베이스를 분석해 docs/를 실제 내용으로 채운다.
기존 CLAUDE.md/AGENTS.md가 있으면 백업 후 승인을 받아 재구성한다. 완료 후엔 일반 사이클을 쓴다.

## 워크플로

```
새 작업:   /plan → 사용자 승인 → /build → /review → 머지
무인 실행: /plan 으로 계획 승인 후 → python3 scripts/execute.py <task-name>
```

상세는 `docs/WORKFLOW.md` — 이 파일은 새 프로젝트에 복사되어 함께 이동한다.

## Codex에서 사용

- **대화형**: 슬래시 커맨드 대신 커맨드 파일을 지정한다 — "`.claude/commands/plan.md`를 읽고 그 워크플로로 진행해"
- **무인 실행**: `python3 scripts/execute.py <task-name> --agent codex`
- Codex는 `AGENTS.md`를 자동으로 읽으므로 프로젝트 지침은 그대로 적용된다.

## 커스터마이징

- **필요 없는 문서는 삭제한다.** UI가 없으면 `UI_GUIDE.md`, 보안 표면이 없으면 `SECURITY.md`를 지운다. 빈 껍데기 문서는 없는 것보다 나쁘다 — 다음 에이전트가 "문서가 있으니 정보가 있겠지"라고 오판한다.
- `scripts/verify.sh`는 반드시 채운다. 채우기 전에는 의도적으로 exit 1 한다(검증 없는 완료 주장을 막기 위해).
- `.claude/settings.json`의 차단 패턴은 `scripts/hooks/block_dangerous.py`에서 조정한다.
