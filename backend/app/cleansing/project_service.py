"""Project-level operations for Settings: rename and hard-delete an entire
project (every row across every content table scoped to it, plus its own
Stage and Project rows). Distinct from Delete Records (a pipeline stage that
nulls selected columns but never removes rows) - this is closing out a
project entirely, e.g. after a botched test import.
"""

import uuid

from sqlalchemy import Table, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import TenantBase

# SQLAlchemy's declarative metadata only registers a table once its model
# class has actually been imported somewhere - importing the models module
# here guarantees TenantBase.metadata.tables is complete regardless of
# what else has (or hasn't) been imported wherever else in the current
# process.
import app.models.tenant  # noqa: F401
from app.models.dataset import CheckFinding, Dataset, DatasetRow
from app.models.tenant import Project, Stage

_EXCLUDED_TABLES = {"projects", "stages", "datasets"}


def _content_tables() -> list[Table]:
    return [table for name, table in TenantBase.metadata.tables.items() if name not in _EXCLUDED_TABLES]


class ProjectNotFound(ValueError):
    pass


async def rename_project(db: AsyncSession, project_id: uuid.UUID, new_name: str) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFound(f"No project {project_id}")
    project.name = new_name
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFound(f"No project {project_id}")

    # DatasetRow/CheckFinding reference Dataset by dataset_id, not
    # project_id, so the generic project_id-scoped sweep below can't see
    # them - removed explicitly first or they'd be left orphaned (and
    # block deleting `datasets` itself via FK).
    dataset_ids = select(Dataset.id).where(Dataset.project_id == project_id)
    await db.execute(delete(DatasetRow).where(DatasetRow.dataset_id.in_(dataset_ids)))
    await db.execute(delete(CheckFinding).where(CheckFinding.dataset_id.in_(dataset_ids)))

    # `datasets` itself is excluded from this generic sweep and deleted
    # explicitly afterward: several other project_id-scoped tables
    # (DatasetRelation, CustomCheckDefinition, MappingDefinition) also
    # reference a dataset's id, and the dict-order sweep below has no
    # defined ordering relative to `datasets` - only relative to
    # `project_id`, which all of these share equally.
    for table in _content_tables():
        if "project_id" in table.c:
            await db.execute(delete(table).where(table.c.project_id == project_id))

    await db.execute(delete(Dataset).where(Dataset.project_id == project_id))
    await db.execute(delete(Stage).where(Stage.project_id == project_id))
    await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()
