# Discovery: How Discovery Works

**Date:** 2026-02-11
**Phase:** Discovery (active — recursive: discovering the discovery process)
**Parent work area:** Work Tracking Meta-Structure
**Participants:** Human + Claude Code agent

---

## What is this?

Defining how the discovery phase works in Compose — the process by which loose thinking becomes structured enough to transition to requirements.

This is recursive: we're using discovery to define discovery.

---

## What we know so far

### What just happened (the session that produced the parent document)

1. A friction point surfaced: "the roadmap says NEXT but we're not ready"
2. That triggered a question: "how do we encode where we actually are?"
3. Options were brainstormed (redefine roadmap vs. new construct)
4. Each option surfaced more questions (what granularity? what format? what layers?)
5. Insights accumulated through dialogue (crystallization model, three layers, loopback)
6. A discovery document was written to capture the state

**Pattern:** irritant → question → options → deeper questions → insights → document

### Observations about what we did

- Discovery was **conversational** — not a solo activity. Ideas bounced between human and agent.
- The human's role was **steering and gating** — "no, don't build yet", "hold up", "what are the options?"
- The agent's role was **expanding and structuring** — surfacing options, naming patterns, connecting to existing concepts.
- Progress was **non-linear** — we went sideways into keybindings, then back. Topics forked and merged.
- The trigger was **friction with the current model** — not a planned exploration, but a real need.

---

## Thread 1: Use cases for discovery

**Status:** Complete — enumerated, then reframed.

### Initial enumeration (activities)

First attempt listed classes of activities people do during discovery:

**Triggered by friction/need:**
1. Something isn't working → diagnose why
2. A tool/process doesn't fit → articulate the gap
3. A constraint changed → reassess assumptions
4. A failure happened → understand the causal chain
5. Someone is frustrated → find the root cause

**Triggered by curiosity/vision:**
6. "What if we..." → open-ended ideation
7. "How do others solve this?" → landscape research
8. "I have a hunch" → explore an intuition
9. "These things are connected" → pattern recognition
10. "What's possible now that wasn't before?" → opportunity scanning

**Expanding the space:**
11. Brainstorming — generate volume, no constraints
12. Option enumeration — what are ALL the ways we could go?
13. Divergent thinking — deliberately widen before narrowing
14. Analogical reasoning — "this is like X in domain Y"
15. Stakeholder perspectives — what do different people need?

**Narrowing the space:**
16. Feasibility check — can this even work?
17. Trade-off analysis — costs/benefits of each option
18. POC/prototype — build a throwaway to learn
19. Convergent thinking — narrow to promising directions
20. Kill decision — this direction is a dead end, stop

**Sense-making:**
21. Naming — give the thing a name so we can talk about it
22. Framing — choose a lens to view the problem through
23. Connecting — link this to existing concepts/decisions
24. Summarizing — compress what we've learned so far
25. Questioning — surface what we don't know

**Meta:**
26. Defining the process itself (what we're doing right now)
27. Choosing how structured to be at this stage
28. Deciding when to stop exploring and start deciding

### Reframing: these are activities, not use cases

Human correction: the above are classes of *activities* (what people DO), not *use cases* (WHY they're there and WHAT they're carrying). The real question is about the state space of starting conditions.

Examples that illustrate the spectrum:
- "I'm a founder and I came up with a genius idea!" — conviction without validation
- "I'm a founder and I discovered a validated pain point with a market gap" — evidence-based starting point
- "I'm a developer and I'm doing what I've been told" — executor, received the why
- "I'm an exec and same thing" — different authority, same received-why pattern
- "I lead a team..." — responsible for others' work, not just your own

**Key insight:** The WHY and the IDEA are at the same level because they iterate — conviction gets tested, evidence reshapes the idea, the reshaped idea surfaces new evidence.

---

## Thread 2: The state space — axiomatic dimensions of work

**Status:** Level 1 resolved — 3 working dimensions + knowledge layer. Level 2 brainstorming next.

### Proposed dimensions

| Dimension | Question | Spectrum |
|-----------|----------|----------|
| **Why (Purpose)** | Why does this work exist? | Hunch → Validated thesis |
| **What (Vision)** | What's the idea / current understanding? | Napkin sketch → Detailed spec |
| **Who (Agency)** | Who's involved and what's their relationship? | Solo originator → Full org |
| **Evidence (Knowledge)** | What do we know and how do we know it? | Gut feeling → Hard data |

Each dimension has a **fidelity level** — from vague to crisp — that increases as work progresses through the lifecycle.

### Detailed breakdown per dimension

**Why does this work exist?**
- Conviction / vision ("I believe X should exist")
- Experienced pain ("I/we hit this problem repeatedly")
- Observed pain ("Others have this problem")
- Validated opportunity ("The gap exists and is underserved")
- Assigned problem ("Someone told me to solve this")
- Regulatory/external force ("We must because the world changed")
- Technology enables ("This is now possible and wasn't before")
- Competitive response ("Others are doing this, we need to")
- Iteration ("This exists but isn't good enough")
- Pivot ("What we're doing isn't working, need new direction")

**What's the idea / current understanding?**
- Clear singular vision ("I know exactly what to build")
- Hypothesis ("I think X might work, need to test")
- Multiple competing directions ("Could be A, B, or C")
- Vague direction ("I know the space but not the shape")
- Solution seeking problem ("I built a thing, who needs it?")
- Problem seeking solution ("I know the pain, not the remedy")
- Evolving ("Learning as we go, reshaping constantly")

**Who's involved?**
- Originator — owns the why
- Champion — adopted the why, driving it
- Executor — received the why, building it
- Leader — accountable for a team doing it
- Contributor — working on a piece
- Evaluator — assessing whether it's working
- Stakeholder — affected but not building

Roles shift: a developer told to build something may discover the why is wrong and become the originator of a pivot.

**What evidence exists?**
- None — pure intuition
- Personal experience only
- Anecdotal (talked to people)
- Qualitative research (interviews, observations)
- Quantitative data (metrics, surveys, market data)
- Competitive analysis
- Working prototype / POC
- Previous failed attempts (evidence of what doesn't work)

### Stress test: are these axiomatic?

**Orthogonality (are they independent?):**
- Why vs What: ✓ — can have clear pain with no solution, or clear idea with no articulated motivation
- Why vs Who: ✓ — clear motivation with no team, or team assigned without understanding why
- What vs Who: ✓ — idea exists regardless of who works on it
- Evidence vs others: **Questionable** — see debate below

**Irreducibility (can you derive one from the others?):**
- Why from What+Evidence+Who: No. Knowing solution, data, and team doesn't tell you why it matters. ✓
- What from Why+Evidence+Who: Not fully. Multiple whats serve the same why. ✓
- Who from Why+What+Evidence: Not fully. Work implies who's needed, but not actual actors. ✓
- Evidence from Why+What+Who: No. Motivation + idea + team doesn't generate knowledge. ✓

**Completeness (is anything missing?):**

Scenarios tested:
- "Ship before competitor launches in 3 months" → urgency folds into Why (why now) and What (scope bounded by time). Uncomfortable fit.
- "$50K budget and 2 engineers" → constraints fold into Who (capacity) and What (feasibility). Uncomfortable fit.
- "CEO wants this but engineering thinks it's wrong" → conflict within Who dimension. ✓ Captured.
- "Tried this 3 times and failed" → Evidence. ✓ But also reshapes Why and What.
- "Regulation changes in 6 months" → external context, folds into Why + constraints.

### The Evidence debate

**Argument: Evidence is a meta-attribute, not a peer dimension.**
Every other dimension has its own evidence — "how sure are we about the why/what/who?" Evidence is the confidence level of each, not its own axis.

**Counter-argument: Evidence is also a body of knowledge.**
Market research, user data, competitive analysis — these exist as raw material BEFORE being interpreted through why/what/who. Unprocessed research sitting in a spreadsheet doesn't belong to any dimension until someone makes sense of it. Evidence accumulates independently.

**Tentative resolution:** Evidence is both — it's cross-cutting (a quality of each dimension) AND its own body (accumulated knowledge). This might make it a different *kind* of dimension rather than disqualifying it.

### Possible missing dimensions

**Constraints** — budget, time, regulations, technology limitations.
- For: independently variable, externally imposed, bound the solution space
- Against: only matter in how they affect other dimensions. A budget constraint reduces What (scope) and Who (capacity). Without affecting another dimension, a constraint is inert.

**Value/Impact** — what's at stake, magnitude of the opportunity.
- For: "this pain exists" (Why) ≠ "solving it is worth $10M" (Value). Same pain, different value at different scale.
- Against: value is the quantitative expression of Why. Property of Why, not separate axis.

**How/Approach** — build vs buy, AI-first vs traditional, incremental vs big bang.
- Against: emerges from interaction of What+Who+Evidence. It's a decision (design phase), not an input (discovery). Unless the approach IS the starting point, in which case How IS the What.

### Reframe: What matters in practice vs. what matters in theory

Human challenge: Who and Why (as personal motivation) aren't working dimensions. Users don't engage with them day-to-day, and they carry privacy concerns — commercial devs won't document org politics or personal uncertainty.

**What users actually work with:** What and How. That's where Compose adds real-time value.

**Who** is not axiomatic. It's onboarding context at best. In practice:
- Solo dev + AI: Who is constant ("me + Claude"). Zero information.
- Team: Who = assignee field. Already a property of work items, not a dimension.
- The "role spectrum" (originator → executor → evaluator) is really describing the actor's *fidelity on the other dimensions* — an executor who doesn't understand the Why has low Why-fidelity, not a different Who.

**Why splits into two things:**
- **Personal Why** (conviction, org pressure, assigned task) — onboarding calibration. Useful at setup to understand starting conditions. Not operational. Privacy-sensitive.
- **Factual Why** (knowledge reasoning) — "why does this decision hold?" "what evidence supports this approach?" "what assumptions does this rest on?" This is the reasoning chain, and it's **huge** operationally. It's what makes the AI useful — it can reason about justifications and flag when they break down.

**How** was previously dismissed ("emerges from What+Who+Evidence, it's a design-phase decision"). But if What and How are the actual working pair that users engage with, How deserves elevation. It covers approach, method, constraints, and is where Compose tailors itself to the user's actual work.

### Current position (revised)

Two levels. The working surface and the knowledge layer underneath.

**Primary working surface** (what the user sees and engages with):

| Dimension | Role |
|-----------|------|
| **What** | The work itself — its state, shape, substance. Primary navigation and tracking. |
| **How** | Approach, method, constraints. Tailoring, templates, guidance. |
| **Why** | Present when the user introduces it — brainstorming, direction-setting. Not assumed, not required. Can be as simple as "because I want it that way." |

**Knowledge layer** (where the AI earns its keep):

The knowledge discovery/reasoning loop operates underneath the working surface. When reasoning about what's known vs. assumed, what evidence supports a decision, or what changed that invalidates prior conclusions, the system uses who/what/how/why as **facets of reasoning** — not as top-level dimensions imposed on the user.

```
Working surface:  What, How
                  (+ Why when user-initiated)

Knowledge layer:  Discovery / reasoning loop
                  └─ uses who, what, how, why as reasoning facets
                  └─ tracks evidence, assumptions, justification chains
                  └─ surfaces when reasoning breaks down or context changes
```

The UI is about What and How. The intelligence is in the knowledge layer underneath. The user doesn't need to fill in "Why" fields or "Who" fields — the system reasons about those internally and surfaces them when relevant.

**Key design implications:**
- Compose tailors itself to What and How, not Who and Why. A developer tracking a React app gets React-relevant patterns. The tailoring follows the work, not the person.
- The knowledge layer is where `informs` dependencies, evidence tracking, and assumption management live. It's the AI's primary value-add.
- Why doesn't need ceremony. It can be obvious, trivial, or "because the user said so." It just needs to be traceable when someone asks.

**The use case listings** (Thread 1, the 28 activities, the role spectrum, the motivation spectrum) are design research — they helped US understand the problem space. They are not features Compose presents to users or dimensions it tracks at runtime.

---

## Thread 3: Split-view markdown viewer

**Status:** Direction set, ready for design when prioritized.

During this discovery session, a UX friction surfaced: the agent writes to docs but the human can't see them without leaving the conversation. The doc and the discussion should be visible together.

### Design direction

**Layout:** Vertical split — terminal on left, **canvas** on right. Not a markdown viewer — a canvas whose first component is a markdown editor/viewer. The canvas will evolve.

**The canvas is the right panel. The terminal is the left panel. Both are primary.** Full-width terminal goes away — this split IS the default layout.

**Markdown behavior:**
- Auto-opens when agent writes a markdown file
- Human can **pin** a doc to hold it in view — new writes don't steal focus
- Pinned doc = gate (human controls view), unpinned = skip (agent drives view)
- Flag mode: agent writes to a new file, viewer shows indicator but doesn't switch

**Editing is bidirectional:**
- Agent writes to the doc (via file writes)
- Human edits directly in the canvas
- When human edits, agent sees the diff — the doc is a truly shared artifact
- Neither party "owns" the doc — both contribute

**Evolution path:**
- V1: Markdown editor/viewer in canvas, single doc, auto-follow, pin/unpin
- V2: Multiple tabs in canvas
- V3+: Canvas components beyond markdown — diagrams, structured data views, work hierarchy tree, whatever's needed

**Insight this surfaces about discovery in Compose:**
- The **terminal** (conversation) is the process — steering, questioning, deciding
- The **canvas** (document) is the artifact — accumulated understanding
- Both visible simultaneously = the artifact evolves in front of you, not behind the scenes
- Both human and agent write to the artifact — it's a shared surface, not agent-owned
- Changes the agent's default: write TO the shared doc as primary output, conversation is steering

---

## Resolved (Level 1)

- ~~Are the dimensions 3, 4, or 5?~~ → **3 working dimensions** (What, How, Why-factual) + onboarding inputs (personal why, who, starting conditions)
- ~~Is Evidence its own dimension?~~ → Evidence is cross-cutting AND a body of knowledge. Folded into the knowledge layer rather than a top-level dimension.
- ~~Is Who axiomatic?~~ → No. It's onboarding context. Solo dev: constant. Team: assignee field.
- ~~Is How derived?~~ → No. Elevated to working dimension — users engage with What and How day-to-day.

## Open questions (Level 2)

**How dimensions manifest mechanically:**
- How does factual Why (knowledge reasoning) manifest mechanically? Is it the `informs` dependency? Artifact versioning? Assumption tracking? Something else?
- What does "What" look like at different lifecycle phases? How does its shape change as structure crystallizes?
- What does "How" look like as a user-facing concept? Templates? Approach selection? Constraint fields?
- How does the knowledge layer reason underneath? When does it surface? What triggers it?

**How dimensions connect to existing constructs:**
- How do What/How/Why-factual map onto Work, Policy, Session?
- How does the state space model connect to the lifecycle phases?
- How does the 3-mode dial apply per dimension?

**Discovery process itself:**
- When is discovery "done"? What signals transition to requirements?
- What are the valid outputs of discovery? (Document, questions, direction, kill decision?)
- How does Compose represent a discovery conversation?
- How much structure should discovery have?
- Can discovery loop internally?

**Onboarding:**
- What does onboarding actually look like? Minimal — what does Compose need to know to start being useful?

---

*This is a living document. Updated as we discuss.*
