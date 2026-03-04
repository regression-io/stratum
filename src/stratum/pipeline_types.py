"""Pipeline primitive types: Capability, Policy, and named assertion vocabulary."""

from __future__ import annotations

from enum import Enum


class Capability(str, Enum):
    """Abstract agent capability tier. Connectors resolve to concrete agents/models."""

    SCOUT   = "scout"    # fast, read-only exploration
    BUILDER = "builder"  # full capability — writes code, edits files, runs tests
    CRITIC  = "critic"   # review and assessment — reads output, evaluates quality


class Policy(str, Enum):
    """Gate/flag/skip dial attached to a phase transition."""

    GATE = "gate"  # block until human explicitly approves
    FLAG = "flag"  # proceed, notify human, log decision
    SKIP = "skip"  # proceed silently, record for audit trail


# ---------------------------------------------------------------------------
# Named assertion vocabulary
#
# Portable assertions any connector can evaluate natively. The bar for adding
# an assertion is high: it must be meaningful for every connector and
# implementable in any language without external dependencies.
#
# Parameterised assertions (file_exists, file_contains) are distinguished
# from bare assertions by their presence in PARAMETERISED_ASSERTIONS.
# ---------------------------------------------------------------------------

BARE_ASSERTIONS: frozenset[str] = frozenset({
    "tests_pass",    # result.tests_pass is truthy
    "lint_clean",    # result.lint_clean is truthy
    "files_changed", # result.changed_files is non-empty
    "approved",      # result.approved is truthy
    "no_issues",     # result.issues is empty
})

PARAMETERISED_ASSERTIONS: frozenset[str] = frozenset({
    "file_exists",   # file_exists(path) — file exists on disk
    "file_contains", # file_contains(path, substring)
})

NAMED_ASSERTIONS: frozenset[str] = BARE_ASSERTIONS | PARAMETERISED_ASSERTIONS


def _parens_balanced(s: str) -> bool:
    """Return True iff every ( in s has a matching )."""
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def is_named_assertion(expr: str) -> bool:
    """
    Return True if expr is a named assertion (bare or parameterised call).

    Bare:          "tests_pass"
    Parameterised: "file_exists('.stratum/runs/abc/discovery.json')"
    """
    stripped = expr.strip()
    if stripped in BARE_ASSERTIONS:
        return True
    for name in PARAMETERISED_ASSERTIONS:
        if not stripped.startswith(name):
            continue
        suffix = stripped[len(name):]
        if (
            suffix.startswith("(")
            and suffix.endswith(")")
            and suffix[1:-1].strip()        # must have at least one argument
            and _parens_balanced(suffix)
        ):
            return True
    return False
