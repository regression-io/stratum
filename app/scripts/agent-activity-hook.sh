#!/bin/bash
# agent-activity-hook.sh — PostToolUse hook that forwards tool activity to Forge server.
#
# Receives JSON on stdin from Claude Code with tool_name, tool_input, tool_response.
# POSTs a compact summary to the Forge server which broadcasts it via WebSocket
# to the Vision Tracker's agent activity feed.
#
# Runs quickly — curl with 1s timeout, backgrounded, non-blocking.

INPUT=$(cat)

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ -z "$TOOL" ] && exit 0

# Extract tool_input as compact JSON
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')

# Extract first 500 chars of tool_response (for error detection server-side)
RESPONSE=$(echo "$INPUT" | jq -c '.tool_response // null' | head -c 500)

# Build POST body safely with jq to avoid JSON injection
BODY=$(jq -n --arg tool "$TOOL" --argjson input "$TOOL_INPUT" --argjson response "$RESPONSE" \
  '{tool: $tool, input: $input, response: $response}')

# Fire and forget — don't block the agent
curl -s -m 1 -X POST http://localhost:3001/api/agent/activity \
  -H 'Content-Type: application/json' \
  -d "$BODY" \
  > /dev/null 2>&1 &

exit 0
