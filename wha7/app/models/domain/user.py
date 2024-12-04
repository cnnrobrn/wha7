"""Pydantic models for user management.

These models handle data validation and serialization for the user management
endpoints. They provide strong typing and validation rules while maintaining
flexibility for future extensions.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any

class UserCreate(BaseModel):
    """Model for user registration."""
    phone_number: str = Field(
        ...,
        description="User's phone number",
        example="+11234567890"
    )
    referral_code: Optional[str] = Field(
        None,
        description="Referral code if user was invited"
    )
    
    @validator('phone_number')
    def validate_phone(cls, v):
        """Ensure phone number follows correct format."""
        import re
        if not re.match(r'^\+?1?\d{10}$', v.replace('-', '')):
            raise ValueError('Invalid phone number format')
        return v

class UserPreferences(BaseModel):
    """User preference settings."""
    notifications_enabled: bool = Field(
        True,
        description="Whether user wants to receive notifications"
    )
    private_profile: bool = Field(
        False,
        description="Whether user's profile is private"
    )
    theme: str = Field(
        "light",
        description="User's preferred theme"
    )
    language: str = Field(
        "en",
        description="User's preferred language"
    )

class UserActivity(BaseModel):
    """Model for user activity tracking."""
    user_id: int
    activity_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ReferralStats(BaseModel):
    """Model for referral statistics."""
    total_referrals: int
    unique_referrals: int
    recent_referrals: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    phone_number: str
    is_activated: bool
    instagram_username: Optional[str]
    preferences: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True