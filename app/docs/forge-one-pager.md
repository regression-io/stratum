# Forge

## What it is

A structured implementation pipeline for AI-driven development. You say what you want. Forge decomposes it, asks the right questions, makes decisions at the right moments, and directs AI agents to build it.

## The problem

AI agents can write code. But going from "I want X" to "X is built correctly" requires a process: decomposition, design decisions, acceptance criteria, sequencing, verification, and course correction when things drift. Today that process lives in the developer's head. It's manual, fragile, and doesn't persist between sessions.

## How it works

**One pipeline, variable entry points.**

```
Any prompt → Context → Decompose → Q&A → Decide → Design → Plan → Build
```

- "Build me X" — full pipeline from scratch
- "Fix this bug" — context + diagnosis → design fix → build
- "Add Y to Z" — context(Z) → plan(Y) → build
- "Continue where I left off" — recover state → rejoin mid-stream
- "I have a fuzzy idea" — optional discovery on-ramp → converge to a goal → enter pipeline

Every entry point passes through a context phase (F0) that gathers what's needed: code context always, project history and work state when available. First use is lightweight. Tenth use has accumulated reasoning.

## What keeps it on rails

LLMs drift. The rails are:

- **Traceability** — every output links to the goal it serves
- **Acceptance criteria** — "done" is defined before work starts
- **Verification hooks** — automated checks at each pipeline step
- **The 3-mode dial** — gate (human decides), flag (AI proceeds, human notified), skip (AI autonomous)
- **Self-escalation** — AI tightens the dial when it's uncertain. Only the human loosens.
- **Hard limits** (always enforced: tests pass, no secrets, traceability) vs **soft limits** (flex by trust level: conventions, review, documentation)

## Features

| Feature | What it does | Role |
|---|---|---|
| **F0: Context** | Gather code, project history, work state before decomposing | Front door |
| **F4: Plan & Decompose** | Break goals into executable work with dependencies | Core pipeline |
| **F3: Distill & Decide** | Resolve decision points, converge evidence into commitments | Core pipeline |
| **F5: Execute with Agents** | Direct AI agents, provide context, enforce guardrails | Core pipeline |
| **F2: Capture Knowledge** | Record decisions, rationale, evidence as the pipeline runs | Support |
| **F6: See Everything** | Visibility into pipeline state, confidence, status | Support |
| **F1: Discover** | Explore when the goal is fuzzy, brainstorm, converge | On-ramp |

## Architecture

**4 primitives:** Discovery (Q&A process between phases), Work (trackable items), Policy (gate/flag/skip dials), Session (actors doing work).

**7 phases:** Vision → Requirements → Design → Planning → Implementation → Verification → Release. Phases are levels of concreteness. Discovery is the process that moves between them.

**Cross-cutting:** Tracking, confidence (Bayesian), visibility, knowledge capture, the 3-mode dial, persistence, audit/history.

**Connectors:** Persistence, retrieval, agents, and external systems are swappable. Built-in default: markdown files in git. No infrastructure required.

## Who it's for

**Primary:** Solo developer working with AI agents. Knows what to build, wants the process on rails.

**Secondary:** Founder/PM who shifts between strategic thinking and hands-on building. Same person, different depth — "developer mode" vs "product mode."

**Not for (v1):** Large teams, enterprise workflows, non-technical users.

## What it's NOT

- Not a task tracker (though it tracks work)
- Not a chat wrapper (though it involves conversation)
- Not an IDE (though it embeds terminals and agents)
- Not a project management tool (though it manages projects)

It's the structured process between "I want X" and "X is built correctly."

## Current state

Vision phase. Conceptual model validated through 6 sessions of discovery. No implementation beyond terminal embed and crash resilience from bootstrap. Next: requirements for the core pipeline (F0, F3, F4, F5).
