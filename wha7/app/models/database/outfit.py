# app/models/database/outfit.py
"""Outfit model and related database configurations."""

from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, Index
from .base import Base
from .item import Item  # We'll create this next

class Outfit(Base):
    """Represents a complete outfit with associated items and metadata."""
    __tablename__ = 'outfits'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    phone_id: Mapped[int] = mapped_column(
        ForeignKey('phone_numbers.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    image_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    # Relationships
    owner: Mapped["PhoneNumber"] = relationship(back_populates="outfits")
    items: Mapped[List["Item"]] = relationship(
        back_populates="outfit",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_outfit_description', 'description', postgresql_using='gin'),
    )