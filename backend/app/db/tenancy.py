"""Schema-per-tenant provisioning and per-request tenant-scoped sessions.

Design: TenantBase-derived models (see app/db/base.py) declare no explicit
schema. When we need to talk to a specific tenant's data, we bind a session
to a connection whose `schema_translate_map` remaps the default (`None`)
schema to that tenant's Postgres schema name. The same ORM models then work
for any tenant without per-tenant model classes.

Known scaffolding simplification: tenant schemas are kept current by running
`TenantBase.metadata.create_all()` against them (idempotent - only creates
tables that don't exist yet), rather than being tracked by Alembic per
tenant. This is fine while the tenant side is only ever added to, never
altered in place (a real column change needs a proper per-schema migration
runner, e.g. looping Alembic's `command.upgrade` once per tenant schema -
not needed yet).

A tenant provisioned before some table existed in the model (e.g. any
tenant created before this session added Dataset/DatasetRow/CheckFinding)
would otherwise never get that table, since `create_tenant_schema` only
ran once, at provisioning time. `ensure_tenant_schema_current` closes that
gap: `get_tenant_db` calls it on every request, but it only actually
touches the database the first time a given schema is seen by this
process (an in-memory set, not a persisted flag) - a `create_all` call is
too much overhead to pay on every single request forever.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.db.base import TenantBase
from app.db.session import engine

_schemas_ensured_this_process: set[str] = set()


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


async def ensure_tenant_schema_current(schema_name: str) -> None:
    """Create any TenantBase table that's missing from this tenant's schema
    (new since it was provisioned). No-ops after the first call per schema
    per process - see module docstring."""
    if schema_name in _schemas_ensured_this_process:
        return

    def _create_all(sync_conn):
        TenantBase.metadata.create_all(
            bind=sync_conn.execution_options(schema_translate_map={None: schema_name})
        )

    async with engine.connect() as conn:
        await conn.run_sync(_create_all)
        await conn.commit()

    _schemas_ensured_this_process.add(schema_name)
