#!/usr/bin/env bash
# Stratum hook (T2-M2): inject project MEMORY.md at session open.
#
# Claude Code passes session context as JSON on stdin.
# Stdout is injected into the session context — so we print MEMORY.md content
# directly, letting Claude see project-specific patterns without being asked.

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd', ''))" 2>/dev/null)
MEMORY="${CWD:-.}/.claude/memory/MEMORY.md"

if [[ -f "$MEMORY" ]]; then
    cat "$MEMORY"
fi

exit 0
