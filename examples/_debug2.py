import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import asyncio, litellm
litellm.suppress_debug_info = True

from stratum import contract, infer, flow, Budget
from typing import Literal

@contract
class SentimentResult:
    label: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str

def my_ensure(r):
    conf = r.confidence
    result = conf > 0.7
    conf_repr = repr(conf)
    print(f"  ensure: confidence={conf_repr} type={type(conf).__name__} result={result}")
    return result

@infer(
    intent="Classify the emotional tone of this customer feedback",
    context="Treat sarcasm as negative.",
    ensure=my_ensure,
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=1,
)
def classify_sentiment(text: str) -> SentimentResult: ...

@flow(budget=Budget(ms=30000, usd=0.05))
async def analyse_batch(texts: list):
    results = []
    for text in texts:
        results.append(await classify_sentiment(text=text))
    return results

async def main():
    results = await analyse_batch(texts=["I love this product!"])
    print("Result:", results[0].label, results[0].confidence)

asyncio.run(main())
