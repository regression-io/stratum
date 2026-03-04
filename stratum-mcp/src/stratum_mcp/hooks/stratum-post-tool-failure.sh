#!/usr/bin/env bash
# Stratum hook (T2-M4): record tool failures in project MEMORY.md.
#
# Claude Code passes failure context as JSON on stdin with fields:
#   is_interrupt — true when the user interrupted (skip logging)
#   tool_name    — name of the tool that failed
#   error        — error message
#   cwd          — project working directory

INPUT=$(cat)
IS_INTERRUPT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('is_interrupt', False)).lower())" 2>/dev/null)
[[ "$IS_INTERRUPT" == "true" ]] && exit 0

TOOL=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name', 'unknown'))" 2>/dev/null)
ERROR=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error', '')[:300])" 2>/dev/null)
[[ -z "$ERROR" ]] && exit 0

CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd', ''))" 2>/dev/null)
MEMORY="${CWD:-.}/.claude/memory/MEMORY.md"
[[ ! -f "$MEMORY" ]] && exit 0

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
    printf '\n## Tool failure %s\n\n' "$TIMESTAMP"
    printf 'Tool: %s\nError: %s\n' "$TOOL" "$ERROR"
} >> "$MEMORY"

exit 0
