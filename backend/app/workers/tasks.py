"""Background jobs. Stage-processing jobs (Load Data, Address Cleansing, ...)
are added here in Phase 1c, one per pipeline stage, each running against a
tenant-scoped DB session the same way the API routes do (see
app/db/tenancy.py::get_tenant_sessionmaker).
"""

from typing import Any


async def ping(ctx: dict[str, Any]) -> str:
    """Trivial job used to confirm the worker is wired up to Redis correctly."""
    return "pong"


async def process_load_data(ctx: dict[str, Any], tenant_slug: str, project_id: str, upload_path: str) -> dict:
    """Placeholder for the Load Data stage job - implemented in Phase 1c.

    Will parse the uploaded client file, standardize columns (porting
    mdm_shared.standardize_columns from the original Streamlit app), and
    write rows into the tenant's `mandanten` table.
    """
    raise NotImplementedError("Load Data job will be implemented in Phase 1c.")
