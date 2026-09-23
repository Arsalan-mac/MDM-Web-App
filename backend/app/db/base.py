"""Declarative bases for the two kinds of tables in this app.

PublicBase: tables that live in a fixed `public` schema, shared across all
tenants (the tenant registry itself, and the tenant/Clerk-user mapping).
Tables declare `schema="public"` explicitly so they are never remapped by a
schema_translate_map.

TenantBase: tables that live inside each tenant's own Postgres schema
(projects, stages, and every stage-specific table added as pipeline stages
are ported). These tables intentionally do NOT set a schema — the same
metadata is reused for every tenant by translating the (default) schema at
the connection level via `execution_options(schema_translate_map=...)`. See
`app/db/tenancy.py`.
"""

from sqlalchemy.orm import DeclarativeBase


class PublicBase(DeclarativeBase):
    pass


class TenantBase(DeclarativeBase):
    pass
