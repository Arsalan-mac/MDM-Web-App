"""Persistence for the Load Data stage's Mandanten (client master data) upload."""

import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cleansing.constants import MANDANT_PRIMARY_KEY, STANDARD_MANDANT_COLUMNS
from app.models.tenant import Mandant


def _row_to_record(row: dict, extra_cols: list[str], file_name: str) -> dict:
    record: dict = {}
    for col in STANDARD_MANDANT_COLUMNS:
        val = row.get(col)
        record[col] = None if pd.isna(val) else val
    record["extra"] = {c: (None if pd.isna(row.get(c)) else row.get(c)) for c in extra_cols}
    record["Source_FILE"] = file_name
    record["Change_Reason"] = ""
    return record


async def initial_load_mandanten(db: AsyncSession, df: pd.DataFrame, file_name: str) -> dict:
    """Full replace of the mandanten table - "Initial Load ersetzt die Tabelle
    vollständig", matching the original app's df.to_sql(if_exists="replace").

    Delta upload (upsert against an existing table, with Change_Reason
    tracking per data_upload_module.run_delta_upsert) is not yet ported -
    Phase 1c only covers the initial load needed to unblock Address
    Cleansing.
    """
    if MANDANT_PRIMARY_KEY not in df.columns:
        raise ValueError(
            f"Uploaded file has no '{MANDANT_PRIMARY_KEY}' column (after column "
            f"standardization) - cannot identify rows."
        )

    df = df.dropna(subset=[MANDANT_PRIMARY_KEY])
    df = df.drop_duplicates(subset=MANDANT_PRIMARY_KEY, keep="first")
    if df.empty:
        raise ValueError(f"No rows with a valid '{MANDANT_PRIMARY_KEY}' found in the uploaded file.")

    extra_cols = [c for c in df.columns if c not in STANDARD_MANDANT_COLUMNS]
    records = [_row_to_record(row, extra_cols, file_name) for row in df.to_dict(orient="records")]

    await db.execute(delete(Mandant))
    await db.execute(insert(Mandant.__table__), records)
    await db.commit()

    preview_df = df.head(5)
    preview_df = preview_df.astype(object).where(preview_df.notna(), None)

    return {
        "row_count": len(records),
        "columns": list(df.columns),
        "preview": preview_df.to_dict(orient="records"),
    }
