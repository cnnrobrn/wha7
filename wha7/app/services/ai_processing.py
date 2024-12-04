
"""AI service integration for image and text processing.

This module provides a comprehensive AI service using OpenAI's GPT-4 Vision model for:
- Image analysis and item identification
- Style recommendations
- Content moderation
- Text processing
- Trend analysis

The service is designed to work with both image and text inputs while maintaining
type safety and proper error handling.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import base64
from pydantic import BaseModel
from openai import OpenAI
import asyncio
from functools import wraps

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain.outfit import OutfitBase
from app.models.domain.item import ItemBase
from app.models.domain.common import (
    ContentModerationResult,
    StyleRecommendation,
    TrendAnalysis
)

# Initialize components
logger = get_logger(__name__)
settings = get_settings()

class AIService:
    """Core AI service implementing OpenAI integrations."""
    
    def __init__(self):
        """Initialize AI service with OpenAI client."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Latest model for image and text processing
    
    async def analyze_outfit_image(
        self,
        image_data: str,
        message_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze outfit image to identify items and generate descriptions.
        
        Args:
            image_data: Base64 encoded image data
            message_text: Optional text context for the analysis
            
        Returns:
            Dict containing identified items and analysis
        """
        try:
            # Construct the system prompt for item identification
            system_prompt = """
            You are an expert fashion analyst. Identify each clothing item and 
            accessory in the image with precise detail, including:
            - Item type and category
            - Colors and patterns
            - Materials and textures
            - Brand identification if possible
            - Style characteristics
            Provide a detailed search description for each item.
            """
            
            # Format prompt for outfit analysis
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add image and text content
            user_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            ]
            
            if message_text:
                user_content.insert(0, {
                    "type": "text",
                    "text": message_text
                })
                
            messages.append({
                "role": "user",
                "content": user_content
            })
            
            # Make API call with parse type hints
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=OutfitAnalysisResponse,
                max_tokens=1000
            )
            
            return response.choices[0].message.parsed.dict()
            
        except Exception as e:
            logger.error("Image analysis failed", error=e)
            raise

    async def get_style_recommendations(
        self,
        user_preferences: Dict[str, Any],
        outfit_history: List[Dict[str, Any]]
    ) -> List[StyleRecommendation]:
        """Generate personalized style recommendations.
        
        Uses user preferences and outfit history to generate relevant
        style suggestions and trend recommendations.
        """
        try:
            # Construct prompt for style recommendations
            prompt = f"""
            Based on the user's preferences and outfit history, provide 
            personalized style recommendations. Consider:
            - Current fashion trends
            - User's past choices
            - Seasonal appropriateness
            - Style consistency
            
            User Preferences: {user_preferences}
            Recent Outfits: {outfit_history[-5:]}  # Last 5 outfits
            """
            
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a personal style consultant."},
                    {"role": "user", "content": prompt}
                ],
                response_format=StyleRecommendationResponse,
                max_tokens=500
            )
            
            return response.choices[0].message.parsed.recommendations
            
        except Exception as e:
            logger.error("Style recommendation failed", error=e)
            raise

    async def moderate_content(
        self,
        image_data: Optional[str] = None,
        text_content: Optional[str] = None
    ) -> ContentModerationResult:
        """Moderate image and text content for appropriateness.
        
        Checks content against community guidelines and flags potential issues.
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": "Analyze content for compliance with community guidelines."
                }
            ]
            
            # Add content to analyze
            user_content = []
            if text_content:
                user_content.append({
                    "type": "text",
                    "text": text_content
                })
            
            if image_data:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                })
            
            messages.append({
                "role": "user",
                "content": user_content
            })
            
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=ContentModerationResponse,
                max_tokens=200
            )
            
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error("Content moderation failed", error=e)
            raise

    async def analyze_trends(
        self,
        recent_outfits: List[Dict[str, Any]],
        timeframe: str = "last_30_days"
    ) -> TrendAnalysis:
        """Analyze fashion trends based on user data.
        
        Identifies emerging trends, popular styles, and seasonal patterns.
        """
        try:
            prompt = f"""
            Analyze recent outfit data to identify:
            - Popular style patterns
            - Emerging trends
            - Seasonal preferences
            - Color combinations
            - Common item pairings
            
            Timeframe: {timeframe}
            Recent Outfits: {recent_outfits}
            """
            
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fashion trend analyst."},
                    {"role": "user", "content": prompt}
                ],
                response_format=TrendAnalysisResponse,
                max_tokens=800
            )
            
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error("Trend analysis failed", error=e)
            raise

# Pydantic models for structured responses
class OutfitAnalysisResponse(BaseModel):
    """Response model for outfit analysis."""
    items: List[Dict[str, str]]
    style_description: str
    occasion_suggestions: List[str]
    confidence_score: float

class StyleRecommendationResponse(BaseModel):
    """Response model for style recommendations."""
    recommendations: List[StyleRecommendation]

class ContentModerationResponse(BaseModel):
    """Response model for content moderation."""
    is_appropriate: bool
    confidence_score: float
    flags: List[str]
    explanation: Optional[str]

class TrendAnalysisResponse(BaseModel):
    """Response model for trend analysis."""
    trends: List[Dict[str, Any]]
    seasonal_insights: Dict[str, List[str]]
    popularity_metrics: Dict[str, float]

# Service initialization
async def get_ai_service() -> AIService:
    """Get initialized AI service instance."""
    return AIService()
