"""URL manipulation utilities for the Wha7 application.

This module provides comprehensive URL handling functionality including:
- URL validation and security checking
- URL cleaning and normalization
- Parameter handling and manipulation
- Shortening services integration
- Analytics tracking for links
- Security and safety checks

The utilities are designed to work with shopping links and ensure
proper tracking and security measures.
"""

from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
import re
import hashlib
import time
from datetime import datetime
import tldextract
import validators
from redis import asyncio as aioredis
import httpx
import logging
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

# Initialize components
logger = get_logger(__name__)
settings = get_settings()

class URLValidationError(Exception):
    """Raised when URL validation fails."""
    pass

class URLProcessingError(Exception):
    """Raised when URL processing fails."""
    pass

# Regular expressions for URL validation
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
    r'localhost|'  # localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)

# Known shopping domains for validation
SHOPPING_DOMAINS = {
    'amazon.com',
    'ebay.com',
    'etsy.com',
    # Add more as needed
}

async def validate_url(url: str, check_reachable: bool = False) -> bool:
    """Validate URL format and optionally check if it's reachable.
    
    Args:
        url: URL to validate
        check_reachable: Whether to perform HTTP check
        
    Returns:
        bool: Whether URL is valid
        
    Raises:
        URLValidationError: If validation fails
    """
    try:
        # Basic format validation
        if not URL_PATTERN.match(url):
            raise URLValidationError("Invalid URL format")
        
        # Parse URL
        parsed = urlparse(url)
        
        # Security checks
        if not parsed.scheme in {'http', 'https'}:
            raise URLValidationError("Invalid URL scheme")
        
        # Domain validation
        domain = tldextract.extract(url).registered_domain
        if not domain:
            raise URLValidationError("Invalid domain")
        
        # Optional reachability check
        if check_reachable:
            async with httpx.AsyncClient() as client:
                response = await client.head(url, follow_redirects=True)
                if response.status_code >= 400:
                    raise URLValidationError(f"URL not reachable: {response.status_code}")
        
        return True
        
    except Exception as e:
        logger.error("URL validation failed", error=str(e), url=url)
        raise URLValidationError(f"URL validation failed: {str(e)}")

def clean_url(url: str, remove_tracking: bool = True) -> str:
    """Clean and normalize URL.
    
    Args:
        url: URL to clean
        remove_tracking: Whether to remove tracking parameters
        
    Returns:
        str: Cleaned URL
    """
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Remove known tracking parameters
        if remove_tracking:
            params = parse_qs(parsed.query)
            cleaned_params = {
                k: v for k, v in params.items()
                if not k.lower() in {
                    'utm_source', 'utm_medium', 'utm_campaign',
                    'ref', 'affiliate', 'tracking'
                }
            }
            cleaned_query = urlencode(cleaned_params, doseq=True)
        else:
            cleaned_query = parsed.query
        
        # Reconstruct URL
        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            cleaned_query,
            ''  # Remove fragment
        ))
        
        return cleaned
        
    except Exception as e:
        logger.error("URL cleaning failed", error=str(e), url=url)
        return url

@lru_cache(maxsize=1000)
def is_shopping_url(url: str) -> bool:
    """Check if URL is from a known shopping domain."""
    try:
        domain = tldextract.extract(url).registered_domain.lower()
        return domain in SHOPPING_DOMAINS
    except Exception:
        return False

async def shorten_url(
    url: str,
    redis_client: aioredis.Redis
) -> str:
    """Generate shortened URL.
    
    Args:
        url: URL to shorten
        redis_client: Redis client for storage
        
    Returns:
        str: Shortened URL
    """
    try:
        # Validate URL
        await validate_url(url)
        
        # Generate short code
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        short_code = f"{int(time.time())}-{url_hash}"
        
        # Store in Redis with expiration
        key = f"url:{short_code}"
        await redis_client.setex(
            key,
            settings.URL_EXPIRATION_DAYS * 24 * 60 * 60,  # Convert days to seconds
            url
        )
        
        # Return shortened URL
        return f"{settings.SHORT_URL_DOMAIN}/{short_code}"
        
    except Exception as e:
        logger.error("URL shortening failed", error=str(e), url=url)
        raise URLProcessingError(f"URL shortening failed: {str(e)}")

async def expand_url(
    short_code: str,
    redis_client: aioredis.Redis
) -> Optional[str]:
    """Expand shortened URL.
    
    Args:
        short_code: Short URL code
        redis_client: Redis client for storage
        
    Returns:
        Optional[str]: Original URL if found
    """
    try:
        key = f"url:{short_code}"
        url = await redis_client.get(key)
        return url.decode() if url else None
    except Exception as e:
        logger.error("URL expansion failed", error=str(e), code=short_code)
        return None

async def track_url_click(
    url: str,
    user_id: Optional[int],
    redis_client: aioredis.Redis
):
    """Track URL click analytics.
    
    Args:
        url: Clicked URL
        user_id: Optional user ID
        redis_client: Redis client for storage
    """
    try:
        # Generate keys
        url_hash = hashlib.md5(url.encode()).hexdigest()
        click_key = f"clicks:{url_hash}"
        user_key = f"clicks:user:{user_id}" if user_id else None
        
        # Record click
        pipeline = redis_client.pipeline()
        
        # Increment click count
        pipeline.hincrby(click_key, "total", 1)
        pipeline.hincrby(click_key, datetime.now().strftime("%Y-%m-%d"), 1)
        
        # Record user click if available
        if user_key:
            pipeline.sadd(user_key, url_hash)
        
        await pipeline.execute()
        
    except Exception as e:
        logger.error("Click tracking failed", error=str(e), url=url)

def extract_product_info(url: str) -> Dict[str, Any]:
    """Extract product information from shopping URL.
    
    Args:
        url: Shopping URL
        
    Returns:
        dict: Extracted product information
    """
    try:
        parsed = urlparse(url)
        domain = tldextract.extract(url).domain
        
        # Extract based on domain patterns
        if domain == 'amazon':
            return _extract_amazon_info(parsed)
        elif domain == 'ebay':
            return _extract_ebay_info(parsed)
        else:
            return {
                'domain': domain,
                'path': parsed.path,
                'query': parse_qs(parsed.query)
            }
            
    except Exception as e:
        logger.error("Product info extraction failed", error=str(e), url=url)
        return {}

def _extract_amazon_info(parsed_url: urlparse) -> Dict[str, Any]:
    """Extract product information from Amazon URL."""
    info = {}
    
    # Extract product ID
    match = re.search(r'/dp/([A-Z0-9]{10})', parsed_url.path)
    if match:
        info['product_id'] = match.group(1)
    
    # Extract other information
    params = parse_qs(parsed_url.query)
    if 'tag' in params:
        info['affiliate_tag'] = params['tag'][0]
    
    return info

def _extract_ebay_info(parsed_url: urlparse) -> Dict[str, Any]:
    """Extract product information from eBay URL."""
    info = {}
    
    # Extract item ID
    match = re.search(r'/itm/.*?/(\d+)', parsed_url.path)
    if match:
        info['item_id'] = match.group(1)
    
    return info

# Usage example:
"""
from app.utils.url_helpers import validate_url, clean_url, shorten_url

async def process_product_url(url: str, redis_client: aioredis.Redis) -> str:
    try:
        # Validate URL
        await validate_url(url, check_reachable=True)
        
        # Clean URL
        cleaned_url = clean_url(url)
        
        # Generate short URL
        short_url = await shorten_url(cleaned_url, redis_client)
        
        return short_url
        
    except URLValidationError as e:
        logger.error("URL validation failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except URLProcessingError as e:
        logger.error("URL processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
"""