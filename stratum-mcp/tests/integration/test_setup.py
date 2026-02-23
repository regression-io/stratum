"""Tests for `stratum-mcp setup` CLI command."""
import json
import pytest
from pathlib import Path

from stratum_mcp.server import _cmd_setup, _CLAUDE_MD_MARKER, _CLAUDE_MD_BLOCK


def _run_setup(tmp_path: Path) -> None:
    """Run _cmd_setup with cwd set to tmp_path."""
    import os
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        _cmd_setup()
    finally:
        os.chdir(old)


# ---------------------------------------------------------------------------
# .claude/mcp.json
# ---------------------------------------------------------------------------

def test_setup_creates_mcp_json_when_absent(tmp_path, capsys):
    _run_setup(tmp_path)
    mcp_file = tmp_path / ".claude" / "mcp.json"
    assert mcp_file.exists()
    config = json.loads(mcp_file.read_text())
    assert config["mcpServers"]["stratum"]["command"] == "stratum-mcp"
    assert "created" in capsys.readouterr().out


def test_setup_merges_into_existing_mcp_json(tmp_path, capsys):
    mcp_dir = tmp_path / ".claude"
    mcp_dir.mkdir()
    existing = {"mcpServers": {"other-server": {"command": "other"}}}
    (mcp_dir / "mcp.json").write_text(json.dumps(existing))

    _run_setup(tmp_path)

    config = json.loads((mcp_dir / "mcp.json").read_text())
    assert config["mcpServers"]["stratum"]["command"] == "stratum-mcp"
    assert config["mcpServers"]["other-server"]["command"] == "other"
    assert "added stratum server" in capsys.readouterr().out


def test_setup_skips_mcp_json_when_stratum_already_present(tmp_path, capsys):
    mcp_dir = tmp_path / ".claude"
    mcp_dir.mkdir()
    existing = {"mcpServers": {"stratum": {"command": "stratum-mcp"}}}
    mcp_file = mcp_dir / "mcp.json"
    mcp_file.write_text(json.dumps(existing))
    original_mtime = mcp_file.stat().st_mtime

    _run_setup(tmp_path)

    assert mcp_file.stat().st_mtime == original_mtime  # not rewritten
    assert "skipped" in capsys.readouterr().out


def test_setup_handles_malformed_mcp_json(tmp_path):
    mcp_dir = tmp_path / ".claude"
    mcp_dir.mkdir()
    (mcp_dir / "mcp.json").write_text("{not valid json")

    _run_setup(tmp_path)  # must not raise

    config = json.loads((mcp_dir / "mcp.json").read_text())
    assert config["mcpServers"]["stratum"]["command"] == "stratum-mcp"


# ---------------------------------------------------------------------------
# CLAUDE.md
# ---------------------------------------------------------------------------

def test_setup_creates_claude_md_when_absent(tmp_path, capsys):
    _run_setup(tmp_path)
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    assert _CLAUDE_MD_MARKER in claude_md.read_text()
    assert "created" in capsys.readouterr().out


def test_setup_appends_to_existing_claude_md(tmp_path, capsys):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Existing content\n\nSome existing instructions.\n")

    _run_setup(tmp_path)

    content = claude_md.read_text()
    assert "Existing content" in content
    assert _CLAUDE_MD_MARKER in content
    assert "added Stratum section" in capsys.readouterr().out


def test_setup_skips_claude_md_when_section_already_present(tmp_path, capsys):
    claude_md = tmp_path / "CLAUDE.md"
    existing = f"# Existing\n\n{_CLAUDE_MD_MARKER}\n\nAlready here.\n"
    claude_md.write_text(existing)
    original_mtime = claude_md.stat().st_mtime

    _run_setup(tmp_path)

    assert claude_md.stat().st_mtime == original_mtime
    assert "skipped" in capsys.readouterr().out


def test_setup_claude_md_contains_all_six_instructions(tmp_path):
    _run_setup(tmp_path)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "stratum_plan" in content
    assert "stratum_step_done" in content
    assert "stratum_audit" in content
    assert "never show it to the user" in content


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_setup_is_idempotent(tmp_path, capsys):
    _run_setup(tmp_path)
    _run_setup(tmp_path)
    out = capsys.readouterr().out
    assert "nothing to do" in out

    # Content should not be duplicated
    content = (tmp_path / "CLAUDE.md").read_text()
    assert content.count(_CLAUDE_MD_MARKER) == 1


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------

def test_setup_finds_root_via_git(tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "mymodule"
    subdir.mkdir(parents=True)

    import os
    old = os.getcwd()
    try:
        os.chdir(subdir)
        _cmd_setup()
    finally:
        os.chdir(old)

    # Files written at repo root, not subdir
    assert (tmp_path / ".claude" / "mcp.json").exists()
    assert (tmp_path / "CLAUDE.md").exists()


def test_setup_finds_root_via_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Existing\n")
    subdir = tmp_path / "nested"
    subdir.mkdir()

    import os
    old = os.getcwd()
    try:
        os.chdir(subdir)
        _cmd_setup()
    finally:
        os.chdir(old)

    assert (tmp_path / ".claude" / "mcp.json").exists()


def test_setup_done_message_on_changes(tmp_path, capsys):
    _run_setup(tmp_path)
    out = capsys.readouterr().out
    assert "Restart Claude Code" in out


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

EXPECTED_SKILLS = ["stratum-review", "stratum-feature", "stratum-debug", "stratum-refactor"]
SKILLS_HOME = Path.home() / ".claude" / "skills"


def test_setup_installs_all_skills(tmp_path, capsys):
    _run_setup(tmp_path)
    for skill in EXPECTED_SKILLS:
        assert (SKILLS_HOME / skill / "SKILL.md").exists(), f"Missing skill: {skill}"


def test_setup_skill_contains_frontmatter(tmp_path):
    _run_setup(tmp_path)
    for skill in EXPECTED_SKILLS:
        content = (SKILLS_HOME / skill / "SKILL.md").read_text()
        assert content.startswith("---"), f"{skill} missing frontmatter"
        assert f"name: {skill}" in content


def test_setup_skill_contains_key_instructions(tmp_path):
    _run_setup(tmp_path)
    for skill in EXPECTED_SKILLS:
        content = (SKILLS_HOME / skill / "SKILL.md").read_text()
        assert "stratum_plan" in content, f"{skill} missing stratum_plan reference"
        assert "stratum_step_done" in content, f"{skill} missing stratum_step_done reference"
        assert "never show it to the user" in content, f"{skill} missing privacy instruction"


def test_setup_skill_idempotent(tmp_path, capsys):
    _run_setup(tmp_path)
    _run_setup(tmp_path)
    out = capsys.readouterr().out
    assert "nothing to do" in out
    for skill in EXPECTED_SKILLS:
        content = (SKILLS_HOME / skill / "SKILL.md").read_text()
        assert content.count(f"name: {skill}") == 1
