# 현재 상태

> 작성 기준: 매 사이클 갱신. "완료"는 검증된 상태만 — 테스트 없는 구현은 "구현됨, 미검증"으로 구분해서 적는다. "남은 것"은 막연한 개선("성능 개선 필요")이 아니라 구체적 항목.

기준 시점: 2026-08-11 / 브랜치 `main` / phase `daily-brief-mvp` **완료**

리포: https://github.com/ggangddagood/ai-secretary (공개) · 매일 08:00 KST 자동 발송 가동 중

## 완료

`bash scripts/verify.sh` exit 0 (ruff check + ruff format --check + pytest **67 passed**).

- **step 0 project-setup** — pyproject(src 레이아웃, ruff+pytest 게이트), `config`/`models`/`log` 뼈대 — 테스트 통과 (2026-08-09)
- **step 1 sources** — HN(Algolia) / GeekNews / GitHub Search / RSS 4개 소스 + 공유 httpx 클라이언트, 소스별 실패 흡수 — 테스트 통과 + 실제 수집 108건 확인 (2026-08-09)
- **step 2 state-dedupe** — URL 정규화·sha1 키, `seen.json` 원자적 저장, 90일 prune — 테스트 통과 + **실제 중복 제거 확인**(2회차 실행에서 135건 중 기발송 5건 제외 → 132건) (2026-08-11)
- **step 3 extract** — trafilatura 본문 추출, 300자 미만·모든 예외는 `None`, 8000자 상한 — 테스트 통과 + 실제 사이트 추출 확인 (2026-08-09)
- **step 4 llm-curate-summarize** — Gemini `gemini-3.6-flash`로 선별·요약(JSON Schema 강제), 본문 없는 항목은 모델에 미전송 — 테스트 통과 + 실제 호출 확인 (2026-08-10)
- **step 5 delivery** — 텔레그램 HTML 렌더링·4096자 분할, `sendMessage` 발송, 봇 토큰 마스킹 — 테스트 통과 + **실제 발송 성공** (2026-08-11)
- **step 6 pipeline** — `main.py` 전체 배선, 발송 성공 후에만 기록 갱신 — 테스트 통과 + 실제 `--dry-run` exit 0(수집 143건 → 선별 5건 → 본문 4/5) (2026-08-10)
- **step 7 ops-docs** — `.github/workflows/daily.yml`, `AGENTS.md`·`docs/`·`README.md` 작성 + **GitHub Actions 실행 검증 완료** (2026-08-11)
- **로그 토큰 마스킹 수정** — httpx의 INFO 요청 로그가 봇 토큰을 평문으로 남기던 문제. URL 로깅 라이브러리 WARNING 고정 + 출력 직전 마스킹 필터 + `basicConfig(force=True)` — 회귀 테스트 6건, 공개 Actions 로그에서 `bot***` 확인 (2026-08-11)

### 운영 검증 기록 (실제 실행)

| 항목 | 결과 |
| --- | --- |
| 로컬 실발송 (2026-08-11) | 수집 144 → 선별 5 → 본문 3/5 → 발송 성공, 기록 5건 |
| GitHub Actions 수동 실행 (run 31500137637) | conclusion **success**. 수집 135 → 중복 제거 132 → 선별 5 → 본문 5/5 → 발송 성공, 기록 10건 |
| 공개 Actions 로그 시크릿 노출 | 없음 (`bot***`로 마스킹 확인) |
| 상태 파일 자동 커밋 | `chore: update seen state` 커밋이 리포에 반영됨 |
| GitHub Secrets | `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 등록 완료 |

## 남은 것 (우선순위 순)

1. **소스 편중 관측** — 1회차 선별 5건 중 4건이 GitHub 저장소였다. 축(tech/money/enterprise/marketing)은 4개가 모두 채워졌으므로 축 편중은 아니고 **소스** 쏠림이다. 며칠 받아보고도 같으면 소스별 상한(예: 한 소스 최대 2건)을 검토한다. 표본이 부족해 지금 손대지 않는다.
2. **본문 추출 실패율 관측** — 1회차 2/5 실패(Docker 403, 본문 170자). 2회차는 0/5 실패. 실패한 항목은 설계대로 제목·링크만 나가므로 치명적이지 않지만, 실패율이 계속 높으면 User-Agent 조정이나 소스별 처리를 검토한다.
3. **발송 시각 조정** — 현재 `0 23 * * *` UTC(08:00 KST). 바꾸려면 `.github/workflows/daily.yml`의 cron만 수정한다. 절차는 `docs/OPERATIONS.md`.

## 블로커

없음.
