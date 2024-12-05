# app/database/repositories/users.py
"""Repository for user-related database operations."""

from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.database.user import PhoneNumber, ReferralCode, Referral
from .base import BaseRepository

class UserRepository(BaseRepository[PhoneNumber]):
    """Repository for managing user data."""
    
    async def get_by_phone(self, phone_number: str) -> Optional[PhoneNumber]:
        """Get user by phone number."""
        query = select(PhoneNumber).where(
            PhoneNumber.phone_number == phone_number
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_instagram(self, username: str) -> Optional[PhoneNumber]:
        """Get user by Instagram username."""
        query = select(PhoneNumber).where(
            PhoneNumber.instagram_username == username
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_referral_stats(self, user_id: int) -> Dict[str, int]:
        """Get referral statistics for a user."""
        referrals_query = (
            select(
                func.count(Referral.id).label('total_referrals'),
                func.count(func.distinct(Referral.referred_id)).label('unique_referrals')
            )
            .where(Referral.referrer_id == user_id)
        )
        result = await self.session.execute(referrals_query)
        stats = result.first()
        
        return {
            'total_referrals': stats.total_referrals,
            'unique_referrals': stats.unique_referrals
        }

class ReferralRepository(BaseRepository[ReferralCode]):
    """Repository for managing referral codes and tracking."""
    
    async def get_by_code(self, code: str) -> Optional[ReferralCode]:
        """Get referral code details."""
        query = select(ReferralCode).where(ReferralCode.code == code)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_active_referrals(self, user_id: int) -> List[Referral]:
        """Get active referrals made by user."""
        query = (
            select(Referral)
            .where(Referral.referrer_id == user_id)
            .order_by(Referral.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

# Usage in endpoints:
"""
@router.get("/outfits/{outfit_id}")
async def get_outfit(
    outfit_id: int,
    session: AsyncSession = Depends(get_session)
):
    repository = OutfitRepository(Outfit, session)
    outfit = await repository.get_with_items(outfit_id)
    if not outfit:
        raise HTTPException(status_code=404, detail="Outfit not found")
    return outfit
"""
