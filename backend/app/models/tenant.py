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


class Mandant(TenantBase):
    """The client master-data table ('Mandanten' in the original app).

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

    __tablename__ = "mandanten"

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

    # Set by the (not-yet-ported) SAP-CARP-Ueberschreibung stage. Excluded
    # from every downstream cleansing population, matching the original
    # app's "Durch SAP ueberschrieben" flag (address_common.FLAG_COL) - a
    # proper bool here rather than the original's "Ja"/"" string, since this
    # is an internal flag we set, not a raw field from an uploaded file.
    SapOverridden: Mapped[bool] = mapped_column(Boolean, default=False)

    extra: Mapped[dict] = mapped_column(JSONB, default=dict)

    Load_Date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    Source_FILE: Mapped[str | None] = mapped_column(String(255))
    Change_Reason: Mapped[str] = mapped_column(String(255), default="")


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
