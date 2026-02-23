"""
06 — Human-in-the-loop (HITL)

The LLM drafts a customer reply; a human reviews and approves before it
goes out. A custom ReviewSink drives the approval channel — swap two lines
to route reviews through Slack, email, a web UI, or any other system.

Run modes:
  HITL_AUTO=1 python examples/06_hitl.py   # non-interactive (auto-approve)
  python examples/06_hitl.py               # interactive (prompts at terminal)
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import litellm
litellm.suppress_debug_info = True

from pydantic import BaseModel
from stratum import contract, infer, flow, Budget, configure
from stratum.hitl import await_human, PendingReview
from stratum.types import HumanDecision, HumanReviewContext
from stratum.trace import all_records, clear as clear_traces


@contract
class CustomerReply(BaseModel):
    subject: str
    body: str
    tone: Literal["formal", "friendly", "apologetic"]


@infer(
    intent="Draft a customer support reply to this complaint",
    context=[
        "Be empathetic and solution-focused.",
        "Offer a concrete next step or resolution timeline.",
        "Keep the body under 120 words.",
        "tone: apologetic for billing/service issues, friendly for general questions.",
    ],
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=6000, usd=0.01),
    retries=2,
)
def draft_reply(complaint: str) -> CustomerReply: ...


# ---------------------------------------------------------------------------
# ReviewSink — swap this class to change the approval channel
# ---------------------------------------------------------------------------

class DemoReviewSink:
    """
    Shows the draft and routes to human input or auto-approve.

    Production replacement examples:
      - SlackReviewSink: posts to a channel, resolves on button click
      - EmailReviewSink: sends email, resolves on reply
      - WebhookReviewSink: POSTs to an endpoint, resolves via callback
    """

    async def emit(self, review: PendingReview) -> None:
        draft = review.context.artifacts.get("draft", {})
        print(f"\n  Subject: {draft.get('subject', '')}")
        print(f"  Tone:    {draft.get('tone', '')}")
        print(f"\n  {draft.get('body', '')}\n")

        if os.environ.get("HITL_AUTO"):
            asyncio.create_task(self._auto_approve(review))
        else:
            asyncio.create_task(self._prompt_human(review))

    async def _auto_approve(self, review: PendingReview) -> None:
        await asyncio.sleep(0.05)
        await review.resolve(HumanDecision(
            value="approve",
            reviewer="auto",
            rationale="HITL_AUTO mode",
            decided_at=datetime.utcnow(),
            review_id=review.review_id,
        ))

    async def _prompt_human(self, review: PendingReview) -> None:
        loop = asyncio.get_running_loop()
        while not review._future.done():
            raw = await loop.run_in_executor(
                None, input, "  [a]pprove / [r]eject / [e]dit → "
            )
            choice = raw.strip().lower()
            value = {"a": "approve", "e": "edit", "r": "reject"}.get(choice, choice)
            try:
                await review.resolve(HumanDecision(
                    value=value,
                    reviewer="human",
                    rationale=None,
                    decided_at=datetime.utcnow(),
                    review_id=review.review_id,
                ))
                return
            except TypeError as exc:
                print(f"  Invalid input: {exc}. Try again.")


configure(review_sink=DemoReviewSink())


# ---------------------------------------------------------------------------
# Flow: draft → review → send (or discard)
# ---------------------------------------------------------------------------

@flow(budget=Budget(ms=120000, usd=0.10))
async def handle_complaint(complaint: str) -> dict:
    # Step 1: LLM drafts the reply
    draft = await draft_reply(complaint=complaint)

    # Step 2: human reviews before it goes out
    decision = await await_human(
        context=HumanReviewContext(
            question="Review this draft reply before sending:",
            artifacts={
                "draft": {
                    "subject": draft.subject,
                    "body": draft.body,
                    "tone": draft.tone,
                }
            },
        ),
        decision_type=str,
        options=["approve", "reject"],
        timeout=timedelta(seconds=60),
        on_timeout="approve",   # auto-approve if reviewer goes quiet
    )

    return {
        "draft": draft,
        "decision": decision.value,
        "reviewer": decision.reviewer,
        "sent": decision.value == "approve",
    }


async def main():
    complaints = [
        "I've been waiting 2 weeks for my order. The tracking just says 'processing'. This is completely unacceptable.",
        "You charged me $49.99 but I only signed up for the $9.99 plan. I need this fixed right now.",
    ]

    mode = "auto-approve" if os.environ.get("HITL_AUTO") else "interactive"
    print(f"Customer Support HITL Pipeline  [{mode}]")
    print("=" * 60)

    clear_traces()
    for i, complaint in enumerate(complaints, 1):
        print(f"\n[{i}] Complaint: {complaint[:70]}...")
        print(f"\n[HITL] Review this draft reply before sending:")

        result = await handle_complaint(complaint=complaint)

        print(f"\n  Decision:  {result['decision']}  (by {result['reviewer']})")
        print(f"  Sent:      {'yes' if result['sent'] else 'no — discarded'}")

    records = all_records()
    total_cost = sum(r.cost_usd or 0 for r in records)
    print(f"\n{'-' * 60}")
    print(f"  {len(records)} @infer calls  ${total_cost:.5f}")


if __name__ == "__main__":
    asyncio.run(main())
