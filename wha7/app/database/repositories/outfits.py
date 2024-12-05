# app/database/repositories/outfits.py
"""Repository for outfit-related database operations."""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from app.models.database.outfit import Outfit, Item
from .base import BaseRepository

class OutfitRepository(BaseRepository[Outfit]):
    """Repository for managing outfit data."""
    
    async def get_with_items(self, outfit_id: int) -> Optional[Outfit]:
        """Get outfit with all its items and links."""
        query = (
            select(Outfit)
            .options(selectinload(Outfit.items).selectinload(Item.links))
            .where(Outfit.id == outfit_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_outfits(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20
    ) -> List[Outfit]:
        """Get outfits for a specific user."""
        query = (
            select(Outfit)
            .where(Outfit.phone_id == user_id)
            .order_by(Outfit.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_user_outfit_count(self, user_id: int) -> int:
        """Get total number of outfits for a user."""
        query = select(func.count(Outfit.id)).where(
            Outfit.phone_id == user_id
        )
        result = await self.session.execute(query)
        return result.scalar_one()