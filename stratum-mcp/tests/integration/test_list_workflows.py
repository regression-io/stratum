"""Tests for stratum_list_workflows MCP tool."""
import asyncio
import textwrap
from pathlib import Path

import pytest

from stratum_mcp.server import stratum_list_workflows


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


_WORKFLOW_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Do it"
        input: {}
        output: Out
    workflow:
      name: build
      description: "Build the thing"
      input:
        feature: {type: string}
    flows:
      build:
        input: {feature: {type: string}}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
""")

_INTERNAL_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Do it"
        input: {}
        output: Out
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
""")


def test_list_workflows_finds_workflow_specs(tmp_path: Path):
    (tmp_path / "build.stratum.yaml").write_text(_WORKFLOW_SPEC)
    result = _run(stratum_list_workflows(str(tmp_path)))
    assert len(result["workflows"]) == 1
    wf = result["workflows"][0]
    assert wf["name"] == "build"
    assert wf["description"] == "Build the thing"
    assert "feature" in wf["input"]
    assert wf["path"] == str(tmp_path / "build.stratum.yaml")
    assert result["errors"] == []


def test_list_workflows_skips_internal_specs(tmp_path: Path):
    (tmp_path / "internal.stratum.yaml").write_text(_INTERNAL_SPEC)
    result = _run(stratum_list_workflows(str(tmp_path)))
    assert len(result["workflows"]) == 0
    assert result["errors"] == []


def test_list_workflows_skips_invalid_specs(tmp_path: Path):
    (tmp_path / "bad.stratum.yaml").write_text("not: valid: yaml: {{")
    result = _run(stratum_list_workflows(str(tmp_path)))
    assert len(result["workflows"]) == 0
    assert len(result["errors"]) == 1
    assert "bad.stratum.yaml" in result["errors"][0]


def test_list_workflows_detects_duplicate_names(tmp_path: Path):
    (tmp_path / "a-build.stratum.yaml").write_text(_WORKFLOW_SPEC)
    (tmp_path / "b-build.stratum.yaml").write_text(_WORKFLOW_SPEC)
    result = _run(stratum_list_workflows(str(tmp_path)))
    assert len(result["workflows"]) == 1
    assert result["workflows"][0]["name"] == "build"
    assert len(result["errors"]) == 1
    assert "Duplicate" in result["errors"][0]
