# app/models/database/item.py
"""Item and Link models for product management."""

from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Float, ForeignKey, Integer, Index
from .base import Base

class Item(Base):
    """Individual clothing items within an outfit."""
    __tablename__ = 'items'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    outfit_id: Mapped[int] = mapped_column(
        ForeignKey('outfits.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relationships
    outfit: Mapped["Outfit"] = relationship(back_populates="items")
    links: Mapped[List["Link"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_item_search', 'search', postgresql_using='gin'),
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    click_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    @property
    def click_through_rate(self) -> float:
        """Calculate click-through rate."""
        return self.click_count / self.view_count if self.view_count > 0 else 0.0


class Link(Base):
    """Shopping links and product information for clothing items."""
    __tablename__ = 'links'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey('items.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    price: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    title: Mapped[str] = mapped_column(String(2000), nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    merchant_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True
    )
    
    # Relationship
    item: Mapped["Item"] = relationship(back_populates="links")
    
    __table_args__ = (
        Index('idx_link_merchant_rating', 'merchant_name', 'rating'),
        Index('idx_link_price', 'price'),
    )