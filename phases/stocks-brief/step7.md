# Step 7: ops-docs

워크플로를 만들고 문서를 갱신한다. 이 step이 끝나면 리포지토리가 "주식 브리핑도 도는 프로젝트"로
일관되게 읽혀야 한다.

## 읽어야 할 파일

- `phases/stocks-brief/spec.md`   ← "확정 근거" 절이 ADR의 재료다
- `.github/workflows/daily.yml` — 기존 워크플로 구조. **이 파일을 수정하지 않는다**
- `AGENTS.md`, `README.md`
- `docs/` 전체 (ARCHITECTURE, BUSINESS_RULES, STANDARDS, SECURITY, OPERATIONS,
  ENGINEERING_NOTES, DECISIONS, tracking/STATUS.md)
- step 0~6 산출물 전부

## 작업

### 1. `.github/workflows/stocks-us.yml` 신설

```yaml
name: stocks-us
on:
  schedule:
    - cron: "0 22 * * 1-5"   # UTC 월~금 22:00 = KST 화~토 07:00
  workflow_dispatch:
permissions:
  contents: read
```

- `runs-on: ubuntu-latest`, `timeout-minutes: 10`
- `actions/checkout@v4` → `actions/setup-python@v5`(3.11, `cache: pip`) → `pip install -e ".[dev]"`
- 실행 step의 `env`:
  `TELEGRAM_BOT_TOKEN`·`TELEGRAM_CHAT_ID`·`GEMINI_API_KEY`는 `${{ secrets.* }}`,
  `STOCKS_WATCHLIST_US`는 **`${{ vars.STOCKS_WATCHLIST_US }}`** (Secrets가 아니라 Variables다)
- `run: python -m secretary.stocks --market us`

**cron 요일 주석을 반드시 남긴다.** 미국장은 KST 새벽에 마감하므로 UTC 요일과 KST 요일이
하루 어긋난다. UTC 금요일 22:00은 KST 토요일 07:00이고, 이때 보내는 것은 미국 금요일장 종가다.

### 2. `.github/workflows/stocks-kr.yml` 신설

같은 구조에서 아래만 다르다.

- `cron: "0 7 * * 1-5"` — UTC 월~금 07:00 = KST 월~금 16:00 (한국장 15:30 마감 30분 뒤)
- `STOCKS_WATCHLIST_KR: ${{ vars.STOCKS_WATCHLIST_KR }}`
- `run: python -m secretary.stocks --market kr`

**`permissions: contents: read` 이고 상태 커밋 step이 없다.** 이 파이프라인은 상태 파일을
쓰지 않으므로 `contents: write`도, `concurrency` 그룹도 필요 없다. 기존 `daily.yml`을 복사한 뒤
지우는 방식이면 이 두 가지가 남지 않았는지 확인한다.

### 3. `docs/ARCHITECTURE.md`

- 디렉토리 구조에 `stocks/` 서브패키지와 공용 모듈(`tghtml.py`, `gemini.py`)을 추가한다.
- "대표 흐름 1개"를 흐름 2개로 바꾼다 — 기존 AI 브리핑 흐름은 그대로 두고 주가 브리핑 흐름을
  추가한다. 주가 흐름에는 상태 저장 단계가 없다는 점을 명시한다.
- 워크플로가 3개(`daily.yml`, `stocks-us.yml`, `stocks-kr.yml`)임을 반영한다.

### 4. `docs/BUSINESS_RULES.md` — "주가 브리핑 규칙" 절 신설

기존 AI 브리핑 규칙은 건드리지 않고 새 절을 덧붙인다. spec에서 옮길 것:

- 용어(관심 종목, 시장 지표, 급등락 종목, 기준일)
- 등락률 계산 규칙 (`close`의 `None` 제거 후 마지막 두 유효값. `chartPreviousClose` 금지)
- 급등락 판정 (`abs(change_pct) >= threshold`, 기본 5.0, 시장 지표는 대상 아님)
- 해설 규칙 (**헤드라인이 유일한 근거. 헤드라인 없으면 해설 없음.** 투자 의견 금지)
- 휴장 판정 (기준일 != 시장 로컬 날짜)
- 렌더링 규칙 (숫자 포맷, 방향 표시)
- 엣지 케이스 표 (spec의 표를 옮긴다)

### 5. `docs/STANDARDS.md` — "모듈 경계"에 추가

- `stocks/`는 `secretary.main`·`sources`의 수집 계층·`state`·`extract`를 import 하지 않는다.
  공용 모듈(`config`, `http`, `log`, `telegram`, `tghtml`, `gemini`)과 `sources.base`의
  순수 헬퍼만 쓴다.
- `stocks/models.py`는 다른 `secretary` 모듈을 import 하지 않는다(`config.py`가 이를 쓰므로 순환).
- 검증 게이트에 `python -m secretary.stocks --market {us,kr} --dry-run`을 추가한다.

### 6. `docs/SECURITY.md`

- 시크릿은 여전히 3종이고 주식 파이프라인이 **그대로 재사용**한다는 점을 명시한다.
- **Variables와 Secrets의 구분**을 새로 적는다: `STOCKS_WATCHLIST_*`는 시크릿이 아니므로
  Variables에 둔다. 로그에 찍혀도 무해하며 GitHub의 자동 마스킹 대상이 아니다.
  그럼에도 리포지토리에 커밋하지 않는 이유는 **리포지토리가 공개이고 관심 종목이 사적 정보이기
  때문**이다. 보안이 아니라 프라이버시 결정임을 분명히 적는다.
- 발송 메시지에 나가는 것은 공개 시세와 뉴스 제목뿐임을 적는다.

### 7. `docs/OPERATIONS.md`

- 관심 종목 등록 절차:
  ```bash
  gh variable set STOCKS_WATCHLIST_US --body "AAPL:애플,NVDA:엔비디아"
  gh variable set STOCKS_WATCHLIST_KR --body "005930.KS:삼성전자,035720.KQ:카카오"
  gh variable list
  ```
  웹 UI 경로(Settings → Secrets and variables → Actions → **Variables** 탭)도 적는다.
  **Secrets 탭이 아니라는 점**을 명시한다.
- 심볼 찾는 법: Yahoo Finance에서 종목을 검색해 URL의 심볼을 쓴다. 한국은 코스피 `.KS`,
  코스닥 `.KQ` 접미가 붙는다(예: `005930.KS`).
- 로컬 실행 예시와 수동 실행(`gh workflow run stocks-us`).
- 발송 시각 변경 표에 주식 워크플로 2개를 추가한다. **미국장은 UTC 요일과 KST 요일이 하루
  어긋난다**는 주의를 적는다.
- 환경 변수 표에 `STOCKS_WATCHLIST_US`/`STOCKS_WATCHLIST_KR`/`STOCKS_MOVE_THRESHOLD`를 추가한다.

### 8. `docs/DECISIONS.md` — ADR 3개 추가

spec의 "확정 근거"를 근거로 쓰되, **대안에 구체적 기각 이유**를 적는다.

- **ADR-007: 주가 브리핑을 같은 리포지토리의 별도 파이프라인으로 만든다**
  대안: 기존 브리핑에 소스로 추가(하드 게이트 충돌, AI 뉴스 5건 자리를 잠식) /
  완전히 별도 리포지토리(봇 토큰 마스킹 코드와 문서 하네스를 복제하게 된다).
  결과: 리포지토리 정체성이 "AI 정보 배치"에서 "개인 비서"로 넓어졌고, 공용 모듈 2개를 추출했다.
- **ADR-008: 시세를 Yahoo Finance v8 chart 직접 호출로 가져온다**
  대안: KIS Open API(계좌 개설 + 24시간 토큰 갱신 — ADR-001에서 카카오톡을 기각한 것과 같은
  종류의 함정) / Twelve Data(무료 티어의 KRX 포함 여부 불확실) / Alpha Vantage(무료 25 req/day로
  부족) / pykrx(미국을 못 준다) / `yfinance` 라이브러리(pandas 의존성, 잦은 파손).
  결과: 비공식 엔드포인트라 예고 없이 막힐 수 있다. 막히면 조회 실패 경로를 타 실패 알림이 오고,
  교체 시 손댈 파일은 `stocks/quotes.py` 하나다.
- **ADR-009: 관심 종목을 GitHub Actions Variables에 둔다**
  대안: 리포지토리에 커밋(공개 리포라 관심 종목이 노출된다) / 리포를 private으로 전환
  (Actions 무료 분당 2,000분/월 제한이 생기고 기존 AI 브리핑까지 비공개가 된다) /
  Secrets에 저장(시크릿이 아닌 값을 넣으면 마스킹 때문에 로그 디버깅이 어려워진다).
  결과: 종목 변경 이력이 남지 않고, 종목을 바꾸려면 리포지토리 설정 화면에 들어가야 한다.

### 9. `docs/ENGINEERING_NOTES.md` — 함정 4개 추가

각 항목은 증상 → 원인 → 대응 → 검증 순으로 적는다.

- **`meta.chartPreviousClose`는 직전 거래일 종가가 아니다** — 조회 창 시작 이전의 종가다.
  실측: 삼성전자 `chartPreviousClose=239500`인데 직전 거래일 종가는 268500이었다.
  이걸 쓰면 예외 없이 그럴듯하게 틀린 등락률이 나간다. 대응: `close` 배열의 마지막 두 유효값.
  검증: `tests/test_stocks_quotes.py`의 회귀 테스트.
- **Yahoo chart의 `close` 배열에는 `None`이 섞인다** — 중간에도, **마지막 원소에도** 들어온다.
  실측: `USDKRW=X`는 중간에, `035720.KQ`는 마지막 원소가 `None`이었다. `closes[-1]`을 그냥 쓰면
  터진다. 대응: `None` 제거 후 유효값 2개 이상일 때만 계산.
- **Yahoo v8 chart는 이 프로젝트의 User-Agent를 거부하지 않는다** — 계획 단계에서 6개 심볼을
  `ai-secretary/0.1`로 호출해 전부 200을 받았다. 브라우저 UA 위장이 불필요하므로
  `http.make_client`를 그대로 쓴다. 다만 v7/quote 엔드포인트는 막혀 있으니 v8/chart를 쓴다.
- **미국장 워크플로의 cron 요일은 KST 요일과 하루 어긋난다** — 미국장은 KST 새벽 05~06시에
  마감한다. `0 22 * * 1-5`(UTC 월~금)는 KST 화~토 07:00에 실행되며, 각 실행이 다루는 것은
  그 전날 미국장이다. UTC 요일로 적혀 있으니 KST 요일로 착각해 고치지 않는다.

또한 "RSS 피드 추가/교체" 옆에 **"관심 종목 추가/교체" 체크리스트**를 넣는다:
1. Yahoo Finance에서 심볼 확인 → 검증: v8 chart를 실제 호출해 HTTP 200이고 `close` 유효값이 2개 이상
2. `gh variable set STOCKS_WATCHLIST_*` → 검증: `gh variable list`
3. 검증: `STOCKS_WATCHLIST_XX="..." python -m secretary.stocks --market xx --dry-run` exit 0

### 10. `AGENTS.md`

- 개요를 두 배치로 고쳐 쓴다(AI 브리핑 + 주가 브리핑). "웹 화면도 서버도 없다"는 유지된다.
- 기술 스택에 Yahoo v8 chart와 Google News RSS를 추가한다.
- **하드 게이트에 추가**: "헤드라인을 확보하지 못한 종목에 급등락 해설을 생성하지 않는다"
- 명령어에 `python -m secretary.stocks --market {us,kr} --dry-run`을 추가한다.
- "작업 전 체크리스트"에 주가 규칙을 건드릴 때 볼 문서를 추가한다.

### 11. `README.md`

두 배치를 모두 소개하도록 갱신한다. 발송 시각 3개(08:00 / 07:00 / 16:00 KST)를 적는다.

### 12. `docs/tracking/STATUS.md`

phase `stocks-brief`의 진행 상황을 기록한다. 완료된 step, 검증 결과(`verify.sh` exit code와
테스트 개수), 남은 것(실제 Actions 실행 검증, Variables 등록)을 적는다.
**아직 확인하지 않은 것을 완료로 적지 않는다.**

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
import pathlib, sys
need = ['.github/workflows/stocks-us.yml', '.github/workflows/stocks-kr.yml']
missing = [p for p in need if not pathlib.Path(p).exists()]
print('missing:', missing); sys.exit(1 if missing else 0)
"
grep -n 'cron' .github/workflows/stocks-us.yml .github/workflows/stocks-kr.yml
grep -c 'contents: write' .github/workflows/stocks-us.yml .github/workflows/stocks-kr.yml || echo "contents:write 없음 (정상)"
grep -n 'vars.STOCKS_WATCHLIST' .github/workflows/stocks-us.yml .github/workflows/stocks-kr.yml
grep -n 'ADR-007\|ADR-008\|ADR-009' docs/DECISIONS.md
python -m secretary.main --dry-run > /dev/null; echo "regression exit=$?"
```

- 워크플로에 `contents: write`가 **없어야** 한다.
- `secrets.STOCKS_WATCHLIST`가 아니라 `vars.STOCKS_WATCHLIST`여야 한다.

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 exit code를 캡처해 보고한다.
2. 문서 상호 참조를 확인한다: AGENTS.md의 문서 내비게이션에서 언급한 경로가 실제로 존재하는가,
   ARCHITECTURE.md의 디렉토리 구조가 실제 파일과 일치하는가.
3. 결과에 따라 `phases/stocks-brief/index.json`의 해당 step을 갱신한다.
4. **실제 GitHub Actions 실행 검증은 이 step의 범위 밖이다.** `workflow_dispatch`는 워크플로
   파일이 기본 브랜치에 있어야 목록에 뜨기 때문이다(ENGINEERING_NOTES). 머지 후 수동 실행할
   항목으로 STATUS.md의 "남은 것"에 적는다.

## 금지사항

- `.github/workflows/daily.yml`을 수정하지 마라. 기존 AI 브리핑은 그대로 돈다.
- 주식 워크플로에 `contents: write` 권한이나 상태 커밋 step을 넣지 마라. 이유: 이 파이프라인은
  상태 파일을 쓰지 않는다. 불필요한 쓰기 권한이다.
- `STOCKS_WATCHLIST_*`를 `secrets.`로 참조하지 마라. Variables다.
- 관심 종목 예시를 실제 사용자의 종목으로 채우지 마라. 문서 예시는 일반적인 종목명을 쓴다.
- 문서에 시크릿 **값**을 적지 마라. 이름만 적는다.
- 확인하지 않은 것을 STATUS.md에 완료로 적지 마라. 실제 Actions 실행은 아직 검증되지 않았다.
- spec의 "범위 제외"에 있는 것을 만들지 마라.
