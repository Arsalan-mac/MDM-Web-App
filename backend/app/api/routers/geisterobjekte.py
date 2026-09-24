import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.geisterobjekte_service import (
    get_status,
    quarantine_ghosts,
    restore_ghosts,
    run_consistency_check,
)

router = APIRouter(prefix="/projects/{project_id}/geisterobjekte", tags=["geisterobjekte"])


class StatusOut(BaseModel):
    mandant_count: int
    ghost_count: int


@router.get("/status", response_model=StatusOut)
async def status(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    return await get_status(db, project_id)


class QuarantineOut(BaseModel):
    quarantined: int


@router.post("/quarantine", response_model=QuarantineOut)
async def quarantine(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Find Mandanten with no Auftrag/ConnectedParty/MandantGegner reference
    and move them to the quarantine table."""
    count = await quarantine_ghosts(db, project_id)
    return {"quarantined": count}


class RestoreOut(BaseModel):
    restored: int
    skipped: int


@router.post("/restore", response_model=RestoreOut)
async def restore(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Move every quarantined ghost back to Mandanten."""
    return await restore_ghosts(db, project_id)


class ConsistencyFindingOut(BaseModel):
    table: str
    ghost_rows: int
    hint: str


@router.get("/consistency", response_model=list[ConsistencyFindingOut])
async def consistency(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[dict]:
    """Which result tables still reference now-quarantined ghosts (their
    analysis ran before the quarantine and should be re-run)."""
    return await run_consistency_check(db, project_id)
