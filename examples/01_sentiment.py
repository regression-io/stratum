"""
01 — Sentiment classification

The basics: @contract defines the output shape, @infer calls the LLM with
retry and budget, @flow orchestrates multiple steps deterministically.

Run: python examples/01_sentiment.py
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
from stratum import contract, infer, compute, flow, Budget
from stratum.trace import all_records, clear as clear_traces


@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str


@infer(
    intent="Classify the emotional tone of this customer feedback",
    context=[
        "Treat sarcasm as negative.",
        "When genuinely ambiguous, use neutral.",
        "Always commit to a label with confidence >= 0.8. Confidence reflects certainty about your label choice, not whether the text is extreme.",
    ],
    ensure=lambda r: r.confidence > 0.7,
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=3,
)
def classify_sentiment(text: str) -> SentimentResult: ...


@compute
def format_result(result: SentimentResult) -> str:
    icons = {"positive": "✓", "negative": "✗", "neutral": "~"}
    bar = "█" * int(result.confidence * 20)
    return f"  {icons[result.label]} [{result.label.upper():8}] {bar:<20} {result.confidence:.0%}"


@flow(budget=Budget(ms=30000, usd=0.05))
async def analyse_batch(texts: list[str]) -> list[SentimentResult]:
    results = []
    for text in texts:
        results.append(await classify_sentiment(text=text))
    return results


async def main():
    clear_traces()

    samples = [
        "This product completely changed my life — I love it!",
        "Arrived broken. Support never responded. Total waste of money.",
        "It works fine I guess. Nothing special.",
        "Oh great, another update that breaks everything. Love that for us.",
    ]

    print("Sentiment Analysis")
    print("=" * 60)

    results = await analyse_batch(texts=samples)

    for text, result in zip(samples, results):
        print(f"\n  {text}")
        print(format_result(result))
        print(f"  Reasoning: {result.reasoning[:80]}")

    print("\n" + "-" * 60)
    print("Trace:")
    for rec in all_records():
        retries = f"  ({len(rec.retry_reasons)} retries)" if rec.retry_reasons else ""
        print(f"  {rec.function}: {rec.attempts} attempt(s)  ${rec.cost_usd or 0:.5f}  {rec.duration_ms:.0f}ms{retries}")


if __name__ == "__main__":
    asyncio.run(main())
