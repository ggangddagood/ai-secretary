# 운영

> 작성 기준: 순서대로 실행하면 동작해야 한다. 셋업은 사전 요구부터 복붙 가능한 명령으로 적고, 순서를 바꾸면 실패하는 지점을 명시한다. 환경 변수는 이름만이 아니라 역할까지.

## 사전 요구

- {예: Node 24+, pnpm 9+}
- {예: 로컬 PostgreSQL 16 (Docker: docker compose up -d db)}

## 최초 셋업

```bash
{예:
pnpm install
cp .env.example .env      # 아래 환경 변수 표를 보고 채운다
pnpm db:migrate           # install 이후에만 가능 — 마이그레이션 도구가 node_modules에 있다
pnpm db:seed              # 선택: 개발용 시드 데이터
}
```

## 명령어

```bash
bash scripts/verify.sh    # 검증 단일 진입점 (lint + typecheck + test + build)
{pnpm dev                 # 개발 서버 :3000}
```

## 환경 변수

| 이름 | 역할 | 예 |
|------|------|-----|
| {DATABASE_URL} | {Postgres 연결 문자열} | {postgres://localhost:5432/app} |

## 배포

{절차 또는 "없음". 예: main 머지 → Vercel 자동 배포. 마이그레이션은 배포 전에 수동 실행}
