"""Router configuration for the Wha7 application.

This module organizes and configures all API routes, combining endpoints from
different modules into a unified API structure.
"""

from fastapi import APIRouter

# Import endpoint routers
from app.api.v1.endpoints import (
    outfits,
    items,
    users,
    social,
    fashion,
    search
)

# Create main router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(outfits.router, prefix="/outfits", tags=["outfits"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(social.router, prefix="/social", tags=["social"])
api_router.include_router(fashion.router, prefix="/fashion", tags=["fashion"])
api_router.include_router(search.router, prefix="/search", tags=["search"])

# Health check endpoint
@api_router.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}