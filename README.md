# ai-secretary

AI 활용·수익화·마케팅 정보를 매일 수집해, 엄선 5건을 한국어 요약과 실행 힌트로 정리해
텔레그램으로 보내는 배치.

도착하는 메시지의 형태(원문 제목은 원어 그대로, 나머지는 한국어):

```
📅 AI 브리핑 · 8월 10일

1. <원문 제목>  ·  [기술]
   <이 글이 무엇에 관한 글인지 한 줄>
   · <요약 1>
   · <요약 2>
   · <요약 3>
   💡 <내일 해볼 수 있는 것 한 줄>
   rss:Simon Willison
```

- 사용자는 운영자 본인 1명. 가입도 인증도 없다.
- 서버가 없다. GitHub Actions cron이 매일 08:00 KST에 CLI 하나를 돌린다.
- DB가 없다. 발송 기록은 리포지토리 안 `state/seen.json` 하나다.

## 어떻게 동작하나

```
수집 → 중복 제거 → 선별(LLM) → 본문 추출 → 요약(LLM) → 렌더 → 발송 → 상태 저장
```

- **수집**: Hacker News(Algolia), GeekNews, GitHub Search, 지정 RSS 피드에서 지난 24시간
  (GitHub는 7일) 항목. 소스 하나가 죽어도 나머지로 진행한다.
- **선별**: `tech` / `money` / `enterprise` / `marketing` 4개 축으로 5건.
- **요약**: 원문 본문을 추출해 **본문만 근거로** 3줄 요약 + 실행 힌트 1줄. 본문을 확보하지 못한
  항목은 제목·출처·링크만 싣는다 — 제목만 보고 지어내지 않는다.
- **상태 저장**: 텔레그램 발송이 성공한 뒤에만 기록한다. 실패하면 다음 실행에서 다시 시도된다.

## 실행

```bash
pip install -e ".[dev]"
set -a; source .env; set +a          # .env는 자동 로드되지 않는다

python -m secretary.main --dry-run   # 발송·기록 저장 없이 stdout 출력
python -m secretary.main             # 실제 발송
bash scripts/verify.sh               # 검증 단일 진입점 (ruff + pytest)
```

필요한 환경 변수는 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`
(선택: `GITHUB_TOKEN`, `BRIEF_ITEM_COUNT`, `STATE_PATH`, `HTTP_TIMEOUT`).
봇 생성부터 GitHub Secrets 등록까지의 절차는 `docs/OPERATIONS.md`에 있다.

## 문서

| 파일 | 내용 |
| --- | --- |
| `AGENTS.md` / `CLAUDE.md` | 에이전트 진입점, 하드 게이트 |
| `docs/PRD.md` | 무엇을 왜 만드는가 |
| `docs/ARCHITECTURE.md` | 디렉터리 구조와 전체 흐름 |
| `docs/BUSINESS_RULES.md` | 4개 축, 선별·중복·요약·렌더링 규칙 |
| `docs/STANDARDS.md` | 검증 게이트, 모듈 경계 |
| `docs/SECURITY.md` | 시크릿 취급과 마스킹 |
| `docs/OPERATIONS.md` | 셋업·실행·발송 시각 변경 |
| `docs/ENGINEERING_NOTES.md` | 함정과 비자명 지식 |
| `docs/DECISIONS.md` | 트레이드오프가 있었던 결정(ADR) |
| `docs/tracking/` | 진행 상황(STATUS)과 미해결 문제(FINDINGS) |

## 이 리포의 작업 방식

`/plan` → `/build` → `/review` 사이클과 `phases/`, `scripts/execute.py`를 쓰는 프레임워크 위에서
개발한다. 프레임워크 자체의 사용법은 **[`docs/WORKFLOW.md`](docs/WORKFLOW.md)** 를 본다.
