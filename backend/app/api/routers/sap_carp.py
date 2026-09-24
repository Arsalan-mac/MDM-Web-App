import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.constants import FIELD_MAPPING_COLUMNS
from app.cleansing.load_data import UnsupportedFileType, harmonize_reference_dataframe, parse_uploaded_file
from app.cleansing.reference_tables import load_reference_table
from app.cleansing.sap_carp_service import (
    apply_name_split,
    clear_redundant_company_names,
    get_name_distribution_status,
    get_name_split_status,
    get_overwrite_status,
    load_sap_stammdaten,
    preview_name_split,
    run_name_distribution,
    run_overwrite,
)
from app.models.tenant import FieldMapping

router = APIRouter(prefix="/projects/{project_id}/sap-carp", tags=["sap-carp"])


def _parse_upload(filename: str | None, content: bytes):
    if not filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No file name on the upload.")
    try:
        df = parse_uploaded_file(filename, content)
    except (UnsupportedFileType, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file has no rows.")
    return harmonize_reference_dataframe(df)


class StammdatenUploadOut(BaseModel):
    row_count: int
    columns: list[str]
    sap_key_col: str
    dup_keys: int


@router.post("/stammdaten/upload", response_model=StammdatenUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_stammdaten(
    project_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Upload the 'SAP-Allgemeine Stammdaten' export (join key: 'IDParty' on
    newer exports, 'Ext. Partnernummer' on older ones)."""
    content = await file.read()
    df = _parse_upload(file.filename, content)
    try:
        return await load_sap_stammdaten(db, project_id, df, file.filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


class LoadSummaryOut(BaseModel):
    row_count: int
    columns: list[str]


@router.post("/field-mapping/upload", response_model=LoadSummaryOut, status_code=status.HTTP_201_CREATED)
async def upload_field_mapping(
    project_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Upload the Field-Mapping file: which Mandanten column each SAP column
    overwrites, and under what IsOrganisation condition."""
    content = await file.read()
    df = _parse_upload(file.filename, content)
    try:
        return await load_reference_table(db, project_id, FieldMapping, FIELD_MAPPING_COLUMNS, df, file.filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


class ColMapEntryOut(BaseModel):
    mandant_column: str
    sap_column: str
    condition: str | None


class OverwriteStatusOut(BaseModel):
    sap_ok: bool
    field_ok: bool
    mandant_ok: bool
    sap_key_col: str | None
    mapping_rows: int
    match_count: int
    already_flagged: int
    missing_sap: list[str]
    col_map: list[ColMapEntryOut]


@router.get("/overwrite/status", response_model=OverwriteStatusOut)
async def overwrite_status(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    return await get_overwrite_status(db, project_id)


class OverwriteRunRequest(BaseModel):
    reset_flag: bool = False


class OverwriteRunOut(BaseModel):
    flagged: int
    sap_rows: int
    reset_flag: bool


@router.post("/overwrite/run", response_model=OverwriteRunOut)
async def overwrite_run(
    project_id: uuid.UUID, payload: OverwriteRunRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Step 1: overwrite Mandanten fields with SAP values based on
    Field-Mapping, and flag every changed record as SapOverridden."""
    try:
        return await run_overwrite(db, project_id, reset_flag=payload.reset_flag)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


class NameDistributionStatusOut(BaseModel):
    affected_rows: int
    already_split: int


@router.get("/name-distribution/status", response_model=NameDistributionStatusOut)
async def name_distribution_status(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    return await get_name_distribution_status(db, project_id)


class NameDistributionRunRequest(BaseModel):
    chunk_size: int = 40


class NameDistributionRunOut(BaseModel):
    affected: int
    chunk_size: int


@router.post("/name-distribution/run", response_model=NameDistributionRunOut)
async def name_distribution_run(
    project_id: uuid.UUID, payload: NameDistributionRunRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Step 2: for IsOrganisation=1 rows, wrap CompanyName word-by-word into
    the SAP Name 1-4 export slots (Mandant.extra)."""
    return await run_name_distribution(db, project_id, chunk_size=payload.chunk_size)


class NameSplitStatusOut(BaseModel):
    candidate_count: int
    cleanup_count: int


@router.get("/name-split/status", response_model=NameSplitStatusOut)
async def name_split_status(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    return await get_name_split_status(db, project_id)


class NameSplitPreviewOut(BaseModel):
    id_party: str
    company_name: str
    first_name: str
    last_name: str
    method: str


@router.post("/name-split/preview", response_model=list[NameSplitPreviewOut])
async def name_split_preview(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[dict]:
    """Step 3: rule-based first/last-name split for natural persons
    (IsOrganisation=0) with no SAP override. Names of 3+ tokens and no comma
    are resolved via a batched Claude Haiku call when ANTHROPIC_API_KEY is
    configured; otherwise (or on an LLM error) they fall back to a
    first-token/rest split, method "unklar", same as the original app."""
    return await preview_name_split(db, project_id)


class NameSplitEntryIn(BaseModel):
    id_party: str
    first_name: str
    last_name: str


class NameSplitApplyRequest(BaseModel):
    entries: list[NameSplitEntryIn]


class NameSplitApplyOut(BaseModel):
    written: int


@router.post("/name-split/apply", response_model=NameSplitApplyOut)
async def name_split_apply(
    project_id: uuid.UUID, payload: NameSplitApplyRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    return await apply_name_split(db, project_id, [e.model_dump() for e in payload.entries])


class ClearCompanyNameOut(BaseModel):
    cleared: int


@router.post("/name-split/clear-company-name", response_model=ClearCompanyNameOut)
async def clear_company_name(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Empty CompanyName where FirstName+LastName are already filled in."""
    return await clear_redundant_company_names(db, project_id)
