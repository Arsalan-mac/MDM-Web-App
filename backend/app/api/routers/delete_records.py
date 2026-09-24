import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.delete_records_service import InvalidTableOrColumn, clear_all_rows, clear_by_ids, list_tables
from app.cleansing.load_data import UnsupportedFileType, parse_uploaded_file

router = APIRouter(prefix="/projects/{project_id}/delete-records", tags=["delete-records"])


class TableInfoOut(BaseModel):
    table: str
    columns: list[str]
    clearable_columns: list[str]


@router.get("/tables", response_model=list[TableInfoOut])
async def get_tables() -> list[dict]:
    """Every content table in this project's data, with the columns
    available for ID-list matching and the subset safe to clear (excludes
    project_id and primary-key columns).
    """
    return list_tables()


class ClearAllRequest(BaseModel):
    table: str
    columns: list[str]


class ClearOut(BaseModel):
    updated: int


@router.post("/clear-all", response_model=ClearOut)
async def clear_all(project_id: uuid.UUID, payload: ClearAllRequest, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Sets the given columns to NULL for every row of `table` in this
    project. Rows are never deleted - only the selected field values.
    """
    try:
        updated = await clear_all_rows(db, project_id, payload.table, payload.columns)
    except InvalidTableOrColumn as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"updated": updated}


@router.post("/clear-by-ids", response_model=ClearOut)
async def clear_ids(
    project_id: uuid.UUID,
    table: str = Form(...),
    columns: list[str] = Form(...),
    excel_id_col: str = Form(...),
    db_id_col: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Sets the given columns to NULL for rows of `table` in this project
    whose `db_id_col` matches one of the IDs in the uploaded file's
    `excel_id_col` column.
    """
    content = await file.read()
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No file name on the upload.")
    try:
        df = parse_uploaded_file(file.filename, content)
    except (UnsupportedFileType, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if excel_id_col not in df.columns:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Column {excel_id_col!r} not found in the uploaded file.")
    id_list = [str(v) for v in df[excel_id_col].dropna().unique().tolist()]
    if not id_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No IDs found in the uploaded file's selected column.")

    try:
        updated = await clear_by_ids(db, project_id, table, columns, db_id_col, id_list)
    except InvalidTableOrColumn as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"updated": updated}
