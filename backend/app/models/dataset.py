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


class DatasetRelation(TenantBase):
    """A named, reusable link between two datasets - the generic analogue
    of e.g. SAP's KNA1 (customer master) to KNVV (sales areas): one column
    in each dataset that should hold matching values, and the cardinality
    the relationship is supposed to have.

    Doesn't enforce anything on its own - it's a declaration other things
    read: a `cross_dataset_exists` custom check (app/checks/custom.py) uses
    one to check every row on the "from" side has a match on the "to"
    side (the generic form of the old fixed-schema Geisterobjekte check),
    and the planned Mapping/Transform Studio will use the same relations
    to join data across tables when building a target field.
    """

    __tablename__ = "dataset_relations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))

    from_dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    from_column: Mapped[str] = mapped_column(String(255))

    to_dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    to_column: Mapped[str] = mapped_column(String(255))

    # one_to_one | one_to_many | many_to_many - from_dataset's side first,
    # e.g. one Customer -> many SalesAreas is "one_to_many".
    cardinality: Mapped[str] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomCheckDefinition(TenantBase):
    """A user-defined check - no Python required. `rule_type` picks one of
    a small fixed set of generic rule interpreters (app/checks/custom.py:
    required, regex, in_list, range, unique, cross_dataset_exists), and
    `params` configures it (which column, the pattern/list/range, or - for
    cross_dataset_exists - which DatasetRelation to check against).

    Scoped to one dataset (`dataset_id`) even for cross_dataset_exists,
    since a finding is always reported against a row of *some* dataset -
    the relation's from_dataset must match this check's dataset_id for
    that rule type.

    Every dataset can have zero of these - checks are always opt-in, never
    assumed, which is the whole point: not every table needs (or has) any
    checks defined for it.
    """

    __tablename__ = "custom_check_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    rule_type: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # error | warning | info

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MappingDefinition(TenantBase):
    """A saved recipe for building a new table out of one source Dataset -
    the generic analogue of the old fixed SAP Template Migration step (BUT000/
    ADRC mapping), but for any target shape, not just an SAP import file.

    `fields` is an ordered list of target-field specs, each
    {"target": <output column name>, "kind": ..., "config": {...}}:
      - "column":         config={"column": <source column>} - copy verbatim.
      - "constant":       config={"value": <literal>} - same value every row.
      - "concat":         config={"columns": [...], "separator": " "} - join
                           several source columns into one output value.
      - "relation_lookup": config={"relation_id": <DatasetRelation id>,
                           "column": <column on the relation's "to" dataset>}
                           - pulls a value from a *related* dataset via a
                           DatasetRelation (this mapping's source dataset must
                           be that relation's from_dataset), the first place
                           Relations get used for something other than checks.

    No Python or SQL from the user - the AI-assisted suggest endpoint
    (app/cleansing/mapping_service.py::suggest_mapping) proposes "column"
    mappings by name/value similarity, which the user reviews before saving.
    """

    __tablename__ = "mapping_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    source_dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), index=True)
    fields: Mapped[list] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
