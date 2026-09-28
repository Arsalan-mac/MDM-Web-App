"""Report: aggregates a project's pipeline progress and outstanding
findings into one read-only summary, and offers a plain CSV export of
Mandanten. Doesn't touch any of the propose/accept tables it counts - an
"open finding" count here is simply that table's current row count, since
every accept flow (see address_service.py, register_cleansing_service.py)
removes a proposal's row once it's been applied.
"""

import csv
import io
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import (
    AddressDecompositionResult,
    Auftrag,
    GhostObject,
    JunkAddress,
    Mandant,
    RegisterCleansingResult,
)


async def _count(db: AsyncSession, model, project_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count()).select_from(model).where(model.project_id == project_id))
    return result.scalar_one()


async def get_summary(db: AsyncSession, project_id: uuid.UUID) -> dict:
    return {
        "mandant_count": await _count(db, Mandant, project_id),
        "auftrag_count": await _count(db, Auftrag, project_id),
        "ghost_count": await _count(db, GhostObject, project_id),
        "open_findings": {
            "junk_address": await _count(db, JunkAddress, project_id),
            "address_decomposition": await _count(db, AddressDecompositionResult, project_id),
            "register_cleansing": await _count(db, RegisterCleansingResult, project_id),
        },
    }


async def export_mandanten_csv(db: AsyncSession, project_id: uuid.UUID) -> str:
    """One row per Mandant. Typed columns first (declaration order, minus
    project_id), then every key ever seen in `extra` (sorted, so the header
    is stable across rows even though `extra`'s keys vary row to row)."""
    result = await db.execute(select(Mandant).where(Mandant.project_id == project_id).order_by(Mandant.IDParty))
    rows = result.scalars().all()

    # `attr.key` is the Python attribute name (e.g. "Name1"); a handful of
    # columns (Name 1-4) were declared with an explicit DB column name that
    # differs from it (mapped_column("Name 1", ...)), so `getattr` must use
    # the attribute key while the CSV header shows the more familiar DB name -
    # same mismatch already fixed once in sap_carp_service.py.
    typed_attrs = [
        (attr.key, attr.columns[0].name)
        for attr in Mandant.__mapper__.column_attrs
        if attr.key not in ("project_id", "extra")
    ]
    extra_keys: set[str] = set()
    for row in rows:
        extra_keys.update(row.extra.keys())
    header = [col_name for _, col_name in typed_attrs] + sorted(extra_keys)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        values = [getattr(row, attr_key) for attr_key, _ in typed_attrs]
        values += [row.extra.get(key, "") for key in sorted(extra_keys)]
        writer.writerow(values)
    return buffer.getvalue()
