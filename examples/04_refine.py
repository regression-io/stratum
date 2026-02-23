"""
04 — @refine: iterative improvement loop

@refine wraps an @infer function with an outer convergence loop. Each
iteration the model receives its previous output's specific shortcomings
as additional context, and regenerates until all quality gates pass.

Useful for drafting, rewriting, or any structured generation that must
satisfy measurable criteria.

Run: python examples/04_refine.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import litellm
litellm.suppress_debug_info = True

from pydantic import BaseModel
from stratum import contract, infer, refine, flow, Budget
from stratum.trace import all_records, clear as clear_traces


@contract
class PullRequestDescription(BaseModel):
    title: str
    summary: str        # what changed and why, 2–4 sentences
    test_plan: str      # how a reviewer should verify this works
    breaking_change: bool


# ---------------------------------------------------------------------------
# Quality gates and feedback — pure Python, no LLM calls
# ---------------------------------------------------------------------------

def _is_acceptable(pr: PullRequestDescription) -> bool:
    return (
        len(pr.title) >= 15
        and len(pr.summary.split()) >= 25
        and len(pr.test_plan.split()) >= 15
    )


def _collect_feedback(pr: PullRequestDescription) -> str:
    issues = []
    if len(pr.title) < 15:
        issues.append(
            f"title is too short ({len(pr.title)} chars, need ≥15); "
            "it must summarise the change in one imperative sentence"
        )
    if len(pr.summary.split()) < 25:
        issues.append(
            f"summary is too brief ({len(pr.summary.split())} words, need ≥25); "
            "explain what changed, why, and any important context"
        )
    if len(pr.test_plan.split()) < 15:
        issues.append(
            f"test_plan is too sparse ({len(pr.test_plan.split())} words, need ≥15); "
            "describe the specific steps a reviewer should take to verify correctness"
        )
    return "; ".join(issues)


# ---------------------------------------------------------------------------
# @refine stacked on @infer — convergence loop wraps the LLM call
# ---------------------------------------------------------------------------

@refine(
    until=_is_acceptable,
    feedback=_collect_feedback,
    max_iterations=4,
)
@infer(
    intent="Write a pull request description for the given diff summary",
    context=[
        "title: one imperative sentence (e.g. 'Add index on users.email'), no trailing punctuation",
        "summary: explain what changed and why; include performance or behaviour impact if relevant",
        "test_plan: specific steps a reviewer should take — commands, pages to visit, metrics to check",
        "breaking_change: true only if this changes a public API contract or data schema",
    ],
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=6000, usd=0.01),
    retries=1,
)
def write_pr_description(diff_summary: str) -> PullRequestDescription: ...


@flow(budget=Budget(ms=60000, usd=0.10))
async def generate_pr(diff_summary: str) -> PullRequestDescription:
    return await write_pr_description(diff_summary=diff_summary)


async def main():
    diff_summary = """
    Added a composite index on (users.email, users.status). Rewrote the login
    query to use the new index instead of a full table scan. Load tests show
    login p99 dropped from 850ms to 12ms at 500 concurrent users.

    A backfill migration creates the index concurrently (no table lock).
    The change is schema-compatible with the previous app version — no
    application code changes required for existing clients.
    """

    print("PR Description Generator  (@refine)")
    print("=" * 60)

    clear_traces()
    result = await generate_pr(diff_summary=diff_summary)

    print(f"\nTitle:\n  {result.title}")
    print(f"\nBreaking change: {result.breaking_change}")
    print(f"\nSummary:\n  {result.summary}")
    print(f"\nTest Plan:\n  {result.test_plan}")

    records = all_records()
    total_cost = sum(r.cost_usd or 0 for r in records)
    iterations = len(records)
    had_refinement = any(r.retry_reasons for r in records) or iterations > 1

    print(f"\n{'-' * 60}")
    print(f"  iterations:   {iterations}")
    print(f"  total cost:   ${total_cost:.5f}")
    print(f"  refined:      {had_refinement}")
    if had_refinement:
        print(f"  (quality gates triggered at least one refinement pass)")


if __name__ == "__main__":
    asyncio.run(main())
