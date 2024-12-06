"""Social media service for the Wha7 application.

This service handles all social media integrations including:
- Instagram Graph API integration
- Webhook processing and validation
- Rate limiting and quota management
- Error handling and retries
- Event tracking and analytics

The service is designed to work with the social endpoints while maintaining
proper separation of concerns and security practices.
"""

from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta
import json
import httpx
from fastapi import HTTPException
import time
from redis import asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.image_processing import ImageProcessingService
from app.services.ai_processing import AIService
from app.models.domain.social import (
    InstagramMessage,
    ProcessedMedia,
    WebhookPayload
)

# Initialize components
logger = get_logger(__name__)
settings = get_settings()

class RateLimiter:
    """Rate limit implementation for API calls."""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.window_size = 3600  # 1 hour window
        self.max_requests = 1000  # Maximum requests per window
    
    async def check_rate_limit(self, key: str) -> bool:
        """Check if operation is within rate limits."""
        current = int(time.time())
        window_key = f"ratelimit:{key}:{current // self.window_size}"
        
        # Get current count
        count = await self.redis.get(window_key)
        if not count:
            await self.redis.setex(
                window_key,
                self.window_size,
                1
            )
            return True
            
        count = int(count)
        if count >= self.max_requests:
            return False
            
        await self.redis.incr(window_key)
        return True

class SocialMediaService:
    """Service for handling social media integrations."""
    
    def __init__(
        self,
        image_service: ImageProcessingService,
        ai_service: AIService,
        redis_client: aioredis.Redis
    ):
        """Initialize service with required dependencies."""
        self.image_service = image_service
        self.ai_service = ai_service
        self.rate_limiter = RateLimiter(redis_client)
        
        # Initialize HTTP client with timeouts
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5)
        )
        
        # Load configuration
        self.graph_api_url = settings.GRAPH_API_URL
        self.access_token = settings.INSTAGRAM_ACCESS_TOKEN
        self.webhook_token = settings.WEBHOOK_VERIFY_TOKEN
    
    async def verify_webhook(
        self,
        mode: str,
        token: str,
        challenge: str
    ) -> Optional[str]:
        """Verify Instagram webhook challenge.
        
        This method verifies the webhook challenge according to
        Instagram's requirements. It ensures the webhook is properly
        configured and secured.
        """
        try:
            logger.info("Verifying webhook", mode=mode, token=token)
            
            if not all([mode, token, challenge]):
                raise ValueError("Missing required verification parameters")
            
            if mode != 'subscribe':
                raise ValueError(f"Invalid mode: {mode}")
                
            if token != self.webhook_token:
                raise ValueError("Token verification failed")
                
            return challenge
            
        except Exception as e:
            logger.error("Webhook verification failed", error=e)
            raise HTTPException(status_code=400, detail="Verification failed")
    
    async def process_webhook(
        self,
        payload: WebhookPayload
    ) -> Dict[str, Any]:
        """Process incoming webhook events from Instagram.
        
        This method handles different types of webhook events:
        - Direct messages
        - Media shares
        - Story mentions
        - Comments
        """
        try:
            logger.info("Processing webhook payload", payload=payload)
            
            if not await self.rate_limiter.check_rate_limit('webhook'):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            results = []
            for entry in payload.entry:
                # Process each message in the entry
                for message in entry.messaging:
                    result = await self._process_message(message)
                    results.append(result)
            
            return {"processed_messages": len(results)}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Webhook processing failed", error=e)
            raise HTTPException(status_code=500, detail="Processing failed")
    # app/services/social_media.py

    async def process_reel(reel_url: str, message: InstagramMessage):
        """Process Instagram reel with optimized frame sampling."""
        frames = []
        video = cv2.VideoCapture(reel_url)
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * 2)  # Sample every 2 seconds
        max_frames = 5
        frame_count = 0
        
        while len(frames) < max_frames:
            ret, frame = video.read()
            if not ret:
                break
                
            if frame_count % frame_interval == 0:
                # Check if frame is unique using image similarity
                if not frames or is_frame_unique(frame, frames[-1]):
                    frames.append(frame)
                    
            frame_count += 1
        
        video.release()
        
        # Process unique frames
        for frame in frames:
            analysis = await ai_service.analyze_outfit_image(frame)
            await store_outfit_analysis(analysis, message.sender)
    
    def is_frame_unique(new_frame, prev_frame, threshold=0.8):
        """Check if frame is significantly different from previous."""
        similarity = structural_similarity(new_frame, prev_frame, multichannel=True)
        return similarity < threshold
    
    async def _process_message(
        self,
        message: InstagramMessage
    ) -> Dict[str, Any]:
        """Process individual Instagram message.
        
        This method:
        1. Gets user information
        2. Processes any media content
        3. Generates appropriate response
        4. Tracks analytics
        """
        try:
            # Get user information
            username = await self._get_username(message.sender_id)
            
            # Process media if present
            media_results = []
            for attachment in message.attachments:
                if attachment.type in ['image', 'video', 'reel']:
                    result = await self._process_media(
                        attachment,
                        username,
                        message.text
                    )
                    media_results.append(result)
            
            # Generate and send response
            response = await self._generate_response(
                username,
                message,
                media_results
            )
            
            await self._send_response(
                message.sender_id,
                response
            )
            
            return {
                "message_id": message.message_id,
                "processed_media": len(media_results),
                "username": username
            }
            
        except Exception as e:
            logger.error("Message processing failed", error=e)
            raise
    
    async def _process_media(
        self,
        attachment: Dict[str, Any],
        username: str,
        message_text: Optional[str]
    ) -> ProcessedMedia:
        """Process media content from Instagram.
        
        Handles:
        1. Media download
        2. Format conversion
        3. AI analysis
        4. Storage management
        """
        try:
            media_url = attachment.payload.url
            
            if attachment.type == 'video':
                # Extract frames from video
                frames = await self.image_service.process_video_frames(
                    media_url
                )
                
                # Analyze each frame
                results = []
                for frame in frames:
                    analysis = await self.ai_service.analyze_outfit_image(
                        frame,
                        message_text
                    )
                    results.append(analysis)
                
                return ProcessedMedia(
                    media_id=str(time.time()),
                    instagram_username=username,
                    media_type='video',
                    processed_url=media_url,
                    message_text=message_text,
                    analysis_results=results
                )
                
            else:  # Image processing
                image_data = await self.image_service.process_url(media_url)
                
                analysis = await self.ai_service.analyze_outfit_image(
                    image_data,
                    message_text
                )
                
                return ProcessedMedia(
                    media_id=str(time.time()),
                    instagram_username=username,
                    media_type='image',
                    processed_url=media_url,
                    message_text=message_text,
                    analysis_results=[analysis]
                )
                
        except Exception as e:
            logger.error("Media processing failed", error=e)
            raise
    
    async def _get_username(self, user_id: str) -> str:
        """Get Instagram username from user ID."""
        try:
            if not await self.rate_limiter.check_rate_limit(f'user:{user_id}'):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            url = f"{self.graph_api_url}/{user_id}"
            params = {
                "fields": "username",
                "access_token": self.access_token
            }
            
            async with self.http_client as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
            return data.get("username")
            
        except Exception as e:
            logger.error("Username lookup failed", error=e)
            raise
    
    async def _send_response(
        self,
        user_id: str,
        message: str
    ) -> Dict[str, Any]:
        """Send response message to Instagram user."""
        try:
            if not await self.rate_limiter.check_rate_limit(f'message:{user_id}'):
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            url = f"{self.graph_api_url}/me/messages"
            data = {
                "recipient": {"id": user_id},
                "message": {"text": message},
                "access_token": self.access_token
            }
            
            async with self.http_client as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error("Message send failed", error=e)
            raise

# Initialize service
async def get_social_service(
    image_service: ImageProcessingService = Depends(get_image_service),
    ai_service: AIService = Depends(get_ai_service),
    redis: aioredis.Redis = Depends(get_redis)
) -> SocialMediaService:
    """Get initialized social media service."""
    return SocialMediaService(
        image_service=image_service,
        ai_service=ai_service,
        redis_client=redis
    )
