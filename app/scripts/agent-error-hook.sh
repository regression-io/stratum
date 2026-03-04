#!/bin/bash
# agent-error-hook.sh — PostToolUseFailure hook that forwards tool errors to Forge server.
#
# Receives JSON on stdin from Claude Code with tool_name, tool_input, error.
# POSTs to the Forge error endpoint for classification and UI display.
#
# Fire-and-forget, non-blocking.

INPUT=$(cat)

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ -z "$TOOL" ] && exit 0

# Extract fields
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
ERROR=$(echo "$INPUT" | jq -r '.error // empty' | head -c 500)

# Build POST body safely with jq
BODY=$(jq -n --arg tool "$TOOL" --argjson input "$TOOL_INPUT" --arg error "$ERROR" \
  '{tool: $tool, input: $input, error: $error}')

# Fire and forget
curl -s -m 1 -X POST http://localhost:3001/api/agent/error \
  -H 'Content-Type: application/json' \
  -d "$BODY" \
  > /dev/null 2>&1 &

exit 0
