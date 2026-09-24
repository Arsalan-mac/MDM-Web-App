import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.quality_service import (
    run_auftrag_id_project_check,
    run_communication_check,
    run_completeness_check,
    run_date_standardization,
    run_fuzzy_duplicate_check,
    run_register_number_check,
    run_value_cleanup,
)

router = APIRouter(prefix="/projects/{project_id}/quality", tags=["quality"])


class ValueCleanupRequest(BaseModel):
    bad_values: list[str]


class ValueCleanupOut(BaseModel):
    cleared: int


@router.post("/value-cleanup", response_model=ValueCleanupOut)
async def value_cleanup(
    project_id: uuid.UUID, payload: ValueCleanupRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """DB-Bereinigung: replace known junk values (exact match, e.g. '(Leer)',
    'NULL', '-') with empty across every Mandant text field, including `extra`."""
    return await run_value_cleanup(db, project_id, payload.bad_values)


class FuzzyMatchOut(BaseModel):
    id_party_i: str
    is_inactive_i: str | None
    company_name_i: str | None
    address_i: str | None
    city_i: str | None
    zip_code_i: str | None
    usercode_kummerer_i: str | None
    id_party_j: str
    is_inactive_j: str | None
    company_name_j: str | None
    address_j: str | None
    city_j: str | None
    zip_code_j: str | None
    usercode_kummerer_j: str | None
    country_code: str
    similarity_pct: float
    category: str


@router.post("/fuzzy-duplicates", response_model=list[FuzzyMatchOut])
async def fuzzy_duplicates(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[dict]:
    """TF-IDF + Nearest Neighbors duplicate detection, blocked by country
    (and ZIP prefix for large countries). Top 500 matches by similarity."""
    try:
        return await run_fuzzy_duplicate_check(db, project_id)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


class QualityReportRowOut(BaseModel):
    type: str
    total_clients: int
    total_valid: int
    total_junk: int
    total_empty: int
    pct_valid: float
    pct_junk: float
    pct_empty: float


class RegisterJunkOut(BaseModel):
    id_party: str
    company_name: str | None
    is_organisation: str | None
    is_individual: str | None
    is_inactive: str | None
    country_code: str | None
    register_number: str | None
    register_city: str | None
    register_court_kind_code: str | None
    reason: str


class RegisterNumberCheckOut(BaseModel):
    junk: list[RegisterJunkOut]
    quality_report: list[QualityReportRowOut]


@router.post("/register-number", response_model=RegisterNumberCheckOut)
async def register_number_check(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Register-Nr. junk detection (placeholders, no digits, dummy sequences,
    court/context text). Standardization lives in RegisterNumber Cleansing."""
    return await run_register_number_check(db, project_id)


class ContactIssueOut(BaseModel):
    id_party: str
    company_name: str | None
    is_organisation: str | None
    is_individual: str | None
    is_inactive: str | None
    invalid_value: str | None = None
    cleaned_value: str | None = None
    reason: str


class ContactCheckOut(BaseModel):
    issues: list[ContactIssueOut]
    quality_report: list[QualityReportRowOut]


class CommunicationCheckOut(BaseModel):
    email: ContactCheckOut
    website: ContactCheckOut
    phone: ContactCheckOut
    fax: ContactCheckOut


@router.post("/communication", response_model=CommunicationCheckOut)
async def communication_check(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Email / Website / Phone / Fax format checks."""
    return await run_communication_check(db, project_id)


class CompletenessRowOut(BaseModel):
    type: str
    attribute: str
    check_type: str
    total_rows: int
    count_relevant: int
    pct: float | None


@router.post("/completeness", response_model=list[CompletenessRowOut])
async def completeness_check(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[dict]:
    """Fill-rate per attribute, split by Organisation / Natuerliche Person."""
    return await run_completeness_check(db, project_id)


class DateChangeOut(BaseModel):
    old: str | None
    new: str


class DateStandardizationRowOut(BaseModel):
    id_party: str
    company_name: str | None
    changes: dict[str, DateChangeOut]


class DateStandardizationOut(BaseModel):
    updated: int
    preview: list[DateStandardizationRowOut]


@router.post("/date-standardization", response_model=DateStandardizationOut)
async def date_standardization(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Parses and rewrites DateFounded/LiquidationDate/RegisterCourtDate to
    YYYY-MM-DD in place (unlike every other check here, this one writes)."""
    return await run_date_standardization(db, project_id)


class AuftragIdProjectRowOut(BaseModel):
    id_party: str | None
    project_name: str | None
    added_date: str | None
    service_name: str | None


@router.post("/auftrag-id-project", response_model=list[AuftragIdProjectRowOut])
async def auftrag_id_project_check(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[dict]:
    """Flags Auftraege rows where (IDParty, ProjectName, AddedDate) share
    more than one distinct ServiceName."""
    return await run_auftrag_id_project_check(db, project_id)
