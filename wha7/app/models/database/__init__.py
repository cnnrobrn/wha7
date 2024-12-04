# app/models/database/__init__.py
"""Database models initialization."""

from .base import Base
from .outfit import Outfit
from .item import Item, Link
from .user import PhoneNumber, ReferralCode, Referral

# This makes imports cleaner elsewhere in the application
__all__ = [
    'Base',
    'Outfit',
    'Item',
    'Link',
    'PhoneNumber',
    'ReferralCode',
    'Referral'
]