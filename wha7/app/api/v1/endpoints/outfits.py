"""FastAPI endpoints for outfit management.

This module implements endpoints for managing outfit-related operations including:
- CRUD operations for outfits and their items
- Image processing and storage
- Search and filtering functionality
- Social sharing features
- Analytics and reporting
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

# Internal imports
from app.core.security import get_current_active_user
from app.core.logging import get_logger, monitor_performance
from app.database.session import get_session
from app.services.ai_processing import process_outfit_image
from app.services.image_processing import store_image, generate_thumbnail
from app.models.database.outfit import Outfit, Item, Link
from app.models.database.user import PhoneNumber
from app.models.domain.outfit import (
    OutfitCreate,
    OutfitResponse,
    OutfitUpdate,
    OutfitWithItems,
    OutfitAnalytics,
    OutfitSearchParams
)

# Initialize router and logger
router = APIRouter(prefix="/outfits", tags=["outfits"])
logger = get_logger(__name__)

@router.post("/", response_model=OutfitResponse)
@monitor_performance("create_outfit")
async def create_outfit(
    outfit_data: OutfitCreate,
    image: Optional[UploadFile] = File(None),
    current_user: PhoneNumber = Depends(get_current_active_user),
    ai_service: AIService = Depends(get_ai_service),  # Add AI service dependency
    db: AsyncSession = Depends(get_session)
):
    """Create a new outfit with image analysis."""
    try:
        logger.info("Creating new outfit", user_id=current_user.id)
        
        # Process and store image
        image_data = None
        ai_analysis = None
        if image:
            image_data = await store_image(image)
            # Add AI analysis
            ai_analysis = await ai_service.analyze_outfit_image(
                image_data=image_data,
                message_text=outfit_data.description
            )
        
        # Create outfit record
        new_outfit = Outfit(
            phone_id=current_user.id,
            image_data=image_data,
            description=outfit_data.description
        )
        db.add(new_outfit)
        await db.flush()
        
        # Create items from AI analysis
        if ai_analysis:
            for item_data in ai_analysis['items']:
                item = Item(
                    outfit_id=new_outfit.id,
                    description=item_data['description'],
                    search=item_data['search']
                )
                db.add(item)
        
        await db.commit()
        await db.refresh(new_outfit)
        
        return OutfitResponse.model_validate(new_outfit)
        
    except Exception as e:
        logger.error("Failed to create outfit", error=e)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create outfit"
        )

@router.get("/{outfit_id}", response_model=OutfitWithItems)
@monitor_performance("get_outfit")
async def get_outfit(
    outfit_id: int = Path(..., description="The ID of the outfit to retrieve"),
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Retrieve a specific outfit with all its items and links."""
    try:
        query = (
            select(Outfit)
            .options(
                selectinload(Outfit.items).selectinload(Item.links)
            )
            .where(Outfit.id == outfit_id)
        )
        
        result = await db.execute(query)
        outfit = result.scalar_one_or_none()
        
        if not outfit:
            raise HTTPException(status_code=404, detail="Outfit not found")
            
        # Check permission
        if outfit.phone_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this outfit")
            
        return OutfitWithItems.model_validate(outfit)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve outfit", error=e, outfit_id=outfit_id)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[OutfitResponse])
@monitor_performance("search_outfits")
async def search_outfits(
    search_params: OutfitSearchParams = Depends(),
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Search and filter outfits with pagination support."""
    try:
        # Build base query
        query = select(Outfit).where(Outfit.phone_id == current_user.id)
        
        # Apply filters
        if search_params.search_term:
            query = query.where(
                Outfit.description.ilike(f"%{search_params.search_term}%")
            )
            
        # Apply pagination
        query = query.offset(search_params.skip).limit(search_params.limit)
        
        # Execute query
        result = await db.execute(query)
        outfits = result.scalars().all()
        
        return [OutfitResponse.model_validate(outfit) for outfit in outfits]
        
    except Exception as e:
        logger.error("Failed to search outfits", error=e)
        raise HTTPException(status_code=500, detail="Failed to search outfits")

@router.delete("/{outfit_id}")
@monitor_performance("delete_outfit")
async def delete_outfit(
    outfit_id: int = Path(..., description="The ID of the outfit to delete"),
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Delete an outfit and all associated items and links."""
    try:
        # Get outfit with owner check
        query = select(Outfit).where(
            Outfit.id == outfit_id,
            Outfit.phone_id == current_user.id
        )
        result = await db.execute(query)
        outfit = result.scalar_one_or_none()
        
        if not outfit:
            raise HTTPException(status_code=404, detail="Outfit not found")
            
        # Delete outfit (cascade will handle items and links)
        await db.delete(outfit)
        await db.commit()
        
        logger.info("Outfit deleted successfully", outfit_id=outfit_id)
        return {"message": "Outfit deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete outfit", error=e, outfit_id=outfit_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete outfit")

@router.get("/analytics/user", response_model=OutfitAnalytics)
@monitor_performance("get_user_analytics")
async def get_user_analytics(
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Get analytics about user's outfits and engagement."""
    try:
        # Get total outfits count
        outfits_query = select(func.count(Outfit.id)).where(
            Outfit.phone_id == current_user.id
        )
        outfits_result = await db.execute(outfits_query)
        total_outfits = outfits_result.scalar_one()
        
        # Get total items count
        items_query = (
            select(func.count(Item.id))
            .join(Outfit)
            .where(Outfit.phone_id == current_user.id)
        )
        items_result = await db.execute(items_query)
        total_items = items_result.scalar_one()
        
        # Calculate average items per outfit
        avg_items = total_items / total_outfits if total_outfits > 0 else 0
        
        return OutfitAnalytics(
            total_outfits=total_outfits,
            total_items=total_items,
            average_items_per_outfit=round(avg_items, 2)
        )
        
    except Exception as e:
        logger.error("Failed to get analytics", error=e, user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Failed to get analytics")

# Add the router to your FastAPI app in main.py:
# app.include_router(router)