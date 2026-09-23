"""Tables that live inside each tenant's own Postgres schema.

See app/db/base.py::TenantBase and app/db/tenancy.py for how the schema is
resolved per request.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
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
