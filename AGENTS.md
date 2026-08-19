# ai-secretary

## 개요

운영자 한 사람에게 텔레그램으로 정보를 보내는 배치 **둘**이다. 사용자는 운영자 본인 1명이고,
가입·인증·다중 사용자 개념이 없다. 웹 화면도 서버도 없다 — GitHub Actions cron이 돌리는
CLI뿐이다. 과한 인프라를 들이지 않는다.

1. **AI 브리핑** (`secretary.main`) — AI 활용·수익화·마케팅 정보를 여러 소스에서 매일 수집해,
   엄선 5건을 한국어 요약과 실행 힌트로 정리해 하루 1회 발송한다.
2. **주가 브리핑** (`secretary.stocks`) — 관심 종목의 종가·등락과 시장 지표를, 크게 움직인
   종목의 뉴스 근거와 함께 정리해 미국장·한국장 마감 후 각 1회 발송한다.

둘은 **독립된 파이프라인**이다. 실행 시각도 CLI도 워크플로도 분리돼 있고, 주가 브리핑은
`state/seen.json`을 읽지도 쓰지도 않는다. 공유하는 것은 발송·HTTP·로깅·설정 모듈뿐이다.

## 기술 스택

- Python 3.11 (src 레이아웃, `src/secretary/`)
- 수집: httpx + feedparser / 본문 추출: trafilatura
- 시세: Yahoo Finance v8 chart (인증 없음) / 종목 뉴스: Google News RSS (헤드라인까지만)
- LLM: Gemini `gemini-3.6-flash` (`google-genai` SDK — AI 브리핑은 선별 1회 + 요약 1회,
  주가 브리핑은 급등락 해설 1회)
- 실행: GitHub Actions cron 3개 — `daily.yml`(08:00 KST) / `stocks-us.yml`(KST 화~토 07:00) /
  `stocks-kr.yml`(KST 월~금 16:00)
- 상태: 리포지토리 내 JSON 파일 (`state/seen.json`) — DB 없음. 주가 브리핑은 상태가 없다
- 검증: ruff (lint + format) + pytest

## 하드 게이트 (CRITICAL)

위반하면 안 되는 최상위 규칙. 전체 규칙은 `docs/STANDARDS.md`.

- CRITICAL: 본문을 확보하지 못한 항목에 요약을 생성하지 않는다
- CRITICAL: 헤드라인을 확보하지 못한 종목에 급등락 해설을 생성하지 않는다
- CRITICAL: 등락률을 `meta.chartPreviousClose`로 계산하지 않는다 (조회 창 *이전*의 종가다)
- CRITICAL: 발송 기록(`state/seen.json`)은 텔레그램 발송 성공 이후에만 갱신한다
- CRITICAL: 모든 환경 변수는 `config.py`를 통해서만 읽는다. `os.environ` 직접 참조 금지
- CRITICAL: 시크릿을 로그·예외 메시지·발송 메시지·커밋에 남기지 않는다

## 명령어

```bash
bash scripts/verify.sh              # 검증 단일 진입점 (ruff check + ruff format --check + pytest)
python -m secretary.main --dry-run  # AI 브리핑 — 실제 수집·요약 후 발송 없이 stdout 출력
python -m secretary.stocks --market us --dry-run   # 주가 브리핑(미국장), --market은 필수
python -m secretary.stocks --market kr --dry-run   # 주가 브리핑(한국장)
```

## 문서 내비게이션

```
AGENTS.md / CLAUDE.md        ← 진입점 (이 파일)
docs/
├── WORKFLOW.md              ← AI 작업 사이클 사용법
├── PRD.md                   ← 제품 요구사항 — 무엇을 왜 만드는가
├── ARCHITECTURE.md          ← 시스템 구조와 데이터 흐름
├── BUSINESS_RULES.md        ← 도메인 규칙의 정본 (AI: 4개 축·선별·중복·보존 / 주가: 등락률·급등락·해설·휴장)
├── STANDARDS.md             ← 규칙 전체 (위반 판정 가능한 것만)
├── SECURITY.md              ← 시크릿 3종의 출처·저장·마스킹·유출 대응
├── UI_GUIDE.md              ← UI 없음 — 해당 없음
├── OPERATIONS.md            ← 봇 생성·시크릿 등록·로컬 실행·수동 실행·시각 변경
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
3. 선별·중복·요약 규칙을 건드리면 `docs/BUSINESS_RULES.md`
4. 등락률·급등락·해설·휴장 규칙을 건드리면 `docs/BUSINESS_RULES.md`의 "주가 브리핑 규칙" 절과
   `docs/ENGINEERING_NOTES.md`의 Yahoo chart 함정 2개(`chartPreviousClose`, `close`의 `None`)
5. 시크릿·발송을 건드리기 전에 `docs/SECURITY.md`의 마스킹 규칙. 관심 종목은 시크릿이 아니라
   Variables다 — 같은 문서의 "Variables는 시크릿이 아니다" 절
6. 새 소스를 추가하기 전에 `docs/ENGINEERING_NOTES.md`의 "RSS 피드 추가/교체" 체크리스트
7. 관심 종목을 추가·교체하기 전에 같은 문서의 "관심 종목 추가/교체" 체크리스트

## 워크플로

- 새 기능/큰 변경: `/plan`(계획·승인) → `/build`(실행) → `/review`(검증). 상세: `docs/WORKFLOW.md`
- **자동 전환 규칙**: 사용자가 `/plan`을 명시하지 않았더라도, 요청이 아래 기준에 하나라도 해당하면 바로 구현하지 말고 `.claude/commands/plan.md`의 워크플로를 따른다. 전환할 때는 "계획부터 만들겠다"고 한 줄 알리고 시작한다:
  - 새 기능 또는 새 도메인 엔티티 추가
  - 상태 파일 스키마, 외부 인터페이스(CLI 계약), 시크릿 취급을 건드리는 변경
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

- 시크릿이 로그·커밋·발송 메시지에 노출된 흔적을 발견 → 즉시 사용자에게 보고하고 중단 (대응 절차는 `docs/SECURITY.md`)
- 발송하지 않은 항목이 `state/seen.json`에 들어간 정황을 발견 → 즉시 보고하고 중단. 그 항목은 영영 발송되지 않는다
- 헤드라인 없이 해설이 붙은 종목, 또는 `chartPreviousClose`로 계산된 등락률을 발견 → 즉시 보고하고 중단. 둘 다 조용히 틀린 값이 발송된다
- 그 외 당장 못 고치는 문제 → `docs/tracking/FINDINGS.md`에 기록 (증상→영향→왜 지금 못 고치나)
