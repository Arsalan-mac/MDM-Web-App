import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.relation_service import RelationError, create_relation, delete_relation, list_relations
from app.models.dataset import DatasetRelation

router = APIRouter(prefix="/projects/{project_id}/relations", tags=["relations"])


class RelationOut(BaseModel):
    id: uuid.UUID
    name: str
    from_dataset_id: uuid.UUID
    from_column: str
    to_dataset_id: uuid.UUID
    to_column: str
    cardinality: str

    model_config = {"from_attributes": True}


class CreateRelationIn(BaseModel):
    name: str
    from_dataset_id: uuid.UUID
    from_column: str
    to_dataset_id: uuid.UUID
    to_column: str
    cardinality: str


@router.post("", response_model=RelationOut, status_code=status.HTTP_201_CREATED)
async def create_project_relation(
    project_id: uuid.UUID, payload: CreateRelationIn, db: AsyncSession = Depends(get_tenant_db)
) -> DatasetRelation:
    try:
        return await create_relation(
            db,
            project_id,
            payload.name,
            payload.from_dataset_id,
            payload.from_column,
            payload.to_dataset_id,
            payload.to_column,
            payload.cardinality,
        )
    except RelationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("", response_model=list[RelationOut])
async def list_project_relations(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[DatasetRelation]:
    return await list_relations(db, project_id)


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_relation(
    project_id: uuid.UUID, relation_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> None:
    try:
        await delete_relation(db, project_id, relation_id)
    except RelationError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
