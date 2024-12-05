
"""Validation utilities for the Wha7 application.

This module provides custom validation functions and decorators for:
- Data format validation (phone numbers, usernames, etc.)
- Type checking and conversion
- Custom validation rules
- Error message generation
- Validation chaining
- Common validation patterns

The validators are designed to work with both Pydantic models and 
standalone validation needs.
"""

from typing import Any, Callable, Dict, List, Optional, Type, Union, TypeVar
import re
from datetime import datetime
from functools import wraps
import phonenumbers
from pydantic import BaseModel, ValidationError, validator
import logging
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)

# Type definitions
T = TypeVar('T')
ValidationResult = tuple[bool, Optional[str]]

class ValidationError(Exception):
    """Custom validation error with detailed message."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)

# Phone number validation
def validate_phone_number(phone_number: str) -> ValidationResult:
    """Validate phone number format."""
    try:
        # Clean input
        phone_number = phone_number.strip()
        
        # Parse with phonenumbers library
        parsed = phonenumbers.parse(phone_number, "US")
        
        # Check if valid
        if not phonenumbers.is_valid_number(parsed):
            return False, "Invalid phone number format"
            
        # Format consistently
        formatted = phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164
        )
        
        return True, formatted
        
    except Exception as e:
        logger.error(f"Phone validation failed: {str(e)}")
        return False, "Invalid phone number"

# Instagram username validation
def validate_instagram_username(username: str) -> ValidationResult:
    """Validate Instagram username format."""
    try:
        # Remove @ if present
        username = username.lstrip('@')
        
        # Instagram username rules
        pattern = r'^[a-zA-Z0-9_.]{1,30}$'
        
        if not re.match(pattern, username):
            return False, "Invalid Instagram username format"
            
        return True, username
        
    except Exception as e:
        logger.error(f"Username validation failed: {str(e)}")
        return False, "Invalid username"

# Image validation
def validate_image_format(
    mime_type: str,
    allowed_types: Optional[List[str]] = None
) -> ValidationResult:
    """Validate image MIME type."""
    if allowed_types is None:
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    
    if mime_type not in allowed_types:
        return False, f"Unsupported image format. Allowed: {', '.join(allowed_types)}"
    
    return True, None

def validate_image_size(
    size: int,
    max_size: int = 10 * 1024 * 1024  # 10MB default
) -> ValidationResult:
    """Validate image file size."""
    if size > max_size:
        return False, f"Image too large. Maximum size: {max_size/1024/1024}MB"
    
    return True, None

# URL validation
def validate_url(url: str, required_https: bool = True) -> ValidationResult:
    """Validate URL format."""
    try:
        # Basic URL pattern
        pattern = (
            r'^https?:\/\/'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$'
        )
        
        if not re.match(pattern, url, re.IGNORECASE):
            return False, "Invalid URL format"
            
        if required_https and not url.startswith('https://'):
            return False, "URL must use HTTPS"
            
        return True, url
        
    except Exception as e:
        logger.error(f"URL validation failed: {str(e)}")
        return False, "Invalid URL"

# Generic validators
def validate_length(
    value: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
) -> ValidationResult:
    """Validate string length."""
    if min_length and len(value) < min_length:
        return False, f"Must be at least {min_length} characters"
        
    if max_length and len(value) > max_length:
        return False, f"Must be no more than {max_length} characters"
        
    return True, None

def validate_range(
    value: Union[int, float],
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None
) -> ValidationResult:
    """Validate numeric range."""
    if min_value is not None and value < min_value:
        return False, f"Must be greater than or equal to {min_value}"
        
    if max_value is not None and value > max_value:
        return False, f"Must be less than or equal to {max_value}"
        
    return True, None

# Validation decorators
def validate_input(**validators: Dict[str, Callable]) -> Callable:
    """Decorator for input validation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            errors = []
            
            # Apply validators
            for field, validator_func in validators.items():
                if field in kwargs:
                    is_valid, error = validator_func(kwargs[field])
                    if not is_valid:
                        errors.append(f"{field}: {error}")
            
            if errors:
                raise ValidationError("; ".join(errors))
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Pydantic model validators
class PhoneNumberValidator:
    """Phone number validator for Pydantic models."""
    
    @classmethod
    def validate(cls, v: str) -> str:
        is_valid, result = validate_phone_number(v)
        if not is_valid:
            raise ValueError(result)
        return result

class InstagramUsernameValidator:
    """Instagram username validator for Pydantic models."""
    
    @classmethod
    def validate(cls, v: str) -> str:
        is_valid, result = validate_instagram_username(v)
        if not is_valid:
            raise ValueError(result)
        return result

# Example Pydantic model using validators
class UserCreate(BaseModel):
    """Example model with custom validation."""
    phone_number: str
    instagram_username: Optional[str] = None
    
    # Validators
    _validate_phone = validator('phone_number', allow_reuse=True)(
        PhoneNumberValidator.validate
    )
    _validate_instagram = validator('instagram_username', allow_reuse=True)(
        InstagramUsernameValidator.validate
    )

# Usage examples:
"""
# Function with validation decorator
@validate_input(
    phone_number=validate_phone_number,
    instagram=validate_instagram_username
)
async def create_user(phone_number: str, instagram: Optional[str] = None):
    # Function implementation here
    pass

# Direct validation use
phone_valid, phone_result = validate_phone_number("+1234567890")
if not phone_valid:
    raise ValidationError(phone_result)

# Pydantic model validation
try:
    user = UserCreate(
        phone_number="+1234567890",
        instagram_username="user123"
    )
except ValidationError as e:
    logger.error(f"Validation failed: {e.json()}")
    raise
"""