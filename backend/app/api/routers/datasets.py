import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.checks import list_checks, missing_roles
from app.checks.custom import RULE_TYPES
from app.cleansing.dataset_service import (
    CUSTOM_CHECK_PREFIX,
    DatasetError,
    accept_finding,
    create_custom_check,
    create_dataset,
    delete_custom_check,
    dismiss_finding,
    get_dataset,
    list_custom_checks,
    list_datasets,
    list_findings,
    run_checks,
    sample_rows,
    set_role_mapping,
)
from app.cleansing.load_data import UnsupportedFileType, harmonize_reference_dataframe, parse_uploaded_file
from app.models.dataset import CheckFinding, CustomCheckDefinition, Dataset

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["datasets"])


# Registered before any "/{dataset_id}" route below - otherwise FastAPI
# would match a request for this literal path as "/{dataset_id}" with
# dataset_id="rule-types" instead, since routes are matched in
# registration order.
@router.get("/rule-types", response_model=list[str])
async def get_custom_check_rule_types() -> list[str]:
    return RULE_TYPES


class DatasetOut(BaseModel):
    id: uuid.UUID
    name: str
    source_filename: str | None
    columns: list[str]
    primary_key_column: str | None
    role_mapping: dict
    row_count: int

    model_config = {"from_attributes": True}


class DatasetDetailOut(DatasetOut):
    sample_rows: list[dict]


@router.post("/upload", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    name: str = Form(...),
    primary_key_column: str | None = Form(None),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dataset:
    """Upload any file as a new dataset - no fixed schema. Columns are
    taken exactly as they appear in the file (only whitespace/BOM-stripped
    and NA-like values blanked, via harmonize_reference_dataframe)."""
    content = await file.read()
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No file name on the upload.")
    try:
        df = parse_uploaded_file(file.filename, content)
    except (UnsupportedFileType, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    df = harmonize_reference_dataframe(df)

    try:
        dataset = await create_dataset(db, project_id, name, file.filename, df, primary_key_column or None)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return dataset


@router.get("", response_model=list[DatasetOut])
async def list_project_datasets(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> list[Dataset]:
    return await list_datasets(db, project_id)


@router.get("/{dataset_id}", response_model=DatasetDetailOut)
async def get_project_dataset(
    project_id: uuid.UUID, dataset_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    try:
        dataset = await get_dataset(db, project_id, dataset_id)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    rows = await sample_rows(db, dataset_id)
    return {**DatasetOut.model_validate(dataset).model_dump(), "sample_rows": rows}


class RoleMappingIn(BaseModel):
    role_mapping: dict


@router.put("/{dataset_id}/role-mapping", response_model=DatasetOut)
async def update_role_mapping(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: RoleMappingIn,
    db: AsyncSession = Depends(get_tenant_db),
) -> Dataset:
    try:
        dataset = await get_dataset(db, project_id, dataset_id)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return await set_role_mapping(db, dataset, payload.role_mapping)


class CheckDefinitionOut(BaseModel):
    key: str
    label: str
    description: str
    required_roles: list[str]
    optional_roles: list[str]
    missing_roles: list[str] = []
    custom: bool = False


@router.get("/{dataset_id}/checks", response_model=list[CheckDefinitionOut])
async def list_available_checks(
    project_id: uuid.UUID, dataset_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> list[dict]:
    """The full Check Catalog, annotated with which roles are still unmapped
    for *this* dataset (an empty missing_roles means it's ready to run)."""
    try:
        dataset = await get_dataset(db, project_id, dataset_id)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    builtin = [
        {
            "key": c.key,
            "label": c.label,
            "description": c.description,
            "required_roles": c.required_roles,
            "optional_roles": c.optional_roles,
            "missing_roles": missing_roles(c.key, dataset.role_mapping),
            "custom": False,
        }
        for c in list_checks()
    ]
    custom = [
        {
            "key": f"{CUSTOM_CHECK_PREFIX}{c.id}",
            "label": c.name,
            "description": f"Custom check ({c.rule_type})",
            "required_roles": [],
            "optional_roles": [],
            "missing_roles": [],
            "custom": True,
        }
        for c in await list_custom_checks(db, project_id, dataset_id)
    ]
    return builtin + custom


class CustomCheckOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    rule_type: str
    params: dict
    severity: str

    model_config = {"from_attributes": True}


class CreateCustomCheckIn(BaseModel):
    name: str
    rule_type: str
    params: dict
    severity: str = "warning"


@router.get("/{dataset_id}/custom-checks", response_model=list[CustomCheckOut])
async def get_custom_checks(
    project_id: uuid.UUID, dataset_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> list[CustomCheckDefinition]:
    return await list_custom_checks(db, project_id, dataset_id)


@router.post("/{dataset_id}/custom-checks", response_model=CustomCheckOut, status_code=status.HTTP_201_CREATED)
async def create_dataset_custom_check(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: CreateCustomCheckIn,
    db: AsyncSession = Depends(get_tenant_db),
) -> CustomCheckDefinition:
    try:
        return await create_custom_check(
            db, project_id, dataset_id, payload.name, payload.rule_type, payload.params, payload.severity
        )
    except DatasetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.delete("/{dataset_id}/custom-checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_custom_check(
    project_id: uuid.UUID, dataset_id: uuid.UUID, check_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)
) -> None:
    try:
        await delete_custom_check(db, project_id, check_id)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


class RunChecksIn(BaseModel):
    check_keys: list[str]


@router.post("/{dataset_id}/checks/run")
async def run_selected_checks(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: RunChecksIn,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    try:
        dataset = await get_dataset(db, project_id, dataset_id)
        counts = await run_checks(db, dataset, payload.check_keys)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"finding_counts": counts}


class FindingOut(BaseModel):
    id: uuid.UUID
    row_key: str
    check_key: str
    field: str
    severity: str
    message: str
    proposed_value: str | None
    status: str

    model_config = {"from_attributes": True}


@router.get("/{dataset_id}/findings", response_model=list[FindingOut])
async def get_findings(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    check_key: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[CheckFinding]:
    await get_dataset(db, project_id, dataset_id)  # 404s if not this project's dataset
    return await list_findings(db, dataset_id, check_key)


@router.post("/{dataset_id}/findings/{finding_id}/accept", response_model=FindingOut)
async def accept_dataset_finding(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
) -> CheckFinding:
    await get_dataset(db, project_id, dataset_id)
    try:
        return await accept_finding(db, dataset_id, finding_id)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/{dataset_id}/findings/{finding_id}/dismiss", response_model=FindingOut)
async def dismiss_dataset_finding(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
) -> CheckFinding:
    await get_dataset(db, project_id, dataset_id)
    try:
        return await dismiss_finding(db, dataset_id, finding_id)
    except DatasetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
