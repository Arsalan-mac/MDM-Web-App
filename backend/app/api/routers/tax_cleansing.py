import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.tax_service import (
    apply_taxtype_remap,
    apply_taxtype_row_fixes,
    delete_taxtype_remaps,
    delete_taxtype_row_fixes,
    list_fiscal_rules,
    list_taxtype_remaps,
    list_taxtype_row_fixes,
    list_vat_mapping,
    reset_fiscal_rules,
    reset_vat_mapping,
    run_fiscal_code_analysis,
    run_steuer_migration,
    run_taxtype_validation,
    run_vat_analysis,
    run_vat_duplicate_check,
    run_vat_migration,
    save_taxtype_remap_entry,
    save_taxtype_row_fix_entry,
    save_vat_mapping,
    suggest_collision_code,
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


# ─────────────────────────────────────────────────────────────────────────
# Migration Preparation
# ─────────────────────────────────────────────────────────────────────────


class VatMappingOut(BaseModel):
    code: str = Field(alias="SapCode")
    region: str = Field(alias="Region")

    model_config = {"from_attributes": True, "populate_by_name": True}


@router.get("/vat-mapping", response_model=list[VatMappingOut], response_model_by_alias=False)
async def get_vat_mapping(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list:
    """This project's country -> TAXTYPE mapping used by the VAT migration
    track (seeded from the official defaults on first read)."""
    return await list_vat_mapping(db, project_id)


class VatMappingEntryIn(BaseModel):
    code: str
    region: str = "Non-EU"


class SaveVatMappingRequest(BaseModel):
    entries: list[VatMappingEntryIn]


class SaveVatMappingOut(BaseModel):
    saved: int


@router.post("/vat-mapping", response_model=SaveVatMappingOut)
async def save_vat_mapping_endpoint(
    project_id: uuid.UUID, payload: SaveVatMappingRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Full replace of this project's VAT mapping table."""
    saved = await save_vat_mapping(db, project_id, [e.model_dump() for e in payload.entries])
    return {"saved": saved}


class ResetVatMappingOut(BaseModel):
    row_count: int


@router.post("/vat-mapping/reset", response_model=ResetVatMappingOut)
async def reset_vat_mapping_endpoint(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    return {"row_count": await reset_vat_mapping(db, project_id)}


class TaxtypeValidationFindingOut(BaseModel):
    migration: str
    id_party: str
    source_value: str
    taxtype: str
    country_code: str | None
    finding: str
    sap_description: str


class TaxtypeValidationOut(BaseModel):
    error: str | None = None
    total: int | None = None
    unknown: int | None = None
    obsolete: int | None = None
    mismatch: int | None = None
    vat_hint: int | None = None
    collision: int | None = None
    findings: list[TaxtypeValidationFindingOut] | None = None


class MigrationRunOut(BaseModel):
    total_raw: int
    total_junk_removed: int
    total_empty_removed: int
    migrated: int
    validation: TaxtypeValidationOut


@router.post("/migration/vat", response_model=MigrationRunOut)
async def run_vat_migration_endpoint(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Builds the VAT-track rows of TaxMigrationResult and re-runs TAXTYPE
    validation. Replaces only this project's VAT-migration rows."""
    return await run_vat_migration(db, project_id)


@router.post("/migration/steuernummer", response_model=MigrationRunOut)
async def run_steuer_migration_endpoint(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Builds the STEUERNUMMER-track rows of TaxMigrationResult and re-runs
    TAXTYPE validation. Replaces only this project's Steuernummer rows."""
    return await run_steuer_migration(db, project_id)


@router.get("/migration/validation", response_model=TaxtypeValidationOut)
async def get_taxtype_validation(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Re-derives the TAXTYPE validation findings from the current
    TaxMigrationResult, without running a migration."""
    return await run_taxtype_validation(db, project_id)


@router.get("/migration/collision-suggestion", response_model=dict)
async def get_collision_suggestion(country_code: str, current_code: str, migration: str) -> dict:
    """A suggested replacement code for a KEY_COLLISION finding."""
    return {"suggested_code": suggest_collision_code(country_code.strip().upper(), current_code.strip().upper(), migration)}


class TaxtypeRemapOut(BaseModel):
    source_code: str = Field(alias="SourceCode")
    target_code: str = Field(alias="TargetCode")

    model_config = {"from_attributes": True, "populate_by_name": True}


@router.get("/taxtype-remap", response_model=list[TaxtypeRemapOut], response_model_by_alias=False)
async def get_taxtype_remaps(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list:
    return await list_taxtype_remaps(db, project_id)


class SaveTaxtypeRemapRequest(BaseModel):
    source_code: str
    target_code: str


@router.post("/taxtype-remap", status_code=204)
async def save_taxtype_remap_endpoint(
    project_id: uuid.UUID, payload: SaveTaxtypeRemapRequest, db: AsyncSession = Depends(get_tenant_db)
) -> None:
    """Persists a global source->target TAXTYPE correction. Takes effect on
    the next migration run (VAT or Steuernummer)."""
    await save_taxtype_remap_entry(db, project_id, payload.source_code, payload.target_code)


class DeleteTaxtypeRemapRequest(BaseModel):
    source_codes: list[str]


class DeleteOut(BaseModel):
    deleted: int


@router.post("/taxtype-remap/delete", response_model=DeleteOut)
async def delete_taxtype_remaps_endpoint(
    project_id: uuid.UUID, payload: DeleteTaxtypeRemapRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    return {"deleted": await delete_taxtype_remaps(db, project_id, payload.source_codes)}


class TaxtypeRowFixOut(BaseModel):
    id_party: str = Field(alias="IDParty")
    migration: str = Field(alias="Migration")
    source_code: str = Field(alias="SourceCode")
    target_code: str = Field(alias="TargetCode")

    model_config = {"from_attributes": True, "populate_by_name": True}


@router.get("/taxtype-row-fix", response_model=list[TaxtypeRowFixOut], response_model_by_alias=False)
async def get_taxtype_row_fixes(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list:
    return await list_taxtype_row_fixes(db, project_id)


class SaveTaxtypeRowFixRequest(BaseModel):
    id_party: str
    migration: str
    source_code: str
    target_code: str


@router.post("/taxtype-row-fix", status_code=204)
async def save_taxtype_row_fix_endpoint(
    project_id: uuid.UUID, payload: SaveTaxtypeRowFixRequest, db: AsyncSession = Depends(get_tenant_db)
) -> None:
    """Persists a row-level TAXTYPE correction for one (IDParty, Migration,
    source code). Takes effect on the next migration run."""
    await save_taxtype_row_fix_entry(
        db, project_id, payload.id_party, payload.migration, payload.source_code, payload.target_code
    )


class DeleteTaxtypeRowFixRequest(BaseModel):
    keys: list[tuple[str, str, str]]


@router.post("/taxtype-row-fix/delete", response_model=DeleteOut)
async def delete_taxtype_row_fixes_endpoint(
    project_id: uuid.UUID, payload: DeleteTaxtypeRowFixRequest, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    return {"deleted": await delete_taxtype_row_fixes(db, project_id, payload.keys)}
