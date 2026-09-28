import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.mapping_service import (
    MappingError,
    create_mapping,
    delete_mapping,
    generate_mapping_rows,
    get_mapping,
    list_mappings,
    mapping_to_csv,
    suggest_mapping,
    update_mapping_fields,
)
from app.models.dataset import MappingDefinition

router = APIRouter(prefix="/projects/{project_id}/mappings", tags=["mappings"])


class MappingFieldIn(BaseModel):
    target: str
    kind: str
    config: dict = {}


class MappingOut(BaseModel):
    id: uuid.UUID
    name: str
    source_dataset_id: uuid.UUID
    fields: list[dict]

    model_config = {"from_attributes": True}


class CreateMappingIn(BaseModel):
    name: str
    source_dataset_id: uuid.UUID
    fields: list[MappingFieldIn] = []


class UpdateFieldsIn(BaseModel):
    fields: list[MappingFieldIn]


class SuggestIn(BaseModel):
    source_dataset_id: uuid.UUID
    target_fields: list[str]


@router.post("", response_model=MappingOut, status_code=status.HTTP_201_CREATED)
async def create_project_mapping(
    project_id: uuid.UUID, payload: CreateMappingIn, db: AsyncSession = Depends(get_tenant_db)
) -> MappingDefinition:
    try:
        return await create_mapping(
            db, project_id, payload.name, payload.source_dataset_id, [f.model_dump() for f in payload.fields]
        )
    except MappingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("", response_model=list[MappingOut])
async def list_project_mappings(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[MappingDefinition]:
    return await list_mappings(db, project_id)


@router.get("/{mapping_id}", response_model=MappingOut)
async def get_project_mapping(
    project_id: uuid.UUID, mapping_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> MappingDefinition:
    try:
        return await get_mapping(db, project_id, mapping_id)
    except MappingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.put("/{mapping_id}/fields", response_model=MappingOut)
async def update_project_mapping_fields(
    project_id: uuid.UUID, mapping_id: uuid.UUID, payload: UpdateFieldsIn, db: AsyncSession = Depends(get_tenant_db)
) -> MappingDefinition:
    try:
        return await update_mapping_fields(db, project_id, mapping_id, [f.model_dump() for f in payload.fields])
    except MappingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_mapping(
    project_id: uuid.UUID, mapping_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> None:
    try:
        await delete_mapping(db, project_id, mapping_id)
    except MappingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/{mapping_id}/preview")
async def preview_project_mapping(
    project_id: uuid.UUID, mapping_id: uuid.UUID, limit: int = 20, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    try:
        targets, rows = await generate_mapping_rows(db, project_id, mapping_id)
    except MappingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"columns": targets, "rows": rows[:limit], "total_rows": len(rows)}


@router.get("/{mapping_id}/export.csv")
async def export_project_mapping(
    project_id: uuid.UUID, mapping_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> Response:
    try:
        csv_text = await mapping_to_csv(db, project_id, mapping_id)
    except MappingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mapping_export.csv"},
    )


@router.post("/suggest")
async def suggest_project_mapping(
    project_id: uuid.UUID, payload: SuggestIn, db: AsyncSession = Depends(get_tenant_db)
) -> dict[str, str | None]:
    try:
        return await suggest_mapping(db, project_id, payload.source_dataset_id, payload.target_fields)
    except MappingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
