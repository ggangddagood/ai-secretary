#!/usr/bin/env bash
# 이 프레임워크를 복사해 새 프로젝트를 시작한다.
# 사용법: bash scripts/new-project.sh <대상-디렉토리> [프로젝트명]
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-}"
if [ -z "$DEST" ]; then
  echo "사용법: bash scripts/new-project.sh <대상-디렉토리> [프로젝트명]" >&2
  exit 1
fi
NAME="${2:-$(basename "$DEST")}"

if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  echo "ERROR: ${DEST} 가 비어 있지 않습니다." >&2
  exit 1
fi

mkdir -p "$DEST"
rsync -a "$SRC"/ "$DEST"/ \
  --exclude '.git' \
  --exclude 'README.md' \
  --exclude 'phases/*/' \
  --exclude '.backup' \
  --exclude '__pycache__' \
  --exclude '.claude/settings.local.json' \
  --exclude '.DS_Store'

# 프로젝트명 치환
python3 - "$DEST" "$NAME" <<'EOF'
import pathlib
import sys

dest, name = sys.argv[1], sys.argv[2]
for rel in ["AGENTS.md", "docs/PRD.md"]:
    p = pathlib.Path(dest) / rel
    if p.exists():
        p.write_text(p.read_text(encoding="utf-8").replace("{프로젝트명}", name), encoding="utf-8")
EOF

cat > "$DEST/README.md" <<EOF
# ${NAME}

{프로젝트 소개를 작성하세요}

## 개발

- AI 작업 사이클: docs/WORKFLOW.md
- 검증: \`bash scripts/verify.sh\`
EOF

cd "$DEST"
git init -q
git add -A
git commit -qm "chore: ai-framework 템플릿으로 초기화"

echo "완료: ${DEST} (프로젝트: ${NAME})"
echo ""
echo "다음 단계:"
echo "  1. Claude Code를 열고 /plan 으로 첫 작업을 시작한다"
echo "     (첫 사이클에서 제품 목표·스택·docs/ 기반과 scripts/verify.sh를 함께 확정)"
echo "  2. Codex 사용 시: \".claude/commands/plan.md 를 읽고 그 워크플로로 진행해\""
