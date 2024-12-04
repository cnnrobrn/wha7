# File: app/models/database/base.py

"""Base configuration and utilities for SQLAlchemy models.

This module provides the foundational setup for all database models, including:
- Base class configuration
- Common model mixins
- Shared utilities and types
- Audit field implementations
"""

# app/models/database/base.py
from datetime import datetime
from typing import Any
from sqlalchemy import event
from sqlalchemy.ext.declarative import declared_attr

class BaseMixin:
    """Mixin class for common model functionality."""
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name automatically from class name."""
        return cls.__name__.lower()
    
    # Add soft delete capability
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    def soft_delete(self) -> None:
        """Mark record as deleted without removing from database."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
    
    @classmethod
    def not_deleted(cls):
        """Query filter for non-deleted records."""
        return cls.is_deleted.is_(False)

class Base(BaseMixin, DeclarativeBase):
    """Enhanced base class for all database models."""
    
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
