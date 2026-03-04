"""Tests for `stratum-mcp uninstall` CLI command."""
import json
import os
import pytest
from pathlib import Path

from stratum_mcp.server import _cmd_setup, _cmd_uninstall, _CLAUDE_MD_MARKER


SKILLS_HOME = Path.home() / ".claude" / "skills"


def _run(tmp_path: Path, fn, **kwargs) -> None:
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        fn(**kwargs)
    finally:
        os.chdir(old)


def _setup(tmp_path):
    _run(tmp_path, _cmd_setup)


def _uninstall(tmp_path, **kwargs):
    _run(tmp_path, _cmd_uninstall, **kwargs)


# ---------------------------------------------------------------------------
# .claude/mcp.json
# ---------------------------------------------------------------------------

def test_uninstall_removes_stratum_from_mcp_json(tmp_path, capsys):
    _setup(tmp_path)
    capsys.readouterr()

    _uninstall(tmp_path)

    mcp_file = tmp_path / ".claude" / "mcp.json"
    assert not mcp_file.exists(), "mcp.json should be deleted when stratum was the only server"
    assert "removed stratum server" in capsys.readouterr().out


def test_uninstall_leaves_other_servers_in_mcp_json(tmp_path, capsys):
    mcp_dir = tmp_path / ".claude"
    mcp_dir.mkdir()
    config = {"mcpServers": {"stratum": {"command": "stratum-mcp"}, "other": {"command": "other"}}}
    (mcp_dir / "mcp.json").write_text(json.dumps(config))

    _uninstall(tmp_path)

    remaining = json.loads((mcp_dir / "mcp.json").read_text())
    assert "stratum" not in remaining["mcpServers"]
    assert remaining["mcpServers"]["other"]["command"] == "other"


def test_uninstall_skips_mcp_json_when_stratum_not_present(tmp_path, capsys):
    mcp_dir = tmp_path / ".claude"
    mcp_dir.mkdir()
    config = {"mcpServers": {"other": {"command": "other"}}}
    (mcp_dir / "mcp.json").write_text(json.dumps(config))

    _uninstall(tmp_path)

    assert "stratum not present" in capsys.readouterr().out


def test_uninstall_skips_mcp_json_when_file_absent(tmp_path, capsys):
    _uninstall(tmp_path)
    assert ".claude/mcp.json: not found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# CLAUDE.md
# ---------------------------------------------------------------------------

def test_uninstall_removes_stratum_section_from_claude_md(tmp_path, capsys):
    _setup(tmp_path)
    capsys.readouterr()

    _uninstall(tmp_path)

    out = capsys.readouterr().out
    assert "removed Stratum section" in out
    # File deleted because it had no other content
    claude_md = tmp_path / "CLAUDE.md"
    assert not claude_md.exists()


def test_uninstall_preserves_existing_claude_md_content(tmp_path, capsys):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# My Project\n\nExisting instructions.\n")

    _setup(tmp_path)
    capsys.readouterr()

    _uninstall(tmp_path)

    content = claude_md.read_text()
    assert "My Project" in content
    assert _CLAUDE_MD_MARKER not in content


def test_uninstall_skips_claude_md_when_section_not_present(tmp_path, capsys):
    (tmp_path / "CLAUDE.md").write_text("# No stratum here\n")

    _uninstall(tmp_path)

    assert "Stratum section not present" in capsys.readouterr().out


def test_uninstall_skips_claude_md_when_absent(tmp_path, capsys):
    _uninstall(tmp_path)
    assert "CLAUDE.md: not found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def test_uninstall_removes_skills(tmp_path, capsys):
    _setup(tmp_path)
    capsys.readouterr()

    _uninstall(tmp_path)

    from stratum_mcp.server import _cmd_setup as _  # just to get pkg_skills path
    from pathlib import Path as P
    import stratum_mcp.server as srv_mod
    pkg_skills = P(srv_mod.__file__).parent / "skills"
    for skill_dir in pkg_skills.iterdir():
        if not skill_dir.is_dir():
            continue
        assert not (SKILLS_HOME / skill_dir.name / "SKILL.md").exists(), \
            f"Skill {skill_dir.name} was not removed"


def test_uninstall_keep_skills_flag(tmp_path, capsys):
    _setup(tmp_path)
    capsys.readouterr()

    _uninstall(tmp_path, keep_skills=True)

    import stratum_mcp.server as srv_mod
    from pathlib import Path as P
    pkg_skills = P(srv_mod.__file__).parent / "skills"
    for skill_dir in pkg_skills.iterdir():
        if not skill_dir.is_dir():
            continue
        assert (SKILLS_HOME / skill_dir.name / "SKILL.md").exists(), \
            f"Skill {skill_dir.name} was removed despite --keep-skills"
    assert "--keep-skills" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Roundtrip: setup → uninstall → setup
# ---------------------------------------------------------------------------

def test_setup_after_uninstall_works(tmp_path):
    _setup(tmp_path)
    _uninstall(tmp_path)
    _setup(tmp_path)

    mcp_file = tmp_path / ".claude" / "mcp.json"
    assert mcp_file.exists()
    config = json.loads(mcp_file.read_text())
    assert config["mcpServers"]["stratum"]["command"] == "stratum-mcp"

    claude_md = tmp_path / "CLAUDE.md"
    assert _CLAUDE_MD_MARKER in claude_md.read_text()


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

def test_uninstall_prints_done_when_something_removed(tmp_path, capsys):
    _setup(tmp_path)
    capsys.readouterr()
    _uninstall(tmp_path)
    assert "Restart Claude Code" in capsys.readouterr().out


def test_uninstall_prints_nothing_to_remove_when_already_clean(tmp_path, capsys):
    _uninstall(tmp_path)
    assert "Nothing to remove" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Hooks (T2-M2/M3/M4)
# ---------------------------------------------------------------------------

from stratum_mcp.server import _HOOK_SCRIPTS


def test_uninstall_removes_hook_scripts(tmp_path, capsys):
    _run(tmp_path, _cmd_setup)
    capsys.readouterr()
    _uninstall(tmp_path)

    hooks_dir = tmp_path / ".claude" / "hooks"
    for script_name in _HOOK_SCRIPTS.values():
        assert not (hooks_dir / script_name).exists(), \
            f"Hook script still present after uninstall: {script_name}"


def test_uninstall_removes_hooks_from_settings_json(tmp_path, capsys):
    _run(tmp_path, _cmd_setup)
    capsys.readouterr()
    _uninstall(tmp_path)

    settings_file = tmp_path / ".claude" / "settings.json"
    # File may be deleted entirely or have hooks removed
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
        hooks = settings.get("hooks", {})
        for event, script_name in _HOOK_SCRIPTS.items():
            commands = [
                h.get("command", "")
                for entry in hooks.get(event, [])
                for h in entry.get("hooks", [])
            ]
            assert not any(script_name in cmd for cmd in commands), \
                f"hooks.{event} still has {script_name} after uninstall"


def test_uninstall_preserves_other_hooks_in_settings_json(tmp_path, capsys):
    """Non-stratum hooks must survive uninstall."""
    # Seed settings.json with a foreign hook before setup
    settings_file = tmp_path / ".claude" / "settings.json"
    (tmp_path / ".claude").mkdir(parents=True)
    foreign_entry = {"hooks": [{"type": "command", "command": "bash other-hook.sh"}]}
    settings_file.write_text(json.dumps(
        {"hooks": {"SessionStart": [foreign_entry]}}
    ))

    _run(tmp_path, _cmd_setup)
    capsys.readouterr()
    _uninstall(tmp_path)

    assert settings_file.exists(), "settings.json was deleted but foreign hooks remained"
    settings = json.loads(settings_file.read_text())
    session_hooks = settings.get("hooks", {}).get("SessionStart", [])
    commands = [
        h.get("command", "")
        for entry in session_hooks
        for h in entry.get("hooks", [])
    ]
    assert "bash other-hook.sh" in commands, "Foreign hook was removed by uninstall"


def test_uninstall_does_not_crash_when_settings_json_has_no_hooks_key(tmp_path, capsys):
    """P1: _remove_hooks() must not raise KeyError when settings.json lacks 'hooks'."""
    settings_file = tmp_path / ".claude" / "settings.json"
    (tmp_path / ".claude").mkdir(parents=True)
    settings_file.write_text(json.dumps({"permissions": {"allow": ["Bash(pytest:*)"]}}))

    _uninstall(tmp_path)  # must not raise

    # permissions key must be preserved
    assert settings_file.exists()
    assert json.loads(settings_file.read_text())["permissions"]["allow"] == ["Bash(pytest:*)"]
