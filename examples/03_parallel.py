"""
03 — Parallel extraction

Fire multiple @infer calls concurrently against the same document.
parallel(require="all") collects all results; wall-clock time is bounded
by the slowest single call — not the sum of all calls.

Run: python examples/03_parallel.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import litellm
litellm.suppress_debug_info = True

from pydantic import BaseModel
from stratum import contract, infer, flow, Budget
from stratum.concurrency import parallel
from stratum.trace import all_records, clear as clear_traces


@contract
class Summary(BaseModel):
    headline: str
    key_points: list
    sentiment: Literal["positive", "negative", "neutral", "mixed"]


@contract
class ActionItems(BaseModel):
    items: list
    deadline_mentioned: bool


@contract
class RiskFlags(BaseModel):
    flags: list
    severity: Literal["none", "low", "medium", "high"]
    requires_escalation: bool


@infer(
    intent="Summarise this document: provide a headline, 3-5 key points, and overall sentiment",
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=1,
)
def summarise(document: str) -> Summary: ...


@infer(
    intent="Extract all action items and whether any deadline is explicitly mentioned",
    context="Items should be specific tasks assigned to named people or teams.",
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=1,
)
def extract_actions(document: str) -> ActionItems: ...


@infer(
    intent="Identify legal, financial, security, or reputational risk flags in this document",
    context="Flag only concrete, specific risks — not general observations.",
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=1,
)
def flag_risks(document: str) -> RiskFlags: ...


@flow(budget=Budget(ms=30000, usd=0.10))
async def analyse_document(document: str):
    # All three fire concurrently — wall time ≈ max(t₁, t₂, t₃), not t₁+t₂+t₃
    summary, actions, risks = await parallel(
        summarise(document=document),
        extract_actions(document=document),
        flag_risks(document=document),
    )
    return summary, actions, risks


async def main():
    document = """
    Q3 Engineering Review — 2024-10-01

    Performance: API p99 latency increased from 180ms to 340ms after the September
    deploy. Root cause: N+1 query in the user-list endpoint. Fix is in review;
    Alice will merge by Friday or the release is blocked.

    Security: Third-party audit flagged two medium-severity issues in the auth
    module. Both are patched in PR #441. We must deploy before 15 October or risk
    failing our SOC2 renewal — legal has been notified.

    Staffing: Bob is leaving end of month. His on-call rotation needs reassignment
    ASAP. Carol has volunteered but needs a ramp-up week first. On-call coverage
    gap of ~5 days is a risk.

    Budget: We are 12% over on cloud spend this quarter. DevOps to audit idle
    resources by next Friday and report back with a reduction plan.

    Overall the team is under pressure but morale is holding. Recommend an async
    retrospective to capture lessons before the next sprint.
    """

    print("Document Analysis  (3 concurrent @infer calls)")
    print("=" * 60)
    print(f"  document: {len(document.strip())} chars\n")

    clear_traces()
    t0 = time.monotonic()
    summary, actions, risks = await analyse_document(document=document)
    elapsed_ms = (time.monotonic() - t0) * 1000

    print(f"Summary  [{summary.sentiment}]")
    print(f"  {summary.headline}")
    for pt in summary.key_points:
        print(f"  • {pt}")

    print(f"\nAction Items")
    for item in actions.items:
        print(f"  → {item}")
    if actions.deadline_mentioned:
        print(f"  (deadlines mentioned)")

    print(f"\nRisk Flags  [{risks.severity.upper()}]")
    if risks.flags:
        for flag in risks.flags:
            print(f"  ⚠  {flag}")
    else:
        print(f"  (none)")
    if risks.requires_escalation:
        print(f"  *** ESCALATION REQUIRED ***")

    records = all_records()
    total_cost = sum(r.cost_usd or 0 for r in records)
    serial_estimate_ms = sum(r.duration_ms for r in records)

    print(f"\n{'-' * 60}")
    print(f"  wall time:          {elapsed_ms:.0f}ms")
    print(f"  serial estimate:    ~{serial_estimate_ms:.0f}ms")
    print(f"  parallelism gain:   ~{serial_estimate_ms / elapsed_ms:.1f}x")
    print(f"  total cost:         ${total_cost:.5f}")


if __name__ == "__main__":
    asyncio.run(main())
