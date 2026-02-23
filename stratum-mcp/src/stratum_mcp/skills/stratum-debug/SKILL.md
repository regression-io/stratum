---
name: stratum-debug
description: Debug a failing test or unexpected behavior using the Stratum MCP server — structured hypothesis formation and elimination, targeted fix. Never guess.
---

# Stratum Debug

Debug a failure using Stratum: read → analyze → hypothesize → test → fix.

## Instructions

1. Get the failure details — test name, error message, "fails in CI but not locally" if applicable
2. Read the failing test and relevant source files before writing the spec
3. Write a `.stratum.yaml` spec internally — **never show it to the user**
4. Call `stratum_plan` with the spec, flow `"debug_failure"`, and inputs containing file contents
5. Execute each step, calling `stratum_step_done` after each
6. Narrate in plain English — what you're reading, what you found, what you're testing

**Critical postconditions:**
- Hypothesis step: `result.ci_discrepancy_addressed` must be non-empty if failure is local-vs-CI
- Diagnosis step: `result.confirmed` must be non-empty AND `result.ruled_out` must be non-empty — you cannot claim a fix without eliminating the alternatives
- Fix step: **Do not change the test assertion** unless the test is provably wrong about expected behavior

## Spec Template

```yaml
version: "0.1"
contracts:
  TestSpec:
    what_it_tests: {type: string}
    expectation: {type: string}
    mock_setup: {type: string}
  CodeAnalysis:
    enforcement_points: {type: string}
    relevant_behavior: {type: string}
  EnvironmentAnalysis:
    differences: {type: string}
  HypothesisList:
    hypotheses: {type: string}
    ci_discrepancy_addressed: {type: string}
  DiagnosisReport:
    confirmed: {type: string}
    evidence: {type: string}
    code_location: {type: string}
    ruled_out: {type: string}
  FixResult:
    files_changed: {type: string}
    explanation: {type: string}

functions:
  read_failing_test:
    mode: infer
    intent: >
      Read the failing test. Understand exactly what it tests, what it expects,
      and how it mocks or sets up its environment.
    input:
      test_content: {type: string}
    output: TestSpec
    ensure:
      - "result.expectation != ''"
    retries: 2

  read_relevant_code:
    mode: infer
    intent: >
      Read the source code being tested. Find every enforcement point relevant
      to the test's expectation. Note any behavior that could differ by environment.
    input:
      source_content: {type: string}
      test_spec: {type: string}
    output: CodeAnalysis
    ensure:
      - "result.enforcement_points != ''"
    retries: 2

  check_environment:
    mode: infer
    intent: >
      Read the CI configuration. Check Python version, OS, env vars, test
      isolation, timing assumptions, and anything else that differs from local.
    input:
      ci_config: {type: string}
    output: EnvironmentAnalysis
    retries: 2

  form_hypotheses:
    mode: infer
    intent: >
      List candidate root causes ranked by likelihood.
      If the failure is local-vs-CI, at least one hypothesis must specifically
      explain the environmental discrepancy.
    input:
      test_spec: {type: string}
      code_analysis: {type: string}
      environment: {type: string}
    output: HypothesisList
    ensure:
      - "result.hypotheses != ''"
      - "result.ci_discrepancy_addressed != ''"
    retries: 3

  test_hypotheses:
    mode: infer
    intent: >
      Evaluate each hypothesis against the evidence. For each: identify the
      specific code path, check whether it explains the failure, rule in or out.
      Exactly one hypothesis should be confirmed. All others must be explicitly
      ruled out with reasoning.
    input:
      hypotheses: {type: string}
      code_analysis: {type: string}
    output: DiagnosisReport
    ensure:
      - "result.confirmed != ''"
      - "result.ruled_out != ''"
      - "result.code_location != ''"
    retries: 3

  implement_fix:
    mode: infer
    intent: >
      Fix the confirmed root cause at the identified code location.
      Do not change the test assertion unless it is provably wrong about
      expected behavior — fix the code, not the test.
    input:
      diagnosis: {type: string}
      code_location: {type: string}
      source_content: {type: string}
    output: FixResult
    ensure:
      - "result.files_changed != ''"
      - "result.explanation != ''"
    retries: 3

flows:
  debug_failure:
    input:
      test_content: {type: string}
      source_content: {type: string}
      ci_config: {type: string}
    output: FixResult
    steps:
      - id: s1
        function: read_failing_test
        inputs:
          test_content: "$.input.test_content"
      - id: s2
        function: read_relevant_code
        inputs:
          source_content: "$.input.source_content"
          test_spec: "$.steps.s1.output.expectation"
        depends_on: [s1]
      - id: s3
        function: check_environment
        inputs:
          ci_config: "$.input.ci_config"
        depends_on: [s1]
      - id: s4
        function: form_hypotheses
        inputs:
          test_spec: "$.steps.s1.output.expectation"
          code_analysis: "$.steps.s2.output.enforcement_points"
          environment: "$.steps.s3.output.differences"
        depends_on: [s2, s3]
      - id: s5
        function: test_hypotheses
        inputs:
          hypotheses: "$.steps.s4.output.hypotheses"
          code_analysis: "$.steps.s2.output.relevant_behavior"
        depends_on: [s4]
      - id: s6
        function: implement_fix
        inputs:
          diagnosis: "$.steps.s5.output.confirmed"
          code_location: "$.steps.s5.output.code_location"
          source_content: "$.input.source_content"
        depends_on: [s5]
```

## Narration Pattern

```
Reading the test...
Reading the source code...
Checking CI environment...
Forming hypotheses...
Testing hypotheses — [confirmed hypothesis in plain English]
Fixing...

Root cause: [plain English]
Fix: [what changed]
```
