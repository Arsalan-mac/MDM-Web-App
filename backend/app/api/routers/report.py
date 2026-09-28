import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.report_service import export_mandanten_csv, get_summary

router = APIRouter(prefix="/projects/{project_id}/report", tags=["report"])


class OpenFindingsOut(BaseModel):
    junk_address: int
    address_decomposition: int
    register_cleansing: int


class SummaryOut(BaseModel):
    mandant_count: int
    auftrag_count: int
    ghost_count: int
    open_findings: OpenFindingsOut


@router.get("/summary", response_model=SummaryOut)
async def summary(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    return await get_summary(db, project_id)


@router.get("/export/mandanten.csv")
async def export_mandanten(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> Response:
    csv_text = await export_mandanten_csv(db, project_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mandanten_export.csv"},
    )
