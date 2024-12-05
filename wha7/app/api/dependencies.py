"""Dependencies for FastAPI application.

This module defines dependencies used across API endpoints including:
- Database session management
- Service instances
- Authentication/security checks
- Configuration access
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis

# Internal imports
from app.core.config import get_settings
from app.core.security import get_current_active_user
from app.database.session import get_session
from app.services.ai_processing import AIService, get_ai_service
from app.services.image_processing import ImageProcessingService, get_image_service
from app.services.social_media import SocialMediaService, get_social_service
from app.services.search import SearchService, get_search_service
from app.services.messaging import MessageService, get_message_service
from app.models.database.user import PhoneNumber

settings = get_settings()

# Database Dependencies
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    try:
        db = get_session()
        async with db() as session:
            yield session
    finally:
        await session.close()

# Redis Dependencies
async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Dependency for getting Redis connection."""
    redis = await aioredis.from_url(settings.REDIS_URL)
    try:
        yield redis
    finally:
        await redis.close()

# Service Dependencies
async def get_services(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
) -> dict:
    """Get all service instances."""
    return {
        'ai_service': await get_ai_service(),
        'image_service': await get_image_service(),
        'social_service': await get_social_service(),
        'search_service': await get_search_service(redis),
        'message_service': await get_message_service()
    }

# User Dependencies
async def get_current_user(
    db: AsyncSession = Depends(get_db)
) -> PhoneNumber:
    """Get current authenticated user."""
    return await get_current_active_user(db)

async def get_optional_user(
    db: AsyncSession = Depends(get_db)
) -> Optional[PhoneNumber]:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_active_user(db)
    except HTTPException:
        return None

# Common Query Parameters
class CommonQueryParams:
    """Common query parameters for pagination."""
    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        order: str = "desc"
    ):
        self.skip = skip
        self.limit = limit
        self.order_by = order_by
        self.order = order

# Usage in endpoints:
"""
from app.api.dependencies import get_current_user, get_services, CommonQueryParams

@router.get("/outfits")
async def get_outfits(
    commons: CommonQueryParams = Depends(),
    current_user: PhoneNumber = Depends(get_current_user),
    services: dict = Depends(get_services),
    db: AsyncSession = Depends(get_db)
):
    ai_service = services['ai_service']
    search_service = services['search_service']
    # Implementation here
"""
