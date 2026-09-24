"""Delete Records: nullify selected columns for all rows, or for rows
matching an uploaded ID list - never physically removes rows, matching the
original app's own explicit design ("Rows are never physically removed —
only the selected field values are cleared").

Ported from 2202MandantenCleansing.py::app_delete_ui, which let a user pick
ANY table and ANY column in the original's single-workspace SQLite
database. This app's tenant schema holds several *projects*' data side by
side (the original never had that concept), so every operation here is
additionally scoped to the current project - a scope boundary the original
simply didn't need. Table/column names come from this app's own SQLAlchemy
metadata (not a raw "list what's in the database" query, since there's no
possibility of an arbitrary user-created table here) and are validated
against it before any query is built - never interpolated from client
input directly, unlike the original's f-string SQL (which got away with it
only because its own dropdowns were themselves populated from a real
PRAGMA table_info call).

`project_id`, and each table's own primary-key column(s), are excluded
from the *clearable* column list (nulling either would break either tenant
scoping or the row's own identity) - but not from the *matching* column
list for ID-list mode, where matching by the primary key (e.g. IDParty) is
exactly the point.
"""

import uuid

from sqlalchemy import Table, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import TenantBase

# SQLAlchemy's declarative metadata only registers a table once its model
# class has actually been imported somewhere - importing the models module
# here guarantees TenantBase.metadata.tables is complete regardless of
# what else has (or hasn't) been imported yet in the current process.
import app.models.tenant  # noqa: F401

_EXCLUDED_TABLES = {"projects", "stages"}
_ALWAYS_EXCLUDED_FROM_CLEAR = {"project_id"}


def _content_tables() -> dict[str, Table]:
    return {
        name: table
        for name, table in TenantBase.metadata.tables.items()
        if name not in _EXCLUDED_TABLES
    }


def list_tables() -> list[dict]:
    """One entry per content table: its name, every column (for ID-list
    matching), and the subset of columns safe to clear (excludes project_id
    and primary-key columns).
    """
    result = []
    for name, table in sorted(_content_tables().items()):
        pk_cols = {c.name for c in table.primary_key.columns}
        all_cols = [c.name for c in table.columns]
        clearable = [c for c in all_cols if c not in pk_cols and c not in _ALWAYS_EXCLUDED_FROM_CLEAR]
        result.append({"table": name, "columns": all_cols, "clearable_columns": clearable})
    return result


class InvalidTableOrColumn(ValueError):
    pass


def _validated_table_and_columns(table_name: str, columns: list[str], *, for_clearing: bool) -> Table:
    tables = _content_tables()
    table = tables.get(table_name)
    if table is None:
        raise InvalidTableOrColumn(f"Unknown table: {table_name!r}")
    valid_cols = {c.name for c in table.columns}
    if for_clearing:
        pk_cols = {c.name for c in table.primary_key.columns}
        valid_cols -= pk_cols
        valid_cols -= _ALWAYS_EXCLUDED_FROM_CLEAR
    unknown = [c for c in columns if c not in valid_cols]
    if unknown:
        raise InvalidTableOrColumn(f"Not a clearable column of {table_name!r}: {', '.join(unknown)}")
    return table


async def clear_all_rows(db: AsyncSession, project_id: uuid.UUID, table_name: str, columns: list[str]) -> int:
    """Sets `columns` to NULL for every row of `table_name` in this project.
    Returns the number of rows updated."""
    if not columns:
        return 0
    table = _validated_table_and_columns(table_name, columns, for_clearing=True)
    stmt = update(table).where(table.c.project_id == project_id).values(**{c: None for c in columns})
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def clear_by_ids(
    db: AsyncSession,
    project_id: uuid.UUID,
    table_name: str,
    columns: list[str],
    db_id_col: str,
    id_list: list[str],
) -> int:
    """Sets `columns` to NULL for rows of `table_name` in this project where
    `db_id_col` matches one of `id_list`. Returns the number of rows updated.
    """
    if not columns or not id_list:
        return 0
    table = _validated_table_and_columns(table_name, columns, for_clearing=True)
    # db_id_col is validated against the full column set (matching by a
    # primary key like IDParty is the whole point of this mode).
    _validated_table_and_columns(table_name, [db_id_col], for_clearing=False)
    stmt = (
        update(table)
        .where(table.c.project_id == project_id, table.c[db_id_col].in_(id_list))
        .values(**{c: None for c in columns})
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
