# 보안

> 작성 기준: 무엇을 보호하고, 누가 무엇을 할 수 있고, 무엇을 기록하는지. 성공 경로만이 아니라 실패 경로(잘못된 크리덴셜, 만료, 잠금)를 적는다. "보안 베스트 프랙티스를 따른다" 같은 문장 금지 — 이 프로젝트의 결정만.

이 프로젝트에는 로그인도, 사용자도, 수신 엔드포인트도 없다. 보호 대상은 오직 시크릿 3종이다.

## 시크릿

| 이름 | 출처 | 저장 위치 | 만료 |
| --- | --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | BotFather가 봇 생성 시 발급 | GitHub Secrets (로컬은 `.env`) | 없음. revoke할 때까지 유효 |
| `TELEGRAM_CHAT_ID` | `getUpdates`로 확인한 수신 채팅 ID | GitHub Secrets (로컬은 `.env`) | 없음 |
| `GEMINI_API_KEY` | Google AI Studio | GitHub Secrets (로컬은 `.env`) | 없음. 콘솔에서 삭제·재발급 |

- `GITHUB_TOKEN`은 워크플로가 `${{ github.token }}`으로 주입하는 실행별 임시 토큰이다. 등록할
  시크릿이 아니다. 로컬에서는 없어도 동작한다(GitHub API 60req/h 제한).
- `.env`는 `.gitignore`에 있다. 커밋되지 않는다.
- 값은 환경 변수로만 들어온다. 파일·코드·문서에 값을 적지 않는다. 발급 절차는 `OPERATIONS.md`.

## 로그 마스킹 규칙

- 텔레그램은 인증을 헤더가 아니라 **경로**에 담는다(`/bot<token>/sendMessage`). URL을 남기는
  모든 경로가 유출 경로다 — 로그, 예외 메시지, `__context__`로 이어진 원인 예외.
- 그래서 `telegram.py`는:
  - `raise_for_status()`를 쓰지 않는다. httpx가 만드는 예외 메시지에 요청 URL이 그대로 들어간다.
    대신 응답 JSON의 `ok`를 직접 본다.
  - httpx 예외는 `TelegramError`로 감싸고 `from None`으로 원인 사슬을 끊는다.
  - 메시지에 남은 토큰 문자열을 `***`로 치환한다.
  - 로그에는 상수 `MASKED_URL`(`https://api.telegram.org/bot***/sendMessage`)만 찍는다.
  - 검증: `tests/test_telegram.py::test_bot_token_never_appears_in_errors_or_logs`
- `config.py`의 에러 메시지에는 변수 **이름**만 담는다. 값은 출력하지 않는다.
  검증: `tests/test_config.py::test_error_message_does_not_leak_values`
- 실패 알림 메시지(`render_failure`)에는 `describe_error`가 만든 예외 타입 + 한 줄 요약만 담는다.
  스택트레이스는 stderr 로그에만 남긴다.
- GitHub Actions는 등록된 시크릿 값이 로그에 나타나면 자동으로 `***`로 가린다. 이것은 마지막
  안전망이지 1차 방어가 아니다 — 값이 변형되어(예: URL 인코딩) 찍히면 가려지지 않는다.

## 발송 메시지

- 텔레그램으로 나가는 내용은 공개된 기사 제목·링크·요약뿐이다. 환경 변수 값이나 파일 경로를
  메시지에 담지 않는다.
- Gemini로 보내는 내용도 공개된 기사 제목·본문뿐이다. 무료 티어 입력이 모델 개선에 쓰일 수
  있으므로 비공개 정보를 프롬프트에 넣지 않는다.

## 유출 시 대응

- **봇 토큰**: BotFather에서 해당 봇에 `/revoke` → 새 토큰 발급 → GitHub Secrets의
  `TELEGRAM_BOT_TOKEN` 갱신 → 로컬 `.env` 갱신. 옛 토큰은 즉시 무효가 된다.
- **Gemini 키**: Google AI Studio에서 키 삭제 후 새 키 발급 → `GEMINI_API_KEY` 갱신.
- **커밋에 섞인 경우**: 위 재발급을 **먼저** 한다. 히스토리에서 지우는 것은 그다음이다.
  리포지토리가 public이면 지우기 전에 이미 복제됐다고 가정한다.
- `chat_id`는 그 자체로 발송 권한을 주지 않는다(봇 토큰이 있어야 한다). 토큰 재발급으로 충분하다.

## 감사 로그

별도의 감사 로그는 없다. 남는 것은 두 가지다.

- GitHub Actions 실행 로그: 소스별 수집 건수, 선별·추출 건수, 발송 조각 수, 실패 사유
- `state/seen.json` 커밋 히스토리: 언제 몇 건이 발송됐는지 (URL은 sha1이라 원문이 남지 않는다)
