"""Schema-per-tenant provisioning and per-request tenant-scoped sessions.

Design: TenantBase-derived models (see app/db/base.py) declare no explicit
schema. When we need to talk to a specific tenant's data, we bind a session
to a connection whose `schema_translate_map` remaps the default (`None`)
schema to that tenant's Postgres schema name. The same ORM models then work
for any tenant without per-tenant model classes.

Known scaffolding simplification: new tenant schemas are created by running
`TenantBase.metadata.create_all()` against the freshly-created schema at
provisioning time, rather than being tracked by Alembic per tenant. This is
fine while the tenant-side schema is only added to (never altered) during
Phase 1; a proper per-schema migration runner (e.g. looping Alembic's
`command.upgrade` once per tenant schema) is planned before Phase 2 starts
altering tenant tables in place.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.db.base import TenantBase
from app.db.session import engine


def schema_name_for_tenant(tenant_slug: str) -> str:
    """Deterministic Postgres schema name for a tenant slug.

    Prefixed and constrained to what Postgres accepts as an unquoted
    identifier; the tenant slug itself is validated (see app/models/public.py)
    before ever reaching here.
    """
    return f"tenant_{tenant_slug}"


async def create_tenant_schema(conn: AsyncConnection, schema_name: str) -> None:
    await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    def _create_all(sync_conn):
        TenantBase.metadata.create_all(
            bind=sync_conn.execution_options(schema_translate_map={None: schema_name})
        )

    await conn.run_sync(_create_all)


def get_tenant_sessionmaker(schema_name: str) -> async_sessionmaker[AsyncSession]:
    """Return a sessionmaker bound to a connection scoped to one tenant schema."""
    scoped_engine = engine.execution_options(schema_translate_map={None: schema_name})
    return async_sessionmaker(bind=scoped_engine, expire_on_commit=False)
