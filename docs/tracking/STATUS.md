# 현재 상태

> 작성 기준: 매 사이클 갱신. "완료"는 검증된 상태만 — 테스트 없는 구현은 "구현됨, 미검증"으로 구분해서 적는다. "남은 것"은 막연한 개선("성능 개선 필요")이 아니라 구체적 항목.

기준 시점: 2026-08-10 / 브랜치 `feat-daily-brief-mvp` / phase `daily-brief-mvp`

## 완료

`bash scripts/verify.sh` exit 0 (ruff check + ruff format --check + pytest 61 passed).

- **step 0 project-setup** — pyproject(src 레이아웃, ruff+pytest 게이트), `config`/`models`/`log` 뼈대 — 테스트 통과 (2026-08-09)
- **step 1 sources** — HN(Algolia) / GeekNews / GitHub Search / RSS 4개 소스 + 공유 httpx 클라이언트, 소스별 실패 흡수 — 테스트 통과 + 실제 수집 108건 확인 (2026-08-09)
- **step 2 state-dedupe** — URL 정규화·sha1 키, `seen.json` 원자적 저장, 90일 prune — 테스트 통과 (2026-08-09)
- **step 3 extract** — trafilatura 본문 추출, 300자 미만·모든 예외는 `None`, 8000자 상한 — 테스트 통과 + 실제 사이트 추출 확인 (2026-08-09)
- **step 4 llm-curate-summarize** — Gemini `gemini-3.6-flash`로 선별·요약(JSON Schema 강제), 본문 없는 항목은 모델에 미전송 — 테스트 통과 + 실제 호출 확인 (2026-08-10)
- **step 5 delivery** — 텔레그램 HTML 렌더링·4096자 분할, `sendMessage` 발송, 봇 토큰 마스킹 — 테스트 통과 (2026-08-09)
- **step 6 pipeline** — `main.py` 전체 배선, 발송 성공 후에만 기록 갱신 — 테스트 통과 + 실제 `--dry-run` exit 0(수집 143건 → 선별 5건 → 본문 4/5) (2026-08-10)
- **step 7 ops-docs (부분)** — `.github/workflows/daily.yml` 작성, `AGENTS.md`·`docs/`·`README.md` 실제 내용으로 채움 — 로컬 검증만 통과 (verify exit 0, 워크플로 YAML 파싱 ok, 플레이스홀더 0건). **워크플로 실제 실행은 미검증** (2026-08-10)

## 남은 것 (우선순위 순)

1. **GitHub Secrets 등록** — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`. 절차는 `docs/OPERATIONS.md`. 이것 없이는 워크플로가 어떤 실행에서도 성공할 수 없다.
2. **워크플로 수동 실행 검증** — 워크플로 파일을 기본 브랜치에 머지한 뒤 `gh workflow run daily-brief` → 텔레그램 도착 확인 → `git pull` 후 `state/seen.json` 갱신 확인 → 로그에 시크릿 노출 없음 확인.
3. **리포지토리 정리 판단** — 현재 remote는 `ggangddagood/ai-framework`(프레임워크 템플릿)이다. 이 배치를 여기서 돌릴지, ai-secretary 전용 리포로 옮길지 결정이 필요하다. 시크릿을 어느 리포에 등록할지가 여기에 달려 있다.
4. **축 편중 관측** — `money`/`marketing` 축 후보가 얇다. 며칠 발송해 보고 판단한다. 상세는 `FINDINGS.md`.

## 블로커

- GitHub Secrets 3종이 등록되어 있지 않다(`gh secret list` 결과 없음). 값은 운영자만 만들 수 있으므로 에이전트가 해결할 수 없다. step 7의 실행 검증이 여기서 막혀 있다.
