# app/models/domain/item.py
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime

# app/models/domain/item.py
class ItemBase(BaseModel):
    """Base model for item data."""
    description: str = Field(..., min_length=1, max_length=1000)
    search: Optional[str] = Field(None, max_length=1000)

class ItemCreate(ItemBase):
    """Schema for creating a new item."""
    outfit_id: int = Field(..., gt=0)
    generate_links: bool = Field(default=True, description="Whether to automatically generate shopping links")

    @validator('description')
    def description_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip()

class ItemResponse(ItemBase):
    """Schema for basic item response."""
    id: int
    outfit_id: int
    processed_at: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ItemWithLinks(ItemResponse):
    """Schema for item with all its shopping links."""
    links: List["LinkResponse"]

class ItemUpdate(BaseModel):
    """Schema for updating an item."""
    description: Optional[str] = None
    search: Optional[str] = None
    refresh_links: bool = False

class ItemSearchParams(BaseModel):
    """Schema for item search parameters."""
    query: str
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    merchant: Optional[str] = None

class PricePoint(BaseModel):
    """Schema for price history data point."""
    merchant: str
    price: str
    url: str

class PriceHistory(BaseModel):
    """Schema for item price history."""
    item_id: int
    price_points: List[PricePoint]

class SimilarItemResponse(BaseModel):
    """Schema for similar item search results."""
    id: int
    description: str
    similarity_score: float
    links: List["LinkResponse"]