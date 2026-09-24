import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.sap_template_mappings import SHEETS
from app.cleansing.sap_template_service import build_excel_workbook, generate_all_sheets, generate_sheet

router = APIRouter(prefix="/projects/{project_id}/sap-template", tags=["sap-template"])


class SheetInfoOut(BaseModel):
    name: str
    field_count: int


@router.get("/sheets", response_model=list[SheetInfoOut])
async def list_sheets() -> list[dict]:
    return [{"name": name, "field_count": len(specs)} for name, specs in SHEETS.items()]


class ViolationOut(BaseModel):
    row_index: int
    id_party: str
    field: str
    value: str
    allowed_length: int


class SheetPreviewOut(BaseModel):
    total: int
    rows: list[dict]
    violations: list[ViolationOut]


@router.get("/{sheet_name}/preview", response_model=SheetPreviewOut)
async def preview_sheet(
    project_id: uuid.UUID, sheet_name: str, limit: int = 5, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Dry run: generates the first `limit` rows of one sheet plus every
    overflow violation among them, without producing a download.
    """
    if sheet_name not in SHEETS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown sheet: {sheet_name}")
    return await generate_sheet(db, project_id, sheet_name, limit=limit)


@router.get("/{sheet_name}/generate", response_model=SheetPreviewOut)
async def generate_one_sheet(
    project_id: uuid.UUID, sheet_name: str, db: AsyncSession = Depends(get_tenant_db)
) -> dict:
    """Full generation of one sheet (all rows), as JSON diagnostics."""
    if sheet_name not in SHEETS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown sheet: {sheet_name}")
    return await generate_sheet(db, project_id, sheet_name)


class SheetSummaryOut(BaseModel):
    total: int
    violation_count: int


class GenerateAllOut(BaseModel):
    sheets: dict[str, SheetSummaryOut]


@router.get("/generate", response_model=GenerateAllOut)
async def generate_all(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> dict:
    """Generates every sheet and returns row/violation counts - used to show
    a diagnostics summary before downloading the workbook.
    """
    data = await generate_all_sheets(db, project_id)
    return {"sheets": {name: {"total": d["total"], "violation_count": len(d["violations"])} for name, d in data.items()}}


@router.get("/download")
async def download_workbook(project_id: uuid.UUID, db: AsyncSession = Depends(get_tenant_db)) -> Response:
    """Generates every sheet and returns an .xlsx workbook: one sheet per
    target table, overflow violations highlighted red, plus a consolidated
    Violations sheet.
    """
    data = await generate_all_sheets(db, project_id)
    content = build_excel_workbook(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=SAP_Migration_Template.xlsx"},
    )
