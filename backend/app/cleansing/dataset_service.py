"""Generic dataset ingestion, role-mapping, check execution and finding
acceptance - the engine behind the Check Catalog (app/checks/) that
replaces the fixed Mandanten-only, locked-stage pipeline.

`harmonize_reference_dataframe` (app/cleansing/load_data.py) is reused for
cleaning cell values, deliberately *not* `harmonize_dataframe`: the latter
also renames columns via Mandanten's alias table and mangles punctuation
in column names, both wrong for an arbitrary dataset whose real column
names should be preserved exactly as uploaded.
"""

import uuid

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checks import get_check, missing_roles, run_check
from app.models.dataset import CheckFinding, Dataset, DatasetRow


class DatasetError(ValueError):
    pass


async def create_dataset(
    db: AsyncSession,
    project_id: uuid.UUID,
    name: str,
    filename: str,
    df: pd.DataFrame,
    primary_key_column: str | None = None,
) -> Dataset:
    if df.empty:
        raise DatasetError("The uploaded file has no rows.")

    columns = [str(c) for c in df.columns]
    if primary_key_column and primary_key_column not in columns:
        raise DatasetError(f"{primary_key_column!r} is not a column in this file.")

    dataset = Dataset(
        project_id=project_id,
        name=name,
        source_filename=filename,
        columns=columns,
        primary_key_column=primary_key_column,
        row_count=len(df),
    )
    db.add(dataset)
    await db.flush()

    records = df.to_dict(orient="records")
    for i, record in enumerate(records):
        data = {k: (None if pd.isna(v) else v) for k, v in record.items()}
        row_key = str(data.get(primary_key_column)) if primary_key_column else str(uuid.uuid4())
        db.add(DatasetRow(dataset_id=dataset.id, row_key=row_key, row_index=i, data=data))

    await db.commit()
    await db.refresh(dataset)
    return dataset


async def list_datasets(db: AsyncSession, project_id: uuid.UUID) -> list[Dataset]:
    result = await db.execute(select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at))
    return list(result.scalars().all())


async def get_dataset(db: AsyncSession, project_id: uuid.UUID, dataset_id: uuid.UUID) -> Dataset:
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project_id)
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise DatasetError("Dataset not found.")
    return dataset


async def sample_rows(db: AsyncSession, dataset_id: uuid.UUID, limit: int = 10) -> list[dict]:
    result = await db.execute(
        select(DatasetRow).where(DatasetRow.dataset_id == dataset_id).order_by(DatasetRow.row_index).limit(limit)
    )
    return [row.data for row in result.scalars().all()]


async def set_role_mapping(db: AsyncSession, dataset: Dataset, role_mapping: dict) -> Dataset:
    dataset.role_mapping = role_mapping
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def _all_rows(db: AsyncSession, dataset_id: uuid.UUID) -> list[DatasetRow]:
    result = await db.execute(
        select(DatasetRow).where(DatasetRow.dataset_id == dataset_id).order_by(DatasetRow.row_index)
    )
    return list(result.scalars().all())


async def run_checks(db: AsyncSession, dataset: Dataset, check_keys: list[str]) -> dict[str, int]:
    """Runs each requested check, replacing that check's previous findings
    for this dataset (re-running is always a fresh pass, not additive)."""
    rows = await _all_rows(db, dataset.id)
    row_dicts = [r.data for r in rows]

    counts: dict[str, int] = {}
    for key in check_keys:
        definition = get_check(key)
        if definition is None:
            raise DatasetError(f"Unknown check: {key!r}")
        missing = missing_roles(key, dataset.role_mapping)
        if missing:
            raise DatasetError(f"{definition.label}: map {', '.join(missing)} before running this check.")

        await db.execute(delete(CheckFinding).where(CheckFinding.dataset_id == dataset.id, CheckFinding.check_key == key))

        drafts = run_check(key, row_dicts, dataset.role_mapping)
        for draft in drafts:
            db.add(
                CheckFinding(
                    dataset_id=dataset.id,
                    row_key=rows[draft.row_index].row_key,
                    check_key=key,
                    field=draft.field,
                    severity=draft.severity,
                    message=draft.message,
                    proposed_value=draft.proposed_value,
                )
            )
        counts[key] = len(drafts)

    await db.commit()
    return counts


async def list_findings(db: AsyncSession, dataset_id: uuid.UUID, check_key: str | None = None) -> list[CheckFinding]:
    stmt = select(CheckFinding).where(CheckFinding.dataset_id == dataset_id)
    if check_key:
        stmt = stmt.where(CheckFinding.check_key == check_key)
    result = await db.execute(stmt.order_by(CheckFinding.created_at))
    return list(result.scalars().all())


async def accept_finding(db: AsyncSession, dataset_id: uuid.UUID, finding_id: uuid.UUID) -> CheckFinding:
    finding = await db.get(CheckFinding, finding_id)
    if finding is None or finding.dataset_id != dataset_id:
        raise DatasetError("Finding not found.")
    if finding.proposed_value is None:
        raise DatasetError("This finding has no proposed value to accept.")

    result = await db.execute(
        select(DatasetRow).where(DatasetRow.dataset_id == dataset_id, DatasetRow.row_key == finding.row_key)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        row.data = {**row.data, finding.field: finding.proposed_value}

    finding.status = "accepted"
    await db.commit()
    await db.refresh(finding)
    return finding


async def dismiss_finding(db: AsyncSession, dataset_id: uuid.UUID, finding_id: uuid.UUID) -> CheckFinding:
    finding = await db.get(CheckFinding, finding_id)
    if finding is None or finding.dataset_id != dataset_id:
        raise DatasetError("Finding not found.")
    finding.status = "dismissed"
    await db.commit()
    await db.refresh(finding)
    return finding
