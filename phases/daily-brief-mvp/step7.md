# Step 7: ops-docs

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본
- `AGENTS.md` (플레이스홀더 상태 — 이번에 채운다)
- `docs/` 전체 (대부분 플레이스홀더)
- `src/secretary/main.py` (step 6)
- `src/secretary/state.py` (step 2 — 커밋 대상 파일 경로)

## 작업

배치를 자동 실행시키고, 이 프로젝트의 문서 하네스를 실제 내용으로 채운다.

### 1. `.github/workflows/daily.yml`

```yaml
name: daily-brief
on:
  schedule:
    - cron: "0 23 * * *"   # 08:00 KST
  workflow_dispatch:
permissions:
  contents: write          # state/seen.json 커밋용
```

- `ubuntu-latest`, Python 3.11 setup, pip 캐시
- `pip install -e ".[dev]"` → `python -m secretary.main`
- env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`는 `${{ secrets.* }}`, `GITHUB_TOKEN`은 `${{ github.token }}`
- 실행 후 `state/seen.json`이 변경되었으면 커밋 & 푸시:
  - `git config user.name/email`을 github-actions bot으로 설정
  - `git diff --quiet state/seen.json || (git add state/seen.json && git commit -m "chore: update seen state" && git push)`
  - 이 커밋 단계는 배치가 실패해도 실행되지 않아야 한다(`if: success()`).
- `concurrency: group: daily-brief, cancel-in-progress: false` — 수동 실행과 스케줄이 겹쳐 push가 충돌하지 않게 한다.
- **타임아웃 `timeout-minutes: 15`를 반드시 넣어라.** 무한 대기로 러너 시간을 태우지 않게 한다.

### 2. `AGENTS.md` 플레이스홀더 채우기

- 프로젝트명: `ai-secretary`
- 개요: spec의 목표 + 1인 운영 배치라는 사실
- 기술 스택: Python 3.11 / httpx·feedparser·trafilatura / Anthropic SDK / GitHub Actions cron / 상태는 리포 내 JSON
- 하드 게이트 (CRITICAL) — 아래 4개를 그대로:
  - 본문을 확보하지 못한 항목에 요약을 생성하지 않는다
  - 발송 기록(`state/seen.json`)은 텔레그램 발송 성공 이후에만 갱신한다
  - 모든 환경 변수는 `config.py`를 통해서만 읽는다. `os.environ` 직접 참조 금지
  - 시크릿을 로그·예외 메시지·발송 메시지·커밋에 남기지 않는다
- 명령어 섹션: `bash scripts/verify.sh`, `python -m secretary.main --dry-run`
- 문서 내비게이션의 `UI_GUIDE.md` 줄에 "UI 없음 — 해당 없음" 표기

### 3. `docs/` 채우기

| 파일 | 내용 |
| --- | --- |
| `PRD.md` | spec의 목표·사용자·핵심 기능·MVP 제외 사항. 성공 기준은 "매일 브리핑이 도착하고, 그중 최소 1건은 읽을 가치가 있다" 수준의 측정 가능한 문장으로 |
| `ARCHITECTURE.md` | 디렉터리 구조 + `수집 → 중복제거 → 선별(LLM) → 본문추출 → 요약(LLM) → 렌더 → 발송 → 상태저장` 흐름. 대표 흐름 1개로 이 배치 전체를 서술 |
| `BUSINESS_RULES.md` | 4개 축의 정의, 선별 규칙(최소 3축·품질 우선), 중복 판정 규칙(URL 정규화), 발송 기록 보존 기간 90일 |
| `STANDARDS.md` | 검증 게이트(`verify.sh` exit 0), 모듈 경계(소스 모듈은 llm/telegram을 import 금지), 환경 변수 규칙, conventional commits |
| `SECURITY.md` | 시크릿 3종의 출처와 저장 위치(GitHub Secrets), 로그 마스킹 규칙, 봇 토큰 유출 시 대응(BotFather에서 revoke) |
| `OPERATIONS.md` | 텔레그램 봇 생성 절차(BotFather → 토큰 → chat_id 확인 방법), GitHub Secrets 등록 절차, 로컬 실행 방법, 워크플로 수동 실행 방법, 발송 시각 변경 방법(cron 수정) |
| `ENGINEERING_NOTES.md` | 작업 중 알게 된 비자명한 사실. 최소한: 텔레그램 MarkdownV2 대신 HTML을 쓰는 이유, 카카오톡 200자·토큰 만료 제약, Threads/Reddit이 제외된 이유, 죽은 RSS 피드 목록 |
| `DECISIONS.md` | spec "확정 근거"의 트레이드오프 결정을 ADR 형식으로. 최소 4건: 텔레그램 vs 카카오톡 / GitHub Actions vs 서버 / JSON 상태파일 vs DB / 2단계 LLM 호출 |
| `UI_GUIDE.md` | "이 프로젝트에는 UI가 없다. 텔레그램 메시지 포맷 규칙은 `src/secretary/render.py`와 BUSINESS_RULES.md를 따른다." 한 문단 |
| `tracking/STATUS.md` | 완료된 step 목록과 검증 상태, 남은 것(다음 사이클 후보), 블로커 |

**플레이스홀더 문구(`{...}`)를 하나도 남기지 마라.** `grep -rn "{예:" docs/ AGENTS.md` 가 아무것도 출력하지 않아야 한다.

### 4. `README.md` 갱신

현재 README는 프레임워크 템플릿 설명이다. 이 프로젝트가 무엇이고 어떻게 돌리는지로 바꾼다. 프레임워크 사용법은 `docs/WORKFLOW.md`로 링크만 남긴다.

## Acceptance Criteria

```bash
bash scripts/verify.sh
grep -rn "{예:" docs/ AGENTS.md README.md ; test $? -eq 1
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/daily.yml')); print('workflow yaml ok')"
```

그리고 GitHub에 push한 뒤:

```bash
gh workflow run daily-brief
gh run watch
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행한다.
2. `gh workflow run` 이후 **텔레그램에 브리핑이 실제로 도착했는지 확인한다.** 도착하지 않으면 `gh run view --log`로 원인을 찾는다.
3. 워크플로 실행 후 `state/seen.json`이 갱신·커밋되었는지 확인한다(`git pull` 후 파일 내용 확인).
4. 확인한다: 워크플로 로그에 시크릿이 노출되지 않는가 / 문서에 플레이스홀더가 남아 있지 않은가.
5. GitHub Secrets가 등록되지 않아 워크플로를 실행할 수 없으면 step을 `blocked`로 표시하고, `blocked_reason`에 필요한 시크릿 이름을 적은 뒤 즉시 중단한다.
6. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 7을 갱신한다.

## 금지사항

- 시크릿 값을 워크플로 파일이나 문서에 하드코딩하지 마라. 이름만 적는다.
- `state/seen.json` 커밋 단계를 배치 실패 시에도 실행되게 만들지 마라. 이유: 실패한 실행의 부분 상태가 커밋된다.
- 워크플로에 배포·릴리스·이슈 자동화 같은 요청되지 않은 잡을 추가하지 마라.
- 문서에 "추후 개선 예정" 같은 미래 계획을 나열하지 마라. 현재 사실만 적는다.
