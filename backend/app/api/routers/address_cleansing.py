import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.address_service import FindingNotAcceptable, accept_finding, run_address_analysis
from app.models.tenant import JunkAddress

router = APIRouter(prefix="/projects/{project_id}/address-cleansing", tags=["address-cleansing"])


class AnalysisSummaryOut(BaseModel):
    rows_checked: int
    findings: int
    by_category: dict[str, int]
    by_confidence: dict[str, int]


@router.post("/analyze", response_model=AnalysisSummaryOut, status_code=status.HTTP_201_CREATED)
async def analyze(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Run Adress-Analyse's Address field check against every Mandant in this
    project, replacing any previous findings for that field.
    """
    return await run_address_analysis(db, project_id)


class JunkAddressOut(BaseModel):
    id: uuid.UUID
    IDParty: str
    UserCode_Kummerer: str | None
    CompanyName: str | None
    Address: str | None
    City: str | None
    ZipCode: str | None
    CountryCode: str | None
    Reason: str
    Feld: str
    Alt: str | None
    Neu: str | None
    Kategorie: str
    Aktion: str
    Confidence: str

    model_config = {"from_attributes": True}


@router.get("/junk", response_model=list[JunkAddressOut])
async def list_junk(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[JunkAddress]:
    result = await db.execute(
        select(JunkAddress).where(JunkAddress.project_id == project_id).order_by(JunkAddress.IDParty)
    )
    return list(result.scalars().all())


@router.post("/junk/{finding_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept(project_id: uuid.UUID, finding_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> None:
    """Nacharbeit: apply a Hoch/Mittel-confidence finding's proposal to the
    Mandant record and remove it from the findings list. Findings with no
    automatic proposal (Aktion=MANUELL) or low confidence stay in the list
    for manual handling - matching the original app's "Confidence Hoch/
    Mittel" gating and its "the rest stays in JUNK_ADDRESS permanently" rule.
    """
    try:
        await accept_finding(db, project_id, finding_id)
    except FindingNotAcceptable as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
