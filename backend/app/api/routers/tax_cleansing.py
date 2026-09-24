import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.tax_service import (
    list_fiscal_rules,
    reset_fiscal_rules,
    run_fiscal_code_analysis,
    run_vat_analysis,
    run_vat_duplicate_check,
    upsert_fiscal_rules,
)

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


class FiscalRuleOut(BaseModel):
    country_code: str = Field(alias="CountryCode")
    entity_type: str = Field(alias="EntityType")
    sap_code: str | None = Field(alias="SapCode")
    regex: str = Field(alias="Regex")
    aliases: list[str] = Field(alias="RegexAliases")
    description: str = Field(alias="Description")
    source_url: str | None = Field(alias="SourceUrl")
    confidence: str = Field(alias="Confidence")

    model_config = {"from_attributes": True, "populate_by_name": True}


@router.get("/fiscal-rules", response_model=list[FiscalRuleOut], response_model_by_alias=False)
async def get_fiscal_rules(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list:
    """This project's FiscalCode validation rules (seeded from the official
    reference set on first read)."""
    return await list_fiscal_rules(db, project_id)


class FiscalRuleIn(BaseModel):
    country_code: str
    entity_type: str
    sap_code: str = ""
    regex: str
    aliases: list[str] = []
    description: str = ""
    source_url: str = ""
    confidence: str = "HIGH"


class SaveFiscalRulesRequest(BaseModel):
    rules: list[FiscalRuleIn]


class SaveFiscalRulesOut(BaseModel):
    saved: int


@router.post("/fiscal-rules", response_model=SaveFiscalRulesOut)
async def save_fiscal_rules(
    project_id: uuid.UUID, payload: SaveFiscalRulesRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Add or update rules by (country_code, entity_type)."""
    saved = await upsert_fiscal_rules(db, project_id, [r.model_dump() for r in payload.rules])
    return {"saved": saved}


class ResetFiscalRulesOut(BaseModel):
    rule_count: int


@router.post("/fiscal-rules/reset", response_model=ResetFiscalRulesOut)
async def reset_fiscal_rules_endpoint(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Discards this project's rule edits and reseeds from the code defaults."""
    return {"rule_count": await reset_fiscal_rules(db, project_id)}


class FiscalJunkRowOut(BaseModel):
    id_party: str
    company_name: str | None
    is_organisation: str | None
    is_individual: str | None
    is_inactive: str | None
    country_code: str | None
    fiscal_code: str
    reason: str
    allowed_pattern: str


class FiscalCodeAnalysisOut(BaseModel):
    junk: list[FiscalJunkRowOut]
    quality_report: list[QualityReportRowOut]


@router.post("/fiscal-code/analyze", response_model=FiscalCodeAnalysisOut)
async def analyze_fiscal_code(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """2-stage FiscalCode check: syntax junk, then pattern validation against
    this project's country/entity-type rules."""
    return await run_fiscal_code_analysis(db, project_id)
