/**
 * SDK hook callbacks for the Agent Server.
 *
 * These are in-process JavaScript functions passed to query() — not shell
 * scripts. They POST structured events to the api-server (port 3001), which
 * feeds SessionManager and VisionServer, preserving all Phase 3 monitoring.
 *
 * Single source of truth for TOOL_CATEGORIES (previously duplicated in
 * Terminal.jsx and vision-server.js).
 */

const API_SERVER = 'http://127.0.0.1:3001';

/** Semantic category for each Claude Code tool */
export const TOOL_CATEGORIES = {
  Read: 'reading', Glob: 'searching', Grep: 'searching',
  Write: 'writing', Edit: 'writing', NotebookEdit: 'writing',
  Bash: 'executing', Task: 'delegating', Skill: 'delegating',
  WebFetch: 'fetching', WebSearch: 'searching',
  TodoRead: 'reading', TodoWrite: 'writing',
};

async function post(path, body) {
  try {
    const res = await fetch(`${API_SERVER}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(5000),
    });
    return res;
  } catch {
    // api-server might not be ready yet — swallow silently
  }
}

/**
 * PostToolUse — fires after each successful tool execution.
 * Sends tool name, input, and response to /api/agent/activity.
 */
export async function postToolUseHook(input) {
  const response = input.tool_response;
  const responseStr = typeof response === 'string'
    ? response
    : JSON.stringify(response);

  await post('/api/agent/activity', {
    tool: input.tool_name,
    input: input.tool_input,
    response: responseStr,
    timestamp: new Date().toISOString(),
  });

  return { continue: true };
}

/**
 * PostToolUseFailure — fires when a tool execution fails.
 * Sends error details to /api/agent/error for severity classification.
 */
export async function postToolUseFailureHook(input) {
  await post('/api/agent/error', {
    tool: input.tool_name,
    input: input.tool_input,
    error: input.error,
  });

  return { continue: true };
}

/**
 * SessionStart — fires at session startup or resume.
 * Triggers SessionManager.startSession() via api-server.
 */
export async function sessionStartHook(input) {
  await post('/api/session/start', {
    source: input.source || 'startup',
  });

  return { continue: true };
}

/**
 * SessionEnd — fires when Claude Code exits.
 * Triggers SessionManager.endSession() and potentially journal generation.
 */
export async function sessionEndHook(input) {
  await post('/api/session/end', {
    reason: input.reason || 'completed',
    transcriptPath: input.transcript_path || null,
  });

  return { continue: true };
}

/** Hook configuration object for query() options.hooks */
export const HOOK_OPTIONS = {
  PostToolUse: [{ matcher: '.*', hooks: [postToolUseHook] }],
  PostToolUseFailure: [{ matcher: '.*', hooks: [postToolUseFailureHook] }],
  SessionStart: [{ hooks: [sessionStartHook] }],
  SessionEnd: [{ hooks: [sessionEndHook] }],
};
