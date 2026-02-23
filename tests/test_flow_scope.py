"""Tests for FlowScope context manager."""
import pytest

from stratum import FlowScope
from stratum.budget import Budget


@pytest.mark.asyncio
async def test_flow_scope_sets_flow_id():
    from stratum.decorators import _flow_ctx
    ctx_inside = None
    async with FlowScope() as flow_id:
        ctx_inside = _flow_ctx.get()
    assert ctx_inside is not None
    assert ctx_inside.flow_id == flow_id
    assert _flow_ctx.get() is None  # reset after exit


@pytest.mark.asyncio
async def test_flow_scope_exception_safe():
    from stratum.decorators import _flow_ctx
    with pytest.raises(RuntimeError):
        async with FlowScope():
            raise RuntimeError("boom")
    assert _flow_ctx.get() is None  # must be reset even after exception


@pytest.mark.asyncio
async def test_flow_scope_with_budget_clones():
    from stratum.decorators import _flow_ctx
    b = Budget(ms=5000, usd=0.01)
    async with FlowScope(budget=b) as _:
        ctx = _flow_ctx.get()
        assert ctx.budget is not b  # cloned, not same object
        assert ctx.budget.ms == 5000


@pytest.mark.asyncio
async def test_flow_scope_yields_uuid_string():
    import uuid
    async with FlowScope() as flow_id:
        # must be a valid UUID string
        parsed = uuid.UUID(flow_id)
        assert str(parsed) == flow_id


@pytest.mark.asyncio
async def test_flow_scope_no_budget_ok():
    from stratum.decorators import _flow_ctx
    async with FlowScope() as flow_id:
        ctx = _flow_ctx.get()
        assert ctx.budget is None
        assert ctx.flow_id == flow_id
