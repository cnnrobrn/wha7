"""FastAPI endpoints for item management.

This module implements comprehensive endpoints for managing individual clothing items, including:
- CRUD operations for items and their associated links
- Price tracking and availability monitoring
- Similar item recommendations using vector search
- Categorization and search functionality
- Analytics and performance monitoring

The endpoints integrate with the existing database models and implement proper error
handling, logging, and security measures.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

# Internal imports
from app.core.security import get_current_active_user
from app.core.logging import get_logger, monitor_performance
from app.database.session import get_session
from app.services.ai_processing import get_item_recommendations
from app.services.search import vector_similarity_search
from app.models.database.outfit import Outfit, Item, Link
from app.models.database.user import PhoneNumber
from app.models.domain.item import (
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    ItemWithLinks,
    ItemSearchParams,
    PriceHistory,
    SimilarItemResponse
)

# Initialize router and logger
router = APIRouter(prefix="/items", tags=["items"])
logger = get_logger(__name__)

@router.post("/", response_model=ItemResponse)
@monitor_performance("create_item")
async def create_item(
    item_data: ItemCreate,
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Create a new item and automatically generate shopping links.
    
    This endpoint:
    1. Creates the item record
    2. Processes the description for search terms
    3. Generates shopping recommendations
    4. Creates associated links
    """
    try:
        logger.info("Creating new item", outfit_id=item_data.outfit_id)
        
        # Verify outfit ownership
        outfit_query = select(Outfit).where(
            Outfit.id == item_data.outfit_id,
            Outfit.phone_id == current_user.id
        )
        outfit = await db.execute(outfit_query)
        if not outfit.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not authorized to modify this outfit")
        
        # Create item
        new_item = Item(
            outfit_id=item_data.outfit_id,
            description=item_data.description,
            search=item_data.search or item_data.description  # Use description as fallback
        )
        db.add(new_item)
        await db.flush()  # Get the ID without committing
        
        # Generate shopping links if requested
        if item_data.generate_links:
            links = await get_item_recommendations(new_item.search)
            for link_data in links:
                link = Link(
                    item_id=new_item.id,
                    url=link_data.url,
                    photo_url=link_data.photo_url,
                    price=link_data.price,
                    title=link_data.title,
                    rating=link_data.rating,
                    reviews_count=link_data.reviews_count,
                    merchant_name=link_data.merchant_name
                )
                db.add(link)
        
        await db.commit()
        await db.refresh(new_item)
        
        logger.info("Item created successfully", item_id=new_item.id)
        return ItemResponse.model_validate(new_item)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create item", error=e)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create item")

@router.get("/{item_id}", response_model=ItemWithLinks)
@monitor_performance("get_item")
async def get_item(
    item_id: int = Path(..., description="The ID of the item to retrieve"),
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Retrieve a specific item with all its shopping links."""
    try:
        query = (
            select(Item)
            .options(selectinload(Item.links))
            .join(Outfit)
            .where(
                Item.id == item_id,
                Outfit.phone_id == current_user.id
            )
        )
        
        result = await db.execute(query)
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
            
        return ItemWithLinks.model_validate(item)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve item", error=e, item_id=item_id)
        raise HTTPException(status_code=500, detail="Internal server error")
# In app/api/v1/endpoints/items.py
# In app/api/v1/endpoints/items.py

@router.get("/items")
async def get_outfit_items(
    outfit_id: int = Query(...),
    db: AsyncSession = Depends(get_session)
):
    """Get items for a specific outfit."""
    try:
        query = (
            select(Item)
            .options(selectinload(Item.links))
            .where(Item.outfit_id == outfit_id)
        )
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        return items
    except Exception as e:
        logger.error("Failed to get items", error=e)
        raise HTTPException(status_code=500, detail="Failed to get items")
    
@router.get("/links")
async def get_item_links(
    item_id: int = Query(...),
    db: AsyncSession = Depends(get_session)
):
    """Get shopping links for an item."""
    try:
        query = select(Link).where(Link.item_id == item_id)
        result = await db.execute(query)
        links = result.scalars().all()
        
        return links
    except Exception as e:
        logger.error("Failed to get links", error=e)
        raise HTTPException(status_code=500, detail="Failed to get links")
    
@router.get("/search/similar", response_model=List[SimilarItemResponse])
@monitor_performance("search_similar_items")
async def search_similar_items(
    query: str = Query(..., description="Search query for similar items"),
    limit: int = Query(10, description="Maximum number of results to return"),
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Find similar items using vector similarity search."""
    try:
        # Perform vector similarity search
        similar_items = await vector_similarity_search(
            query=query,
            limit=limit,
            user_id=current_user.id
        )
        
        return [SimilarItemResponse.model_validate(item) for item in similar_items]
        
    except Exception as e:
        logger.error("Failed to search similar items", error=e)
        raise HTTPException(status_code=500, detail="Failed to search similar items")

@router.get("/{item_id}/price-history", response_model=PriceHistory)
@monitor_performance("get_price_history")
async def get_price_history(
    item_id: int = Path(..., description="The ID of the item"),
    days: int = Query(30, description="Number of days of price history"),
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Retrieve price history for an item's shopping links."""
    try:
        # Verify item access
        item_query = (
            select(Item)
            .join(Outfit)
            .where(
                Item.id == item_id,
                Outfit.phone_id == current_user.id
            )
        )
        item = await db.execute(item_query)
        if not item.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Get price history from links
        price_query = (
            select(Link.merchant_name, Link.price, Link.url)
            .where(Link.item_id == item_id)
            .order_by(desc(Link.rating))  # Prioritize highly rated merchants
        )
        
        result = await db.execute(price_query)
        price_data = result.fetchall()
        
        return PriceHistory(
            item_id=item_id,
            price_points=[{
                "merchant": price[0],
                "price": price[1],
                "url": price[2]
            } for price in price_data]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get price history", error=e, item_id=item_id)
        raise HTTPException(status_code=500, detail="Failed to get price history")

@router.put("/{item_id}", response_model=ItemResponse)
@monitor_performance("update_item")
async def update_item(
    item_id: int,
    item_data: ItemUpdate,
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Update an item's details and optionally refresh its shopping links."""
    try:
        # Verify item ownership
        query = (
            select(Item)
            .join(Outfit)
            .where(
                Item.id == item_id,
                Outfit.phone_id == current_user.id
            )
        )
        
        result = await db.execute(query)
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Update fields
        for field, value in item_data.dict(exclude_unset=True).items():
            setattr(item, field, value)
        
        # Refresh shopping links if requested
        if item_data.refresh_links:
            # Delete existing links
            await db.execute(select(Link).where(Link.item_id == item_id).delete())
            
            # Generate new links
            new_links = await get_item_recommendations(item.search)
            for link_data in new_links:
                link = Link(
                    item_id=item.id,
                    url=link_data.url,
                    photo_url=link_data.photo_url,
                    price=link_data.price,
                    title=link_data.title,
                    rating=link_data.rating,
                    reviews_count=link_data.reviews_count,
                    merchant_name=link_data.merchant_name
                )
                db.add(link)
        
        await db.commit()
        await db.refresh(item)
        
        return ItemResponse.model_validate(item)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update item", error=e, item_id=item_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update item")

@router.delete("/{item_id}")
@monitor_performance("delete_item")
async def delete_item(
    item_id: int,
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Delete an item and all its associated links."""
    try:
        # Verify item ownership
        query = (
            select(Item)
            .join(Outfit)
            .where(
                Item.id == item_id,
                Outfit.phone_id == current_user.id
            )
        )
        
        result = await db.execute(query)
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Delete item (cascade will handle links)
        await db.delete(item)
        await db.commit()
        
        logger.info("Item deleted successfully", item_id=item_id)
        return {"message": "Item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete item", error=e, item_id=item_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete item")

@router.post("/analyze")
async def analyze_item(
    item_id: int,
    ai_service: AIService = Depends(get_ai_service),
    db: AsyncSession = Depends(get_session)
):
    """Analyze item using AI for better recommendations."""
    try:
        # Get item
        item = await get_item_with_outfit(item_id, db)
        
        # Perform AI analysis
        analysis = await ai_service.analyze_outfit_image(
            image_data=item.outfit.image_data,
            message_text=item.description
        )
        
        # Update item with analysis
        await update_item_with_analysis(item, analysis, db)
        
        return {
            "message": "Item analyzed successfully",
            "analysis": analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to analyze item", error=e, item_id=item_id)
        raise HTTPException(status_code=500, detail="Failed to analyze item")


# Add the router to your FastAPI app in main.py:
# app.include_router(router)