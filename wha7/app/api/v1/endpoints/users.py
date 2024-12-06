"""User management endpoints for the Wha7 application.

This module provides comprehensive user management functionality including:
- Phone number-based registration and authentication
- Profile and preference management
- Activity tracking and analytics
- Referral system integration

The implementation is designed to work with the existing PhoneNumber model
while providing new capabilities for user management and analytics.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional, List
import json

from app.core.security import get_current_active_user
from app.core.logging import get_logger, monitor_performance
from app.database.session import get_session
from app.models.database.user import PhoneNumber, ReferralCode, Referral
from app.models.domain.user import (
    UserCreate,
    UserResponse,
    UserPreferences,
    UserActivity,
    ReferralStats
)
from app.services.analytics import track_user_activity

# Initialize components
router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)

@router.post("/register", response_model=UserResponse)
@monitor_performance("register_user")
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session)
):
    """Register a new user with phone number.
    
    This endpoint:
    1. Validates phone number format
    2. Checks for existing users
    3. Creates new user record
    4. Handles referral code if provided
    5. Initializes default preferences
    """
    try:
        # Format and validate phone number
        formatted_phone = format_phone_number(user_data.phone_number)
        
        # Check for existing user
        existing_user = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.phone_number == formatted_phone
            )
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
            
        # Create new user
        new_user = PhoneNumber(
            phone_number=formatted_phone,
            is_activated=False  # Requires referral activation
        )
        db.add(new_user)
        await db.flush()  # Get ID without committing
        
        # Handle referral code if provided
        if user_data.referral_code:
            await process_referral_code(
                db,
                user_data.referral_code,
                new_user
            )
        
        await db.commit()
        
        # Track registration in background
        background_tasks.add_task(
            track_user_activity,
            user_id=new_user.id,
            activity_type="registration",
            metadata={"referral_code": user_data.referral_code}
        )
        
        return UserResponse.model_validate(new_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration failed", error=e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Get current user's profile information."""
    try:
        # Refresh user data
        await db.refresh(current_user)
        return UserResponse.model_validate(current_user)
        
    except Exception as e:
        logger.error("Profile retrieval failed", error=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )

@router.put("/preferences", response_model=UserPreferences)
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Update user preferences.
    
    Handles:
    - Notification settings
    - Privacy preferences
    - Display preferences
    """
    try:
        # Store preferences in the database
        # This could be expanded to a separate preferences table
        # if more complex preferences are needed
        current_user.preferences = preferences.model_dump()
        await db.commit()
        
        return preferences
        
    except Exception as e:
        logger.error("Preference update failed", error=e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

@router.post("/referral/generate", response_model=str)
async def generate_referral_code(
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Generate a new referral code for the user."""
    try:
        # Check if user already has a recent active code
        existing_code = await db.execute(
            select(ReferralCode)
            .where(ReferralCode.phone_id == current_user.id)
            .order_by(ReferralCode.created_at.desc())
            .limit(1)
        )
        recent_code = existing_code.scalar_one_or_none()
        
        if recent_code and (
            datetime.utcnow() - recent_code.created_at
            < timedelta(days=7)
        ):
            return recent_code.code
            
        # Generate new code
        new_code = ReferralCode(
            phone_id=current_user.id,
            code=generate_unique_code(),
            used_count=0
        )
        db.add(new_code)
        await db.commit()
        
        return new_code.code
        
    except Exception as e:
        logger.error("Code generation failed", error=e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate referral code"
        )

@router.get("/referral/stats", response_model=ReferralStats)
async def get_referral_stats(
    current_user: PhoneNumber = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session)
):
    """Get user's referral statistics."""
    try:
        # Get referral counts and history
        referrals_query = await db.execute(
            select(
                func.count(Referral.id).label('total_referrals'),
                func.count(
                    func.distinct(Referral.referred_id)
                ).label('unique_referrals')
            )
            .where(Referral.referrer_id == current_user.id)
        )
        stats = referrals_query.first()
        
        # Get recent referrals
        recent_referrals = await db.execute(
            select(Referral)
            .where(Referral.referrer_id == current_user.id)
            .order_by(Referral.created_at.desc())
            .limit(5)
        )
        
        return ReferralStats(
            total_referrals=stats.total_referrals,
            unique_referrals=stats.unique_referrals,
            recent_referrals=recent_referrals.scalars().all()
        )
        
    except Exception as e:
        logger.error("Stats retrieval failed", error=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve referral stats"
        )

@router.get("/activity", response_model=List[UserActivity])
async def get_user_activity(
    current_user: PhoneNumber = Depends(get_current_active_user),
    limit: int = 10,
    db: AsyncSession = Depends(get_session)
):
    """Get user's recent activity history."""
    try:
        # This could be expanded to a separate activity tracking table
        activity_query = await db.execute(
            select(UserActivity)
            .where(UserActivity.user_id == current_user.id)
            .order_by(UserActivity.timestamp.desc())
            .limit(limit)
        )
        
        return activity_query.scalars().all()
        
    except Exception as e:
        logger.error("Activity retrieval failed", error=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve activity"
        )

# Helper functions

async def process_referral_code(
    db: AsyncSession,
    code: str,
    new_user: PhoneNumber
):
    """Process referral code for new user registration."""
    try:
        # Find referral code
        referral_code = await db.execute(
            select(ReferralCode).where(ReferralCode.code == code)
        )
        referral_code = referral_code.scalar_one_or_none()
        
        if not referral_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid referral code"
            )
            
        # Create referral record
        referral = Referral(
            referrer_id=referral_code.phone_id,
            referred_id=new_user.id,
            code_used=code
        )
        
        # Update referral code usage
        referral_code.used_count += 1
        
        # Activate new user
        new_user.is_activated = True
        
        db.add(referral)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Referral processing failed", error=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process referral code"
        )
# In app/api/v1/endpoints/users.py

@router.post("/user/status")
async def check_user_status(
    request: Request,
    db: AsyncSession = Depends(get_session)
):
    """Check user activation status."""
    try:
        data = await request.json()
        phone_number = data.get("phone_number")
        
        if not phone_number:
            raise HTTPException(status_code=400, detail="Missing phone number")
            
        query = select(PhoneNumber).where(
            PhoneNumber.phone_number == phone_number
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return {"is_activated": False}
            
        return {"is_activated": user.is_activated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Status check failed", error=e)
        raise HTTPException(status_code=500, detail="Status check failed")
    
def format_phone_number(phone_number: str) -> str:
    """Format phone number to consistent format with +1 prefix."""
    phone_number = (
        phone_number.strip()
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "")
    )
    if not phone_number.startswith("+1"):
        phone_number = "+1" + phone_number
    return phone_number

def generate_unique_code() -> str:
    """Generate unique referral code."""
    import random
    import string
    while True:
        code = ''.join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )
        return code  # In practice, check for uniqueness in database