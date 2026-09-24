import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.address_service import (
    FindingNotAcceptable,
    accept_decomposition,
    accept_finding,
    run_address_analysis,
    run_decomposition,
)
from app.models.tenant import AddressDecompositionResult, JunkAddress

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


# ─────────────────────────────────────────────────────────────────────────
# Zerlegung: split Address into SAP's ADRC target fields
# ─────────────────────────────────────────────────────────────────────────


class DecompositionSummaryOut(BaseModel):
    candidates: int
    sent_to_llm: int
    llm_resolved: int
    by_method: dict[str, int]
    by_confidence: dict[str, int]


@router.post("/zerlegung/run", response_model=DecompositionSummaryOut, status_code=status.HTTP_201_CREATED)
async def run_zerlegung(
    project_id: uuid.UUID, use_llm: bool = True, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Zerlegung: parse every eligible Mandant's Address into SAP's ADRC
    target fields (STREET/HOUSE_NUM1/STR_SUPPL1-3/BUILDING), replacing any
    previous run's proposals.
    """
    return await run_decomposition(db, project_id, use_llm=use_llm)


class DecompositionResultOut(BaseModel):
    id: uuid.UUID
    IDParty: str
    CompanyName: str | None
    CountryCode: str | None
    Address: str | None
    STREET: str
    HOUSE_NUM1: str
    STR_SUPPL1: str
    STR_SUPPL2: str
    STR_SUPPL3: str
    BUILDING: str
    StreetSpelledOut: str
    ParseMethod: str
    Confidence: str
    Hinweis: str
    Aktion: str

    model_config = {"from_attributes": True}


@router.get("/zerlegung", response_model=list[DecompositionResultOut])
async def list_zerlegung(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[AddressDecompositionResult]:
    result = await db.execute(
        select(AddressDecompositionResult)
        .where(AddressDecompositionResult.project_id == project_id)
        .order_by(AddressDecompositionResult.IDParty)
    )
    return list(result.scalars().all())


class AcceptDecompositionRequest(BaseModel):
    confidences: list[str]
    spell_out: bool = False


class AcceptDecompositionOut(BaseModel):
    updated: int


@router.post("/zerlegung/accept", response_model=AcceptDecompositionOut)
async def accept_zerlegung(
    project_id: uuid.UUID, payload: AcceptDecompositionRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Applies every proposal whose Confidence is in `confidences` (e.g.
    ["hoch"] or ["hoch", "mittel"]) to its Mandant record and removes those
    rows from the list - the original app's confidence-tiered "Übernahme".
    """
    return await accept_decomposition(db, project_id, payload.confidences, spell_out=payload.spell_out)
