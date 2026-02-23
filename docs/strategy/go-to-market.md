# Go-To-Market

## The Honest Assessment

Stratum as a standalone language is unlikely to become the standard without organizational backing. The technically superior independent language loses to the "good enough" language backed by the company whose API you're already using. Microsoft, Anthropic, Google, and OpenAI all have incentives to define this standard and the distribution to win.

The realistic paths to value don't require winning the language war.

Two things that were wrong in an earlier draft of this doc:

1. **Enterprise-first is backwards.** Dev tools don't win by convincing enterprise buyers — they win by building something most developers use, and enterprise follows. No CLAUDE.md is going to get a VP of Engineering to sign a contract. A thousand developers reaching for `@infer` because it's the cleanest way to write an LLM function might.

2. **Publish-first doesn't drive adoption.** Publishing a design doc establishes priority and creates some inbound — but nobody adopts a spec without an implementation. "We have the design" is the wrong unlock. "We have a tool that runs on your existing code and tells you exactly how much you're wasting" is.

Working code ships before writing about it.

---

## Path 1 — Token Audit Tool (first and fastest path to real value)

The insight "you're spending 40% of your LLM bill describing constraints the runtime could enforce for free" has immediate practical value to every developer paying non-trivial LLM API costs. No adoption required — it analyzes existing code.

**The product:**
1. Analyze existing LangChain / LlamaIndex / raw API code
2. Classify every prompt token as structural (wasteable) vs. semantic (irreducible)
3. Show exactly what constrained decoding + post-parse validation would save
4. Generate the migration

**Why this is first:**
- Runs on code the developer already has. Zero adoption barrier.
- Produces a number: "you're wasting 940 tokens per call, ~$180/month at your volume"
- That number is the pitch for everything else
- Doesn't require anyone to understand Stratum's design
- Can be published with real findings from real codebases — evidence, not a whitepaper

**The developer adoption path:** install a CLI tool, point it at your project, get a report. That's the first touch. The report references constrained decoding and structured retry as the fix. That's the second touch. The fix points to `pip install stratum`. That's the adoption.

---

## Path 2 — Python Library (the `@infer` decorator)

Build `stratum` as a Python library first. Deliver 60% of the language value with 10% of the build cost. The `@infer` decorator with `ensure` + structured retry + budget enforcement is the core.

```python
@infer(
    intent="Classify the emotional tone of customer feedback",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3
)
def classify_sentiment(text: str) -> SentimentResult: ...
```

**Why Python first:**
- Largest AI/ML developer audience — DSPy, LangChain, instructor, AutoGen users
- Pydantic already gives you 30% of the contract system
- Most multi-agent pain is felt here today
- Researchers and practitioners who write about it are here

**Open source the library. Build a company on the runtime/cloud.** Classic model: HashiCorp/Terraform, Elastic/Elasticsearch. The library builds community and establishes the standard. The managed platform captures the value.

**TypeScript second** — production deployment, fullstack developers, Vercel AI SDK users.

---

## Path 2b — n8n Migration Tool (warm audience, low friction)

n8n users who hit the reliability ceiling are the warmest possible Stratum adopters. They already know what their workflow should do. They've already felt the pain of untyped inter-node JSON, silent failures, and retry that doesn't learn. They're ready to write code.

**The product:** import an n8n workflow export, generate the equivalent `.stratum` IR, and annotate every untyped inter-node boundary with the contract gap it represents.

```
Input:   n8n workflow JSON
Output:  .stratum flow spec
         + list of typed contract gaps ("node 3 → node 4: untyped, suggest SentimentResult")
         + reliability report ("3 boundaries have no validation, these are your failure points")
```

This isn't a criticism of n8n — it's a migration path. The message: "here's what you already built, here's what typed contracts would look like, here's what they'd catch."

**Why this works as an acquisition channel:**
- No cold adoption — they already have a working workflow
- The tool produces immediate value (the gap report) before they've committed to anything
- The migration is incremental — they can add contracts one boundary at a time
- The n8n community is large and vocal; one good migration story spreads

---

## Path 3 — MCP Server for Claude Code (vibe coder distribution)

The MCP server targets two distinct Claude Code audiences with one installation.

### The vibe coder (primary audience, larger market)

Vibe coders are prompting Claude Code to build things right now. The code Claude generates for LLM-orchestrated tasks is typically: raw API calls, manual retry loops, untyped inter-step JSON, no budget awareness, no observability. It works until it doesn't, and when it breaks there's no structure to debug.

With the Stratum MCP installed, the experience changes invisibly:

- Claude generates `.stratum` IR internally to plan the task — the vibe coder never sees it
- Claude presents a plain-language summary: "I'll do X, Y, Z. Estimated cost: ~$0.02. Proceed?"
- On approval, the flow executes with contracts enforced, retries handled, budget tracked
- **When the output is code**, Claude generates `@infer`-annotated Python using the stratum library — not raw LLM calls

The vibe coder gets professionally structured LLM code as output without knowing what `@infer` means. Their codebase is better than if they'd written it themselves or asked Claude without Stratum in the critical path. They don't need to understand the library; they just need the code to work reliably.

**The HITL moment reframes naturally**: when something needs human judgment — a debate that didn't converge, a low-confidence result — Claude surfaces it as conversation: "I got two conflicting analyses. Here are both. Which should I use?" That's already the interface they're in.

### The professional developer (secondary audience, earlier adopter)

Professional developers who use Claude Code see the typed execution plans, understand the step graph, and can tune the contracts. They're a smaller audience but higher-value advocates. They're also likely to encounter Stratum-annotated code generated by vibe coders and recognize what it is.

### The flywheel

Vibe coder gets better output → their codebase contains `@infer`-annotated code → professional developer inherits or reviews that code → encounters the library → adopts it directly. Adoption spreads in both directions from a single MCP installation.

This is not a distribution strategy for enterprise. It's a distribution strategy for the individual Claude Code user who will notice — or whose colleagues will notice — that their LLM code is more reliable with Stratum in the critical path.

See [`distribution-and-integration.md`](distribution-and-integration.md) and [`how-to-build.md`](how-to-build.md) for implementation.

---

## Path 4 — Publish Results (not the design)

Publish after working tools exist and have been run on real code. Not "here's our design" — "here's what we found when we ran the auditor on 50 LangChain repos."

**What to publish at that point:**
- "We analyzed 50 LangChain codebases. The average prompt wastes 38% of tokens on structural constraints."
- "The case for `ensure` postconditions over retry-in-a-loop" — with benchmarks
- "The 12 design tensions in hybrid LLM systems" — the matrix as a standalone piece

Publishing at this point is credibility amplification on top of something that already exists. Not a cold pitch for something that doesn't.

---

## Path 5 — Language-Agnostic Spec (parallel, not prior)

Define Stratum as a **specification** — like OpenAPI, GraphQL, or JSON Schema — in parallel with building the Python library, not instead of it. The spec lets implementations emerge in other languages without having to wait for Stratum to build them.

```
stratum.yaml   ← the spec artifact
```

A `.stratum` file defines contracts, flows, agent capabilities, budget constraints. Tools in any language can read and execute it.

---

## Path 6 — Design Acquisition

The docs in `stratum/` represent significant design capital. But it's not a pitch-able asset until there's evidence. The auditor findings and real-world usage data are what make the design capital valuable to a potential acquirer.

---

## Recommended Sequence

```
1. @infer + ensure + structured retry  (weeks — pip install stratum, one decorator)
       ↓
2. @flow + @compute                    (weeks — typed orchestration)
       ↓
3. MCP server + plan skill             (weeks — wires into Claude Code for both audiences)
       │                                 professional devs: typed plan review
       │                                 vibe coders: plain-language summary → @infer output
       ↓
4. .stratum IR spec                    (parallel with 1-3 — defines what the library emits)
       ↓
5. Publish results from real usage     (reliability + debuggability evidence, not design docs)
       ↓
6. Token audit tool                    (v2 — needs real workloads to produce meaningful numbers)
       ↓
7. n8n migration tool                  (v2 — warm audience with existing workflows)
       ↓
8. TypeScript library                  (follows Python adoption signal)
       ↓
9. Community → enterprise follows      (enterprise buys what their developers already use)
       ↓
10. Native integration pitch           (requires traction, targets Anthropic/OpenAI)
       ↓
11. Choose: acquire / fund / grow      (based on traction signal)
```

**Why `@infer` is first**: it solves the problem developers feel today — LLM calls that return malformed output, retry loops that loop forever, multi-step flows that fail at step 4 with confusing errors. Reliability and debuggability are the adoption driver, not cost savings.

**Why the MCP server is step 3, not later**: the vibe coder market is larger than the professional developer market, and it's reachable now. Every Claude Code user generating LLM orchestration code is a potential Stratum user who never has to learn the library — they just get better output. The flywheel (vibe coder output → professional dev encounter → direct adoption) compounds early.

**Why the token auditor is step 6**: it needs real workloads to produce meaningful findings. Running it on a codebase with 10 LLM calls produces a number nobody cares about. Running it after teams have adopted `@infer` and accumulated real usage produces a number that sells itself.

---

## The Worst Outcome

Continue refining the design in private until the window closes and the ideas diffuse into the ecosystem anyway — attributed to whoever shipped first.

The window is open but closing. The market hasn't settled on a pattern. In 2-3 years it probably will have.
