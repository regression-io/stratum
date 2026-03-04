"""Task→step compiler for the spec-kit bridge (T3-2).

Reads tasks/*.md files and produces a .stratum.yaml flow where:
  - Each task file becomes one step + one function
  - Acceptance criteria → ensure expressions (where pattern-matchable)
  - [P] in task title → parallel tasks with shared predecessor, no deps between them
  - Sequential tasks → depends_on the prior task(s)
  - Output schema always requires {done: boolean}
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Parsed task representation
# ---------------------------------------------------------------------------

@dataclass
class ParsedTask:
    """Internal representation of one parsed task file."""

    filename: str           # original filename (for ordering)
    step_id: str            # sanitized step identifier (e.g. "t01_research")
    func_name: str          # function name (same as step_id)
    title: str              # task title, [P] stripped
    description: str        # body text before ## Acceptance Criteria
    is_parallel: bool       # True if [P] marker found in title
    ensures: list[str]      # compiled Python ensure expressions
    judgment: list[str]     # freeform criteria — incorporated into intent
    needs_tests_pass: bool  # True if any criterion matched "tests pass"
    needs_lint_clean: bool  # True if any criterion matched "no lint errors"


# ---------------------------------------------------------------------------
# Criterion → ensure expression compiler
# ---------------------------------------------------------------------------

# "file some/path.ts exists"
_FILE_EXISTS_RE = re.compile(r"^file\s+(\S+)\s+exists?$", re.IGNORECASE)

# "file some/path.ts contains some_string"
# "file some/path.ts contains "some string""
# "file some/path.ts contains 'some string'"
_FILE_CONTAINS_RE = re.compile(
    r'^file\s+(\S+)\s+contains?\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))$',
    re.IGNORECASE,
)

# "tests pass", "all tests pass", "tests are passing"
_TESTS_PASS_RE = re.compile(r"\btests?\b.*\bpass", re.IGNORECASE)

# "no lint errors", "lint passes", "lint clean"
_LINT_RE = re.compile(r"(no lint errors?|lint (passes?|clean))", re.IGNORECASE)


def criterion_to_ensure(text: str) -> str | None:
    """
    Convert a natural-language acceptance criterion to an ensure expression.

    Returns None if the criterion is freeform (cannot be machine-evaluated).

    Supported patterns:
      "file X exists"       → file_exists("X")
      "file X contains Y"   → file_contains("X", "Y")
      "tests pass"          → result.tests_pass == True
      "no lint errors"      → result.lint_clean == True
      <anything else>       → None (freeform, goes into intent)
    """
    t = text.strip()

    m = _FILE_EXISTS_RE.match(t)
    if m:
        path = m.group(1)
        return f'file_exists("{path}")'

    m = _FILE_CONTAINS_RE.match(t)
    if m:
        path = m.group(1)
        substring = m.group(2) or m.group(3) or m.group(4)
        # Escape any embedded double-quotes
        substring = substring.replace('"', '\\"')
        return f'file_contains("{path}", "{substring}")'

    if _TESTS_PASS_RE.search(t):
        return "result.tests_pass == True"

    if _LINT_RE.search(t):
        return "result.lint_clean == True"

    return None


# ---------------------------------------------------------------------------
# Step ID helper
# ---------------------------------------------------------------------------

def step_id_from_stem(stem: str) -> str:
    """
    Convert a task filename stem to a safe step identifier.

    "01-research"  → "t01_research"
    "02a-backend"  → "t02a_backend"
    "my_task"      → "my_task"
    "research"     → "research"
    """
    slug = re.sub(r"[^a-z0-9]", "_", stem.lower()).strip("_")
    # Step IDs must start with a letter
    if slug and not slug[0].isalpha():
        slug = "t" + slug
    return slug or "task"


# ---------------------------------------------------------------------------
# Task file parser
# ---------------------------------------------------------------------------

def parse_task_file(path: Path) -> ParsedTask:
    """Parse a spec-kit task markdown file into a ParsedTask.

    Expected format::

        # Task: [P] Title goes here

        Optional body text describing the task.

        ## Acceptance Criteria

        - [ ] file src/foo.ts exists
        - [ ] tests pass
        - [ ] Freeform judgment criterion

    ``[P]`` anywhere in the title marks the task as parallel.
    Criteria under ``## Acceptance Criteria`` are compiled where possible.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- Extract title ---
    title_raw = ""
    title_line_idx = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            # Strip heading markers and optional "Task:" prefix
            title_raw = re.sub(r"^#+\s*(?:Task:\s*)?", "", line.strip())
            title_line_idx = i
            break

    is_parallel = bool(re.search(r"\[P\]", title_raw, re.IGNORECASE))
    title = re.sub(r"\s*\[P\]\s*", " ", title_raw, flags=re.IGNORECASE).strip()

    step_id = step_id_from_stem(path.stem)

    # --- Locate "## Acceptance Criteria" section ---
    criteria_start = None
    for i, line in enumerate(lines):
        if re.match(r"^#+\s*Acceptance Criteria", line, re.IGNORECASE):
            criteria_start = i
            break

    # --- Body: everything between title and criteria header ---
    body_start = title_line_idx + 1
    body_end = criteria_start if criteria_start is not None else len(lines)
    description = "\n".join(lines[body_start:body_end]).strip()

    # --- Parse acceptance criteria checkboxes ---
    raw_criteria: list[str] = []
    if criteria_start is not None:
        for line in lines[criteria_start + 1:]:
            m = re.match(r"^\s*-\s*\[[ xX]\]\s*(.+)", line)
            if m:
                raw_criteria.append(m.group(1).strip())

    # --- Compile criteria → ensures / judgment ---
    ensures: list[str] = []
    judgment: list[str] = []
    needs_tests_pass = False
    needs_lint_clean = False

    for criterion in raw_criteria:
        expr = criterion_to_ensure(criterion)
        if expr is not None:
            ensures.append(expr)
            if "tests_pass" in expr:
                needs_tests_pass = True
            if "lint_clean" in expr:
                needs_lint_clean = True
        else:
            judgment.append(criterion)

    return ParsedTask(
        filename=path.name,
        step_id=step_id,
        func_name=step_id,
        title=title,
        description=description,
        is_parallel=is_parallel,
        ensures=ensures,
        judgment=judgment,
        needs_tests_pass=needs_tests_pass,
        needs_lint_clean=needs_lint_clean,
    )


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

def build_dependency_graph(tasks: list[ParsedTask]) -> dict[str, list[str]]:
    """
    Build a ``depends_on`` mapping for each task.

    Rules:
    - Sequential tasks (no [P]): depend on the most recent parallel group
      (all tasks in it) if one exists, or the last sequential task, or nothing.
    - Parallel tasks ([P]): all share the same predecessor (the last sequential
      task), forming a group with no edges between them.

    Example::

        T1 (seq)   → []
        T2a (par)  → [T1]
        T2b (par)  → [T1]
        T3  (seq)  → [T2a, T2b]
        T4  (seq)  → [T3]
    """
    deps: dict[str, list[str]] = {}
    last_sequential: str | None = None
    current_parallel_group: list[str] = []

    for task in tasks:
        if task.is_parallel:
            # All parallel tasks in a group share the same predecessor
            dep: list[str] = [last_sequential] if last_sequential else []
            deps[task.step_id] = dep
            current_parallel_group.append(task.step_id)
        else:
            # Sequential: depends on the whole parallel group, or last sequential
            if current_parallel_group:
                dep = list(current_parallel_group)
                current_parallel_group = []
            elif last_sequential:
                dep = [last_sequential]
            else:
                dep = []
            deps[task.step_id] = dep
            last_sequential = task.step_id

    return deps


# ---------------------------------------------------------------------------
# YAML generator
# ---------------------------------------------------------------------------

def build_yaml(tasks: list[ParsedTask], flow_name: str = "tasks") -> str:
    """
    Build a .stratum.yaml document from a list of parsed tasks.

    Each task becomes one function + one step. The shared output contract is
    ``TaskResult`` with ``done: boolean`` required. Steps with ``tests_pass``
    or ``lint_clean`` ensures get matching fields added to their ``output_schema``.
    """
    deps = build_dependency_graph(tasks)

    doc: dict[str, Any] = {
        "version": "0.1",
        "contracts": {
            "TaskResult": {
                "done": {"type": "boolean"},
            }
        },
        "functions": {},
        "flows": {
            flow_name: {
                "input": {"project_context": {"type": "string"}},
                "output": "TaskResult",
                "steps": [],
            }
        },
    }

    flow_steps: list[dict] = []

    for task in tasks:
        # Build intent: title + description + judgment criteria
        intent_parts = [task.title]
        if task.description:
            intent_parts.append(task.description)
        if task.judgment:
            intent_parts.append("Also verify: " + "; ".join(task.judgment))
        intent = "\n".join(intent_parts)

        # Ensures: machine-evaluable criteria + mandatory done check
        all_ensures = list(task.ensures) + ["result.done == True"]

        doc["functions"][task.func_name] = {
            "mode": "compute",
            "intent": intent,
            "input": {"task_context": {"type": "string"}},
            "output": "TaskResult",
            "ensure": all_ensures,
            "retries": 2,
        }

        # Per-step output_schema — extends TaskResult with optional fields
        required = ["done"]
        properties: dict[str, Any] = {"done": {"type": "boolean"}}
        if task.needs_tests_pass:
            required.append("tests_pass")
            properties["tests_pass"] = {"type": "boolean"}
        if task.needs_lint_clean:
            required.append("lint_clean")
            properties["lint_clean"] = {"type": "boolean"}

        step_entry: dict[str, Any] = {
            "id": task.step_id,
            "function": task.func_name,
            "inputs": {"task_context": "$.input.project_context"},
            "output_schema": {
                "type": "object",
                "required": required,
                "properties": properties,
            },
        }

        step_deps = deps.get(task.step_id, [])
        if step_deps:
            step_entry["depends_on"] = step_deps

        flow_steps.append(step_entry)

    doc["flows"][flow_name]["steps"] = flow_steps
    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compile_tasks(tasks_dir: Path, flow_name: str = "tasks") -> str:
    """
    Compile all task files in ``tasks_dir`` into a .stratum.yaml string.

    Task files are discovered by ``*.md`` glob and sorted alphabetically
    (alphanumeric ordering mirrors typical ``01-``, ``02a-`` naming).

    Raises ``ValueError`` if no task files are found.
    """
    task_files = sorted(tasks_dir.glob("*.md"))
    if not task_files:
        raise ValueError(f"No task files (*.md) found in {tasks_dir}")

    tasks = [parse_task_file(f) for f in task_files]

    # Guard against step ID collisions from filename normalization.
    # e.g. "01-a.md" and "01_a.md" both normalize to "t01_a".
    seen: dict[str, str] = {}  # step_id → first filename that claimed it
    for task in tasks:
        if task.step_id in seen:
            raise ValueError(
                f"Step ID collision: '{task.step_id}' from '{task.filename}' "
                f"conflicts with '{seen[task.step_id]}'. "
                f"Rename one of the files to produce a distinct step ID."
            )
        seen[task.step_id] = task.filename

    return build_yaml(tasks, flow_name)
