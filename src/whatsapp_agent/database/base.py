"""
SQLAlchemy declarative base and shared model mixins.

All ORM models should inherit from Base.
Use the mixins to ensure consistent columns across all models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for all ORM models.

    All models must inherit from this class.
    """
    pass


class UUIDPrimaryKeyMixin:
    """
    Mixin that adds a UUID primary key column.

    Uses PostgreSQL's native UUID type for efficient storage and indexing.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key — universally unique identifier.",
    )


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp columns.

    - created_at: Set automatically on INSERT, never changes.
    - updated_at: Updated automatically on every UPDATE via server-side trigger.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp (UTC).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last-modified timestamp (UTC).",
    )


class SoftDeleteMixin:
    """
    Mixin that adds soft-delete support.

    Records are never physically deleted — they are marked with deleted_at.
    All queries should filter WHERE deleted_at IS NULL.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Soft-delete timestamp. NULL = record is active.",
    )

    @property
    def is_deleted(self) -> bool:
        """True if this record has been soft-deleted."""
        return self.deleted_at is not None


class WorkspaceScopedMixin:
    """
    Mixin that adds a workspace_id foreign key.

    EVERY tenant-owned model MUST include this mixin.
    Enforces multi-tenancy: data belonging to one workspace cannot be
    accessed by another workspace.

    Note: The actual FK constraint is added by child models that import
    Workspace, to avoid circular imports. This mixin only declares the column.
    """

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Tenant workspace ID. All queries MUST filter by this column.",
    )
