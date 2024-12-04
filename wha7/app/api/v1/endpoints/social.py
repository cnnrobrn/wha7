"""Social media integration for the Wha7 application.

This module handles core Instagram integration features:
1. Linking Instagram usernames to existing phone numbers
2. Processing webhook authentication challenges
3. Processing incoming messages and media from Instagram
4. Handling different types of media content (reels, stories, posts, images)

The implementation works with the existing PhoneNumber model and maintains
security best practices for webhook processing.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging
from typing import Optional, Dict, Any
import requests
from datetime import datetime

# Internal imports
from app.core.config import get_settings
from app.core.logging import get_logger, monitor_performance
from app.database.session import get_session
from app.models.database.user import PhoneNumber
from app.services.image_processing import process_media_content

# Initialize components
router = APIRouter(prefix="/social", tags=["social"])
logger = get_logger(__name__)
settings = get_settings()

@router.post("/instagram/link")
@monitor_performance("link_instagram")
async def link_instagram_account(
    phone_number: str,
    instagram_username: str,
    db: AsyncSession = Depends(get_session)
):
    """Link an Instagram username to an existing phone number account.
    
    This endpoint:
    1. Validates the phone number exists in our system
    2. Checks if the Instagram username is already linked
    3. Updates the phone number record with the Instagram username
    """
    try:
        # Format phone number consistently
        formatted_phone = format_phone_number(phone_number)
        
        # Check if phone number exists
        user_query = select(PhoneNumber).where(
            PhoneNumber.phone_number == formatted_phone
        )
        user = await db.execute(user_query)
        user = user.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Phone number not found"
            )
            
        # Remove @ symbol if present
        instagram_username = instagram_username.lstrip('@')
        
        # Check if Instagram username is already linked to another account
        existing_query = select(PhoneNumber).where(
            PhoneNumber.instagram_username == instagram_username,
            PhoneNumber.phone_number != formatted_phone
        )
        existing = await db.execute(existing_query)
        
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Instagram username already linked to another account"
            )
            
        # Update the user record
        user.instagram_username = instagram_username
        await db.commit()
        
        logger.info(
            "Instagram account linked successfully",
            phone_number=formatted_phone,
            instagram_username=instagram_username
        )
        
        return {
            "success": True,
            "message": "Instagram account linked successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to link Instagram account", error=e)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to link Instagram account"
        )

@router.get("/instagram/webhook")
async def verify_instagram_webhook(request: Request):
    """Handle Instagram webhook verification challenge.
    
    This endpoint:
    1. Receives the verification request from Instagram
    2. Validates the verify token matches our configuration
    3. Returns the challenge code if verification succeeds
    """
    try:
        # Get verification parameters from request
        mode = request.query_params.get('hub.mode')
        token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge')
        
        logger.info(
            "Received webhook verification request",
            mode=mode,
            token=token
        )
        
        # Verify the mode and token
        if mode and token:
            if mode == 'subscribe' and token == settings.WEBHOOK_VERIFY_TOKEN:
                logger.info("Webhook verification successful")
                return int(challenge)
                
        raise HTTPException(
            status_code=403,
            detail="Failed to verify webhook"
        )
        
    except Exception as e:
        logger.error("Webhook verification failed", error=e)
        raise HTTPException(
            status_code=500,
            detail="Webhook verification failed"
        )

@router.post("/instagram/webhook")
async def process_instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session)
):
    """Process incoming Instagram webhook events.
    
    This endpoint:
    1. Receives webhook events from Instagram
    2. Processes different types of messages and media
    3. Updates our database and processes content as needed
    
    Handles:
    - Direct messages
    - Media shares (images, reels, stories)
    - Mentions and replies
    """
    try:
        # Get the webhook data
        webhook_data = await request.json()
        logger.info("Received Instagram webhook", data=webhook_data)
        
        # Process each entry in the webhook
        for entry in webhook_data.get('entry', []):
            messaging = entry.get('messaging', [])
            
            for message_event in messaging:
                sender_id = message_event.get('sender', {}).get('id')
                if not sender_id:
                    continue
                    
                # Get the username associated with the sender ID
                instagram_username = await get_instagram_username(sender_id)
                if not instagram_username:
                    logger.warning(
                        "Could not find username for sender",
                        sender_id=sender_id
                    )
                    continue
                
                # Process the message content
                await process_message_content(
                    message_event,
                    instagram_username,
                    background_tasks,
                    db
                )
        
        return {"success": True}
        
    except Exception as e:
        logger.error("Failed to process webhook", error=e)
        raise HTTPException(
            status_code=500,
            detail="Failed to process webhook"
        )

async def process_message_content(
    message_event: Dict[str, Any],
    instagram_username: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession
):
    """Process different types of Instagram message content.
    
    This function:
    1. Identifies the type of content (text, image, reel, story)
    2. Extracts relevant data
    3. Processes media content if present
    4. Stores the information in our database
    """
    try:
        message = message_event.get('message', {})
        message_text = message.get('text', '')
        
        # Handle media attachments
        attachments = message.get('attachments', [])
        for attachment in attachments:
            media_type = attachment.get('type')
            media_url = attachment.get('payload', {}).get('url')
            
            if media_type and media_url:
                background_tasks.add_task(
                    process_media_content,
                    media_type=media_type,
                    media_url=media_url,
                    instagram_username=instagram_username,
                    message_text=message_text,
                    db=db
                )
        
        # Handle text-only messages if no media
        if message_text and not attachments:
            # Process text message
            await store_message(
                instagram_username=instagram_username,
                message_text=message_text,
                db=db
            )
            
    except Exception as e:
        logger.error(
            "Failed to process message content",
            error=e,
            instagram_username=instagram_username
        )
        raise

async def get_instagram_username(sender_id: str) -> Optional[str]:
    """Get Instagram username from sender ID using Graph API."""
    try:
        url = f"{settings.GRAPH_API_URL}/{sender_id}"
        params = {
            "fields": "username",
            "access_token": settings.INSTAGRAM_ACCESS_TOKEN
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json().get("username")
            
        return None
        
    except Exception as e:
        logger.error("Failed to fetch Instagram username", error=e)
        return None

def format_phone_number(phone_number: str) -> str:
    """Format phone number consistently with +1 prefix."""
    phone_number = phone_number.strip().replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    if not phone_number.startswith("+1"):
        phone_number = "+1" + phone_number
    return phone_number

# Add the router to your FastAPI app in main.py:
# app.include_router(router)

@router.post("/sms/webhook")
async def handle_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    ai_service: AIService = Depends(get_ai_service),
    db: AsyncSession = Depends(get_session)
):
    """Handle incoming SMS from Twilio."""
    try:
        # Extract SMS data
        form_data = await request.form()
        from_number = form_data.get('From')
        media_url = form_data.get('MediaUrl0')
        text = form_data.get('Body')
        
        if media_url:
            # Process image
            response = requests.get(media_url)
            if response.status_code == 200:
                image_data = base64.b64encode(response.content).decode('utf-8')
                # Process with AI
                result = await ai_service.analyze_outfit_image(
                    image_data=image_data,
                    message_text=text
                )
                # Store results
                await store_outfit_analysis(
                    result,
                    from_number,
                    image_data,
                    db
                )
                return create_sms_response(result)
            else:
                logger.error("Media fetch failed", status_code=response.status_code, url=media_url)
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to fetch media: HTTP {response.status_code}"
                )
        else:
            logger.warning("SMS webhook received without media URL", from_number=from_number)
            raise HTTPException(
                status_code=400,
                detail="SMS must include an image attachment"
            )
    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.error("Network error during media fetch", error=str(e), url=media_url)
        raise HTTPException(
            status_code=503,
            detail="Network error while fetching media"
        )
    except Exception as e:
        logger.error(
            "Unexpected error in SMS webhook handler",
            error=str(e),
            from_number=from_number
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing SMS"
        )