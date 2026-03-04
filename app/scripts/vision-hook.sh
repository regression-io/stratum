#!/bin/bash
# vision-hook.sh — PostToolUse hook that auto-tracks docs on the Vision Surface.
#
# Triggered after Write|Edit tool uses. Reads JSON from stdin, extracts the
# file path, and calls vision-track.mjs to create or log items.
#
# Only acts on files under docs/. Ignores everything else silently.
# Runs async (backgrounded) so it doesn't block the agent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRACK="$SCRIPT_DIR/vision-track.mjs"
LOG="/tmp/compose-vision-hook.log"

# Read hook JSON from stdin
INPUT=$(cat)

# Extract file path from tool_input (works for both Write and Edit)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Skip if no file path
[ -z "$FILE_PATH" ] && exit 0

# Only track docs/ files
case "$FILE_PATH" in
  */docs/*) ;;
  *) exit 0 ;;
esac

# Extract just the relative path from docs/ onward
REL_PATH="${FILE_PATH##*/docs/}"
FILENAME=$(basename "$FILE_PATH" .md)

# Determine type and phase from path conventions
TYPE=""
PHASE=""
case "$REL_PATH" in
  plans/*)
    TYPE="spec"
    PHASE="planning"
    ;;
  specs/*)
    TYPE="spec"
    PHASE="requirements"
    ;;
  design/*)
    TYPE="decision"
    PHASE="design"
    ;;
  discovery/*)
    TYPE="idea"
    PHASE="vision"
    ;;
  requirements/*)
    TYPE="spec"
    PHASE="requirements"
    ;;
  decisions/*)
    TYPE="decision"
    PHASE="design"
    ;;
  evaluations/*)
    TYPE="evaluation"
    PHASE="verification"
    ;;
  journal/*)
    TYPE="artifact"
    PHASE="implementation"
    ;;
  *)
    # Unknown docs subdirectory — log but don't track
    echo "$(date -Iseconds) | SKIP unknown docs path: $REL_PATH" >> "$LOG"
    exit 0
    ;;
esac

# Check if an item for this file already exists (search by filename)
SEARCH_RESULT=$(node "$TRACK" search "$FILENAME" 2>/dev/null || true)

if [ -n "$SEARCH_RESULT" ]; then
  # Item likely exists — just log the update, don't create duplicates
  echo "$(date -Iseconds) | UPDATE $TOOL_NAME $REL_PATH (existing item found)" >> "$LOG"
else
  # Create a new item
  TITLE=$(echo "$FILENAME" | sed 's/-/ /g' | sed 's/^[0-9 ]*//' | sed 's/^ *//')
  # Capitalize first letter
  TITLE="$(echo "${TITLE:0:1}" | tr '[:lower:]' '[:upper:]')${TITLE:1}"

  ID=$(node "$TRACK" create "$TITLE" \
    --type "$TYPE" \
    --phase "$PHASE" \
    --description "Auto-tracked from $TOOL_NAME to docs/$REL_PATH" \
    2>/dev/null || true)

  if [ -n "$ID" ]; then
    echo "$(date -Iseconds) | CREATE $ID type=$TYPE phase=$PHASE path=$REL_PATH" >> "$LOG"
  else
    echo "$(date -Iseconds) | FAIL create for $REL_PATH" >> "$LOG"
  fi
fi

exit 0
