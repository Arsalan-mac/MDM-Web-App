import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.models.tenant import Project, Stage

router = APIRouter(prefix="/projects", tags=["projects"])


class StageOut(BaseModel):
    key: str
    label: str
    position: int
    status: str

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    stages: list[StageOut]

    model_config = {"from_attributes": True}


class CreateProjectRequest(BaseModel):
    name: str


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> Project:
    project = Project(name=payload.name)
    db.add(project)
    await db.flush()  # assigns project.id so the stages below can reference it

    for stage in project.ensure_default_stages():
        db.add(stage)

    await db.commit()
    await db.refresh(project, attribute_names=["stages"])
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_tenant_db)) -> list[Project]:
    result = await db.execute(select(Project))
    projects = list(result.scalars().all())
    for project in projects:
        await db.refresh(project, attribute_names=["stages"])
    return projects


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one()
    await db.refresh(project, attribute_names=["stages"])
    return project


class UpdateStageStatusRequest(BaseModel):
    status: str  # "in_progress" | "done"


@router.patch("/{project_id}/stages/{stage_key}", response_model=StageOut)
async def update_stage_status(
    project_id: uuid.UUID,
    stage_key: str,
    payload: UpdateStageStatusRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> Stage:
    """Mark a stage in_progress/done and unlock the next stage in sequence.

    Mirrors the original app's locking rule (2202MandantenCleansing.py):
    a stage only becomes reachable once every stage before it is done.
    """
    result = await db.execute(
        select(Stage).where(Stage.project_id == project_id).order_by(Stage.position)
    )
    stages = list(result.scalars().all())
    target = next((s for s in stages if s.key == stage_key), None)
    if target is None:
        raise ValueError(f"Unknown stage '{stage_key}' for this project.")

    target.status = payload.status

    if payload.status == "done":
        next_stage = next((s for s in stages if s.position == target.position + 1), None)
        if next_stage is not None and next_stage.status == "locked":
            next_stage.status = "in_progress"

    await db.commit()
    await db.refresh(target)
    return target
