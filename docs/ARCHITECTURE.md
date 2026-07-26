# 아키텍처

> 작성 기준: 시스템 수준만 — 컴포넌트가 무엇이고 어떻게 연결되는지. 도메인 규칙은 BUSINESS_RULES.md에, 코드 컨벤션은 STANDARDS.md에 쓴다. "모던한 아키텍처를 쓴다" 같은 수식어가 아니라 A → B → C의 구체적 연결과 프로토콜을 적는다.

## 디렉토리 구조

```
{예:
src/
├── app/               # 페이지 + API 라우트
├── components/        # UI 컴포넌트
├── services/          # 도메인 로직 + 외부 API 래퍼
├── lib/               # 유틸리티
└── types/             # 타입 정의
}
```

## 컴포넌트와 연결

{무엇이 무엇과 어떤 프로토콜로 통신하는지, 외부 의존 포함.
예: 웹(Next.js) → REST → API 라우트 핸들러 → services/ → PostgreSQL. 결제는 Stripe webhook 수신(POST /api/webhooks/stripe)}

## 대표 흐름 1개

{대표적인 요청이 진입점부터 응답까지 지나는 경로.
예: 주문 생성 — 폼 제출 → POST /api/orders → services/order.create() → DB 트랜잭션(재고 차감 + 주문 생성) → 201 응답 → UI 갱신}

## 패턴

{예: Server Components 기본, 인터랙션이 필요한 곳만 Client Component}

## 상태 관리

{예: 서버 상태는 Server Components, 클라이언트 상태는 useState/useReducer. 전역 상태 라이브러리 없음}
