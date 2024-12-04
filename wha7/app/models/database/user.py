# File: app/models/database/user.py

"""User-related database models including phone numbers and referral system.

This module contains all models related to user management, including:
- Phone number registration
- Referral system
- User activation status
- Social media integration
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, Index
from .base import Base

class PhoneNumber(Base):
    """User account model based on phone number identification.
    
    This model serves as the primary user entity, managing:
    - Phone number verification
    - Account activation status
    - Social media connections
    - Referral relationships
    """
    __tablename__ = 'phone_numbers'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(20), 
        unique=True,
        nullable=True,
        index=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    # Add preferences relationship
    preferences: Mapped["UserPreferences"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    is_activated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    instagram_username: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True
    )
    
    # Relationships
    outfits: Mapped[List["Outfit"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    referral_codes: Mapped[List["ReferralCode"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_phone_activation', 'phone_number', 'is_activated'),
        Index('idx_instagram_username', 'instagram_username')
    )

class ReferralCode(Base):
    """Referral code management for user invitations.
    
    Tracks:
    - Unique referral codes
    - Usage statistics
    - Ownership and creation details
    """
    __tablename__ = 'referral_codes'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    phone_id: Mapped[int] = mapped_column(
        ForeignKey('phone_numbers.id', ondelete='CASCADE'),
        nullable=False
    )
    code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True
    )
    used_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Relationships
    owner: Mapped["PhoneNumber"] = relationship(back_populates="referral_codes")
    referrals: Mapped[List["Referral"]] = relationship(
        back_populates="referral_code",
        cascade="all, delete-orphan"
    )

class Referral(Base):
    """Tracks referral relationships between users.
    
    Maintains the connection between:
    - Referring user
    - Referred user
    - Referral code used
    """
    __tablename__ = 'referrals'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(
        ForeignKey('phone_numbers.id', ondelete='CASCADE'),
        nullable=False
    )
    referred_id: Mapped[int] = mapped_column(
        ForeignKey('phone_numbers.id', ondelete='CASCADE'),
        nullable=False
    )
    code_used: Mapped[str] = mapped_column(
        ForeignKey('referral_codes.code', ondelete='CASCADE'),
        nullable=False
    )
    
    # Relationships
    referrer: Mapped["PhoneNumber"] = relationship(
        foreign_keys=[referrer_id]
    )
    referred: Mapped["PhoneNumber"] = relationship(
        foreign_keys=[referred_id]
    )
    referral_code: Mapped["ReferralCode"] = relationship(back_populates="referrals")
    
    # Indexes for tracking and analytics
    __table_args__ = (
        Index('idx_referral_tracking', 'referrer_id', 'referred_id', 'code_used'),
    )

class UserPreferences(Base):
    """User preference settings."""
    __tablename__ = 'user_preferences'
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey('phone_numbers.id', ondelete='CASCADE'),
        primary_key=True
    )
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    theme: Mapped[str] = mapped_column(
        String(20),
        default='light',
        nullable=False
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default='en',
        nullable=False
    )
    
    # Relationship
    user: Mapped["PhoneNumber"] = relationship(back_populates="preferences")