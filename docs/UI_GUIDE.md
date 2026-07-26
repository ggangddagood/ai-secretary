# UI 디자인 가이드

> 작성 기준: 이 프로젝트의 시각적 결정만. 값(색/간격/폰트)은 실제 사용값으로 채운다. UI가 없는 프로젝트면 이 파일을 삭제한다. "AI 슬롭 안티패턴" 표는 프로젝트와 무관하게 유지를 권장한다.

## 디자인 원칙

1. {원칙 1 — 예: "도구처럼 보여야 한다. 마케팅 페이지가 아니라 매일 쓰는 대시보드"}
2. {원칙 2}
3. {원칙 3}

## AI 슬롭 안티패턴 — 하지 마라

| 금지 사항 | 이유 |
|-----------|------|
| backdrop-filter: blur() | glass morphism은 AI 템플릿의 가장 흔한 징후 |
| gradient-text (배경 그라데이션 텍스트) | AI가 만든 SaaS 랜딩의 1번 특징 |
| "Powered by AI" 배지 | 기능이 아니라 장식. 사용자에게 가치 없음 |
| box-shadow 글로우 애니메이션 | 네온 글로우 = AI 슬롭 |
| 보라/인디고 브랜드 색상 | "AI = 보라색" 클리셰 |
| 모든 카드에 동일한 rounded-2xl | 균일한 둥근 모서리는 템플릿 느낌 |
| 배경 gradient orb (blur-3xl 원형) | 모든 AI 랜딩 페이지에 있는 장식 |

## 색상

### 배경

| 용도 | 값 |
|------|------|
| 페이지 | {예: #0a0a0a} |
| 카드 | {예: #141414} |

### 텍스트

| 용도 | 값 |
|------|------|
| 주 텍스트 | {예: text-white} |
| 본문 | {예: text-neutral-300} |
| 보조 | {예: text-neutral-400} |
| 비활성 | {예: text-neutral-500} |

### 데이터/시맨틱 색상

| 용도 | 값 |
|------|------|
| 긍정/성공 | {예: #22c55e} |
| 부정/에러 | {예: #ef4444} |
| 중립/기본 | {예: #525252} |

## 컴포넌트

### 카드

```
{예: rounded-lg bg-[#141414] border border-neutral-800 p-6}
```

### 버튼

```
Primary: {예: rounded-lg bg-white text-black hover:bg-neutral-200}
Text:    {예: text-neutral-500 hover:text-neutral-300}
```

### 입력 필드

```
{예: rounded-lg bg-neutral-900 border border-neutral-800 px-4 py-3}
```

## 레이아웃

- 전체 너비: {예: max-w-5xl}
- 정렬: {예: 좌측 정렬 기본. 중앙 정렬 금지}
- 간격: {예: gap-3~4, 섹션 간 space-y-8}

## 타이포그래피

| 용도 | 스타일 |
|------|--------|
| 페이지 제목 | {예: text-4xl font-semibold text-white} |
| 카드 제목 | {예: text-sm font-medium text-neutral-400} |
| 본문 | {예: text-sm text-neutral-300 leading-relaxed} |

## 애니메이션

- {허용할 애니메이션만 나열. 예: fade-in (0.4s), slide-up (0.5s)}
- 그 외 모든 애니메이션 금지

## 아이콘

- {예: SVG 인라인, strokeWidth 1.5}
- {예: 아이콘을 둥근 배경 박스로 감싸지 않는다}
