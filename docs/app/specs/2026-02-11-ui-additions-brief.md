# Forge: UI Additions Brief

**Date:** 2026-02-11
**Audience:** UI developer / AI coding agent
**Scope:** Add deliberation and knowledge work capabilities to existing Forge UI
**Existing codebase:** coder-forge-base44 (React 18, Vite, TailwindCSS, Radix UI)
**Supporting docs:** [UI-BRIEF](../UI-BRIEF.md) (original spec), [Taxonomy](../taxonomy.md)

---

## Context

Forge has a working UI with 5 views: Dashboard (tree), Work Item Detail, Dependency Graph, Board, and Project Settings. It supports creating hierarchical work items, tracking status, managing dependencies (type: "blocks" only), attaching artifacts (as file/link attachments), and filtering/searching.

We need to add capabilities that make Forge usable for **knowledge work** — brainstorming, discussion, decision-making, evaluation — not just task tracking. The additions below extend the existing views rather than creating new ones.

---

## Addition 1: Rich Artifact Editor

**Current state:** Artifacts are attachments — a name, a type dropdown, and a URL or file path. You can link to external content but cannot write content inside Forge.

**What to add:** A markdown editor for artifacts that lets users create and edit rich text documents directly in the Work item detail panel.

**Behavior:**
- Each artifact can be either a link (current behavior) or an inline document (new)
- Inline documents have a markdown editor with toggle between edit mode and rendered preview
- The editor should support standard markdown: headings, bold, italic, lists, code blocks, links, tables
- Artifacts show a "last edited" timestamp
- Artifact content is saved when the user stops editing (auto-save) or clicks save

**Where it appears:** In the Work item detail panel, in the Artifacts section. When a user creates a new artifact and selects type "document", they get the editor instead of a URL field.

**Not needed:** Collaborative real-time editing, image upload, file drag-and-drop. Keep it simple — a markdown text editor with preview.

---

## Addition 2: Artifact Version History

**Current state:** No version tracking on artifacts.

**What to add:** A history view showing how an artifact changed over time.

**Behavior:**
- Each save of an inline artifact creates a version entry: timestamp + snapshot of content
- A "History" button on each artifact opens a list of versions
- Selecting a version shows the content at that point
- Diff view between any two versions (line-level diff, additions in green, removals in red)

**Where it appears:** On each inline artifact in the Work item detail panel.

---

## Addition 3: Cross-Artifact Links

**Current state:** Artifacts belong to one Work item. No way to reference artifacts on other Work items.

**What to add:** Artifacts can link to other Work items or specific artifacts on other Work items.

**Behavior:**
- When editing an artifact (markdown), typing `[[` opens a search popup to find a Work item by name
- Selecting a Work item inserts a link: `[[w-001: Rich Artifact Editor]]`
- These links render as clickable references that navigate to the linked Work item
- In the Work item detail, a "Referenced by" section shows which other artifacts link to this item (backlinks)

**Where it appears:** In the artifact editor (inline links) and in the Work item detail panel (backlinks section).

---

## Addition 4: `informs` and `relates_to` Dependencies

**Current state:** Dependencies only support type "blocks". Adding a dependency creates a "blocks" relationship.

**What to add:** Two additional dependency types: "informs" and "relates_to".

**Behavior:**
- When adding a dependency, a type selector offers three options: blocks, informs, relates_to
- "blocks" = execution dependency (B cannot start until A completes) — existing behavior
- "informs" = knowledge dependency (A's output is relevant to B, but doesn't block it)
- "relates_to" = reference link (A and B are related, no directional flow)
- In the Work item detail, dependencies are grouped by type: "Blocked by", "Informed by", "Related to" (and inverse: "Blocks", "Informs", "Related to")
- In the dependency graph:
  - "blocks" edges are solid lines with arrows
  - "informs" edges are dashed lines with arrows
  - "relates_to" edges are dotted lines, no arrows

**Where it appears:** Work item detail (dependency section), dependency graph view, and when adding a new dependency.

---

## Addition 5: Propagation Indicators

**Current state:** No awareness of staleness. When a dependency completes, downstream items don't know.

**What to add:** Visual indicators when an upstream `informs` dependency has been updated more recently than the downstream item.

**Behavior:**
- When a Work item that has `informs` outgoing dependencies is updated (status change or artifact edit), check each downstream item
- If the downstream item's `updated_at` is older than the upstream's `updated_at`, show a "may need review" indicator
- The indicator is a small badge/icon on the work item in the tree view and detail view
- Clicking the indicator shows which upstream items changed and when
- The user can dismiss the indicator (acknowledge they've reviewed it)

**Where it appears:** Dashboard tree view (badge on affected items), Work item detail (banner at top).

---

## Addition 6: Phase and Type Labels

**Current state:** Labels are free-form strings. No structured taxonomy.

**What to add:** Two label dimensions with default values: phase and type.

**Behavior:**
- Work items have two special label fields: `phase` and `type` (in addition to free-form labels/tags)
- Phase values: discovery, requirements, design, planning, implementation, verification, release
- Type values: task, decision, evaluation, brainstorm, spec, poc, process (and user-defined)
- When creating a Work item, phase and type are selectable dropdowns (not free text) with an "other" option for custom values
- Dashboard supports grouping by phase (shows lifecycle columns) and by type
- Filters include phase and type as independent filter dimensions

**Where it appears:** Work item creation dialog, Work item detail header, dashboard group-by options, filter bar.

---

## Addition 7: Work Item Templates

**Current state:** Creating a Work item starts with empty fields.

**What to add:** Selecting a type pre-fills relevant fields.

**Behavior:**
- When creating a Work item and selecting a type, default fields are populated:
  - **decision**: description template with sections "Question", "Context", "Decision", "Rationale", "Rejected Alternatives"
  - **evaluation**: description template with sections "Evaluated Against", "Structural Gaps", "Functional Gaps", "Expected Gaps", "Surplus"; default acceptance criteria: "All gaps classified", "Gaps converted to work items"
  - **brainstorm**: description template with sections "Problem Space", "Options Explored", "Open Questions", "Next Steps"
  - **spec**: description template with sections "What to Build", "Success Criteria", "What NOT to Build"
- Templates populate the description field. User can edit freely — templates are starting points, not enforced structure.
- If the user has already typed a description, selecting a type does NOT overwrite it (only fills empty fields)

**Where it appears:** Work item creation dialog (triggered by type selection).

---

## Addition 8: Evaluation Interaction

**Current state:** No structured way to do a gap classification. Would be free text in description.

**What to add:** A structured evaluation view for classifying gaps.

**Behavior:**
- When a Work item has type "evaluation", the detail view shows an additional "Gaps" section
- The Gaps section has four categories: Structural, Functional, Expected, Surplus
- Each category is a list where the user can add gap entries (description + notes)
- Each gap entry has a "Create Work Item" button that creates a child Work item from the gap (name = gap description, inherits project and parent)
- A summary shows counts: "2 structural, 5 functional, 3 expected, 1 surplus"

**Where it appears:** Work item detail panel, only visible when type = "evaluation".

---

## Design Constraints

- All additions integrate into the **existing views** — no new top-level pages or navigation items
- Follow the existing dark theme and design patterns (Radix UI, Tailwind)
- Maintain information density — these features should add capability without adding clutter
- All new features should work with keyboard navigation where applicable
- Do not change the data model structure — add new fields to existing entities, don't create new entity types
- The dependency type field already exists in the data model as `type: enum: blocks | relates_to | informs` — it just needs to be exposed in the UI
