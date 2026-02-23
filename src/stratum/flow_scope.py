"""Public FlowScope — async context manager for establishing flow execution context."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .budget import Budget
# These private symbols are the only permitted internal imports in flow_scope.py.
# If _FlowContext fields change (decorators.py:22-26), update FlowScope accordingly.
from .decorators import _FlowContext, _flow_ctx


@asynccontextmanager
async def FlowScope(budget: Budget | None = None) -> AsyncGenerator[str, None]:
    """
    Async context manager. Establishes a flow context for the duration of the block.
    Yields the flow_id. All execute_infer calls within the block inherit this
    flow_id, budget, and session cache.

        async with FlowScope(budget=Budget(ms=5000)) as flow_id:
            result = await execute_infer(spec, inputs, flow_budget=budget, flow_id=flow_id)
    """
    flow_id = str(uuid.uuid4())
    flow_budget = budget.clone() if budget is not None else None
    ctx = _FlowContext(flow_id=flow_id, budget=flow_budget)
    token = _flow_ctx.set(ctx)
    try:
        yield flow_id
    finally:
        _flow_ctx.reset(token)
