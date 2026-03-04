# Process: Delivery Intake

**Purpose:** Evaluate code or work delivered by an external builder (human, AI agent, or platform) against the spec that requested it. Produce actionable next steps.

**Related:** [Base44 UI Evaluation](../evaluations/2026-02-11-base44-ui-eval.md) (first use of this process)

---

## When to Use

Any time delivered work needs to be evaluated before integration:
- External developer delivers code against a brief
- AI agent completes a work item
- Imported code from another system
- Any handoff between producers

---

## Process

### Step 1: Identify the Spec

What was the delivery supposed to satisfy? Find the spec, brief, or work item with acceptance criteria. If there isn't one, the evaluation has no basis — write the criteria first, then evaluate.

### Step 2: Structural Scan

Before evaluating features, assess whether the delivery is architecturally compatible:

- **Can it run independently?** Or is it locked to a platform/service?
- **Where are the seams?** How is data access structured? Is it abstracted or hardcoded?
- **What are the hard dependencies?** Auth, persistence, external APIs — what must change before anything else works?

Structural gaps block everything. They determine whether integration is a swap (clean seam exists) or a rewrite (no seam, tangled).

### Step 3: Classify Gaps

Compare delivery against spec. Put every delta into one of four categories:

| Category | Definition | Action |
|----------|-----------|--------|
| **Structural** | Architecture doesn't support our needs | Fix first — blocks all other work |
| **Functional** | Feature missing or incomplete vs. spec | Becomes a work item |
| **Expected** | Deliberately excluded from the spec | No action — validate it's truly expected |
| **Surplus** | Delivered but not requested | Decide: keep, strip, or ignore |

### Step 4: Classify Surplus

For each surplus item, decide:
- **Keep** — useful even though not requested
- **Strip** — adds weight, complexity, or confusion
- **Ignore** — harmless, leave it alone

### Step 5: Order by Unblocking

Don't prioritize by importance. Prioritize by what unblocks the most downstream work. The first fix should be the one that makes the next ten fixes possible.

### Step 6: Generate Work Items

Each gap (structural or functional) becomes a work item with:
- Clear description of what's wrong or missing
- Reference to the spec requirement it violates
- Acceptance criteria for when the gap is filled
- Dependencies on structural fixes if applicable

---

## Learnings from First Use (Base44 Eval)

1. **Behavioral specs produce better deliveries.** When we removed technology prescriptions from the UI-BRIEF, the builder made their own structural choices — and those choices (single SDK entry point, React Query abstraction) actually made integration easier. Prescribing technology constrains the builder without guaranteeing better outcomes.

2. **The structural scan is the most valuable step.** Knowing that `base44Client.js` is a clean seam told us more about integration effort than any feature checklist. A delivery with 100% feature coverage but tangled data access would be harder to integrate than what we got.

3. **Expected gaps validate the spec, not the delivery.** If the spec said "don't build Policy UI" and the delivery doesn't have it, that's not a gap — it's compliance. Classifying these separately prevents false negatives in the evaluation.

4. **Surplus needs active decision.** Ignoring surplus leads to bloat. Deciding keep/strip/ignore forces awareness of what's in the codebase.

---

## How Compose Should Handle This

This manual process maps directly to Compose workflows:

### As a Work Item Type

A delivery intake is a Work item in `review` status with:
- **Acceptance criteria** drawn from the spec
- **Evidence** = the delivered code/artifacts
- **Child work items** auto-generated from gap classification
- **Status flow**: `review` → gap analysis complete → children created as `planned` → parent moves to `in_progress` as children are worked

### As a Reusable Pattern

Compose should support "evaluation templates" — a standard set of acceptance criteria categories (structural, functional, expected, surplus) that can be applied to any delivery review. This isn't a special feature; it's a work item pattern with structured children.

### Policy Implications

The gap classification maps to policies:
- **Structural gaps** = gate (blocks everything, must be resolved before proceeding)
- **Functional gaps** = flag (work can continue on other items, but these need attention)
- **Expected gaps** = skip (no action needed, already accounted for)
- **Surplus** = flag (needs a keep/strip/ignore decision)

### What Compose Automates

In later phases, Compose can:
- Auto-generate the gap classification by comparing delivery evidence against acceptance criteria
- Auto-create child work items from identified gaps
- Apply the unblocking order based on dependency analysis
- Track which gaps are structural (blocking) vs. functional (parallel-workable)

For now, we do this manually. The process doc is the spec for what Compose eventually does.
