# Step 5: delivery

## 읽어야 할 파일

- `phases/daily-brief-mvp/spec.md`   ← 요구 동작의 정본 (엣지 케이스: 4096자 초과, 발송 실패)
- `src/secretary/models.py` (step 0 — `Brief`, `BriefEntry`)
- `src/secretary/config.py` (step 0)
- `src/secretary/http.py` (step 1)

## 작업

브리핑을 텔레그램 메시지로 렌더링하고 발송한다.

### `src/secretary/render.py`

```python
TELEGRAM_LIMIT = 4096

def render_brief(brief: Brief) -> list[str]: ...
def render_failure(reason: str) -> str: ...
```

- 출력은 텔레그램 **HTML** 포맷이다(`parse_mode=HTML`). 허용 태그는 `<b> <i> <u> <s> <code> <pre> <a href="">` 뿐이다.
- 태그가 아닌 모든 텍스트는 `&`, `<`, `>` 를 이스케이프한다. 제목·요약에 `<`나 `&`가 들어와도 발송이 깨지지 않아야 한다.
- 항목 형식(참고안 — 세부 문구는 재량):

```
📅 <b>AI 브리핑 · 8월 9일</b>

1. <a href="URL">원문 제목</a>  ·  [기술]
<i>한국어 부제</i>
· 요약 1
· 요약 2
· 요약 3
💡 실행 힌트 한 줄
<code>hackernews · 342점</code>
```

- `summary_ko`가 빈 리스트인 항목은 요약·힌트·부제 줄을 통째로 생략하고 제목·축·출처·링크만 남긴다. "요약 실패" 같은 문구를 억지로 넣지 마라.
- 축 라벨 한국어 매핑: `tech`→기술, `money`→수익화, `enterprise`→기업 사례, `marketing`→마케팅.
- `render_brief`는 **문자열 리스트**를 반환한다. 전체가 `TELEGRAM_LIMIT` 이하면 1개, 넘으면 **항목 경계에서** 분할한다. 항목 하나가 단독으로 한도를 넘으면 그 항목만 잘라내고 말미에 `…` 를 붙인다.
- `render_failure(reason)`: "⚠️ 오늘 브리핑을 만들지 못했습니다: {reason}" 형태. **reason에 시크릿이나 전체 스택트레이스를 넣지 마라.**

### `src/secretary/telegram.py`

```python
def send_messages(cfg: Config, messages: list[str]) -> None: ...
```

- `POST https://api.telegram.org/bot{token}/sendMessage`
- body: `chat_id`, `text`, `parse_mode="HTML"`, `disable_web_page_preview=True`
- 여러 건이면 순서대로 발송한다. 중간 실패 시 예외를 올린다(step 6이 처리).
- 응답 JSON의 `ok`가 `false`면 `description`을 담아 예외를 던진다. HTTP 200이어도 실패일 수 있다.
- **토큰을 로그·예외 메시지에 절대 넣지 마라.** URL을 로그에 남길 때는 토큰 부분을 `***`로 마스킹한다.

### 테스트 `tests/test_render.py` / `tests/test_telegram.py`

- 요약이 있는 항목과 없는 항목이 섞인 `Brief` → 없는 항목에 요약/힌트 줄이 나타나지 않는가
- 제목에 `<script>` 와 `&` 가 들어간 항목 → 이스케이프되어 출력되는가
- 항목이 많아 4096자를 넘는 `Brief` → 반환 리스트가 2개 이상이고 **각 조각이 모두 4096자 이하**인가
- 항목 1개가 단독으로 한도를 넘는 경우 → 잘려서 한도 이하가 되는가
- `send_messages`: HTTP는 monkeypatch. `ok: false` 응답에서 예외가 나는가 / 예외 메시지와 로그에 봇 토큰 문자열이 포함되지 않는가 ← **이 테스트는 반드시 있어야 한다**

## Acceptance Criteria

```bash
bash scripts/verify.sh
python -c "
from datetime import datetime, timezone
from secretary.models import Brief, BriefEntry
from secretary.render import render_brief
e1 = BriefEntry(title='A <script> & B', subtitle_ko='부제', url='https://x.com/1',
                source='hackernews', axis='tech', summary_ko=['a','b','c'], action_hint_ko='해봐라')
e2 = BriefEntry(title='본문 없음', subtitle_ko='', url='https://x.com/2',
                source='github', axis='money', summary_ko=[], action_hint_ko=None)
parts = render_brief(Brief(generated_at=datetime.now(timezone.utc), entries=[e1, e2]))
assert all(len(p) <= 4096 for p in parts)
assert '<script>' not in parts[0]
print(parts[0])
"
```

## 검증 절차

1. 위 AC 커맨드를 실제로 실행하고 출력된 메시지를 눈으로 확인한다.
2. 확인한다: 모든 조각이 4096자 이하인가 / 이스케이프가 동작하는가 / 토큰 마스킹 테스트가 통과하는가.
3. 결과에 따라 `phases/daily-brief-mvp/index.json`의 step 5를 갱신한다.

## 금지사항

- `parse_mode=MarkdownV2`를 쓰지 마라. 이유: `.`, `-`, `!`, `(` 등 18개 문자를 모두 이스케이프해야 하고, 요약 문장에서 한 글자만 놓쳐도 발송이 400으로 실패한다.
- 텔레그램 SDK 라이브러리(python-telegram-bot 등)를 추가하지 마라. 이유: sendMessage 하나를 위해 봇 프레임워크 전체를 들일 이유가 없다.
- 카카오톡 발송 경로를 만들지 마라. spec의 범위 제외 항목이다.
- 발송 실패를 삼키고 성공한 척하지 마라. 이유: 발송 기록이 갱신되어 해당 항목이 영영 유실된다.
