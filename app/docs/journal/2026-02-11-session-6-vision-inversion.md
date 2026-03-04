# Session 6: The Vision Inversion

**Date:** 2026-02-11
**Phase:** Discovery Level 2 (continued)
**Participants:** Human + Claude Code agent

---

## What happened

We came in continuing Level 2 discovery. The session produced four significant advances — each one a correction of something we'd gotten wrong or incomplete.

### Vision phase renamed

The taxonomy had "discovery" as both a phase label and a primitive name. That collision was confusing. The human confirmed: the phase is "Vision" — the level of concreteness where you're setting direction. Discovery stays as the primitive — the Q&A decomposition process that operates at every phase boundary. Clean separation. Taxonomy updated.

### The interaction surface analysis

We asked: "what does the user actually touch?" The answer split the primitives into two interaction patterns — objects you manipulate (Work, Policy) and processes you participate in (Discovery, Session). We proposed that the three dimensions (What, How, Why) are facets of one interaction on a Work item, and that the three untouched clusters (How, Why-factual, Knowledge layer) are layers of the same thing.

Then we ran six counterfactuals against those claims. Four landed hard:

1. Dimensions exist at multiple scopes, not just on individual Work items
2. The Knowledge layer is a user surface for founder/PM mode, not just infrastructure
3. Discovery needs to be trackable as an object, not just participatory as a process
4. How partially dissolves into What + Why — the residue is Policy

The model got less clean and more honest. First real use of the confidence evaluation process.

### The confidence model earned a bump

The human noticed what we were doing before we did. Running counterfactuals and revising claims IS the Bayesian process — prior, challenge, revised posterior. We'd been describing the confidence model for two sessions. This was the first time we actually used it. The model went from "elegant on paper, zero use" to "ran it once, produced useful output." Small bump, but the first evidence update.

We wrote out the full analysis: what moves confidence up/down, when to evaluate (and when not to — don't kill divergent thinking), how to infer processes from their traces. The timing insight: evaluation pulses between divergence and convergence. The human's role has been triggering the pauses.

### The vision inversion

Then the human asked: "do we have our product vision statement?"

We didn't. The agent proposed one centered on "making direction durable" — capturing the thinking behind work. The human corrected: that's not what Compose is.

The original idea: **"Put implementation on rails. Say 'Build me X' and Compose figures out the rest — decomposing, asking questions, making decisions, building."** The structured process is the product. What/How/Why/Confidence are reasoning infrastructure that makes the pipeline work, not the user-facing goal.

Further: discovery/brainstorming is an optional on-ramp. Half of dev users will skip it — they know what they want to build. Founders/PMs may use it more. It's valuable but not the core product.

This inverted the entire priority structure. The pipeline features (F3 Distill & Decide, F4 Plan & Decompose, F5 Execute with Agents) have had the least design attention but ARE the core product. F1 (Discover) has had the most attention but serves the smallest user slice.

The human's closing observation: brainstorming is the hardest feature because of its ambiguity and lack of structure. That's true — and it's why we tackled it first. The concepts extracted (confidence model, false crystallization, process inference) apply to the entire pipeline. The pipeline will be easier to design because it has more inherent structure.

### The pipeline takes shape

With the vision grounded, we pressure-tested the tagline with six counterfactuals. All landed to some degree but were resolved by feature design rather than changing the vision. The key advancement: not every prompt is "Build me X." The pipeline handles variable entry points — fix, extend, refactor, resume — by scaling a context phase at the front.

This produced F0 (Context) as a new top-level feature: the front door of every pipeline run. It gathers what Compose needs before it can decompose. Autonomous context (code) is always available. Opportunistic context (project history, work state) is used when it exists. The pipeline works with just the prompt + code. Everything else makes it better over time.

### The rails question

The human surfaced the core design question: how do we keep implementation on rails through the lifecycle? LLMs drift, hallucinate, scope-creep. But humans have the same problem and have developed processes — traceability, acceptance criteria, gates, testing, change control.

We analyzed Claude Code's own mechanisms (CLAUDE.md, rules, skills, hooks, memory) and mapped each to Compose equivalents. The architecture emerged: at each pipeline step — context injection, constraint injection, execution, verification hook, drift detection, knowledge capture. The 3-mode dial governs human involvement, not constraint level.

Key insights from this thread:
- **Permissive mode needs MORE automated rails, not fewer.** When the human steps back, something else steps up.
- **Self-escalation:** The AI can tighten the dial (skip → flag) based on confidence, never loosen it. Only the human loosens.
- **Hard limits vs soft limits.** Hard limits (verification) are always enforced. Soft limits (guidance) flex via the 3-mode dial.
- **Rules vs guidelines vs suggestions** — three weight classes with different context budgets. Rules always loaded, guidelines per-step, suggestions on demand.
- **Knowledge retrieval is a connector.** The built-in system is markdown files. Good enough, proven, zero infrastructure. Connector architecture lets users swap in more.

## What we built

No code. 4 new discovery docs, 5 docs updated:

| File | What it captures |
|------|-----------------|
| `vision-statement.md` | "Build me X" → Compose handles the rest. Pressure-tested. Variable entry points. |
| `confidence-evaluation-process.md` | Evaluation mechanics, timing, process inference |
| `counterfactuals-session-6.md` | 6 challenges against interaction surface analysis, verdicts |
| `rails-architecture.md` | The core design question: keeping AI on rails. Human patterns, Claude Code patterns, hard/soft limits, constraint weight classes, self-escalation. |
| `level-2-brainstorm.md` | Updated: interaction surface section, new doc links |
| `feature-map.md` | Updated: F0 Context added, cross-cutting capabilities expanded to 8, priority table, pipeline-first flow |
| `CLAUDE.md` | Updated: project overview rewritten around pipeline |
| `taxonomy.md` | Updated: discovery phase → vision phase |
| `discovery-as-primitive.md` | Updated: operates at every phase boundary, vision/discovery separation resolved |
| `model-gaps.md` | Updated: Gap 5 reframed around confidence on outputs |
| `session-5-meta-trace.md` | Updated: moves 21-24 |

## What we learned

1. **The agent had the vision inverted.** Two sessions deep in discovery brainstorming, the agent naturally centered the vision on the discovery work. The human had to pull it back to the original idea: a structured implementation pipeline. Proximity bias is real — you think the thing you're working on is the most important thing.

2. **Counterfactuals are the sharpest evaluation tool.** Six counterfactuals reshaped the model more than hours of forward reasoning. The pattern: make a claim, generate plausible alternatives, see which ones land. What survives is stronger. What doesn't reveals where the model is thin.

3. **The confidence model works in practice.** Not as math. As a reasoning pattern: prior → challenge → revised posterior. The first real use produced useful results. That's evidence.

4. **Evaluation has timing.** Too early kills divergence. Too late lets false crystallization set in. The human's instinct for when to challenge is the current timing mechanism. The question for Compose: can AI learn this timing?

5. **Processes are inferred, not designed.** We didn't plan to run the confidence evaluation process. We just did it naturally. Recognized it afterward. This suggests Compose's process support should watch what people do and name it, not impose templates.

6. **Product dimensions and process dimensions use the same words but operate at different levels.** How/When for Work items (the product) is different from how/when for discovery (the process). Don't conflate them.

7. **The hardest feature isn't the most important one.** Brainstorming is hard because it's unstructured. The pipeline is important because it's the core product. We did the hard thing first and extracted concepts that serve the important thing. That's fine — as long as you notice the inversion before it calcifies.

8. **Permissive mode needs heavier rails.** Counterintuitive: when the human trusts the AI more (skip mode), the system needs more automated enforcement, not less. The human was the quality check. Remove the human, something else must check.

9. **Self-escalation ties confidence to governance.** The AI can tighten the dial based on its own confidence. Low confidence → escalate. It can never loosen — only the human loosens. Conservative by default.

10. **Constraint weight classes manage context budget.** Rules (always loaded), guidelines (per-step), suggestions (on demand). More constraints = better quality but worse focus. Scoping solves it.

11. **Markdown files are the right default.** Not a compromise. Human-readable, version-controlled, zero infrastructure, proven by Claude Code. Connector architecture keeps the door open for more.

## Open threads

- [ ] Pipeline features (F0, F3, F4, F5) need design attention — core product with least definition
- [ ] "Build me X" decomposition mechanics — how does Compose break a goal into steps?
- [ ] Q&A mechanics — how does Compose know what to ask? When to ask vs. proceed?
- [ ] Rails enforcement mechanics — how are verification hooks and drift detection implemented?
- [ ] Self-escalation thresholds — what confidence level triggers escalation?
- [ ] Constraint routing — how does F0 decide which guidelines are relevant per step?
- [ ] Knowledge capture during pipeline — how is knowledge automatically captured and linked as the pipeline runs?
- [ ] Counterfactual 3: trackable unit of Discovery (lighter than Work, but visible)
- [ ] Counterfactual 6: temporal context — evidence needs timestamps
- [ ] Level 2 clusters (How, Why-factual, Knowledge layer) — gaps narrowed but not closed
- [ ] Dogfooding: how does Compose track its own development?

---

*The session that started by refining the model and ended by designing the rails. Two inversions: the agent's vision was backwards, and permissive mode needs more constraints, not fewer.*
