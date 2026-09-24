import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_user
from app.db.session import engine, get_public_session
from app.db.tenancy import create_tenant_schema, schema_name_for_tenant
from app.models.public import Tenant, TenantUser, validate_tenant_slug

router = APIRouter(prefix="/tenants", tags=["tenants"])


class ProvisionTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=60)
    # Clerk's default (v2) session token is minimal and does not carry an
    # email claim - confirmed while testing sign-in against a real token.
    # The frontend already has the signed-in user's email client-side
    # (via Clerk's useUser()), so it's passed explicitly rather than
    # re-derived from the token.
    email: str = ""


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str

    model_config = {"from_attributes": True}


@router.post("/provision", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def provision_tenant(
    payload: ProvisionTenantRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_public_session),
) -> Tenant:
    """Create the Tenant row + its Postgres schema for the caller's active Clerk org.

    Idempotent: calling this again for an already-provisioned org just
    returns the existing tenant.
    """
    if not user.clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization on this session.",
        )

    existing = await db.execute(select(Tenant).where(Tenant.clerk_org_id == user.clerk_org_id))
    tenant = existing.scalar_one_or_none()
    if tenant is not None:
        return tenant

    try:
        slug = validate_tenant_slug(payload.slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    schema_name = schema_name_for_tenant(slug)
    tenant_id = uuid.uuid4()

    tenant = Tenant(id=tenant_id, clerk_org_id=user.clerk_org_id, name=payload.name, slug=slug)
    db.add(tenant)
    db.add(
        TenantUser(
            tenant_id=tenant_id,
            clerk_user_id=user.clerk_user_id,
            email=payload.email,
            role="admin",
        )
    )

    async with engine.begin() as conn:
        await create_tenant_schema(conn, schema_name)

    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/me", response_model=TenantOut)
async def get_my_tenant(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_public_session),
) -> Tenant:
    if not user.clerk_org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active organization on this session.")
    result = await db.execute(select(Tenant).where(Tenant.clerk_org_id == user.clerk_org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not provisioned yet.")
    return tenant
