"""Pydantic models for social media integration.

This module defines the data models used for request validation and response
formatting in the social media integration endpoints. The models are designed
to work with our existing database structure while providing strong type checking
and validation for the API layer.

Key model categories:
1. Request validation models for linking accounts and processing webhooks
2. Response models for API endpoints
3. Internal models for processing message and media content
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List, Dict, Literal
from datetime import datetime
import re

class InstagramLinkRequest(BaseModel):
    """Request model for linking Instagram account to phone number."""
    
    phone_number: str = Field(
        ...,
        description="Phone number to link Instagram account to",
        example="+11234567890"
    )
    instagram_username: str = Field(
        ...,
        description="Instagram username without @ symbol",
        example="username123",
        min_length=1,
        max_length=30
    )
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Ensure phone number follows the correct format."""
        # Remove any formatting characters
        cleaned = re.sub(r'[^0-9+]', '', v)
        # Check if it matches our expected format
        if not re.match(r'^\+1[0-9]{10}$', cleaned):
            raise ValueError('Phone number must be in format +1XXXXXXXXXX')
        return cleaned
    
    @validator('instagram_username')
    def validate_instagram_username(cls, v):
        """Clean and validate Instagram username."""
        # Remove @ symbol if present
        cleaned = v.lstrip('@')
        # Check if it follows Instagram's username rules
        if not re.match(r'^[a-zA-Z0-9_.]{1,30}$', cleaned):
            raise ValueError('Invalid Instagram username format')
        return cleaned

class InstagramLinkResponse(BaseModel):
    """Response model for successful Instagram account linking."""
    
    success: bool = Field(
        ...,
        description="Whether the linking was successful"
    )
    message: str = Field(
        ...,
        description="Success or error message"
    )
    instagram_username: str = Field(
        ...,
        description="The linked Instagram username"
    )

class WebhookVerification(BaseModel):
    """Model for Instagram webhook verification challenge."""
    
    mode: str = Field(
        ...,
        description="Verification mode from Instagram"
    )
    verify_token: str = Field(
        ...,
        description="Token to verify webhook authenticity"
    )
    challenge: str = Field(
        ...,
        description="Challenge string to return to Instagram"
    )

class MediaContent(BaseModel):
    """Model for media content in Instagram messages."""
    
    type: Literal["image", "video", "reel", "story"] = Field(
        ...,
        description="Type of media content"
    )
    url: HttpUrl = Field(
        ...,
        description="URL of the media content"
    )
    thumbnail_url: Optional[HttpUrl] = Field(
        None,
        description="URL of content thumbnail, if available"
    )
    duration: Optional[float] = Field(
        None,
        description="Duration in seconds for video content"
    )

class MessageAttachment(BaseModel):
    """Model for attachments in Instagram messages."""
    
    type: str = Field(
        ...,
        description="Type of attachment"
    )
    payload: Dict = Field(
        ...,
        description="Attachment payload data"
    )

class InstagramMessage(BaseModel):
    """Model for Instagram direct messages."""
    
    message_id: str = Field(
        ...,
        description="Unique message identifier"
    )
    sender_id: str = Field(
        ...,
        description="Instagram user ID of sender"
    )
    text: Optional[str] = Field(
        None,
        description="Text content of the message"
    )
    attachments: List[MessageAttachment] = Field(
        default_factory=list,
        description="List of message attachments"
    )
    timestamp: datetime = Field(
        ...,
        description="Message timestamp"
    )

class WebhookEntry(BaseModel):
    """Model for entries in Instagram webhook payload."""
    
    id: str = Field(
        ...,
        description="Entry identifier"
    )
    time: datetime = Field(
        ...,
        description="Entry timestamp"
    )
    messaging: List[InstagramMessage] = Field(
        ...,
        description="List of messaging events"
    )

class WebhookPayload(BaseModel):
    """Model for complete Instagram webhook payload."""
    
    object: str = Field(
        ...,
        description="Webhook object type"
    )
    entry: List[WebhookEntry] = Field(
        ...,
        description="List of webhook entries"
    )

class ProcessedMedia(BaseModel):
    """Model for processed media content."""
    
    media_id: str = Field(
        ...,
        description="Unique identifier for the media"
    )
    instagram_username: str = Field(
        ...,
        description="Username of content creator"
    )
    media_type: str = Field(
        ...,
        description="Type of media content"
    )
    processed_url: HttpUrl = Field(
        ...,
        description="URL of processed media"
    )
    message_text: Optional[str] = Field(
        None,
        description="Associated message text"
    )
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of processing"
    )

class MessageProcessingResponse(BaseModel):
    """Response model for message processing status."""
    
    success: bool = Field(
        ...,
        description="Whether processing was successful"
    )
    message_id: str = Field(
        ...,
        description="ID of the processed message"
    )
    processed_media: Optional[ProcessedMedia] = Field(
        None,
        description="Details of processed media, if any"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if processing failed"
    )

# Example usage in the API endpoints:
"""
@router.post("/instagram/link", response_model=InstagramLinkResponse)
async def link_instagram_account(
    request: InstagramLinkRequest,
    db: AsyncSession = Depends(get_session)
):
    # Implementation using the validated request data
    pass

@router.post("/instagram/webhook")
async def process_instagram_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session)
):
    # Implementation using the validated webhook payload
    pass
"""