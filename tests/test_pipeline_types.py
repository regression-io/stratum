"""Tests for Capability, Policy, and named assertion vocabulary."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from stratum import Capability, Policy, NAMED_ASSERTIONS, BARE_ASSERTIONS, PARAMETERISED_ASSERTIONS, is_named_assertion


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------

def test_capability_values():
    assert Capability.SCOUT   == "scout"
    assert Capability.BUILDER == "builder"
    assert Capability.CRITIC  == "critic"


def test_capability_is_str():
    # str subclass — usable anywhere a string is expected
    assert isinstance(Capability.SCOUT, str)


def test_capability_from_string():
    assert Capability("scout")   is Capability.SCOUT
    assert Capability("builder") is Capability.BUILDER
    assert Capability("critic")  is Capability.CRITIC


def test_capability_invalid():
    with pytest.raises(ValueError):
        Capability("planner")


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

def test_policy_values():
    assert Policy.GATE == "gate"
    assert Policy.FLAG == "flag"
    assert Policy.SKIP == "skip"


def test_policy_is_str():
    assert isinstance(Policy.GATE, str)


def test_policy_from_string():
    assert Policy("gate") is Policy.GATE
    assert Policy("flag") is Policy.FLAG
    assert Policy("skip") is Policy.SKIP


def test_policy_invalid():
    with pytest.raises(ValueError):
        Policy("block")


# ---------------------------------------------------------------------------
# Named assertion vocabulary
# ---------------------------------------------------------------------------

def test_bare_assertions_present():
    for name in ("tests_pass", "lint_clean", "files_changed", "approved", "no_issues"):
        assert name in BARE_ASSERTIONS


def test_parameterised_assertions_present():
    for name in ("file_exists", "file_contains"):
        assert name in PARAMETERISED_ASSERTIONS


def test_named_assertions_is_union():
    assert NAMED_ASSERTIONS == BARE_ASSERTIONS | PARAMETERISED_ASSERTIONS


def test_named_assertions_are_frozen():
    with pytest.raises((AttributeError, TypeError)):
        NAMED_ASSERTIONS.add("new_assertion")  # type: ignore


# ---------------------------------------------------------------------------
# is_named_assertion
# ---------------------------------------------------------------------------

def test_bare_assertion_recognised():
    assert is_named_assertion("tests_pass")
    assert is_named_assertion("lint_clean")
    assert is_named_assertion("files_changed")
    assert is_named_assertion("approved")
    assert is_named_assertion("no_issues")


def test_bare_assertion_with_whitespace():
    assert is_named_assertion("  tests_pass  ")


def test_parameterised_assertion_recognised():
    assert is_named_assertion("file_exists('some/path.py')")
    assert is_named_assertion('file_contains("README.md", "stratum")')


def test_arbitrary_expression_not_named():
    assert not is_named_assertion("result.coverage > 0.8")
    assert not is_named_assertion("len(result.changed_files) > 0")
    assert not is_named_assertion("result.tests_pass == True")


def test_malformed_parameterised_assertion_not_named():
    # missing closing paren
    assert not is_named_assertion("file_exists(")
    assert not is_named_assertion("file_contains(")
    assert not is_named_assertion("file_exists('path'")
    # extra closing paren — passes prefix/suffix check but unbalanced
    assert not is_named_assertion("file_exists())")
    # unclosed inner paren — passes prefix/suffix check but unbalanced
    assert not is_named_assertion("file_exists(()")
    # empty argument — parameterised assertions require at least one argument
    assert not is_named_assertion("file_exists()")
    assert not is_named_assertion("file_contains()")


def test_unknown_name_not_named():
    assert not is_named_assertion("all_good")
    assert not is_named_assertion("file_exists_somewhere('x')")  # wrong name


def test_non_prefixed_call_not_named():
    # Any expression whose len(name)-length prefix is not exactly the name
    # must not be classified as named, even when the suffix is syntactically
    # valid.  Regression for: suffix-slice without startswith() check.
    assert not is_named_assertion("file_existx('path')")     # off-by-one in name
    assert not is_named_assertion("XXXXXXXXXXX('path')")     # 11-char non-name prefix
    assert not is_named_assertion("XXXXXXXXXXXXX('path')")   # 13-char non-name prefix
