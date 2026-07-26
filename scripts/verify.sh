#!/usr/bin/env bash
# 프로젝트 검증의 단일 진입점.
# /build, /review, execute.py가 모두 이 스크립트로 검증한다.
# 프로젝트 스택에 맞는 명령으로 채운 뒤, 마지막 placeholder 블록을 삭제하라.
set -euo pipefail
cd "$(dirname "$0")/.."

# ── 여기에 검증 명령을 채운다 ─────────────────────────────
# 예: Node/TypeScript
#   npm run lint
#   npx tsc --noEmit
#   npm test
#   npm run build
#
# 예: Python
#   ruff check .
#   pytest -q
# ────────────────────────────────────────────────────────

# 채우기 전에는 의도적으로 실패한다 — 검증 없는 "완료" 주장을 막기 위함.
echo "verify.sh: 검증 명령이 아직 설정되지 않았습니다. scripts/verify.sh를 프로젝트에 맞게 채우세요." >&2
exit 1
