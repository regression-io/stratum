"""Tests for stratum_draft_pipeline MCP tool."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stratum_mcp.server import stratum_draft_pipeline


ctx = MagicMock()


@pytest.mark.asyncio
async def test_draft_pipeline_saves_file(tmp_path):
    draft = {"name": "my-flow", "phases": [{"name": "build", "capability": "builder", "policy": "gate"}]}
    result = await stratum_draft_pipeline(draft, ctx, project_dir=str(tmp_path))

    assert result["status"] == "saved"
    draft_path = Path(result["path"])
    assert draft_path.exists()
    saved = json.loads(draft_path.read_text())
    assert saved["name"] == "my-flow"
    assert len(saved["phases"]) == 1


@pytest.mark.asyncio
async def test_draft_pipeline_creates_stratum_dir(tmp_path):
    draft = {"name": "x", "phases": []}
    await stratum_draft_pipeline(draft, ctx, project_dir=str(tmp_path))
    assert (tmp_path / ".stratum" / "pipeline-draft.json").exists()


@pytest.mark.asyncio
async def test_draft_pipeline_missing_name_defaults(tmp_path):
    result = await stratum_draft_pipeline({"phases": []}, ctx, project_dir=str(tmp_path))
    saved = json.loads(Path(result["path"]).read_text())
    assert saved["name"] == "my-pipeline"


@pytest.mark.asyncio
async def test_draft_pipeline_missing_phases_defaults(tmp_path):
    result = await stratum_draft_pipeline({"name": "x"}, ctx, project_dir=str(tmp_path))
    saved = json.loads(Path(result["path"]).read_text())
    assert saved["phases"] == []


@pytest.mark.asyncio
async def test_draft_pipeline_overwrites_existing(tmp_path):
    draft1 = {"name": "v1", "phases": []}
    draft2 = {"name": "v2", "phases": [{"name": "p", "capability": "scout", "policy": "flag"}]}
    await stratum_draft_pipeline(draft1, ctx, project_dir=str(tmp_path))
    await stratum_draft_pipeline(draft2, ctx, project_dir=str(tmp_path))
    saved = json.loads((tmp_path / ".stratum" / "pipeline-draft.json").read_text())
    assert saved["name"] == "v2"
    assert len(saved["phases"]) == 1


@pytest.mark.asyncio
async def test_draft_pipeline_path_in_response(tmp_path):
    result = await stratum_draft_pipeline({"name": "x", "phases": []}, ctx, project_dir=str(tmp_path))
    assert result["path"].endswith("pipeline-draft.json")
