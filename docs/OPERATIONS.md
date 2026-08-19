# 운영

> 작성 기준: 순서대로 실행하면 동작해야 한다. 셋업은 사전 요구부터 복붙 가능한 명령으로 적고, 순서를 바꾸면 실패하는 지점을 명시한다. 환경 변수는 이름만이 아니라 역할까지.

## 사전 요구

- Python 3.11 이상 (GitHub Actions는 3.11로 고정 실행한다)
- 텔레그램 계정
- Google AI Studio 계정 (Gemini API 키 발급용, 신용카드 불필요)
- GitHub CLI `gh` (시크릿 등록·수동 실행에 쓴다. 웹 UI로 해도 된다)

## 1. 텔레그램 봇 만들기

1. 텔레그램에서 **@BotFather** 와 대화를 시작하고 `/newbot` 을 보낸다.
2. 봇 표시 이름 → 봇 username(반드시 `bot`으로 끝난다) 순으로 답한다.
3. BotFather가 `123456789:AAH...` 형태의 토큰을 준다. 이것이 `TELEGRAM_BOT_TOKEN` 이다.
4. **만든 봇과의 대화방을 열고 아무 메시지나 보낸다.** 봇은 먼저 말을 걸 수 없으므로, 이 단계를
   건너뛰면 다음 단계에서 `result: []`만 나온다.
5. 수신 채팅 ID를 확인한다:

   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" \
     | python3 -c "import json,sys; print([u['message']['chat']['id'] for u in json.load(sys.stdin)['result'] if 'message' in u])"
   ```

   출력된 숫자가 `TELEGRAM_CHAT_ID` 다(개인 대화는 양수, 그룹은 `-100...`으로 시작하는 음수).

## 2. Gemini API 키 발급

1. <https://aistudio.google.com/apikey> 에서 **Create API key**.
2. 발급된 문자열이 `GEMINI_API_KEY` 다. 화면을 벗어나면 다시 볼 수 없으므로 그 자리에서 저장한다.

## 3. GitHub Secrets 등록

워크플로가 읽는 이름 그대로 등록한다. 값은 프롬프트로 입력되어 셸 히스토리에 남지 않는다.

```bash
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
gh secret set GEMINI_API_KEY
gh secret list          # 세 개가 보이면 완료
```

웹 UI로 할 경우: 리포지토리 → Settings → Secrets and variables → Actions → New repository secret.

`GITHUB_TOKEN` 은 등록하지 않는다. 워크플로가 `${{ github.token }}` 으로 자동 주입한다.

## 4. 관심 종목 등록 (주가 브리핑)

관심 종목은 **Secrets가 아니라 Variables** 다. 시크릿이 아니므로 마스킹되지 않고, 그래야
Actions 로그에서 어떤 심볼이 조회에 실패했는지 볼 수 있다. 그런데도 리포지토리에 커밋하지 않는
이유는 이 리포가 공개이고 관심 종목이 사적 정보이기 때문이다(`SECURITY.md`).

```bash
gh variable set STOCKS_WATCHLIST_US --body "AAPL:애플,NVDA:엔비디아"
gh variable set STOCKS_WATCHLIST_KR --body "005930.KS:삼성전자,035720.KQ:카카오"
gh variable list
```

웹 UI로 할 경우: 리포지토리 → Settings → Secrets and variables → Actions → **Variables 탭** →
New repository variable. **Secrets 탭이 아니다.**

형식은 쉼표로 구분된 `심볼:표시명` 목록이다. 표시명을 생략하면 심볼을 표시명으로 쓰고,
표시명은 급등락 해설의 뉴스 검색어로도 쓰인다(전체 규칙은 `BUSINESS_RULES.md`).

**심볼 찾는 법**: <https://finance.yahoo.com> 에서 종목을 검색해 URL에 찍힌 심볼을 그대로 쓴다
(`finance.yahoo.com/quote/AAPL` → `AAPL`). 한국 종목은 접미가 붙는다 — 코스피는 `.KS`,
코스닥은 `.KQ` 다(예: `005930.KS`). 등록 전에 실제로 도는지 확인하는 절차는
`ENGINEERING_NOTES.md` 의 "관심 종목 추가/교체" 체크리스트에 있다.

관심 종목을 등록하지 않아도 브리핑은 돈다 — 시장 지표(지수·환율)만 실려 온다.

## 5. 로컬 실행

```bash
pip install -e ".[dev]"

# 아래 "환경 변수" 표를 보고 .env 를 만든다 (KEY=value 한 줄씩)
set -a; source .env; set +a   # 코드가 .env를 자동으로 읽지 않는다 — 반드시 셸에 export한다

python -m secretary.main --dry-run          # 발송·기록 저장 없이 stdout 출력
python -m secretary.main --dry-run --limit 2 --verbose
python -m secretary.main                    # 실제 발송 + state/seen.json 갱신

# 주가 브리핑 — --market 은 필수다(빠지면 exit 2)
python -m secretary.stocks --market us --dry-run
python -m secretary.stocks --market kr --dry-run --verbose
python -m secretary.stocks --market us      # 실제 발송

# 관심 종목을 .env 없이 한 번만 시험할 때
STOCKS_WATCHLIST_US="AAPL:애플" python -m secretary.stocks --market us --dry-run
```

- `--dry-run`은 텔레그램 시크릿 없이도 돈다. `GEMINI_API_KEY`는 필요하다(두 배치 모두).
- `.env`는 `.gitignore`에 있다. 커밋되지 않는다.

## 6. 워크플로 수동 실행

`workflow_dispatch`는 워크플로 파일이 **기본 브랜치에 있어야** 목록에 뜬다. 기능 브랜치에만 있는
상태에서는 실행되지 않는다.

```bash
gh workflow run daily-brief     # AI 브리핑 (기본 브랜치에서 실행)
gh workflow run stocks-us       # 미국장 주가 브리핑
gh workflow run stocks-kr       # 한국장 주가 브리핑
gh run watch                    # 진행 상황 따라가기
gh run view --log               # 실패 시 로그 확인
```

텔레그램에 메시지가 도착했는지 확인한다. AI 브리핑은 추가로 `git pull` 후 `state/seen.json`이
갱신됐는지 본다 — 주가 브리핑은 상태 파일을 쓰지 않으므로 볼 것이 없다.

## 7. 발송 시각 변경

해당 워크플로의 cron 한 줄만 고친다. 값은 **UTC** 다 (KST = UTC + 9시간).

| 워크플로 | 현재 cron (UTC) | 실행 시각 (KST) | 내용 |
| --- | --- | --- | --- |
| `daily.yml` | `0 23 * * *` | 매일 08:00 | AI 브리핑 |
| `stocks-us.yml` | `0 22 * * 1-5` | **화~토** 07:00 | 미국장 종가 |
| `stocks-kr.yml` | `0 7 * * 1-5` | 월~금 16:00 | 한국장 종가 |

**미국장은 UTC 요일과 KST 요일이 하루 어긋난다.** 미국장이 KST 새벽에 마감하기 때문이다 —
`0 22 * * 1-5`(UTC 월~금)는 KST 화~토 07:00에 돌고, 각 실행이 다루는 것은 그 전날 미국장이다.
UTC 금요일 22:00 실행이 KST 토요일 아침에 미국 금요일장 종가를 보낸다. 요일 필드를 KST 기준으로
착각해 고치지 않는다.

AI 브리핑처럼 매일 도는 워크플로의 시각 환산:

| 원하는 KST 시각 | cron (UTC) |
| --- | --- |
| 07:00 | `0 22 * * *` |
| 08:00 | `0 23 * * *` |
| 09:00 | `0 0 * * *` |
| 21:00 | `0 12 * * *` |

GitHub Actions의 스케줄은 정시 실행을 보장하지 않는다. 러너가 붐비면 수십 분 늦게 시작한다.

## 명령어

```bash
bash scripts/verify.sh              # 검증 단일 진입점 (ruff check + ruff format --check + pytest)
python -m secretary.main --dry-run  # 실제 수집·요약 후 발송 없이 stdout 출력
python -m secretary.stocks --market us --dry-run   # 주가 브리핑(미국장) 발송 없이 출력
python -m secretary.stocks --market kr --dry-run   # 주가 브리핑(한국장) 발송 없이 출력
```

## 환경 변수

| 이름 | 필수 | 기본값 | 역할 |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | O | — | 봇 인증. 요청 URL 경로에 들어가므로 로그에 남기지 않는다 |
| `TELEGRAM_CHAT_ID` | O | — | 브리핑을 받을 채팅 ID |
| `GEMINI_API_KEY` | O | — | Gemini API 인증 (선별·요약, 급등락 해설) |
| `GITHUB_TOKEN` | X | 없음 | GitHub Search API rate limit 완화. 없으면 60req/h |
| `BRIEF_ITEM_COUNT` | X | `5` | AI 브리핑 항목 수. `--limit N`이 우선한다 |
| `STATE_PATH` | X | `state/seen.json` | AI 브리핑의 발송 기록 파일 경로 |
| `STOCKS_WATCHLIST_US` | X | 빈 값 | 미국 관심 종목 `심볼:표시명` 쉼표 목록. **Variables** |
| `STOCKS_WATCHLIST_KR` | X | 빈 값 | 한국 관심 종목 `심볼:표시명` 쉼표 목록. **Variables** |
| `STOCKS_MOVE_THRESHOLD` | X | `5.0` | 급등락 판정 기준(%). 절댓값이 이 값 이상이면 해설 대상 |
| `HTTP_TIMEOUT` | X | `20` | 외부 HTTP 타임아웃(초). 두 배치 공통 |

`--dry-run`일 때는 필수 검사에서 텔레그램 두 개가 빠지고 `GEMINI_API_KEY`만 요구된다.
두 배치 모두 같은 규칙이다.

`STOCKS_WATCHLIST_*` 는 시크릿이 아니라 Variables다. 등록 절차는 위 "4. 관심 종목 등록",
왜 Secrets가 아닌지는 `SECURITY.md`.

## 배포

배포 개념이 없다. 기본 브랜치에 머지된 코드가 다음 cron 실행에 그대로 쓰인다.
상태 파일(`state/seen.json`)은 `daily.yml` 이 실행 성공 후 자동으로 커밋·푸시한다.
주가 워크플로 둘은 상태 파일을 쓰지 않으므로 커밋 단계도, `contents: write` 권한도 없다.
