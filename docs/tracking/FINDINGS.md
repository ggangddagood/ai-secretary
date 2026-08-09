# 미해결 문제

> 작성 기준: 현재 세션에서 해결할 수 없는 문제만. "조사하기 귀찮은 것"의 보관소가 아니다 — 먼저 고치려고 시도하고, 고쳤으면 여기 남기지 않는다(얻은 지식은 ENGINEERING_NOTES.md로, 새 규칙이 필요하면 STANDARDS.md로). 등록할 땐 "왜 지금 못 고치나"가 반드시 있어야 한다.

### Indie Hackers 피드가 사라져 RSS 후보에서 제외 (step 1)

- **증상**: `https://www.indiehackers.com/feed.xml`, `https://www.indiehackers.com/rss` 모두 HTTP 200을 주지만 `content-type: text/html`에 쿠키 동의 스크립트가 담긴 HTML을 반환한다. feedparser 결과는 `bozo=1`, `entries=0`.
- **영향**: spec이 지정한 "인디해커·마케팅 뉴스레터" 소스가 비어 `money`/`marketing` 축의 후보가 줄어든다.
- **왜 지금 못 고치나**: 사이트가 공개 피드를 폐지한 것으로 보이며 대체 공식 엔드포인트를 찾지 못했다.
- **접근안**: Lenny's Newsletter(`https://www.lennysnewsletter.com/feed`, 20건 확인)로 대체해 `RSS_FEEDS`에 넣었다. 마케팅 축이 계속 얇으면 TLDR Marketing(`https://tldr.tech/api/rss/marketing`, 20건 확인)을 추가 후보로 검토한다.

### RSS 그룹이 Show HN에 쏠린다 (step 1)

- **증상**: 24시간 창에서 실제 수집 결과가 Show HN 20건 / Simon Willison 1건 / Lenny's 2건 / Latent Space·OpenAI·Google AI 0건이었다. RSS 23건 중 20건이 Show HN이다.
- **영향**: step 4의 LLM 선별이 보는 RSS 후보가 사실상 Show HN 단일 소스가 되어, 4개 축 중 `tech`에 편중될 수 있다.
- **왜 지금 못 고치나**: 나머지 피드는 정상이며 단지 발행 주기가 24시간보다 길다. 소스 문제가 아니라 창 크기·소스 구성의 문제이고, 선별 로직이 아직 없어 실제 영향을 측정할 수 없다.
- **접근안**: step 4에서 축별 편중이 확인되면 (a) 저빈도 피드에만 더 긴 창을 주거나 (b) 소스별 상한을 두는 방안을 검토한다.

### `ANTHROPIC_API_KEY`가 없어 실제 LLM 스모크(AC)를 실행하지 못함 (step 6)

- **증상**: `python3 -m secretary.main --dry-run --limit 5`가 `설정 오류: 필수 환경 변수가 없습니다: ANTHROPIC_API_KEY`로 exit 1. 실행 환경(셸, `~/.zshrc`, `.claude/settings*.json`)에 키가 없다.
- **영향**: 선별·요약 프롬프트가 실제 응답에서 의도대로 동작하는지, 요약 3줄이 원문과 맞는지 아직 아무도 확인하지 못했다. step 4의 LLM 코드는 가짜 클라이언트 테스트로만 검증된 상태다.
- **왜 지금 못 고치나**: 시크릿은 사용자만 주입할 수 있다. 코드로 우회할 수 있는 문제가 아니다.
- **접근안**: `ANTHROPIC_API_KEY=... python3 -m secretary.main --dry-run --limit 5`를 사용자가 1회 실행해 exit 0과 요약 품질을 확인하면 step 6이 완료된다. LLM을 스텁으로 둔 상태에서 수집 108건 → 선별 5건 → 본문 추출 5/5 → 렌더링까지는 실제 네트워크로 확인했다.
