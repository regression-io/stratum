# Validation Exercise: Does the Model Fit Real Work?

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Purpose:** Test the Work primitive against things we actually did. Does it fit naturally or feel forced?

---

## Test 1: Terminal Embed (Session 1-2)

**What happened:** Embedded Claude Code in xterm.js via WebSocket + node-pty. It crashed on first boot. We fixed it.

**Trying to model it:**

```
Work: "Embed Claude Code in terminal"
  Type: task
  Phase: implementation
  Status: complete
  Children:
    - "WebSocket + PTY backend" (task, complete)
    - "xterm.js terminal component" (task, complete)
    - "First boot crash fix" (task, complete)
  Dependencies: none (this was the first real build)
  Artifacts: server/terminal.js, src/components/Terminal.jsx
  Evidence: it runs, you can type `claude`
  Acceptance criteria: "Can type `claude` in embedded terminal, survives server restart"
```

**Does it fit?** Mostly yes. This is straightforward implementation work — the model handles it naturally. The child tasks make sense. Artifacts and evidence are clear.

**What feels off:** The crash fix wasn't planned as a child — it emerged from the attempt. The model lets you add children at any time, so mechanically it works. But the *story* is lost — "we tried, it broke, we diagnosed, we fixed" is a sequence with causality. The flat tree doesn't capture that the crash fix was *reactive*, not planned.

---

## Test 2: Crash Resilience (Session 1)

**What happened:** After the crash, we built three layers of defense: try/catch on ws.send, process error handlers, supervisor with auto-restart, client WebSocket reconnection.

**Trying to model it:**

```
Work: "Crash resilience"
  Type: task
  Phase: implementation
  Status: complete
  Children:
    - "try/catch on ws.send calls" (task, complete)
    - "Process error handlers (uncaughtException, SIGTERM)" (task, complete)
    - "Process supervisor with auto-restart" (task, complete)
    - "Client WebSocket reconnection" (task, complete)
  Dependencies: informed by "First boot crash fix" (the diagnosis)
  Artifacts: server/supervisor.js, server/terminal.js, src/components/Terminal.jsx
  Evidence: server survives crashes, client reconnects
```

**Does it fit?** Yes, pretty cleanly. The `informs` dependency from the crash diagnosis to this work captures the "we learned something, then built against it" relationship.

**What feels off:** The *decision* to build resilience rather than just fix the bug isn't captured. We chose "self-healing over error prevention" — that's a design decision that should exist somewhere. In the model it would be:

```
Work: "Self-healing vs error prevention"
  Type: decision
  Phase: design
  Status: complete
  Artifacts: rationale — "a crash becomes a 2-second blip, not a dead app"
  Dependencies: informs "Crash resilience"
```

That works. But nobody wrote that as a separate Work item at the time — it happened in conversation. The model can represent it, but it requires someone (human or AI) to extract it after the fact.

---

## Test 3: This Discovery Session (Session 5)

**What happened:** We're brainstorming how Forge's dimensions work. We defined Level 1 constructs (What, How, Why-factual), opened Level 2, wrote docs, caught the false crystallization insight.

**Trying to model it:**

```
Work: "Discovery: Forge dimensions"
  Type: brainstorm
  Phase: discovery
  Status: in_progress
  Children:
    - "Level 1: Working dimensions" (brainstorm, complete)
    - "Level 2: How dimensions manifest" (brainstorm, in_progress)
      Children:
        - "Cluster 1: What" (brainstorm, in_progress)
        - "Cluster 2: How" (brainstorm, planned)
        - "Cluster 3: Why-factual" (brainstorm, planned)
        - "Cluster 4: Knowledge layer" (brainstorm, planned)
        - "Cluster 5: Primitives mapping" (brainstorm, planned)
    - "Insight: False crystallization" (brainstorm, tentative??)
  Artifacts: discovery-process/README.md, level-2-brainstorm.md, false-crystallization.md
  Acceptance criteria: ???
```

**Does it fit?** Partially. The hierarchy works. The artifacts map. But several things feel forced:

1. **Status doesn't fit discovery well.** "planned → ready → in_progress → review → complete" assumes you know when you're done. Discovery doesn't have a clear "complete." We parked a topic, caught an insight, looped back. The status lifecycle was designed for execution, not exploration.

2. **"Tentative" isn't a status.** The false crystallization insight isn't planned, in_progress, or complete. It's *surfaced but untested*. The model has no way to say that.

3. **Acceptance criteria for brainstorming?** "We understand the problem and have options" is what the taxonomy says. But that's vague. When is a brainstorm "done"? We don't know until we know.

4. **The insight is a different kind of child.** It's not a sub-task or a sub-brainstorm. It's something that *emerged* from doing the work. The tree structure treats it the same as the planned clusters, but it's categorically different — it wasn't anticipated.

---

## What the exercise shows

**What works:**
- Implementation work (Tests 1-2) fits cleanly. The model handles planned, structured work well.
- Hierarchy, artifacts, evidence, acceptance criteria all make sense for execution.
- `informs` dependencies capture "learned something, then built against it."

**What doesn't work:**
- **Discovery doesn't fit the status lifecycle.** The planned→complete progression assumes known endpoints. Exploration doesn't have those.
- **Emergent vs planned children.** The model treats all children the same. But "we planned to do this" and "this surfaced while we were doing something else" are different. The crash fix was reactive. The false crystallization insight was emergent. Neither was a planned child.
- **No way to express confidence.** "Complete" means done. But done ≠ validated. The Work primitive has no tentative/tested distinction.
- **Decisions embedded in conversation are invisible.** The "self-healing over error prevention" decision happened but wasn't captured as a Work item. The model supports it, but real-time extraction is the gap.

---

## Summary

The model works well for **execution** (implementation, verification). It's weaker for **exploration** (discovery, brainstorming). The status lifecycle, the assumption of planned children, and the lack of confidence levels all point to the same gap: the model was designed for work you can plan, not work that unfolds.

This might be fine — maybe discovery is just messier and the model adapts loosely. Or maybe it means the model needs something for exploratory work that it doesn't have yet.
