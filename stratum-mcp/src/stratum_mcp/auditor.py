"""stratum_audit — stub for v0.1."""
from __future__ import annotations
from typing import Any


async def audit(path: str) -> dict[str, Any]:
    return {"message": "audit not yet implemented", "path": path}
