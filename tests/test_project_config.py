"""Tests for StratumConfig (stratum.toml loader)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from pathlib import Path
from stratum import StratumConfig, PipelineConfig
from stratum.pipeline_types import Policy
from stratum.exceptions import StratumCompileError


# ---------------------------------------------------------------------------
# StratumConfig.empty()
# ---------------------------------------------------------------------------

def test_empty_config_has_no_overrides():
    cfg = StratumConfig.empty()
    assert cfg.pipeline.policy       == {}
    assert cfg.pipeline.capabilities == {}
    assert cfg.pipeline.connector    == {}


def test_empty_config_is_frozen():
    cfg = StratumConfig.empty()
    with pytest.raises((AttributeError, TypeError)):
        cfg.pipeline = None  # type: ignore


# ---------------------------------------------------------------------------
# StratumConfig.load() — file not found
# ---------------------------------------------------------------------------

def test_load_missing_file_returns_empty(tmp_path):
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg == StratumConfig.empty()


def test_load_default_path_missing_returns_empty(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no stratum.toml in this dir
    cfg = StratumConfig.load()
    assert cfg == StratumConfig.empty()


# ---------------------------------------------------------------------------
# StratumConfig.load() — valid toml
# ---------------------------------------------------------------------------

def test_load_policy_overrides(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.policy]\npre_gate = "flag"\npost_gate = "gate"\n'
    )
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg.pipeline.policy["pre_gate"]  == Policy.FLAG
    assert cfg.pipeline.policy["post_gate"] == Policy.GATE


def test_load_capabilities(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.capabilities]\nscout = "haiku"\nbuilder = "sonnet"\n'
    )
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg.pipeline.capabilities["scout"]   == "haiku"
    assert cfg.pipeline.capabilities["builder"] == "sonnet"


def test_load_connector_routing(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.connector]\ndefault = "claude-code"\nimplement = "codex"\n'
    )
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg.pipeline.connector["default"]   == "claude-code"
    assert cfg.pipeline.connector["implement"] == "codex"


def test_load_full_config(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.policy]\npre_gate = "flag"\n\n'
        '[pipeline.capabilities]\nscout = "haiku"\n\n'
        '[pipeline.connector]\ndefault = "claude-code"\nimplement = "codex"\n'
    )
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg.pipeline.policy["pre_gate"]          == Policy.FLAG
    assert cfg.pipeline.capabilities["scout"]       == "haiku"
    assert cfg.pipeline.connector["default"]        == "claude-code"
    assert cfg.pipeline.connector["implement"]      == "codex"


def test_load_empty_toml_returns_empty_config(tmp_path):
    (tmp_path / "stratum.toml").write_text("")
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg == StratumConfig.empty()


# ---------------------------------------------------------------------------
# StratumConfig.load() — validation errors
# ---------------------------------------------------------------------------

def test_load_invalid_policy_value_raises(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.policy]\ndiscovery = "block"\n'
    )
    with pytest.raises(StratumCompileError, match="invalid policy 'block'"):
        StratumConfig.load(tmp_path / "stratum.toml")


def test_load_malformed_toml_raises(tmp_path):
    (tmp_path / "stratum.toml").write_text("[[[ not valid toml\n")
    with pytest.raises(StratumCompileError, match="TOML parse error"):
        StratumConfig.load(tmp_path / "stratum.toml")


def test_load_non_string_capability_hint_raises(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.capabilities]\nscout = 42\n'
    )
    with pytest.raises(StratumCompileError, match="must be a string"):
        StratumConfig.load(tmp_path / "stratum.toml")


def test_load_non_string_connector_raises(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.connector]\ndefault = 123\n'
    )
    with pytest.raises(StratumCompileError, match="must be a string"):
        StratumConfig.load(tmp_path / "stratum.toml")


def test_parse_non_string_policy_key_raises():
    with pytest.raises(StratumCompileError, match="keys must be strings"):
        StratumConfig._parse({"pipeline": {"policy": {1: "gate"}}})


def test_parse_non_string_connector_key_raises():
    with pytest.raises(StratumCompileError, match="keys must be strings"):
        StratumConfig._parse({"pipeline": {"connector": {2: "claude-code"}}})


def test_load_unknown_capability_tier_raises(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.capabilities]\nscot = "haiku"\n'  # typo: scot not scout
    )
    with pytest.raises(StratumCompileError, match="unknown capability tier 'scot'"):
        StratumConfig.load(tmp_path / "stratum.toml")


def test_load_all_valid_capability_tiers_accepted(tmp_path):
    (tmp_path / "stratum.toml").write_text(
        '[pipeline.capabilities]\nscout = "haiku"\nbuilder = "sonnet"\ncritic = "sonnet"\n'
    )
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    assert cfg.pipeline.capabilities["scout"]   == "haiku"
    assert cfg.pipeline.capabilities["builder"] == "sonnet"
    assert cfg.pipeline.capabilities["critic"]  == "sonnet"


# ---------------------------------------------------------------------------
# Immutability of mapping fields
# ---------------------------------------------------------------------------

def test_pipeline_config_policy_is_immutable():
    cfg = StratumConfig.empty()
    with pytest.raises(TypeError):
        cfg.pipeline.policy["new_phase"] = Policy.GATE  # type: ignore


def test_pipeline_config_capabilities_is_immutable():
    cfg = StratumConfig.empty()
    with pytest.raises(TypeError):
        cfg.pipeline.capabilities["scout"] = "haiku"  # type: ignore


def test_pipeline_config_connector_is_immutable():
    cfg = StratumConfig.empty()
    with pytest.raises(TypeError):
        cfg.pipeline.connector["default"] = "codex"  # type: ignore


def test_loaded_config_policy_is_immutable(tmp_path):
    (tmp_path / "stratum.toml").write_text('[pipeline.policy]\ndiscovery = "skip"\n')
    cfg = StratumConfig.load(tmp_path / "stratum.toml")
    with pytest.raises(TypeError):
        cfg.pipeline.policy["discovery"] = Policy.GATE  # type: ignore


# ---------------------------------------------------------------------------
# effective_policy
# ---------------------------------------------------------------------------

def test_effective_policy_uses_toml_override():
    cfg = StratumConfig._parse({"pipeline": {"policy": {"discovery": "flag"}}})
    assert cfg.effective_policy("discovery", Policy.GATE) == Policy.FLAG


def test_effective_policy_falls_back_to_phase_policy():
    cfg = StratumConfig.empty()
    assert cfg.effective_policy("discovery", Policy.GATE) == Policy.GATE


def test_effective_policy_unrelated_override_not_applied():
    cfg = StratumConfig._parse({"pipeline": {"policy": {"other": "flag"}}})
    assert cfg.effective_policy("discovery", Policy.SKIP) == Policy.SKIP


# ---------------------------------------------------------------------------
# effective_connector
# ---------------------------------------------------------------------------

def test_effective_connector_phase_spec_wins():
    cfg = StratumConfig._parse({
        "pipeline": {"connector": {"default": "claude-code", "implement": "codex"}}
    })
    # Phase-level spec overrides everything
    assert cfg.effective_connector("implement", "custom", "pipeline-default") == "custom"


def test_effective_connector_toml_phase_beats_toml_default():
    cfg = StratumConfig._parse({
        "pipeline": {"connector": {"default": "claude-code", "implement": "codex"}}
    })
    assert cfg.effective_connector("implement", None, None) == "codex"


def test_effective_connector_toml_default_beats_pipeline_default():
    cfg = StratumConfig._parse({
        "pipeline": {"connector": {"default": "claude-code"}}
    })
    assert cfg.effective_connector("discovery", None, "other-connector") == "claude-code"


def test_effective_connector_falls_back_to_pipeline_default():
    cfg = StratumConfig.empty()
    assert cfg.effective_connector("discovery", None, "pipeline-default") == "pipeline-default"


def test_effective_connector_all_none_returns_none():
    cfg = StratumConfig.empty()
    assert cfg.effective_connector("discovery", None, None) is None


# ---------------------------------------------------------------------------
# model_hint
# ---------------------------------------------------------------------------

def test_model_hint_returns_configured_hint():
    cfg = StratumConfig._parse({
        "pipeline": {"capabilities": {"scout": "haiku", "builder": "sonnet"}}
    })
    assert cfg.model_hint("scout")   == "haiku"
    assert cfg.model_hint("builder") == "sonnet"


def test_model_hint_returns_none_for_unconfigured_tier():
    cfg = StratumConfig.empty()
    assert cfg.model_hint("scout") is None


def test_model_hint_unknown_tier_returns_none():
    cfg = StratumConfig._parse({"pipeline": {"capabilities": {"scout": "haiku"}}})
    assert cfg.model_hint("critic") is None
