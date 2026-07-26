#!/usr/bin/env python3
"""PreToolUse 훅: 파괴적 명령을 차단한다.

Claude Code가 Bash 도구 실행 전에 stdin으로 JSON을 넘겨 호출한다.
exit 2 = 차단 (stderr가 에이전트에게 전달됨), exit 0 = 통과.
패턴을 조정하려면 PATTERNS를 수정한다.
"""

import json
import re
import sys

PATTERNS = [
    r"rm\s+-[a-zA-Z]*[rf][a-zA-Z]*[rf]",      # rm -rf / -fr 및 조합 플래그
    r"git\s+push\s+.*(--force\b|\s-f\b)",     # force push (--force-with-lease 포함)
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-[a-zA-Z]*f",
    r"\bDROP\s+(TABLE|DATABASE)\b",
    r"\bTRUNCATE\s+TABLE\b",
]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    for pattern in PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            print(
                f"BLOCKED: 파괴적 명령 패턴이 감지되었습니다 ({pattern}). "
                "정말 필요하면 사용자에게 직접 실행을 요청하라.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
