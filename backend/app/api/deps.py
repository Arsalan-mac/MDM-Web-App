from typing import AsyncIterator

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, get_current_user
from app.db.session import get_public_session
from app.db.tenancy import get_tenant_sessionmaker, schema_name_for_tenant
from app.models.public import Tenant


async def get_current_tenant(
    user: AuthenticatedUser = Depends(get_current_user),
    public_db: AsyncSession = Depends(get_public_session),
) -> Tenant:
    if not user.clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization on this session. Select or create one in the client.",
        )
    result = await public_db.execute(select(Tenant).where(Tenant.clerk_org_id == user.clerk_org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This organization has not been provisioned yet. Call POST /tenants/provision first.",
        )
    return tenant


async def get_tenant_db(tenant: Tenant = Depends(get_current_tenant)) -> AsyncIterator[AsyncSession]:
    """Yield a session scoped to the current request's tenant schema.

    Every table declared on TenantBase (app/db/base.py) resolves against
    this tenant's schema for the lifetime of this session, via
    schema_translate_map - see app/db/tenancy.py.
    """
    schema_name = schema_name_for_tenant(tenant.slug)
    sessionmaker = get_tenant_sessionmaker(schema_name)
    async with sessionmaker() as session:
        yield session
