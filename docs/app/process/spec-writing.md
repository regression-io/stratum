# Process: Writing Specs for External Builders

**Purpose:** How to write specs that produce usable deliveries from external builders (human devs, AI agents, platforms).

**Learned from:** UI-BRIEF iteration during Compose planning (2026-02-11)

---

## Principles

### Describe behavior, not implementation

Specs should say what the user can do and what the system should do — not which libraries to use, what database to pick, or how to structure the code.

**Why:** Behavioral specs let the builder make structural decisions. Those decisions often produce better architecture than prescriptions, because the builder optimizes for their own constraints. When we removed technology prescriptions from the UI-BRIEF, the Base44 builder made choices (single SDK entry point, React Query abstraction) that made integration easier — choices we didn't ask for and wouldn't have thought to prescribe.

**Bad:** "Use SQLite via better-sqlite3, served by Express on localhost"
**Good:** "Data must persist across sessions. Creating a work item takes <3 seconds."

### Separate what from where

If persistence, deployment mode, or hosting matters to us, handle it ourselves at integration time. Don't push architectural constraints into a behavioral spec — the builder can't optimize for constraints they don't fully understand.

**Example:** We removed storage requirements, local-first, and offline-capable from the UI-BRIEF. These are integration concerns, not UI behavior concerns. The builder doesn't need to understand our deployment model.

### Include acceptance criteria, not checklists

Acceptance criteria are testable. Checklists are inventories. A spec full of "must have X, must have Y" produces compliance. A spec with "user can accomplish Z in under N seconds" produces usable software.

### Exclude what you'll handle yourself

If a concern belongs to integration (persistence mode, auth, deployment), explicitly exclude it. This prevents:
- The builder making assumptions about your infrastructure
- Wasted effort on features you'll replace
- Technology choices that conflict with your stack

### State what not to build

Explicitly listing excluded features prevents over-building. The UI-BRIEF's "What NOT to Build" section was effective — the Base44 delivery didn't include session management, policy UI, or evidence collection, exactly as specified.

---

## Spec Structure (recommended)

1. **What is this?** — One paragraph. What the product does, for whom.
2. **What are we building?** — Scope of this delivery. What's in, what's out.
3. **Data model** — Entities and relationships. What the system knows about.
4. **Views/screens** — What the user sees. Layout, information displayed, interactions.
5. **Key interactions** — What the user does. CRUD, navigation, filtering, shortcuts.
6. **Design principles** — How it should feel. Density, speed, keyboard-first, etc.
7. **What NOT to build** — Explicit exclusions to prevent scope creep.
8. **Success criteria** — Testable conditions for acceptance.

9. **Design decisions** — Numbered checkboxes, one per decision. Each approved independently.

Notably absent: technology choices, architecture, deployment, infrastructure.

### Design Decision Checkboxes

Every design doc and plan must include a numbered list of design decisions as checkboxes:

```markdown
- [ ] **D1: Decision title** — Brief rationale
- [ ] **D2: Decision title** — Brief rationale
```

**Rules:**
- One checkbox per independent decision. Don't lump related-but-separable choices.
- Rejected items get reworked, not dropped silently.
- Who checks the box follows the 3-mode dial:
  - **Gate:** Human reviews and checks each decision.
  - **Flag:** Agent checks, human gets notified and can uncheck.
  - **Skip:** Agent checks, moves on.
- A doc isn't approved until all decisions are checked (or explicitly rejected with rationale).

---

## How Compose Should Handle This

### Specs as Artifacts

A spec is an artifact attached to a Work item. The Work item's acceptance criteria are drawn from the spec's success criteria. When the delivery comes in, the evaluation process ([Delivery Intake](delivery-intake.md)) compares evidence against those criteria.

### Spec → Work Item → Delivery → Evaluation → Child Items

The full cycle:
1. Write spec (artifact on a Work item)
2. Assign to builder (session claims the Work item)
3. Delivery comes in (evidence attached to the Work item)
4. Evaluate delivery against spec (gap classification)
5. Gaps become child Work items
6. Iterate until acceptance criteria are met

This is the same cycle whether the builder is an external platform, an AI agent, or a human developer. Compose doesn't care who builds — it tracks what was requested, what was delivered, and what's left.

### Template Support

Compose should support spec templates — the recommended structure above as a starting point when creating a new spec artifact. Not enforced, just offered.
