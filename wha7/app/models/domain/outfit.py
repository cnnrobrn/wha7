# app/models/domain/outfit.py
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime

# app/models/domain/outfit.py
class OutfitBase(BaseModel):
    """Base model for outfit data."""
    description: str = Field(..., min_length=1, max_length=1000)

class OutfitCreate(OutfitBase):
    """Schema for creating a new outfit."""
    image_data: Optional[str] = None

class OutfitResponse(OutfitBase):
    """Schema for outfit response."""
    id: int
    phone_id: int
    image_data: Optional[str]
    created_at: datetime
    updated_at: datetime
    item_count: int = Field(default=0, description="Number of items in this outfit")

    class Config:
        from_attributes = True

class OutfitWithItems(OutfitResponse):
    """Schema for outfit with nested items and links."""
    items: List["ItemWithLinks"]

class OutfitSearchParams(BaseModel):
    """Schema for outfit search parameters."""
    search_term: Optional[str] = None
    skip: int = 0
    limit: int = 10

class OutfitAnalytics(BaseModel):
    """Schema for outfit analytics."""
    total_outfits: int
    total_items: int
    average_items_per_outfit: float