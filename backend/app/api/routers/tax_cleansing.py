import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.tax_service import run_vat_analysis, run_vat_duplicate_check

router = APIRouter(prefix="/projects/{project_id}/tax-cleansing", tags=["tax-cleansing"])


class QualityReportRowOut(BaseModel):
    type: str
    total_clients: int
    total_valid: int
    total_junk: int
    total_empty: int
    pct_valid: float
    pct_junk: float
    pct_empty: float


class RuPrecleaningRowOut(BaseModel):
    id_party: str
    company_name: str | None
    is_organisation: str | None
    is_individual: str | None
    is_inactive: str | None
    country_code: str | None
    vat_number_original: str
    inn_cleaned: str
    kpp_cleaned: str
    reason: str


class VatJunkRowOut(BaseModel):
    id_party: str
    company_name: str | None
    is_organisation: str | None
    is_individual: str | None
    is_inactive: str | None
    country_code: str | None
    vat_number: str
    reason: str
    rule_used: str


class VatAnalysisOut(BaseModel):
    vies_backfilled: int
    ru_precleaning: list[RuPrecleaningRowOut]
    junk: list[VatJunkRowOut]
    quality_report: list[QualityReportRowOut]


@router.post("/vat/analyze", response_model=VatAnalysisOut)
async def analyze_vat(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Unified VAT analysis: backfills empty VATNumber from ViesNumber,
    applies CH/NO pre-cleaning and RU INN/KPP splitting, then checks every
    VAT number for syntax junk and against its country's pattern."""
    return await run_vat_analysis(db, project_id)


class VatDuplicateRowOut(BaseModel):
    id_party: str
    company_name: str | None
    vat_number: str


@router.post("/vat/duplicates", response_model=list[VatDuplicateRowOut])
async def vat_duplicates(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[dict]:
    """Mandanten sharing the same normalized VAT number."""
    return await run_vat_duplicate_check(db, project_id)
