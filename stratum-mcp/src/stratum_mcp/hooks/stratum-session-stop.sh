#!/usr/bin/env bash
# Stratum hook (T2-M3): append a timestamped summary note to MEMORY.md at
# session close.
#
# Claude Code passes session context as JSON on stdin with fields:
#   cwd                   — project working directory
#   last_assistant_message — full text of the last assistant turn

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd', ''))" 2>/dev/null)
MSG=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('last_assistant_message', '')[:400])" 2>/dev/null)

MEMORY="${CWD:-.}/.claude/memory/MEMORY.md"
[[ -z "$MSG" || ! -f "$MEMORY" ]] && exit 0

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
    printf '\n## Session note %s\n\n' "$TIMESTAMP"
    printf '%s\n' "$MSG"
} >> "$MEMORY"

exit 0
