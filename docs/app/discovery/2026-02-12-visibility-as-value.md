# Visibility as Value

| | |
|---|---|
| **Date** | 2026-02-12 |
| **Context** | Session 10 — reflecting on sessions 0-9 and external reference (Zechner's minimal coding agent) |
| **Status** | Active exploration |

---

## The problem

You say "Build me X." The AI starts working. What follows is hundreds or thousands of lines of text scrolling past — tool calls, file edits, reasoning, error recovery. You can read it all, but you can't see the shape of what's happening. You can't tell:

- What decisions were made (and which were arbitrary)
- What was tried and rejected
- How confident the AI is in its current approach
- What depends on what
- Where you are in the overall arc
- When to intervene vs. when to let it run

The execution layer is increasingly good. Models write competent code. Minimal harnesses (4 tools, <1000 token system prompts) compete with complex ones on benchmarks. The raw coding ability is not the bottleneck.

The bottleneck is steering. The human has no visibility into the thinking layer — what's being decided, why, how it connects, how sure we are. Without visibility, you can't steer. Without steering, you get what the AI decided to build, not what you wanted.

---

## The original goal

Add a product/project management layer on top of vibe coding. Not replacing the coding agent — augmenting it with structure. The agent codes; Compose provides the rails.

Rails doesn't mean process enforcement (write a spec, get approval, write a design, get approval...). Rails means **visibility that enables steering.** You can see what's happening, so you can redirect when it drifts. Same way rails on a road don't slow you down — they keep you from going off the cliff.

---

## What we explored (sessions 0-9)

Sessions 0-4 built the infrastructure: terminal embed, canvas, WebSocket, persistence, crash recovery.

Sessions 5-8 explored the conceptual space: primitives, composition model (phases × things × verbs × processes × lenses), requirements (CR1-CR7), design strategy (jigsaw model), specs. Heavy documentation, heavy gate-mode conversation.

Session 9 built the first visual piece: the vision surface with click-to-ripple connection tracing. This was designed through conversation, not specification — and produced a better result than upfront design would have.

### What we learned about process

The exploration produced a composition model (CR1-CR7) that genuinely constrains the design space. But it also produced a lot of written artifacts (specs, design docs, implementation plans) whose value was questionable:

- **Docs that helped:** The composition model (prevented scope creep), the implementation file manifest (made building mechanical). Both worked as *constraints*, not as *descriptions*.
- **Docs that didn't help:** Competitive analysis, scenario walkthroughs, design approach palettes — written once, read zero times. The exploration was valuable *as conversation*; writing it down added no value over having had the conversation.
- **Best design work had no doc:** The glow/ripple feature was designed by building, seeing, reacting, iterating. Four versions in one session. No spec, no plan.

**Conclusion:** The pipeline phases (vision → requirements → design → planning → implementation → verification) are valuable as a *mental model* the AI uses to track what kind of work is happening. They are not valuable as a *document production process* (write a spec, then a design doc, then a plan).

### External reference: minimal coding agents

Mario Zechner built a coding agent with 4 tools and a <1000 token system prompt that competes with Claude Code on benchmarks. His rejections are instructive:

- Rejected plan mode (file-based planning is better)
- Rejected built-in todo tracking (confuses models)
- Rejected MCP (14-18k tokens of tool definitions for what bash does in 225 tokens)
- Rejected sub-agents (poor observability)

His thesis: the model is the intelligence, the harness should stay out of the way. Structure is overhead.

**Where he's right:** For execution (coding tasks), minimal wins. Don't build abstractions over capabilities the model already has.

**Where the gap is:** His agent has no memory across sessions, no confidence tracking, no decision graph, no "where are we?" view, no governance model. When the developer already knows what to build, that's fine. When the goal is fuzzy, or the project is complex, or you need to trace why something was decided three sessions ago — there's nothing.

That gap is Compose's value.

---

## The five things nobody else has

1. **Persistent decision graph.** A live graph of items + connections that survives across sessions. What was decided, why, what was rejected, what it connects to. Not documents — nodes and edges. The ripple feature (click a card, see its downstream chain light up) is the first visual expression of this.

2. **Confidence as a first-class concept.** Not done/not-done. How sure are we? Untested → low → moderate → high → crystallized. The AI can say "you're building on a low-confidence assumption" because confidence is tracked, not imagined.

3. **Per-decision governance (the 3-mode dial).** Not "autonomous" or "not autonomous" — gate *this* decision, skip *that* one. The dial controls how it feels: gate = waterfall, skip = full autonomy, flag = balanced. Same pipeline underneath, different human involvement.

4. **Phase awareness.** The AI recognizes what kind of work is happening — vision, requirements, design, implementation — and what usually follows. Not enforcement. Recognition. "That looks like design work, but requirements were never pressure-tested."

5. **Accumulated context.** Memory that gets better over time. Not just "what files exist" but "what was explored, what was killed, what confidence shifted, what connections were drawn." A fresh session with no history vs. a session with 9 sessions of accumulated context — different capability entirely.

---

## What to streamline

**Kill the document production chain.** No separate specs, design docs, implementation plans as mandatory pipeline stages. The conversation is the design phase. Items emerge from conversation, not from someone writing a spec.

**The vision surface replaces documents.** Instead of a design doc, you have cards with connections and confidence. The surface is the understanding — live, interactive, traceable.

**Evaluation is inline.** "What if this isn't true?" happens in conversation, updates confidence on the card, done. Not a separate counterfactual document.

**Phase transitions are recognized, not gated by default.** The AI notices "vision is crystallizing, requirements are emerging." It doesn't make you write a document before proceeding. (Gate mode is available when you want it — but it's not the default.)

---

## The pitch

You talk. The AI builds a decision graph as you go — items, connections, confidence, phase awareness. You can see it. You can trace why anything was decided. You can see what's tested and what isn't, what's connected and what's orphaned, where the low-confidence assumptions are.

When you say "build it," the AI has context no fresh session could have.

When something goes wrong, you can trace back through the graph to find the decision that led here.

When you come back tomorrow, the graph is still there. The AI picks up where you left off.

That's the value. Not documents. Not process. Visibility that enables steering.

---

*The rails aren't the process. The rails are being able to see where you're going.*
