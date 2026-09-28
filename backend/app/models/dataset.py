"""Generic, schema-agnostic dataset storage - the foundation for making this
app work with any data model (SAP or not), not just the fixed Mandanten
shape in app/models/tenant.py.

A Dataset is any uploaded table (Mandanten, Customers, Orders, whatever the
user calls it) with an arbitrary, discovered-at-upload-time column list.
Each row is stored as a JSONB blob rather than fixed typed columns, so
nothing about the app needs to know a dataset's shape ahead of time.

`role_mapping` is how a Check (see app/checks/base.py) that was written
against semantic roles ("vat_number", "country_code", ...) finds the real
column that plays that role in *this* dataset - set once per dataset
(by the user, or later by the AI mapping assistant), read by every check
run against it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class Dataset(TenantBase):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    source_filename: Mapped[str | None] = mapped_column(String(255))

    # Column names in upload order - the full set of fields this dataset's
    # rows may have. Not every row necessarily has every key (sparse
    # source files happen), but this is the header a table view renders.
    columns: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Which column (if any) uniquely identifies a row - e.g. "IDParty",
    # "CustomerID", or nothing if the source file has no natural key, in
    # which case DatasetRow.row_key falls back to a generated UUID.
    primary_key_column: Mapped[str | None] = mapped_column(String(255))

    # {role_key: column_name}, e.g. {"vat_number": "VATNumber",
    # "country_code": "Country"} - see app/checks/base.py.
    role_mapping: Mapped[dict] = mapped_column(JSONB, default=dict)

    row_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetRow(TenantBase):
    __tablename__ = "dataset_rows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)

    # Dataset.primary_key_column's value for this row, or a generated UUID
    # when the dataset has no natural key - how findings/mapping results
    # reference "this specific row" without caring what the key means.
    row_key: Mapped[str] = mapped_column(String(255), index=True)
    row_index: Mapped[int] = mapped_column(Integer)

    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class CheckFinding(TenantBase):
    """One finding from running a Check (app/checks/base.py) against a
    Dataset row. Deliberately generic (a `check_key` string, not a table
    per check) so adding a new check never needs a migration."""

    __tablename__ = "check_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    row_key: Mapped[str] = mapped_column(String(255), index=True)

    check_key: Mapped[str] = mapped_column(String(64), index=True)
    field: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(16))  # error | warning | info
    message: Mapped[str] = mapped_column(String)

    # The check's suggested replacement value for `field`, if it has one -
    # accepting a finding writes this into the row's `data[field]`.
    proposed_value: Mapped[str | None] = mapped_column(String)

    status: Mapped[str] = mapped_column(String(16), default="open")  # open | accepted | dismissed

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
