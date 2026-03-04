/**
 * CodexConnector — wraps OpenAI Codex for Forge's agent connector interface.
 *
 * Two capabilities:
 *   run(prompt, opts)    — Execute: spawn Codex CLI, stream typed messages
 *   review(prompt, opts) — Review: OpenAI chat completion w/ structured JSON output
 *
 * The same typed message envelope as agent-server.js is used so the frontend
 * and any future orchestration layer can treat both agents uniformly.
 */

import { spawn } from 'node:child_process';
import OpenAI from 'openai';

// ---------------------------------------------------------------------------
// JSON schema for structured review output
// ---------------------------------------------------------------------------

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['error', 'warning', 'suggestion'] },
          file:     { type: 'string' },
          line:     { type: 'integer' },
          message:  { type: 'string' },
          suggestion: { type: 'string' },
        },
        required: ['severity', 'message'],
        additionalProperties: false,
      },
    },
    clean:   { type: 'boolean' },
    summary: { type: 'string' },
  },
  required: ['findings', 'clean', 'summary'],
  additionalProperties: false,
};

// ---------------------------------------------------------------------------
// CodexConnector
// ---------------------------------------------------------------------------

export class CodexConnector {
  #model;
  #reviewModel;
  #cwd;
  #proc = null;
  #openai = null;

  /**
   * @param {object} opts
   * @param {string} [opts.model='o4-mini']        — model for Codex CLI execution
   * @param {string} [opts.reviewModel='o4-mini']  — model for structured review
   * @param {string} [opts.cwd]                    — working directory (defaults to process.cwd())
   */
  constructor({ model = 'o4-mini', reviewModel = 'o4-mini', cwd = process.cwd() } = {}) {
    this.#model = model;
    this.#reviewModel = reviewModel;
    this.#cwd = cwd;

    if (process.env.OPENAI_API_KEY) {
      this.#openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    }
  }

  // ---------------------------------------------------------------------------
  // Execute — Codex CLI subprocess, yields typed messages
  // ---------------------------------------------------------------------------

  /**
   * Spawn Codex CLI and stream its output as typed messages.
   * Uses the same message envelope as agent-server.js so consumers are uniform.
   *
   * @param {string} prompt
   * @param {object} [opts]
   * @param {string} [opts.cwd]     — override working directory for this run
   * @yields {{ type: string, ... }}
   */
  async *run(prompt, { cwd } = {}) {
    if (this.#proc) {
      throw new Error('Session already active. Call interrupt() first.');
    }

    yield { type: 'system', subtype: 'init', agent: 'codex', model: this.#model };

    const args = [
      '--approval-mode=full-auto',
      '--quiet',
      '--model', this.#model,
      prompt,
    ];

    const proc = spawn('codex', args, {
      cwd: cwd ?? this.#cwd,
      env: { ...process.env },
    });
    this.#proc = proc;

    let buffer = '';

    try {
      // Stream stdout line by line
      for await (const chunk of proc.stdout) {
        buffer += chunk.toString();
        const lines = buffer.split('\n');
        buffer = lines.pop(); // hold incomplete last line
        for (const line of lines) {
          if (line.trim()) {
            yield { type: 'assistant', content: line + '\n' };
          }
        }
      }
      // Flush any remaining buffer
      if (buffer.trim()) {
        yield { type: 'assistant', content: buffer };
      }

      // Collect stderr separately (don't yield — just capture for exit error)
      let stderr = '';
      for await (const chunk of proc.stderr) {
        stderr += chunk.toString();
      }

      // Wait for process exit
      const exitCode = await new Promise((resolve) => {
        proc.on('close', resolve);
      });

      if (exitCode !== 0 && exitCode !== null) {
        yield { type: 'error', message: `Codex exited with code ${exitCode}${stderr ? ': ' + stderr.trim() : ''}` };
      } else {
        yield { type: 'system', subtype: 'complete', agent: 'codex' };
      }
    } catch (err) {
      if (err?.code !== 'ERR_USE_AFTER_CLOSE') {
        yield { type: 'error', message: err.message };
      }
    } finally {
      this.#proc = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Review — OpenAI chat completion with structured JSON schema output
  // ---------------------------------------------------------------------------

  /**
   * Run a structured review using the OpenAI Responses API.
   * Returns parsed findings — never throws on empty findings.
   *
   * @param {string} prompt   — include file contents or diff in the prompt
   * @param {object} [opts]
   * @param {string} [opts.model] — override review model for this call
   * @returns {Promise<{ findings: Finding[], clean: boolean, summary: string }>}
   */
  async review(prompt, { model } = {}) {
    if (!this.#openai) {
      throw new Error('OPENAI_API_KEY is not set — cannot run review');
    }

    const completion = await this.#openai.chat.completions.create({
      model: model ?? this.#reviewModel,
      messages: [{ role: 'user', content: prompt }],
      response_format: {
        type: 'json_schema',
        json_schema: {
          name: 'review_findings',
          schema: FINDINGS_SCHEMA,
          strict: true,
        },
      },
    });

    const raw = completion.choices[0]?.message?.content;
    if (!raw) throw new Error('Empty response from review model');
    return JSON.parse(raw);
  }

  // ---------------------------------------------------------------------------
  // Interrupt
  // ---------------------------------------------------------------------------

  /**
   * Kill the active Codex CLI subprocess, if any.
   */
  interrupt() {
    if (this.#proc) {
      try { this.#proc.kill('SIGTERM'); } catch { /* already dead */ }
      this.#proc = null;
    }
  }

  get isRunning() {
    return this.#proc !== null;
  }
}
