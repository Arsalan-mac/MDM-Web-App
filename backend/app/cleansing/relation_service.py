"""CRUD for DatasetRelation - see app/models/dataset.py for what one is."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset, DatasetRelation

_CARDINALITIES = {"one_to_one", "one_to_many", "many_to_many"}


class RelationError(ValueError):
    pass


async def _get_dataset_or_raise(db: AsyncSession, project_id: uuid.UUID, dataset_id: uuid.UUID) -> Dataset:
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise RelationError(f"Dataset {dataset_id} not found in this project.")
    return dataset


async def create_relation(
    db: AsyncSession,
    project_id: uuid.UUID,
    name: str,
    from_dataset_id: uuid.UUID,
    from_column: str,
    to_dataset_id: uuid.UUID,
    to_column: str,
    cardinality: str,
) -> DatasetRelation:
    if cardinality not in _CARDINALITIES:
        raise RelationError(f"cardinality must be one of {sorted(_CARDINALITIES)}, got {cardinality!r}")

    from_dataset = await _get_dataset_or_raise(db, project_id, from_dataset_id)
    to_dataset = await _get_dataset_or_raise(db, project_id, to_dataset_id)
    if from_column not in from_dataset.columns:
        raise RelationError(f"{from_column!r} is not a column of {from_dataset.name!r}.")
    if to_column not in to_dataset.columns:
        raise RelationError(f"{to_column!r} is not a column of {to_dataset.name!r}.")

    relation = DatasetRelation(
        project_id=project_id,
        name=name,
        from_dataset_id=from_dataset_id,
        from_column=from_column,
        to_dataset_id=to_dataset_id,
        to_column=to_column,
        cardinality=cardinality,
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return relation


async def list_relations(db: AsyncSession, project_id: uuid.UUID) -> list[DatasetRelation]:
    result = await db.execute(
        select(DatasetRelation).where(DatasetRelation.project_id == project_id).order_by(DatasetRelation.created_at)
    )
    return list(result.scalars().all())


async def delete_relation(db: AsyncSession, project_id: uuid.UUID, relation_id: uuid.UUID) -> None:
    relation = await db.get(DatasetRelation, relation_id)
    if relation is None or relation.project_id != project_id:
        raise RelationError("Relation not found.")
    await db.delete(relation)
    await db.commit()
