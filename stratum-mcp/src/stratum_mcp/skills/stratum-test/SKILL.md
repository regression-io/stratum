---
name: stratum-test
description: Write a test suite for existing code that has no tests. Covers golden flows, error paths, and contract boundaries. Each phase is postcondition-checked.
---

# Stratum Test

Write tests for existing untested code using Stratum: analyze → identify cases → write → run.

## When to Use

- Existing module with no test coverage
- After a migration (`/stratum-migrate`) to verify behavior is preserved
- When `stratum_audit` shows a step consistently needs retries — write a targeted test for that behavior

## Instructions

1. Read the file being tested before writing the spec
2. Write a `.stratum.yaml` spec internally — **never show it to the user**
3. Call `stratum_plan` with the spec, flow `"write_tests"`, and file contents as input
4. Execute each step, calling `stratum_step_done` after each
5. Narrate in plain English — what behaviors you're covering, what edge cases matter

**Test strategy (follow `~/.claude/rules/testing.md`):**
- Prefer integration tests with real resources over mocks
- Golden flow first: the happy path that exercises the full behavior
- Error-path harness: table-driven tests for validation errors, not-found, permission denied, timeouts
- Unit tests only when they reduce integration test count (parsing, invariants, rounding logic)
- Do not test implementation details — test observable behavior

**The `write` step's ensure requires `result.failures == "" or result.failures == "none"`** — tests must pass before the step is accepted.

## Spec Template

```yaml
version: "0.1"
contracts:
  BehaviorMap:
    golden_flows: {type: string}
    error_paths: {type: string}
    edge_cases: {type: string}
    skip_reasons: {type: string}
  TestPlan:
    test_cases: {type: string}
    test_file: {type: string}
    approach: {type: string}
  TestResult:
    test_file: {type: string}
    test_count: {type: string}
    failures: {type: string}

functions:
  analyze_behavior:
    mode: infer
    intent: >
      Read the code and identify what behaviors need testing.
      List: golden flows (happy path through the full function/class),
      error paths (what inputs cause specific failures), and edge cases
      (boundary values, empty inputs, concurrent calls).
      Note anything that should NOT be tested (internal implementation details).
    input:
      file_contents: {type: string}
    output: BehaviorMap
    ensure:
      - "result.golden_flows != ''"
      - "result.error_paths != ''"
    retries: 2

  plan_tests:
    mode: infer
    intent: >
      Design the test suite. For each golden flow write one integration test.
      For error paths write a single table-driven harness.
      Add unit tests only for parsing, invariants, or math logic.
      Name the test file following project conventions.
      List each test case with its assertion.
    input:
      behavior_map: {type: string}
      file_contents: {type: string}
    output: TestPlan
    ensure:
      - "result.test_cases != ''"
      - "result.test_file != ''"
    retries: 2

  write_and_run:
    mode: infer
    intent: >
      Write the tests and run them. All tests must pass.
      Use real resources where possible — avoid mocking internals.
      Record the test file path, count, and any failures.
    input:
      test_plan: {type: string}
      file_contents: {type: string}
    output: TestResult
    ensure:
      - "result.test_file != ''"
      - "int(result.test_count) >= 1"
      - "result.failures == '' or result.failures == 'none'"
    retries: 3

flows:
  write_tests:
    input:
      file_contents: {type: string}
    output: TestResult
    steps:
      - id: s1
        function: analyze_behavior
        inputs:
          file_contents: "$.input.file_contents"
      - id: s2
        function: plan_tests
        inputs:
          behavior_map: "$.steps.s1.output.golden_flows"
          file_contents: "$.input.file_contents"
        depends_on: [s1]
      - id: s3
        function: write_and_run
        inputs:
          test_plan: "$.steps.s2.output.test_cases"
          file_contents: "$.input.file_contents"
        depends_on: [s2]
```

## Narration Pattern

```
Reading the code...
Identifying behaviors: [N] golden flows, [M] error paths, [K] edge cases.

Planning tests...
[test 1]: [what it covers]
[test 2]: ...

Writing and running...
Done. [N] tests in [file], all passing.
```

## Memory

**Before writing the spec:** Read the project's `MEMORY.md`. Find any lines tagged `[stratum-test]`. These encode project-specific test conventions — fixture patterns, real vs. mock resource decisions, naming conventions.

**After `stratum_audit`:** If any step needed retries, append to `MEMORY.md`:

```
[stratum-test] project uses factory_boy fixtures, not pytest fixtures — match this pattern
[stratum-test] database tests require explicit transaction rollback — add to fixture setup
[stratum-test] async tests need @pytest.mark.asyncio — already configured in pytest.ini
[stratum-test] golden flow for executor requires litellm mock with {"value": {...}} wrapper
```
