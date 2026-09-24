"""Shared pipeline-stage transitions.

Used both by the generic PATCH endpoint (app/api/routers/projects.py) and by
individual stage jobs that mark themselves done automatically on success
(e.g. app/api/routers/load_data.py after a successful upload), so the
"unlock the next stage" rule lives in exactly one place.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Stage


async def set_stage_status(db: AsyncSession, project_id: uuid.UUID, stage_key: str, new_status: str) -> Stage:
    """Set a stage's status and, if newly "done", unlock the next stage.

    Mirrors the original app's locking rule (2202MandantenCleansing.py):
    a stage only becomes reachable once every stage before it is done.
    Does not commit - callers decide the transaction boundary.
    """
    result = await db.execute(
        select(Stage).where(Stage.project_id == project_id).order_by(Stage.position)
    )
    stages = list(result.scalars().all())
    target = next((s for s in stages if s.key == stage_key), None)
    if target is None:
        raise ValueError(f"Unknown stage '{stage_key}' for this project.")

    target.status = new_status

    if new_status == "done":
        next_stage = next((s for s in stages if s.position == target.position + 1), None)
        if next_stage is not None and next_stage.status == "locked":
            next_stage.status = "in_progress"

    await db.flush()
    return target
