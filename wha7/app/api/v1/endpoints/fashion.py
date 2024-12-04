from fastapi import APIRouter, Depends, File, UploadFile
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_current_active_user
from app.core.dependencies import get_ai_service, get_search_service, get_session
from app.services.ai import AIService
from app.services.search import SearchService
from app.schemas.user import PhoneNumber
from app.utils.image import store_image

@router.post("/advice")
async def get_fashion_advice(
    query: str,
    image: Optional[UploadFile] = File(None),
    current_user: PhoneNumber = Depends(get_current_active_user),
    ai_service: AIService = Depends(get_ai_service),
    search_service: SearchService = Depends(get_search_service),
    db: AsyncSession = Depends(get_session)
):
    """Get personalized fashion advice combining AI and vector search."""
    try:
        # Process image if provided
        image_analysis = None
        if image:
            image_data = await store_image(image)
            image_analysis = await ai_service.analyze_outfit_image(
                image_data=image_data,
                message_text=query
            )
        
        # Get recommendations
        recommendations = await search_service.find_similar_items(
            query=query,
            image_analysis=image_analysis
        )
        
        return {
            "advice": image_analysis['style_description'] if image_analysis else None,
            "recommendations": recommendations
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing fashion advice request: {str(e)}"
        )