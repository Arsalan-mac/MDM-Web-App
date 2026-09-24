"""Tables that live inside each tenant's own Postgres schema.

See app/db/base.py::TenantBase and app/db/tenancy.py for how the schema is
resolved per request.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TenantBase

# The fixed v1 pipeline, in order. Mirrors the original Streamlit app's
# sidebar nav (2202MandantenCleansing.py::nav_items) and its locking rules:
# a stage is locked until every stage before it in this list is "done".
# Phase 1c ports "load_data" and "address_cleansing"; the rest are added one
# at a time in Phase 2.
PIPELINE_STAGES: list[tuple[str, str]] = [
    ("load_data", "Load Data"),
    ("datenmodell", "Datenmodell-Erweiterung"),
    ("geisterobjekte", "Geisterobjekte"),
    ("sap_carp", "SAP-CARP-Ueberschreibung"),
    ("quality", "Quality Analysis"),
    ("report", "Report"),
    ("tax_cleansing", "Tax Cleansing"),
    ("address_cleansing", "Adress-Cleansing"),
    ("sap_template", "SAP Template Migration"),
    ("register_clean", "RegisterNumber Cleansing"),
    ("delete", "Delete Records"),
]


class Project(TenantBase):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stages: Mapped[list["Stage"]] = relationship(back_populates="project", order_by="Stage.position")

    def ensure_default_stages(self) -> list["Stage"]:
        """Build the fixed stage set for a newly created project."""
        stages = []
        for position, (key, label) in enumerate(PIPELINE_STAGES):
            stages.append(
                Stage(
                    project_id=self.id,
                    key=key,
                    label=label,
                    position=position,
                    status="in_progress" if position == 0 else "locked",
                )
            )
        return stages


class Stage(TenantBase):
    __tablename__ = "stages"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_stage_project_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="locked")  # locked | in_progress | done

    project: Mapped["Project"] = relationship(back_populates="stages")


class _MandantColumns:
    """Shared column set for `mandanten` and `geisterobjekte`.

    A ghost object (see GhostObject below) is exactly a Mandant snapshot
    moved to a separate table by the Geisterobjekte stage, so both tables
    have an identical shape - defined once here and mixed into both mapped
    classes, rather than duplicated.

    Field names intentionally keep the original CamelCase business names
    (IDParty, CompanyName, ...) rather than snake_case: they are external
    data field names shared with the rest of the still-to-be-ported domain
    logic (address/tax/register cleansing, SAP export mapping), not Python
    identifiers we control - see mdm_shared.py in the original app and
    app/cleansing/constants.py here.

    Only the standardized columns the ported pipeline stages actually read
    get their own column; every other column present in an uploaded file is
    preserved verbatim in `extra` so no source data is silently dropped.
    """

    # Composite PK: a tenant can run several migration Projects (unlike the
    # original app, which only ever had one workspace/DB per client), and
    # each has its own Mandanten universe - IDParty alone is only unique
    # within one project's source system, not across all of a tenant's
    # projects.
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    IDParty: Mapped[str] = mapped_column(String(64), primary_key=True)
    CompanyName: Mapped[str | None] = mapped_column(Text)
    CountryCode: Mapped[str | None] = mapped_column(String(10))
    Address: Mapped[str | None] = mapped_column(Text)
    City: Mapped[str | None] = mapped_column(Text)
    ZipCode: Mapped[str | None] = mapped_column(String(20))
    DistrictCode: Mapped[str | None] = mapped_column(String(32))
    VATNumber: Mapped[str | None] = mapped_column(String(64))
    IsOrganisation: Mapped[str | None] = mapped_column(String(8))
    IsIndividual: Mapped[str | None] = mapped_column(String(8))
    IsInactive: Mapped[str | None] = mapped_column(String(8))
    # Owner of a record (creator) vs. the person responsible for resolving its
    # data-quality issues (Kummerer) - both needed once Address Cleansing's
    # Nacharbeit step surfaces who should act on a finding.
    UserCode_Added: Mapped[str | None] = mapped_column(String(64))
    UserCode_Kummerer: Mapped[str | None] = mapped_column(String(64))
    FiscalCode: Mapped[str | None] = mapped_column(String(64))
    Email: Mapped[str | None] = mapped_column(String(320))
    WebSite: Mapped[str | None] = mapped_column(String(320))
    PhoneNumber: Mapped[str | None] = mapped_column(String(64))
    FaxNumber: Mapped[str | None] = mapped_column(String(64))
    DateFounded: Mapped[str | None] = mapped_column(String(32))
    LiquidationDate: Mapped[str | None] = mapped_column(String(32))
    RegisterCourtDate: Mapped[str | None] = mapped_column(String(32))

    # Read by Quality Analysis's Register-Nr. check (app/cleansing/
    # register_checks.py) and, later, the RegisterNumber Cleansing stage.
    RegisterNumber: Mapped[str | None] = mapped_column(String(64))
    RegisterCity: Mapped[str | None] = mapped_column(String(128))
    RegisterCourtKindCode: Mapped[str | None] = mapped_column(String(32))

    # Read by Tax Cleansing's VAT analysis, which backfills an empty
    # VATNumber from this field before checking it.
    ViesNumber: Mapped[str | None] = mapped_column(String(64))

    # Set by the SAP-CARP-Ueberschreibung stage. Excluded from every
    # downstream cleansing population, matching the original app's "Durch
    # SAP ueberschrieben" flag (address_common.FLAG_COL) - a proper bool
    # here rather than the original's "Ja"/"" string, since this is an
    # internal flag we set, not a raw field from an uploaded file.
    SapOverridden: Mapped[bool] = mapped_column(Boolean, default=False)

    # Written by SAP-CARP's Name Splitting step (natural persons only,
    # IsOrganisation="0") - kept as typed columns since that same step
    # reads them back (candidate/cleanup queries).
    FirstName: Mapped[str | None] = mapped_column(String(128))
    LastName: Mapped[str | None] = mapped_column(String(128))

    # Written by SAP-CARP's CompanyName -> Name 1-4 distribution step. Kept
    # in `extra` at first (nothing read them back yet - see docs/ROADMAP.md's
    # SAP-CARP-Ueberschreibung entry); promoted to typed columns now that
    # SAP Template Migration's BUT000-General sheet reads them. Original
    # field names ("Name 1", not "Name1") kept via an explicit column name
    # since they're the literal SAP mapping-spec source field references -
    # same pattern as MandantGegner's spaced column names below.
    Name1: Mapped[str | None] = mapped_column("Name 1", String(40))
    Name2: Mapped[str | None] = mapped_column("Name 2", String(40))
    Name3: Mapped[str | None] = mapped_column("Name 3", String(40))
    Name4: Mapped[str | None] = mapped_column("Name 4", String(40))

    # Read by SAP Template Migration's BUT000-General sheet. Generously
    # sized on purpose: source data can be messier/longer than the SAP
    # target field it feeds (TITLE/LEGAL_ENTY are 4/2 chars) - that's the
    # overflow-FLAG mechanism's job to catch downstream, not a storage limit.
    AddedDate: Mapped[str | None] = mapped_column(String(32))
    RoedlCompanyNumber: Mapped[str | None] = mapped_column(String(64))
    TitleCode: Mapped[str | None] = mapped_column(String(64))
    LegalFormCode: Mapped[str | None] = mapped_column(String(64))

    # Written by Address Cleansing's Zerlegung step (SAP address
    # decomposition) - split out of `Address` into SAP's ADRC target field
    # shape. Typed rather than `extra` since SAP Template Migration's ADRC
    # sheet reads them back. REGION intentionally has no column: the
    # original app stopped exporting it (Bundesland codes the SAP cockpit
    # rejected per-country), so ADRC's REGION target field maps to a
    # constant empty string instead - see app/cleansing/sap_template_mappings.py.
    STREET: Mapped[str | None] = mapped_column(String(60))
    HOUSE_NUM1: Mapped[str | None] = mapped_column(String(10))
    STR_SUPPL1: Mapped[str | None] = mapped_column(String(40))
    STR_SUPPL2: Mapped[str | None] = mapped_column(String(40))
    STR_SUPPL3: Mapped[str | None] = mapped_column(String(40))
    BUILDING: Mapped[str | None] = mapped_column(String(20))

    extra: Mapped[dict] = mapped_column(JSONB, default=dict)

    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))
    Change_Reason: Mapped[str] = mapped_column(String(255), default="")


class Mandant(_MandantColumns, TenantBase):
    __tablename__ = "mandanten"


class GhostObject(_MandantColumns, TenantBase):
    """Quarantined Mandant records with no connection to any Auftrag,
    ConnectedParty, or MandantGegner ('Geisterobjekte' in the original app).

    Unlike the original, there's no separate ID-tracking table: a record
    counts as quarantined simply by existing here instead of in `mandanten`.
    The original's separate tracking table existed to detect tampering via
    an external DB tool (someone editing the SQLite file directly) - a much
    smaller concern for a managed Postgres backend, so it's not carried
    forward; see app/cleansing/geisterobjekte_service.py.
    """

    __tablename__ = "geisterobjekte"


class Auftrag(TenantBase):
    """Client engagements/orders ('Auftraege' in the original app).

    Loaded as a plain reference table (see app/cleansing/reference_tables.py)
    - full replace per project, no column-alias mapping since these are
    fixed source-system field names, not user-facing data needing cleanup.
    Primarily exists so Geisterobjekte's ghost query can check "does this
    Mandant have any orders at all". Also read by Quality Analysis's
    Auftraege DQ / ID-Project check (ProjectName, AddedDate, ServiceName).
    """

    __tablename__ = "auftraege"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    IDProject: Mapped[str | None] = mapped_column(String(64))
    IDParty: Mapped[str | None] = mapped_column(String(64), index=True)
    ProjectNumber: Mapped[str | None] = mapped_column(String(64))
    Year: Mapped[str | None] = mapped_column(String(16))
    AssessmentYear: Mapped[str | None] = mapped_column(String(16))
    ProjectName: Mapped[str | None] = mapped_column(String(255))
    AddedDate: Mapped[str | None] = mapped_column(String(32))
    ServiceName: Mapped[str | None] = mapped_column(String(255))
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))


class ConnectedParty(TenantBase):
    """Related-party links ('VERBUNDENE_PARTEIEN' in the original app) -
    symmetric: a Mandant is connected if it appears as either IDParty or
    IDParty_Related on a row. Used by Geisterobjekte's ghost query.
    """

    __tablename__ = "verbundene_parteien"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    IDParty: Mapped[str | None] = mapped_column(String(64), index=True)
    IDParty_Related: Mapped[str | None] = mapped_column(String(64), index=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))


class MandantGegner(TenantBase):
    """Opponent-party links ('MANDANT_GEGNER' in the original app) - a
    Mandant is connected if it appears as either the client or the opponent
    side of a row. Used by Geisterobjekte's ghost query.

    Column names keep the original's literal (spaced) source field names via
    an explicit `name=` override, since standardize_columns only renames
    known aliases and these fixed names pass through unchanged on upload.
    """

    __tablename__ = "mandant_gegner"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ClientIDParty: Mapped[str | None] = mapped_column("Client - IDParty", String(64), index=True)
    OpponentIDParty: Mapped[str | None] = mapped_column("Opponent - IDParty", String(64), index=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))


class JunkAddress(TenantBase):
    """Findings from the Address Cleansing stage's Adress-Analyse check
    ('JUNK_ADDRESS' in the original app) - one row per flagged Mandant per
    field. Currently populated only by the Address field check
    (app/cleansing/address_checks.py); PLZ/City findings are added once the
    Referenzdaten stage (PLZ_RULES, GeoNames) is ported - see docs/ROADMAP.md.

    A snapshot of the Mandant's own data is stored alongside the finding (as
    in the original) so the findings list and Nacharbeit review don't need a
    join back to `mandanten` - and so a finding still shows accurate context
    even if the record changes before it's reviewed.
    """

    __tablename__ = "junk_address"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    IDParty: Mapped[str] = mapped_column(String(64), index=True)

    UserCode_Added: Mapped[str | None] = mapped_column(String(64))
    UserCode_Kummerer: Mapped[str | None] = mapped_column(String(64))
    CompanyName: Mapped[str | None] = mapped_column(Text)
    IsOrganisation: Mapped[str | None] = mapped_column(String(8))
    IsIndividual: Mapped[str | None] = mapped_column(String(8))
    IsInactive: Mapped[str | None] = mapped_column(String(8))
    Address: Mapped[str | None] = mapped_column(Text)
    City: Mapped[str | None] = mapped_column(Text)
    ZipCode: Mapped[str | None] = mapped_column(String(20))
    CountryCode: Mapped[str | None] = mapped_column(String(10))
    Reason: Mapped[str] = mapped_column(Text, default="")

    # The proposed fix: set Mandant.<Feld> from Alt to Neu.
    Feld: Mapped[str] = mapped_column(String(32))
    Alt: Mapped[str | None] = mapped_column(Text)
    Neu: Mapped[str | None] = mapped_column(Text)
    Kategorie: Mapped[str] = mapped_column(String(64))
    Aktion: Mapped[str] = mapped_column(String(16))  # ERSETZEN | LEEREN | MANUELL
    Confidence: Mapped[str] = mapped_column(String(16), default="")  # hoch | mittel | niedrig | ""

    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AddressDecompositionResult(TenantBase):
    """Proposals from Address Cleansing's Zerlegung step ('SAP_ADDRESS_
    RESULT' in the original app) - splits `Mandant.Address` into SAP's ADRC
    target fields (STREET/HOUSE_NUM1/STR_SUPPL1-3/BUILDING). One row per
    candidate Mandant, all six proposed fields together (unlike JunkAddress,
    which is one row per single-field finding) - a tiered regex parser
    handles the bulk of cases, with a Claude Haiku fallback for addresses
    it can't confidently split (same pattern as SAP-CARP's Name Splitting).
    """

    __tablename__ = "address_decomposition_result"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    IDParty: Mapped[str] = mapped_column(String(64), index=True)

    CompanyName: Mapped[str | None] = mapped_column(Text)
    CountryCode: Mapped[str | None] = mapped_column(String(10))
    Address: Mapped[str | None] = mapped_column(Text)

    STREET: Mapped[str] = mapped_column(String(60), default="")
    HOUSE_NUM1: Mapped[str] = mapped_column(String(10), default="")
    STR_SUPPL1: Mapped[str] = mapped_column(String(40), default="")
    STR_SUPPL2: Mapped[str] = mapped_column(String(40), default="")
    STR_SUPPL3: Mapped[str] = mapped_column(String(40), default="")
    BUILDING: Mapped[str] = mapped_column(String(20), default="")
    StreetSpelledOut: Mapped[str] = mapped_column(String(60), default="")  # "Str." -> "Straße"/"Strasse"

    ParseMethod: Mapped[str] = mapped_column(String(16))
    Confidence: Mapped[str] = mapped_column(String(16), default="")  # hoch | mittel | ""
    Hinweis: Mapped[str] = mapped_column(Text, default="")
    Aktion: Mapped[str] = mapped_column(String(16))  # ERSETZEN | MANUELL

    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SapStammdaten(TenantBase):
    """Raw upload of the 'SAP-Allgemeine Stammdaten' export used by
    SAP-CARP-Ueberschreibung to overwrite Mandant fields.

    Unlike the other reference tables, this file's columns aren't a fixed,
    known set - which Mandant column a given SAP column feeds is decided at
    upload time by whatever the user's Field-Mapping file says, so the
    entire row is kept in `data` rather than split into typed columns.
    `sap_key` is the one column resolved and indexed at upload time (the
    join key: 'IDParty' on new exports, 'Ext. Partnernummer' on older ones -
    see app/cleansing/sap_carp_service.py::_resolve_sap_key), so the
    overwrite join doesn't need to inspect the JSONB column for every row.
    """

    __tablename__ = "sap_stammdaten"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    sap_key: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))


class FieldMapping(TenantBase):
    """Which Mandant column each SAP-Allgemeine-Stammdaten column overwrites,
    and under what IsOrganisation condition ('Field-Mapping' in the original
    app). A small, structured file (unlike SapStammdaten's arbitrary bag of
    business columns), so it gets real typed columns - `extra` still catches
    any additional columns the uploaded file happens to carry.

    Column names keep the original's literal (spaced) header names via an
    explicit `name=` override, matching the MandantGegner pattern.
    """

    __tablename__ = "field_mapping"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    MandantColumn: Mapped[str | None] = mapped_column("Mandanten", String(128))
    SapColumn: Mapped[str | None] = mapped_column("SAP-Allgemeine Stammdaten", String(128))
    Condition: Mapped[str | None] = mapped_column("Condition", String(64))
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))


class FiscalRule(TenantBase):
    """Editable country/entity-type FiscalCode format rule ('FISCAL_RULES' in
    the original app), used by Tax Cleansing's Steuernummer-Cleansing check.

    Scoped per-project (like FieldMapping/SapStammdaten) rather than shared
    across a tenant's projects - this codebase has no existing concept of
    tenant-wide shared config, and the original's own scope was one ruleset
    per workspace, which a Project is the closest match to here. Lazily
    seeded from FISCAL_RULES_SEED (app/cleansing/fiscal_rules_seed.py) the
    first time a project's rules are read, exactly like the original's
    ensure_fiscal_rules_table.
    """

    __tablename__ = "fiscal_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "CountryCode", "EntityType", name="uq_fiscal_rule_project_country_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    CountryCode: Mapped[str] = mapped_column(String(4))
    EntityType: Mapped[str] = mapped_column(String(16))  # ORG | IND | GENERIC
    SapCode: Mapped[str | None] = mapped_column(String(16))
    Regex: Mapped[str] = mapped_column(Text)
    RegexAliases: Mapped[list] = mapped_column(JSONB, default=list)
    Description: Mapped[str] = mapped_column(Text, default="")
    SourceUrl: Mapped[str | None] = mapped_column(String(512))
    Confidence: Mapped[str] = mapped_column(String(8), default="HIGH")  # HIGH | MEDIUM | LOW
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VatMapping(TenantBase):
    """Editable country -> SAP TAXTYPE code table for the VAT migration track
    ('VAT_MAPPING' in the original app). Scoped per-project like FiscalRule;
    lazily seeded from VAT_MAPPING_SEED (app/cleansing/vat_mapping_seed.py).
    """

    __tablename__ = "vat_mapping"
    __table_args__ = (UniqueConstraint("project_id", "SapCode", name="uq_vat_mapping_project_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    SapCode: Mapped[str] = mapped_column(String(8))
    Region: Mapped[str] = mapped_column(String(16))  # "EU / Europe" | "Non-EU"
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxMigrationResult(TenantBase):
    """One row per Mandant per migration track ('TAX_MIGRATION_RESULT' in the
    original app) - the SAP-import-ready TAXTYPE/TAXNUML/TAXNUMXL assignment
    produced by Tax Cleansing's Migration Preparation. A full replace of one
    Migration value's rows per run; the other track's rows are untouched.

    No unique constraint: a split Russian VAT value produces two rows (INN
    and KPP) sharing the same IDParty, exactly like the original.
    """

    __tablename__ = "tax_migration_result"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    Migration: Mapped[str] = mapped_column(String(16))  # VAT | STEUERNUMMER
    IDParty: Mapped[str] = mapped_column(String(64), index=True)
    SourceValue: Mapped[str] = mapped_column(String(64))
    TAXTYPE: Mapped[str] = mapped_column(String(8))
    TAXNUML: Mapped[str | None] = mapped_column(String(20))
    TAXNUMXL: Mapped[str | None] = mapped_column(String(64))
    CountryCode: Mapped[str | None] = mapped_column(String(4))
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxtypeRemap(TenantBase):
    """Persistent source->target TAXTYPE code correction ('TAXTYPE_REMAP' in
    the original app), re-applied to TaxMigrationResult on every migration
    run - typically used to resolve an UNKNOWN/OBSOLETE finding globally.
    """

    __tablename__ = "taxtype_remap"
    __table_args__ = (UniqueConstraint("project_id", "SourceCode", name="uq_taxtype_remap_project_source"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    SourceCode: Mapped[str] = mapped_column(String(8))
    TargetCode: Mapped[str] = mapped_column(String(8))
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxtypeRowFix(TenantBase):
    """Row-level TAXTYPE correction ('TAXTYPE_ROW_FIX' in the original app)
    keyed by (IDParty, Migration, SourceCode) - resolves a KEY_COLLISION
    finding for one specific row rather than every row with that source
    code, re-applied to TaxMigrationResult on every migration run.
    """

    __tablename__ = "taxtype_row_fix"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "IDParty", "Migration", "SourceCode", name="uq_taxtype_row_fix_project_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    IDParty: Mapped[str] = mapped_column(String(64))
    Migration: Mapped[str] = mapped_column(String(16))
    SourceCode: Mapped[str] = mapped_column(String(8))
    TargetCode: Mapped[str] = mapped_column(String(8))
    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegisterCleansingResult(TenantBase):
    """Proposals from RegisterNumber Cleansing ('REGISTER_CLEANSING_RESULT'
    in the original app) - standardizes Mandant.RegisterNumber via a
    two-stage pipeline: Stufe 2 deterministic prefix/whitespace
    normalization ("HRB3792" -> "HRB 3792"), then Stufe 3 Claude Haiku
    cleanup for special forms (legacy "HRN" prefix, embedded court text)
    that Stufe 2 can't handle. Junk values (Quality Analysis's Register-Nr.
    check, app/cleansing/register_checks.py) are excluded entirely - this
    stage only ever proposes a change for a value that's already usable,
    never invents a number for one that isn't.
    """

    __tablename__ = "register_cleansing_result"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    IDParty: Mapped[str] = mapped_column(String(64), index=True)

    CompanyName: Mapped[str | None] = mapped_column(Text)
    CountryCode: Mapped[str | None] = mapped_column(String(10))
    RegisterCity: Mapped[str] = mapped_column(String(128), default="")

    RegisterNumber_Alt: Mapped[str] = mapped_column(String(64))
    RegisterNumber_Neu: Mapped[str] = mapped_column(String(64))
    Stufe: Mapped[str] = mapped_column(String(16))  # STANDARD | LLM
    Confidence: Mapped[str] = mapped_column(String(16))  # HIGH | MEDIUM | LOW
    Begruendung: Mapped[str] = mapped_column(Text, default="")

    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
