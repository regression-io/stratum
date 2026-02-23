"""
02 — Migrate @infer → @compute

Key value prop: once you observe that an LLM step consistently produces
rule-like outputs, swap @infer for @compute — identical signature, zero tokens,
zero latency. The @flow and every caller stay unchanged.

Pattern:
  Phase 1  →  @infer:   LLM classifies support tickets
  Phase 2  →  @compute: rules replace the model once patterns emerge

Run: python examples/02_migrate.py
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
from stratum import contract, infer, compute, flow, Budget
from stratum.trace import all_records, clear as clear_traces


@contract
class TicketRoute(BaseModel):
    team: Literal["billing", "technical", "general"]
    priority: Literal["low", "medium", "high"]
    reason: str


# ---------------------------------------------------------------------------
# Phase 1 — LLM routes every ticket
# ---------------------------------------------------------------------------

@infer(
    intent="Route this customer support ticket to the correct team and assign a priority",
    context=[
        "billing:   payment, invoice, refund, subscription, charge",
        "technical: bug, crash, error, not working, broken, performance",
        "general:   question, feedback, feature request, account settings",
        "high:   service down, data loss, security issue, urgent, ASAP",
        "medium: frustrated, days, still not resolved",
        "low:    general questions, minor issues, suggestions",
    ],
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=5000, usd=0.01),
    retries=2,
)
def route_ticket_llm(ticket: str) -> TicketRoute: ...


# ---------------------------------------------------------------------------
# Phase 2 — Rules replace the model (same signature, zero tokens)
#
# After observing LLM outputs you notice a clear pattern: team is always
# determined by keyword presence; priority by urgency signals.
# One decorator swap and the flow is 100x faster at zero cost.
# ---------------------------------------------------------------------------

@compute
async def route_ticket_rules(ticket: str) -> TicketRoute:
    text = ticket.lower()

    if any(w in text for w in ("payment", "invoice", "refund", "charge", "billing", "subscription")):
        team = "billing"
    elif any(w in text for w in ("bug", "crash", "error", "broken", "not working", "fails", "slow")):
        team = "technical"
    else:
        team = "general"

    if any(w in text for w in ("urgent", "asap", "immediately", "data loss", "down", "can't access", "security")):
        priority = "high"
    elif any(w in text for w in ("frustrated", "days", "still not", "annoying", "weeks")):
        priority = "medium"
    else:
        priority = "low"

    return TicketRoute(team=team, priority=priority, reason="keyword match")


# ---------------------------------------------------------------------------
# The @flow is identical — swap one name and it's done
# ---------------------------------------------------------------------------

@flow(budget=Budget(ms=60000, usd=0.10))
async def triage_batch(tickets: list[str], use_llm: bool = True) -> list[TicketRoute]:
    router = route_ticket_llm if use_llm else route_ticket_rules
    results = []
    for ticket in tickets:
        results.append(await router(ticket=ticket))
    return results


async def main():
    tickets = [
        "I was charged twice this month. Please refund immediately.",
        "The app crashes whenever I upload a file larger than 10 MB.",
        "Would love a dark mode option — just a suggestion!",
        "Still can't access my account after 3 days. This is urgent.",
        "My invoice shows the wrong company name.",
        "Getting a 500 error on the dashboard since yesterday.",
    ]

    print("Support Ticket Router")
    print("=" * 60)

    # Phase 1: LLM routing
    clear_traces()
    t0 = time.monotonic()
    llm_results = await triage_batch(tickets=tickets, use_llm=True)
    llm_ms = (time.monotonic() - t0) * 1000
    llm_cost = sum(r.cost_usd or 0 for r in all_records())

    print(f"\nPhase 1 — @infer (LLM)  {llm_ms:.0f}ms  ${llm_cost:.5f}")
    for ticket, result in zip(tickets, llm_results):
        print(f"  [{result.team:9}] [{result.priority:6}]  {ticket[:58]}")

    # Phase 2: Rule-based routing — identical interface, zero LLM calls
    clear_traces()
    t0 = time.monotonic()
    rule_results = await triage_batch(tickets=tickets, use_llm=False)
    rule_ms = (time.monotonic() - t0) * 1000

    print(f"\nPhase 2 — @compute (rules)  {rule_ms:.0f}ms  $0.00000")
    for ticket, result in zip(tickets, rule_results):
        print(f"  [{result.team:9}] [{result.priority:6}]  {ticket[:58]}")

    # Comparison
    team_matches = sum(1 for a, b in zip(llm_results, rule_results) if a.team == b.team)
    prio_matches = sum(1 for a, b in zip(llm_results, rule_results) if a.priority == b.priority)
    speedup = llm_ms / rule_ms if rule_ms > 0 else float("inf")

    print(f"\n{'-' * 60}")
    print(f"  Team agreement:     {team_matches}/{len(tickets)}")
    print(f"  Priority agreement: {prio_matches}/{len(tickets)}")
    print(f"  Speedup:            {speedup:.0f}x")
    print(f"  Cost saving:        100%")
    print(f"\n  The @flow and all callers stayed unchanged. One decorator swap.")


if __name__ == "__main__":
    asyncio.run(main())
