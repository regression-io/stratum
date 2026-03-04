#!/bin/bash
# session-end-hook.sh — SessionEnd hook. Closes session, triggers journal if threshold met.
# Receives JSON on stdin: { reason, transcript_path }
# Cannot block termination — fire and forget.

INPUT=$(cat)
REASON=$(echo "$INPUT" | jq -r '.reason // "exit"')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')

BODY=$(jq -n --arg reason "$REASON" --arg transcript "$TRANSCRIPT" \
  'if $transcript == "" then {reason: $reason} else {reason: $reason, transcriptPath: $transcript} end')

# Fire and forget — session end cannot block
curl -s -m 10 -X POST http://localhost:3001/api/session/end \
  -H 'Content-Type: application/json' \
  -d "$BODY" > /dev/null 2>&1 & disown

exit 0
