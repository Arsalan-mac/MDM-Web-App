"""Persistence for generic reference tables (Auftraege, VERBUNDENE_PARTEIEN,
MANDANT_GEGNER, ...): full replace per project, no dedup - these are
relationship/link tables without a natural unique row key, matching the
original app's data_upload_module.run_data_load_generic.
"""

import uuid

import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession


async def load_reference_table(
    db: AsyncSession,
    project_id: uuid.UUID,
    model: type,
    standard_columns: list[str],
    df: pd.DataFrame,
    file_name: str,
) -> dict:
    if df.empty:
        raise ValueError("The uploaded file has no rows.")

    extra_cols = [c for c in df.columns if c not in standard_columns]
    records = []
    for row in df.to_dict(orient="records"):
        record: dict = {"project_id": project_id}
        for col in standard_columns:
            val = row.get(col)
            record[col] = None if val in (None, "") or pd.isna(val) else val
        record["extra"] = {c: row.get(c) for c in extra_cols if row.get(c) not in (None, "")}
        record["Source_FILE"] = file_name
        records.append(record)

    await db.execute(delete(model).where(model.project_id == project_id))
    await db.execute(insert(model.__table__), records)
    await db.commit()

    return {"row_count": len(records), "columns": list(df.columns)}
