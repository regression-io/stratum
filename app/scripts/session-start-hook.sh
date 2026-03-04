#!/bin/bash
# session-start-hook.sh — SessionStart hook. Creates a session on the Forge server.
# Receives JSON on stdin: { source, model, agent_type }
# Outputs context to stdout (becomes Claude's session context).

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"')

BODY=$(jq -n --arg source "$SOURCE" '{source: $source}')

RESPONSE=$(curl -s -m 2 -X POST http://localhost:3001/api/session/start \
  -H 'Content-Type: application/json' \
  -d "$BODY" 2>/dev/null)

[ -z "$RESPONSE" ] && exit 0

# Extract context — .context is the raw last session object
LAST_SESSION=$(echo "$RESPONSE" | jq -r '.context // empty')
if [ -n "$LAST_SESSION" ] && [ "$LAST_SESSION" != "null" ]; then
  LAST_ITEMS=$(echo "$LAST_SESSION" | jq -r '.items | to_entries[] | "- \(.value.title): \(.value.writes) writes, \(.value.reads) reads"' 2>/dev/null)
  LAST_TOOLS=$(echo "$LAST_SESSION" | jq -r '.toolCount // 0')
  START=$(echo "$LAST_SESSION" | jq -r '.startedAt // empty')
  END=$(echo "$LAST_SESSION" | jq -r '.endedAt // empty')
  if [ -n "$START" ] && [ -n "$END" ]; then
    START_S=$(date -j -f '%Y-%m-%dT%H:%M:%S' "${START%%.*}" '+%s' 2>/dev/null || echo 0)
    END_S=$(date -j -f '%Y-%m-%dT%H:%M:%S' "${END%%.*}" '+%s' 2>/dev/null || echo 0)
    DURATION=$(( END_S - START_S ))
  else
    DURATION=0
  fi
  echo "Last session: ${DURATION}s, ${LAST_TOOLS} tool uses."
  if [ -n "$LAST_ITEMS" ]; then
    echo "Items worked on:"
    echo "$LAST_ITEMS"
  fi
fi

exit 0
