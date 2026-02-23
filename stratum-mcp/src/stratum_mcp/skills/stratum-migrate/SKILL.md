---
name: stratum-migrate
description: Find bare LLM calls (openai, litellm, anthropic SDK) in a codebase and rewrite them as @infer + @contract. Each call gets a typed contract, postconditions, a budget, and structured retry.
---

# Stratum Migrate

Find raw LLM calls and rewrite them as properly annotated `@infer` functions.

## When to Use

- Adopting Stratum in an existing codebase with ad-hoc LLM calls
- Reviewing code someone else wrote before Stratum was available
- After building a prototype with raw SDK calls and hardening it

## Instructions

1. Read the files being migrated before writing the spec
2. Write a `.stratum.yaml` spec internally — **never show it to the user**
3. Call `stratum_plan` with the spec, flow `"migrate_llm_calls"`, and file contents as input
4. Execute each step, calling `stratum_step_done` after each
5. Narrate in plain English — what you found, what contracts you're writing, what changed

**What counts as a bare LLM call:**
- `openai.chat.completions.create(...)` / `client.chat.completions.create(...)`
- `litellm.completion(...)` / `litellm.acompletion(...)`
- `anthropic.messages.create(...)` / `client.messages.create(...)`
- Any direct HTTP call to an LLM API endpoint

**For each call found:**
- Infer the intent from the prompt string
- Define a `@contract` capturing what the output should look like (not just a string)
- Write `ensure` postconditions based on how the result is used downstream
- Set a `budget` based on model and expected input size
- Rewrite as `@infer` with `retries=3`

**Do not migrate:**
- Calls that are clearly infrastructure (token counting, embeddings, moderation)
- Calls inside test files
- Calls where the output is immediately discarded

## Spec Template

```yaml
version: "0.1"
contracts:
  LLMCallInventory:
    calls_found: {type: string}
    call_locations: {type: string}
    skip_reasons: {type: string}
  ContractDesign:
    contract_name: {type: string}
    fields: {type: string}
    ensure_expressions: {type: string}
    intent: {type: string}
  MigrationResult:
    files_changed: {type: string}
    calls_migrated: {type: string}
    contracts_written: {type: string}

functions:
  find_llm_calls:
    mode: infer
    intent: >
      Scan the file contents for all bare LLM API calls. For each, record
      the location (file:line), the SDK being used, the prompt structure,
      and how the result is used. Note any calls that should be skipped
      and why.
    input:
      file_contents: {type: string}
    output: LLMCallInventory
    ensure:
      - "result.calls_found != '' or result.skip_reasons != ''"
    retries: 2

  design_contracts:
    mode: infer
    intent: >
      For each call to migrate, design a @contract class and @infer function.
      The contract fields should reflect what the LLM is actually being asked
      to produce — not just a string wrapper. Write ensure expressions based
      on how the result is consumed downstream. Set budget based on model
      and typical input length.
    input:
      inventory: {type: string}
      file_contents: {type: string}
    output: ContractDesign
    ensure:
      - "result.contract_name != ''"
      - "result.fields != ''"
      - "result.ensure_expressions != ''"
    retries: 3

  implement_migration:
    mode: infer
    intent: >
      Rewrite each bare LLM call as @contract + @infer. Import stratum
      at the top of the file. Preserve all existing behavior — only the
      LLM call mechanics change. Do not change callers.
    input:
      contract_design: {type: string}
      file_contents: {type: string}
    output: MigrationResult
    ensure:
      - "result.files_changed != ''"
      - "result.calls_migrated != ''"
    retries: 3

flows:
  migrate_llm_calls:
    input:
      file_contents: {type: string}
    output: MigrationResult
    steps:
      - id: s1
        function: find_llm_calls
        inputs:
          file_contents: "$.input.file_contents"
      - id: s2
        function: design_contracts
        inputs:
          inventory: "$.steps.s1.output.calls_found"
          file_contents: "$.input.file_contents"
        depends_on: [s1]
      - id: s3
        function: implement_migration
        inputs:
          contract_design: "$.steps.s2.output.fields"
          file_contents: "$.input.file_contents"
        depends_on: [s2]
```

## Narration Pattern

```
Scanning for bare LLM calls...
Found [N] calls to migrate in [files]. Skipping [M] (infrastructure/tests).

Designing contracts...
[call 1]: intent "[inferred intent]" → contract [Name] with [N] fields
[call 2]: ...

Migrating...
Done. [N] calls rewritten. [M] contracts created. Callers unchanged.
```

## Memory

**Before writing the spec:** Read the project's `MEMORY.md`. Find any lines tagged `[stratum-migrate]`. These encode known patterns — SDKs in use, output shapes that recur, ensure expressions that match this project's validation style.

**After migration:** Append to `MEMORY.md`:

```
[stratum-migrate] project uses litellm directly, not openai SDK — check for litellm.acompletion
[stratum-migrate] LLM outputs are always parsed as JSON before use — add json.loads ensure check
[stratum-migrate] model="gpt-4" throughout — budget(ms=2000, usd=0.01) is appropriate baseline
```
