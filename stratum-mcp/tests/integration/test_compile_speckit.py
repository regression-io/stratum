"""Integration tests for the stratum_compile_speckit MCP tool."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from stratum_mcp.server import stratum_compile_speckit


def _write(tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / name).write_text(content)


MINIMAL = "# Task: Quick fix\n"
WITH_CRITERIA = (
    "# Task: Auth middleware\n\n"
    "## Acceptance Criteria\n\n"
    "- [ ] file src/auth.ts exists\n"
    "- [ ] tests pass\n"
)


@pytest.mark.asyncio
async def test_ok_returns_yaml_and_steps(tmp_path):
    _write(tmp_path, "01-task.md", WITH_CRITERIA)
    ctx = MagicMock()
    result = await stratum_compile_speckit(str(tmp_path), ctx)
    assert result["status"] == "ok"
    assert "version: '0.1'" in result["yaml"] or "version: \"0.1\"" in result["yaml"]
    assert len(result["steps"]) == 1
    assert result["steps"][0]["id"] == "t01_task"


@pytest.mark.asyncio
async def test_directory_not_found_returns_error(tmp_path):
    ctx = MagicMock()
    result = await stratum_compile_speckit(str(tmp_path / "nonexistent"), ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "directory_not_found"


@pytest.mark.asyncio
async def test_empty_directory_returns_error(tmp_path):
    ctx = MagicMock()
    result = await stratum_compile_speckit(str(tmp_path), ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "no_tasks"


@pytest.mark.asyncio
async def test_step_id_collision_returns_error(tmp_path):
    """P2 regression: MCP path must apply the same collision guard as compile_tasks()."""
    _write(tmp_path, "01-a.md", MINIMAL)
    _write(tmp_path, "01_a.md", MINIMAL)
    ctx = MagicMock()
    result = await stratum_compile_speckit(str(tmp_path), ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "step_id_collision"
    assert "01-a.md" in result["message"] or "01_a.md" in result["message"]


@pytest.mark.asyncio
async def test_flow_name_parameter(tmp_path):
    _write(tmp_path, "01-task.md", MINIMAL)
    ctx = MagicMock()
    result = await stratum_compile_speckit(str(tmp_path), ctx, flow_name="my_flow")
    assert result["status"] == "ok"
    assert result["flow_name"] == "my_flow"
    assert "my_flow" in result["yaml"]


@pytest.mark.asyncio
async def test_yaml_accepted_by_stratum_plan(tmp_path):
    """Compiled YAML must be parseable and executable via stratum_plan."""
    _write(tmp_path, "01-task.md", WITH_CRITERIA)
    ctx = MagicMock()
    result = await stratum_compile_speckit(str(tmp_path), ctx)
    assert result["status"] == "ok"

    from stratum_mcp.server import stratum_plan
    plan = await stratum_plan(result["yaml"], "tasks", {"project_context": "test"}, ctx)
    assert plan["status"] == "execute_step"
    assert plan["step_id"] == "t01_task"
