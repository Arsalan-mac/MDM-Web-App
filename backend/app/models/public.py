import re
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import PublicBase

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_]{0,58}[a-z0-9])?$")


def validate_tenant_slug(slug: str) -> str:
    """Raise ValueError if `slug` is not safe to use as a Postgres schema suffix.

    Slugs become part of an unquoted-identifier-safe schema name
    (`tenant_<slug>`), so this is a hard security boundary, not just
    cosmetic validation - it runs before the slug ever reaches SQL.
    """
    if not _SLUG_RE.match(slug):
        raise ValueError(
            "Tenant slug must be lowercase alphanumeric/underscore, "
            "1-60 chars, and not start/end with an underscore."
        )
    return slug


class Tenant(PublicBase):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # The Clerk Organization id backing this tenant.
    clerk_org_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    # Used to derive the Postgres schema name (`tenant_<slug>`); see
    # app/db/tenancy.py::schema_name_for_tenant.
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="trial")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["TenantUser"]] = relationship(back_populates="tenant")


class TenantUser(PublicBase):
    __tablename__ = "tenant_users"
    __table_args__ = {"schema": "public"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public.tenants.id"), index=True)
    # The Clerk User id.
    clerk_user_id: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(32), default="member")  # "admin" | "member"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
