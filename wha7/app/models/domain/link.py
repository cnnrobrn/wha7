# app/models/domain/link.py
from typing import Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime

class LinkBase(BaseModel):
    """Base model for link data."""
    url: HttpUrl
    photo_url: Optional[str] = None
    price: Optional[str] = None
    title: str
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    merchant_name: Optional[str] = None

class LinkCreate(LinkBase):
    """Model for creating new links."""
    item_id: int

class LinkResponse(LinkBase):
    """Response model for links."""
    id: int
    item_id: int
    created_at: datetime

    class Config:
        from_attributes = True