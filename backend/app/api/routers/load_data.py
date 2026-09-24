import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.load_data import UnsupportedFileType, harmonize_dataframe, parse_uploaded_file
from app.cleansing.mandanten_service import initial_load_mandanten
from app.cleansing.pipeline import set_stage_status

router = APIRouter(prefix="/projects/{project_id}/load-data", tags=["load-data"])


class LoadSummaryOut(BaseModel):
    row_count: int
    columns: list[str]
    preview: list[dict]


@router.post("/mandanten/upload", response_model=LoadSummaryOut, status_code=status.HTTP_201_CREATED)
async def upload_mandanten(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Initial Load of the client master-data (Mandanten) file.

    Parses the upload, standardizes/cleans columns (app/cleansing/load_data.py,
    ported from the original app's data_upload_module.py), fully replaces the
    tenant's `mandanten` table, and marks the Load Data stage done - which
    unlocks the next stage (see app/cleansing/pipeline.py).
    """
    content = await file.read()
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No file name on the upload.")

    try:
        df = parse_uploaded_file(file.filename, content)
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if df.empty:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file has no rows.")

    df = harmonize_dataframe(df)

    try:
        summary = await initial_load_mandanten(db, project_id, df, file.filename)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await set_stage_status(db, project_id, "load_data", "done")
    await db.commit()

    return summary
