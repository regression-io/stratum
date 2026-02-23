# Type System

## Design Goals

1. **Contracts are prompt artifacts, not just type annotations.** The type system must produce machine-readable schemas that can be injected into LLM prompts.
2. **`infer` and `compute` must be type-compatible.** A caller cannot distinguish the two based on type signature alone.
3. **Postconditions are typed expressions.** `ensure` clauses operate on the declared return type and are statically checked for validity.
4. **Return types for `infer` must be contracts.** Anonymous object types are not allowed as `infer` return types — they cannot be reliably schema-compiled.

---

## Primitive Types

| Type | Notes |
|---|---|
| `string` | UTF-8 text |
| `int` | 64-bit signed integer |
| `float` | 64-bit float |
| `bool` | true / false |
| `null` | explicit null |
| `Date`, `DateTime` | ISO 8601 |
| `bytes` | raw binary |

Ranged primitives:

```stratum
float[0.0..1.0]   // inclusive bounds
int[1..100]
string[1..500]    // length bounds
```

Ranges are enforced both at compile time (static analysis) and runtime (contract validation).

---

## Contract Types

Named, structured types. The unit of schema compilation.

```stratum
contract Address {
  street: string
  city: string
  country: string[2..2]   // ISO country code
  postal_code: string?    // optional
}

contract UserProfile {
  name: string
  age: int[0..150]
  address: Address        // nested contracts
  tags: string[]          // arrays
}
```

In Python, `@contract` works on plain annotated classes. Pydantic `BaseModel` is an optional enhanced backend — not required. Stratum generates JSON Schema from Python type annotations directly (`typing.get_type_hints()`), falling back to Pydantic's schema generation when a Pydantic model is detected. This insulates developer code from Pydantic version changes.

### Literal Unions

```stratum
contract Priority {
  level: "low" | "medium" | "high" | "critical"
}
```

Literal unions compile directly to enum schemas. The LLM is constrained to one of the defined values.

### Discriminated Unions

```stratum
contract Result {
  kind: "success" | "failure"
  value: string?      // present when kind = "success"
  error: string?      // present when kind = "failure"
}
```

Full discriminated union support (with `kind` field convention) is a design goal. Implementation complexity is non-trivial.

---

## Function Signatures

Both `compute` and `infer` use the same signature syntax:

```stratum
compute parse(raw: string, format: DateFormat) -> Date
infer   classify(text: string) -> Category
```

Named parameters are required for `infer` functions — positional-only calls are disallowed. This is because parameter names become part of the prompt context ("text: ...").

Multiple return values via inline contracts:

```stratum
infer analyze(doc: Document) -> { summary: string, topics: string[], confidence: float[0.0..1.0] }
```

Inline anonymous contracts are allowed for `infer` return types in this case (named fields, clear schema).

---

## Postcondition Expressions

`ensure` clauses are typed expressions evaluated against the return value bound to `result`:

```stratum
ensure: result.confidence > 0.7
ensure: result.label in ["positive", "negative", "neutral"]
ensure: result.summary.length < 500
ensure: result.items.length > 0
```

Multiple `ensure` clauses are evaluated in order. Each failure generates a separate retry prompt.

The static analyzer checks that `ensure` expressions reference valid fields of the declared return type. An `ensure` that references a non-existent field is a compile error.

---

## Probabilistic Types

`infer` functions are non-deterministic — the same input may produce different outputs across calls. The type system addresses this with a hybrid model:

### `stable=True` (default)

The developer asserts that this function's output is stable enough to compose safely. Return type is `T`. In test/CI mode, the runtime samples N times and warns if the output distribution is wide. In production, the assertion is trusted.

```python
@infer(
    intent="Classify the emotional tone of customer feedback",
    ensure=lambda r: r.confidence > 0.7,
    stable=True,   # default — return type is SentimentResult
)
def classify_sentiment(text: str) -> SentimentResult: ...
```

### `stable=False`

Return type is `Probabilistic[T]`. Callers must explicitly unwrap — the non-determinism is visible in the type and cannot be ignored.

```python
@infer(
    intent="Generate an execution plan for this task",
    stable=False,  # return type is Probabilistic[ExecutionPlan]
)
def generate_plan(task: Task) -> Probabilistic[ExecutionPlan]: ...

@flow
def run(task: Task) -> Report:
    plan = generate_plan(task)
    chosen = plan.most_likely()      # take modal value
    # or: plan.sample()              # take one draw
    # or: plan.assert_stable()       # raise if confidence interval is wide
```

Use `stable=False` for generative or open-ended tasks where variance is expected and callers should handle it explicitly.

**`Probabilistic[T]` API:**

```python
class Probabilistic(Generic[T]):
    def most_likely(self) -> T:
        # Returns the modal value across samples (test mode),
        # or the single output (production). Never raises.

    def sample(self) -> T:
        # Returns a random draw from collected samples.
        # In production with one sample, returns that sample.

    def assert_stable(self, threshold: float = 0.9) -> T:
        # Raises StabilityAssertionError if sample agreement is below threshold.
        # Agreement = fraction of samples matching the modal value on key fields.
        # Returns the modal value if stable.
```

In production, `_samples = [single_output]` — all three methods behave correctly with no sampling overhead.

The formalism (probability distributions, confidence intervals, type-level variance bounds) is open for future extension without breaking the surface API.

---

## `opaque[T]` Type Modifier

`opaque[T]` is a field-level modifier on contract fields. It marks string (or other) data that originates from an external or agent source and must not be interpolated inline into LLM prompt instruction text.

```python
@contract
class AgentOutput:
    summary: str              # interpolated inline into the next agent's prompt — normal
    reasoning: opaque[str]   # passed as structured data; never inlined
    entities: list[str]       # structured, low injection risk — inline fine
```

**What the prompt compiler does differently:**

```
# Normal field — inline interpolation (injection-vulnerable):
system: "You are a reviewer."
user:   "Summarize this reasoning: {previous.reasoning}"

# opaque field — data channel (safe):
system: "You are a reviewer. Summarize the attached input."
user:   [structured JSON attachment: {"reasoning": "<...value...>"}]
```

The LLM still receives the data. It cannot have its instructions overwritten by it — the same guarantee as parameterized SQL over string concatenation.

**Python annotation syntax:** `opaque` is a class with `__class_getitem__` that returns `Annotated[T, _OpaqueMarker()]`. This makes `opaque[str]` a valid Python type annotation that type checkers treat as `str`, while the prompt compiler detects `_OpaqueMarker` in the annotation metadata to enforce the data-channel rule.

```python
# In a contract:
@contract
class AgentOutput:
    summary: str
    reasoning: opaque[str]   # Annotated[str, _OpaqueMarker()] at runtime
    entities: list[str]
```

**Type system behavior:** `opaque[str]` is assignable to `str` and unwrappable with `.value`. It serializes normally. The restriction is enforced only in the prompt compiler — if an `opaque[T]` field is referenced in an inline string interpolation, the compiler raises `StratumCompileError` before execution.

**Static analysis rule:** see the Static Analysis section below.

---

## `HumanDecision[T]`

`HumanDecision[T]` is the return type of `await_human`. It wraps a typed decision with provenance metadata — downstream code knows whether a value came from a human or an LLM.

```python
@dataclass
class HumanDecision(Generic[T]):
    value: T
    reviewer: str | None      # identity of the reviewer, if provided
    rationale: str | None     # optional human note
    decided_at: datetime
    review_id: str            # stable ID for the review event; correlates with trace records
```

`.value` extracts `T`. `HumanDecision[T]` is transparent to the type system otherwise — it propagates through `flow` steps like any other typed value.

**`HumanReviewContext`:**

```python
@dataclass
class HumanReviewContext:
    question: str
    trigger: str = "explicit"   # "explicit" | "debate_disagreement" | any string — extensible
    artifacts: dict[str, Any] = field(default_factory=dict)
```

`artifacts` is untyped in v1 — pass anything the reviewer needs to make a decision (debate history, retry trace, raw outputs). Typed artifact contracts are v2.

---

## Error Types

Built-in error types raised by the runtime:

| Error | Trigger |
|---|---|
| `PreconditionFailed` | `given` condition is false |
| `PostconditionFailed` | `ensure` condition false after all retries exhausted |
| `ParseFailure` | LLM output could not be parsed against contract schema |
| `BudgetExceeded` | Time or cost budget exceeded |
| `ConvergenceFailure` | `refine` hit `max_iterations` without satisfying `until` |
| `LowConfidence` | Custom — user-defined in `ensure` blocks |
| `HITLTimeoutError` | `await_human` wall-clock timeout exceeded; includes `review_id` for recovery |

User-defined error types:

```stratum
error AmbiguousClassification {
  candidates: string[]
  reason: string
}

infer classify(text: string) -> Category {
  ensure: result.confidence > 0.5 or raise AmbiguousClassification {
    candidates: result.alternatives,
    reason: "confidence below threshold"
  }
}
```

---

## Schema Compilation

Every `contract` compiles to a JSON Schema (draft 2020-12). This schema is:

1. Injected into the LLM prompt for `infer` blocks returning that type
2. Used by the runtime validator to check LLM output
3. Versioned — schema changes increment a content hash embedded in trace records

Every `contract` also gets a **content hash** generated at compile time. The hash is SHA-256 of the contract's compiled JSON Schema in canonical form (keys sorted, no whitespace), truncated to 12 hex characters:

```python
import hashlib, json

def contract_hash(json_schema: dict) -> str:
    canonical = json.dumps(json_schema, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
```

A field rename, type change, or constraint change produces a different JSON Schema → different hash. The hash covers all field names, types, and constraints. It is:
- Embedded in every trace record for that contract
- Used as the cache key for `global` scope caching
- A behavioral version signal — a hash change means the compiled prompt changed, and LLM behavior may differ

Schema compilation rules:

| Stratum type | JSON Schema |
|---|---|
| `string` | `{ "type": "string" }` |
| `string[1..500]` | `{ "type": "string", "minLength": 1, "maxLength": 500 }` |
| `float[0.0..1.0]` | `{ "type": "number", "minimum": 0.0, "maximum": 1.0 }` |
| `"a" \| "b" \| "c"` | `{ "enum": ["a", "b", "c"] }` |
| `T?` | `{ "anyOf": [schema(T), { "type": "null" }] }` |
| `T[]` | `{ "type": "array", "items": schema(T) }` |
| contract | `{ "type": "object", "properties": {...}, "required": [...] }` |

---

## Static Analysis

The static analyzer enforces:

- `infer` return types must be named contracts or primitives (no fully anonymous types)
- `ensure` expressions reference valid fields of the declared return type
- `given` expressions reference valid parameter names and types
- `flow` steps are sequentially typed — each `let` binding has a concrete type
- `refine` until/feedback expressions are `compute`-mode (no LLM calls inside convergence conditions)
- Budget annotations are syntactically valid and within platform limits
- `opaque[T]` fields referenced in inline string interpolations are a `StratumCompileError` — enforcement is structural, not a warning
