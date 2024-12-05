# app/database/repositories/items.py
"""Repository for item-related database operations."""

from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.database.outfit import Item, Link
from .base import BaseRepository

class ItemRepository(BaseRepository[Item]):
    """Repository for managing item data."""
    
    async def get_with_links(self, item_id: int) -> Optional[Item]:
        """Get item with all its shopping links."""
        query = (
            select(Item)
            .options(selectinload(Item.links))
            .where(Item.id == item_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_outfit(self, outfit_id: int) -> List[Item]:
        """Get all items for an outfit."""
        query = (
            select(Item)
            .options(selectinload(Item.links))
            .where(Item.outfit_id == outfit_id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_unprocessed_items(self, limit: int = 10) -> List[Item]:
        """Get items that haven't been processed for links."""
        query = (
            select(Item)
            .where(Item.processed_at.is_(None))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()