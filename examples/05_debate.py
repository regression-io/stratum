"""
05 — debate(): multi-agent deliberation

Two @infer agents argue opposing positions across multiple rounds.
A synthesize function (also @infer) reads the full transcript and
produces a final recommendation.

Convergence is detected automatically: if both agents return the same
`stance` in the final round, debate() passes converged=True to synthesize.

Run: python examples/05_debate.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import litellm
litellm.suppress_debug_info = True

from pydantic import BaseModel
from stratum import contract, infer, flow, Budget
from stratum.concurrency import debate
from stratum.trace import all_records, clear as clear_traces


@contract
class Position(BaseModel):
    stance: Literal["monolith", "microservices", "hybrid"]
    argument: str
    confidence: float


@contract
class Recommendation(BaseModel):
    verdict: Literal["monolith", "microservices", "hybrid"]
    rationale: str
    key_tradeoffs: list
    confidence: float


@infer(
    intent="Argue in favour of a MONOLITH architecture for this engineering context",
    context=[
        "You are advocating for the monolith position.",
        "Be concrete: cite deployment simplicity, team size, data consistency, debugging ease.",
        "If you have seen the opposing argument, address it specifically.",
        "Commit to stance='monolith'.",
    ],
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=6000, usd=0.01),
    retries=1,
    agree_on="stance",
)
def monolith_advocate(topic: str, previous_arguments: list | None = None) -> Position: ...


@infer(
    intent="Argue in favour of MICROSERVICES architecture for this engineering context",
    context=[
        "You are advocating for the microservices position.",
        "Be concrete: cite independent deployability, scaling, team autonomy, fault isolation.",
        "If you have seen the opposing argument, address it specifically.",
        "Commit to stance='microservices'.",
    ],
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=6000, usd=0.01),
    retries=1,
    agree_on="stance",
)
def microservices_advocate(topic: str, previous_arguments: list | None = None) -> Position: ...


@infer(
    intent="Synthesise this architecture debate into a final recommendation",
    context=[
        "Review the full argument transcript (all rounds).",
        "Identify the strongest concrete points on each side.",
        "Produce a verdict supported by clear rationale.",
        "key_tradeoffs: 3-5 short strings capturing the most important trade-offs.",
        "confidence: your certainty that this is the right call given the context.",
    ],
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=1,
)
def synthesise(topic: str, transcript: str, converged: bool) -> Recommendation: ...


async def synthesise_debate(topic, arguments, converged):
    """Bridge: flatten the round history to text, then call the @infer synthesiser."""
    lines = []
    for round_idx, round_args in enumerate(arguments):
        for pos in round_args:
            stance = getattr(pos, "stance", "?")
            argument = getattr(pos, "argument", str(pos))
            lines.append(f"Round {round_idx + 1} / {stance}: {argument}")
    transcript = "\n".join(lines)
    return await synthesise(topic=topic, transcript=transcript, converged=converged)


@flow(budget=Budget(ms=120000, usd=0.30))
async def architecture_debate(topic: str) -> Recommendation:
    return await debate(
        agents=[monolith_advocate, microservices_advocate],
        topic=topic,
        rounds=2,
        synthesize=synthesise_debate,
    )


async def main():
    topic = (
        "6-person startup, Python/FastAPI backend, React frontend, 10k users. "
        "Hiring 4 engineers next quarter. We need to add real-time notifications. "
        "Should we add this as a new microservice or extend the existing monolith?"
    )

    print("Architecture Debate  (2 agents × 2 rounds → synthesis)")
    print("=" * 60)
    print(f"  Topic: {topic}\n")

    clear_traces()
    result = await architecture_debate(topic=topic)

    print(f"Verdict:    {result.verdict.upper()}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"\nRationale:\n  {result.rationale}")
    print(f"\nKey tradeoffs:")
    for tradeoff in result.key_tradeoffs:
        print(f"  • {tradeoff}")

    records = all_records()
    total_cost = sum(r.cost_usd or 0 for r in records)
    print(f"\n{'-' * 60}")
    print(f"  {len(records)} @infer calls  ${total_cost:.5f}")


if __name__ == "__main__":
    asyncio.run(main())
