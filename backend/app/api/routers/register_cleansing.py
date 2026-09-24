import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.register_cleansing_service import accept_cleansing, run_cleansing
from app.models.tenant import RegisterCleansingResult

router = APIRouter(prefix="/projects/{project_id}/register-cleansing", tags=["register-cleansing"])


class RunSummaryOut(BaseModel):
    filled: int
    junk: int
    canonical: int
    std: int
    llm_candidates: int
    llm_done: int


class RunRequest(BaseModel):
    use_llm: bool = True
    llm_limit: int = 0


@router.post("/run", response_model=RunSummaryOut, status_code=status.HTTP_201_CREATED)
async def run(project_id: uuid.UUID, payload: RunRequest, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Runs Stufe 2 (deterministic standardization) and, if enabled, Stufe 3
    (Claude Haiku cleanup for special forms) over every Mandant with a
    non-empty RegisterNumber, replacing this project's proposals.
    """
    return await run_cleansing(db, project_id, use_llm=payload.use_llm, llm_limit=payload.llm_limit)


class ResultOut(BaseModel):
    id: uuid.UUID
    IDParty: str
    CompanyName: str | None
    CountryCode: str | None
    RegisterCity: str
    RegisterNumber_Alt: str
    RegisterNumber_Neu: str
    Stufe: str
    Confidence: str
    Begruendung: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ResultOut])
async def list_results(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[RegisterCleansingResult]:
    result = await db.execute(
        select(RegisterCleansingResult)
        .where(RegisterCleansingResult.project_id == project_id)
        .order_by(RegisterCleansingResult.IDParty)
    )
    return list(result.scalars().all())


class AcceptRequest(BaseModel):
    confidences: list[str]


class AcceptOut(BaseModel):
    updated: int


@router.post("/accept", response_model=AcceptOut)
async def accept(project_id: uuid.UUID, payload: AcceptRequest, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Applies every proposal whose Confidence is in `confidences` (e.g.
    ["HIGH"] or ["HIGH", "MEDIUM"]) to Mandant.RegisterNumber and removes
    those rows from the list.
    """
    return await accept_cleansing(db, project_id, payload.confidences)
