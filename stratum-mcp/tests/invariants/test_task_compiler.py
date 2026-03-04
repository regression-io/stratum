"""Invariant tests for the spec-kit task→step compiler (T3-2)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from stratum_mcp.task_compiler import (
    ParsedTask,
    build_dependency_graph,
    build_yaml,
    compile_tasks,
    criterion_to_ensure,
    parse_task_file,
    step_id_from_stem,
)


# ---------------------------------------------------------------------------
# criterion_to_ensure — pattern matching
# ---------------------------------------------------------------------------

class TestCriterionToEnsure:
    def test_file_exists(self):
        assert criterion_to_ensure("file src/foo.ts exists") == 'file_exists("src/foo.ts")'

    def test_file_exist_singular(self):
        assert criterion_to_ensure("file src/bar.py exist") == 'file_exists("src/bar.py")'

    def test_file_exists_case_insensitive(self):
        assert criterion_to_ensure("File src/Foo.ts Exists") == 'file_exists("src/Foo.ts")'

    def test_file_contains_unquoted(self):
        assert criterion_to_ensure("file src/foo.ts contains verifyJwt") == 'file_contains("src/foo.ts", "verifyJwt")'

    def test_file_contains_double_quoted(self):
        assert criterion_to_ensure('file src/foo.ts contains "some string"') == 'file_contains("src/foo.ts", "some string")'

    def test_file_contains_single_quoted(self):
        assert criterion_to_ensure("file src/foo.ts contains 'hello world'") == 'file_contains("src/foo.ts", "hello world")'

    def test_file_contains_escapes_inner_quotes(self):
        result = criterion_to_ensure('file src/x.ts contains with"quotes')
        assert 'with\\"quotes' in result

    def test_tests_pass(self):
        assert criterion_to_ensure("tests pass") == "result.tests_pass == True"

    def test_all_tests_pass(self):
        assert criterion_to_ensure("all tests pass") == "result.tests_pass == True"

    def test_test_passes(self):
        assert criterion_to_ensure("test passes") == "result.tests_pass == True"

    def test_no_lint_errors(self):
        assert criterion_to_ensure("no lint errors") == "result.lint_clean == True"

    def test_lint_passes(self):
        assert criterion_to_ensure("lint passes") == "result.lint_clean == True"

    def test_lint_clean(self):
        assert criterion_to_ensure("lint clean") == "result.lint_clean == True"

    def test_freeform_returns_none(self):
        assert criterion_to_ensure("Middleware correctly rejects expired tokens") is None

    def test_empty_returns_none(self):
        assert criterion_to_ensure("") is None

    def test_whitespace_only_returns_none(self):
        assert criterion_to_ensure("   ") is None


# ---------------------------------------------------------------------------
# step_id_from_stem
# ---------------------------------------------------------------------------

class TestStepIdFromStem:
    def test_numeric_prefix(self):
        assert step_id_from_stem("01-research") == "t01_research"

    def test_alphanumeric_prefix(self):
        assert step_id_from_stem("02a-backend") == "t02a_backend"

    def test_no_prefix(self):
        assert step_id_from_stem("research") == "research"

    def test_underscores_preserved(self):
        assert step_id_from_stem("my_task") == "my_task"

    def test_spaces_become_underscores(self):
        assert step_id_from_stem("my task") == "my_task"

    def test_uppercase_lowercased(self):
        assert step_id_from_stem("MyTask") == "mytask"

    def test_empty_stem(self):
        assert step_id_from_stem("") == "task"


# ---------------------------------------------------------------------------
# parse_task_file
# ---------------------------------------------------------------------------

SIMPLE_TASK_MD = textwrap.dedent("""\
    # Task: Implement authentication middleware

    Add JWT authentication middleware to all API routes.

    ## Acceptance Criteria

    - [ ] file src/middleware/auth.ts exists
    - [ ] file src/middleware/auth.ts contains verifyJwt
    - [ ] tests pass
    - [ ] no lint errors
    - [ ] Middleware correctly rejects expired tokens
""")

PARALLEL_TASK_MD = textwrap.dedent("""\
    # Task: [P] Write frontend components

    Build the login form.

    ## Acceptance Criteria

    - [ ] file src/components/Login.tsx exists
""")

MINIMAL_TASK_MD = textwrap.dedent("""\
    # Task: Quick fix
""")


def _write_task(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content)
    return p


class TestParseTaskFile:
    def test_title_extracted(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        task = parse_task_file(p)
        assert task.title == "Implement authentication middleware"

    def test_description_extracted(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        task = parse_task_file(p)
        assert "JWT authentication" in task.description

    def test_not_parallel(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        assert not parse_task_file(p).is_parallel

    def test_parallel_marker_detected(self, tmp_path):
        p = _write_task(tmp_path, "02a-frontend.md", PARALLEL_TASK_MD)
        task = parse_task_file(p)
        assert task.is_parallel
        assert "[P]" not in task.title

    def test_ensures_compiled(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        task = parse_task_file(p)
        assert 'file_exists("src/middleware/auth.ts")' in task.ensures
        assert 'file_contains("src/middleware/auth.ts", "verifyJwt")' in task.ensures
        assert "result.tests_pass == True" in task.ensures
        assert "result.lint_clean == True" in task.ensures

    def test_judgment_criterion_not_in_ensures(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        task = parse_task_file(p)
        assert "Middleware correctly rejects expired tokens" in task.judgment
        # Should NOT be in ensures (no matching pattern)
        for e in task.ensures:
            assert "expired" not in e

    def test_needs_tests_pass_flag(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        assert parse_task_file(p).needs_tests_pass is True

    def test_needs_lint_clean_flag(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        assert parse_task_file(p).needs_lint_clean is True

    def test_step_id_from_filename(self, tmp_path):
        p = _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        assert parse_task_file(p).step_id == "t01_auth"

    def test_minimal_task_no_criteria(self, tmp_path):
        p = _write_task(tmp_path, "quick.md", MINIMAL_TASK_MD)
        task = parse_task_file(p)
        assert task.title == "Quick fix"
        assert task.ensures == []
        assert task.judgment == []
        assert not task.needs_tests_pass
        assert not task.needs_lint_clean

    def test_checked_checkbox_included(self, tmp_path):
        """Checked [x] criteria are compiled the same as unchecked [ ] criteria."""
        md = "# Task: Done\n\n## Acceptance Criteria\n\n- [x] file out.txt exists\n"
        p = _write_task(tmp_path, "done.md", md)
        task = parse_task_file(p)
        assert 'file_exists("out.txt")' in task.ensures


# ---------------------------------------------------------------------------
# build_dependency_graph
# ---------------------------------------------------------------------------

def _make_task(step_id: str, is_parallel: bool = False) -> ParsedTask:
    return ParsedTask(
        filename=f"{step_id}.md",
        step_id=step_id,
        func_name=step_id,
        title=step_id,
        description="",
        is_parallel=is_parallel,
        ensures=[],
        judgment=[],
        needs_tests_pass=False,
        needs_lint_clean=False,
    )


class TestBuildDependencyGraph:
    def test_single_sequential(self):
        tasks = [_make_task("t1")]
        deps = build_dependency_graph(tasks)
        assert deps["t1"] == []

    def test_two_sequential(self):
        tasks = [_make_task("t1"), _make_task("t2")]
        deps = build_dependency_graph(tasks)
        assert deps["t1"] == []
        assert deps["t2"] == ["t1"]

    def test_parallel_pair(self):
        tasks = [
            _make_task("t1"),            # sequential
            _make_task("t2a", True),     # parallel
            _make_task("t2b", True),     # parallel
        ]
        deps = build_dependency_graph(tasks)
        assert deps["t1"] == []
        assert deps["t2a"] == ["t1"]
        assert deps["t2b"] == ["t1"]

    def test_sequential_after_parallel(self):
        tasks = [
            _make_task("t1"),
            _make_task("t2a", True),
            _make_task("t2b", True),
            _make_task("t3"),
        ]
        deps = build_dependency_graph(tasks)
        assert deps["t3"] == ["t2a", "t2b"]

    def test_parallel_at_start(self):
        tasks = [
            _make_task("t1a", True),
            _make_task("t1b", True),
        ]
        deps = build_dependency_graph(tasks)
        assert deps["t1a"] == []
        assert deps["t1b"] == []

    def test_chain_after_parallel(self):
        tasks = [
            _make_task("t1"),
            _make_task("t2a", True),
            _make_task("t2b", True),
            _make_task("t3"),
            _make_task("t4"),
        ]
        deps = build_dependency_graph(tasks)
        assert deps["t3"] == ["t2a", "t2b"]
        assert deps["t4"] == ["t3"]


# ---------------------------------------------------------------------------
# build_yaml / compile_tasks — structural correctness
# ---------------------------------------------------------------------------

class TestBuildYaml:
    def test_valid_yaml(self, tmp_path):
        _write_task(tmp_path, "01-task.md", SIMPLE_TASK_MD)
        result = compile_tasks(tmp_path)
        doc = yaml.safe_load(result)
        assert doc["version"] == "0.1"

    def test_contract_always_present(self, tmp_path):
        _write_task(tmp_path, "01-task.md", MINIMAL_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        assert "TaskResult" in doc["contracts"]
        assert "done" in doc["contracts"]["TaskResult"]

    def test_function_generated(self, tmp_path):
        _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        assert "t01_auth" in doc["functions"]
        fn = doc["functions"]["t01_auth"]
        assert fn["mode"] == "compute"
        assert fn["output"] == "TaskResult"
        assert "result.done == True" in fn["ensure"]

    def test_step_generated(self, tmp_path):
        _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        steps = doc["flows"]["tasks"]["steps"]
        assert len(steps) == 1
        assert steps[0]["id"] == "t01_auth"
        assert steps[0]["function"] == "t01_auth"

    def test_output_schema_done_required(self, tmp_path):
        _write_task(tmp_path, "01-task.md", MINIMAL_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        schema = doc["flows"]["tasks"]["steps"][0]["output_schema"]
        assert "done" in schema["required"]
        assert schema["properties"]["done"] == {"type": "boolean"}

    def test_output_schema_tests_pass_added(self, tmp_path):
        _write_task(tmp_path, "01-task.md", SIMPLE_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        schema = doc["flows"]["tasks"]["steps"][0]["output_schema"]
        assert "tests_pass" in schema["required"]
        assert schema["properties"]["tests_pass"] == {"type": "boolean"}

    def test_output_schema_lint_clean_added(self, tmp_path):
        _write_task(tmp_path, "01-task.md", SIMPLE_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        schema = doc["flows"]["tasks"]["steps"][0]["output_schema"]
        assert "lint_clean" in schema["required"]

    def test_parallel_produces_no_cross_deps(self, tmp_path):
        _write_task(tmp_path, "01-seq.md", MINIMAL_TASK_MD)
        _write_task(tmp_path, "02a-par.md", "# Task: [P] Par A\n")
        _write_task(tmp_path, "02b-par.md", "# Task: [P] Par B\n")
        doc = yaml.safe_load(compile_tasks(tmp_path))
        steps = {s["id"]: s for s in doc["flows"]["tasks"]["steps"]}
        # Both parallel tasks depend only on the sequential task
        assert steps["t02a_par"].get("depends_on") == ["t01_seq"]
        assert steps["t02b_par"].get("depends_on") == ["t01_seq"]
        # They don't depend on each other
        assert "t02a_par" not in steps["t02b_par"].get("depends_on", [])

    def test_sequential_after_parallel_depends_on_both(self, tmp_path):
        _write_task(tmp_path, "01-seq.md", MINIMAL_TASK_MD)
        _write_task(tmp_path, "02a-par.md", "# Task: [P] Par A\n")
        _write_task(tmp_path, "02b-par.md", "# Task: [P] Par B\n")
        _write_task(tmp_path, "03-final.md", "# Task: Final\n")
        doc = yaml.safe_load(compile_tasks(tmp_path))
        steps = {s["id"]: s for s in doc["flows"]["tasks"]["steps"]}
        assert set(steps["t03_final"]["depends_on"]) == {"t02a_par", "t02b_par"}

    def test_flow_name_parameter(self, tmp_path):
        _write_task(tmp_path, "01-task.md", MINIMAL_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path, flow_name="my_flow"))
        assert "my_flow" in doc["flows"]

    def test_judgment_in_intent(self, tmp_path):
        _write_task(tmp_path, "01-auth.md", SIMPLE_TASK_MD)
        doc = yaml.safe_load(compile_tasks(tmp_path))
        intent = doc["functions"]["t01_auth"]["intent"]
        assert "expired tokens" in intent

    def test_no_task_files_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No task files"):
            compile_tasks(tmp_path)

    def test_result_parseable_by_stratum(self, tmp_path):
        """Compiled YAML must be accepted by stratum parse_and_validate."""
        _write_task(tmp_path, "01-task.md", SIMPLE_TASK_MD)
        from stratum_mcp.spec import parse_and_validate
        yaml_str = compile_tasks(tmp_path)
        spec = parse_and_validate(yaml_str)
        assert "tasks" in spec.flows

    def test_step_id_collision_raises(self, tmp_path):
        """P2 regression: '01-a.md' and '01_a.md' both normalize to 't01_a'; must error."""
        _write_task(tmp_path, "01-a.md", MINIMAL_TASK_MD)
        _write_task(tmp_path, "01_a.md", MINIMAL_TASK_MD)
        with pytest.raises(ValueError, match="Step ID collision"):
            compile_tasks(tmp_path)

    def test_step_id_collision_names_both_files(self, tmp_path):
        """Error message must identify both colliding filenames."""
        _write_task(tmp_path, "01-a.md", MINIMAL_TASK_MD)
        _write_task(tmp_path, "01_a.md", MINIMAL_TASK_MD)
        with pytest.raises(ValueError, match="01-a.md") as exc_info:
            compile_tasks(tmp_path)
        assert "01_a.md" in str(exc_info.value)

    def test_no_collision_for_distinct_stems(self, tmp_path):
        """Files with distinct stems after normalization must compile without error."""
        _write_task(tmp_path, "01-alpha.md", MINIMAL_TASK_MD)
        _write_task(tmp_path, "01-beta.md", MINIMAL_TASK_MD)
        # Should not raise
        result = compile_tasks(tmp_path)
        assert result
