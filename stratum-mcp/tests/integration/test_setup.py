"""Tests for `stratum-mcp install` CLI command."""
import json
import pytest
from pathlib import Path

from stratum_mcp.server import _cmd_setup, _CLAUDE_MD_MARKER, _CLAUDE_MD_BLOCK, _HOOK_SCRIPTS, _STRATUM_HOOKS_DIR


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


# ---------------------------------------------------------------------------
# Hooks (T2-M2/M3/M4)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=False)
def isolated_hooks_dir(tmp_path, monkeypatch):
    """Redirect _STRATUM_HOOKS_DIR to a temp dir so hook tests are isolated."""
    hooks_dir = tmp_path / ".stratum-hooks-test"
    hooks_dir.mkdir()
    import stratum_mcp.server as srv
    monkeypatch.setattr(srv, "_STRATUM_HOOKS_DIR", hooks_dir)
    return hooks_dir


def test_setup_installs_all_hook_scripts(tmp_path, capsys, isolated_hooks_dir):
    _run_setup(tmp_path)
    for script_name in _HOOK_SCRIPTS.values():
        assert (isolated_hooks_dir / script_name).exists(), f"Missing hook: {script_name}"


def test_setup_hook_scripts_are_executable(tmp_path, capsys, isolated_hooks_dir):
    _run_setup(tmp_path)
    import stat
    for script_name in _HOOK_SCRIPTS.values():
        path = isolated_hooks_dir / script_name
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{script_name} is not user-executable"


def test_setup_hooks_use_absolute_paths_in_settings(tmp_path, capsys, isolated_hooks_dir):
    _run_setup(tmp_path)
    settings_file = tmp_path / ".claude" / "settings.json"
    assert settings_file.exists()
    settings = json.loads(settings_file.read_text())
    hooks = settings.get("hooks", {})
    for event, script_name in _HOOK_SCRIPTS.items():
        assert event in hooks, f"Missing hook event: {event}"
        commands = [
            h.get("command", "")
            for entry in hooks[event]
            for h in entry.get("hooks", [])
        ]
        expected = f"bash {isolated_hooks_dir / script_name}"
        assert expected in commands, \
            f"settings.json hooks.{event} missing absolute path for {script_name}"


def test_setup_hooks_merge_with_existing_settings(tmp_path, isolated_hooks_dir):
    settings_file = tmp_path / ".claude" / "settings.json"
    (tmp_path / ".claude").mkdir(parents=True)
    existing = {"permissions": {"allow": ["Bash(pytest:*)"]}}
    settings_file.write_text(json.dumps(existing))

    _run_setup(tmp_path)

    settings = json.loads(settings_file.read_text())
    # Original key preserved
    assert settings["permissions"]["allow"] == ["Bash(pytest:*)"]
    # Hooks added
    assert "hooks" in settings


def test_setup_hooks_idempotent(tmp_path, capsys, isolated_hooks_dir):
    _run_setup(tmp_path)
    _run_setup(tmp_path)

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings.get("hooks", {})
    for event, script_name in _HOOK_SCRIPTS.items():
        commands = [
            h.get("command", "")
            for entry in hooks.get(event, [])
            for h in entry.get("hooks", [])
        ]
        matching = [c for c in commands if script_name in c]
        assert len(matching) == 1, \
            f"hooks.{event} has {len(matching)} entries for {script_name} (expected 1)"


def test_setup_reports_installed_not_updated_on_first_run(tmp_path, capsys, isolated_hooks_dir):
    """P3: first install must log 'installed', not 'updated'."""
    _run_setup(tmp_path)
    out = capsys.readouterr().out
    for script_name in _HOOK_SCRIPTS.values():
        assert f"{script_name}: installed" in out, \
            f"Expected 'installed' for {script_name}, got: {out}"
        assert f"{script_name}: updated" not in out


def test_setup_migrates_old_per_project_hooks(tmp_path, capsys, isolated_hooks_dir):
    """Old per-project hooks in .claude/hooks/ are cleaned up on install."""
    # Simulate old-style install: put scripts in .claude/hooks/
    old_hooks = tmp_path / ".claude" / "hooks"
    old_hooks.mkdir(parents=True)
    for script_name in _HOOK_SCRIPTS.values():
        (old_hooks / script_name).write_text("#!/bin/bash\n# old")

    # Also write old-style settings.json entries
    settings_file = tmp_path / ".claude" / "settings.json"
    old_settings = {"hooks": {}}
    for event, script_name in _HOOK_SCRIPTS.items():
        old_settings["hooks"][event] = [
            {"hooks": [{"type": "command", "command": f"bash .claude/hooks/{script_name}"}]}
        ]
    settings_file.write_text(json.dumps(old_settings))

    _run_setup(tmp_path)
    out = capsys.readouterr().out

    # Old scripts removed
    for script_name in _HOOK_SCRIPTS.values():
        assert not (old_hooks / script_name).exists(), \
            f"Old hook still present: {script_name}"
        assert "migrated" in out

    # New scripts installed to isolated hooks dir
    for script_name in _HOOK_SCRIPTS.values():
        assert (isolated_hooks_dir / script_name).exists()

    # Settings now use absolute paths
    settings = json.loads(settings_file.read_text())
    for event, script_name in _HOOK_SCRIPTS.items():
        commands = [
            h.get("command", "")
            for entry in settings["hooks"].get(event, [])
            for h in entry.get("hooks", [])
        ]
        expected = f"bash {isolated_hooks_dir / script_name}"
        assert expected in commands, f"Expected absolute path for {event}"
        old_cmd = f"bash .claude/hooks/{script_name}"
        assert old_cmd not in commands, f"Old relative path still in {event}"


def test_setup_migration_preserves_colocated_hooks(tmp_path, capsys, isolated_hooks_dir):
    """Migration must not drop non-Stratum hooks that share a hooks entry."""
    settings_file = tmp_path / ".claude" / "settings.json"
    (tmp_path / ".claude").mkdir(parents=True)

    # A single entry with both old Stratum hook AND a foreign hook
    mixed_entry = {"hooks": [
        {"type": "command", "command": "bash .claude/hooks/stratum-session-start.sh"},
        {"type": "command", "command": "bash my-custom-hook.sh"},
    ]}
    settings_file.write_text(json.dumps({
        "hooks": {"SessionStart": [mixed_entry]}
    }))

    _run_setup(tmp_path)

    settings = json.loads(settings_file.read_text())
    all_commands = [
        h.get("command", "")
        for entry in settings["hooks"]["SessionStart"]
        for h in entry.get("hooks", [])
    ]
    # Foreign hook must survive
    assert "bash my-custom-hook.sh" in all_commands, \
        "Foreign hook in mixed entry was lost during migration"
    # Old Stratum hook must be gone
    assert "bash .claude/hooks/stratum-session-start.sh" not in all_commands
