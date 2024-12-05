
"""Image processing utilities for the Wha7 application.

This module provides low-level image processing functions used by higher-level
services. It handles:
- Image validation and security checks
- Format conversions and optimization
- Metadata management
- Error handling and logging
- Performance optimizations through caching and size management

Note: This module focuses on utility functions used by the ImageProcessingService
and should not be used directly by endpoints.
"""

from typing import Optional, Tuple, Dict, Union
from PIL import Image, ImageOps, ExifTags
import io
import base64
import imghdr
import hashlib
from pathlib import Path
import magic
import numpy as np
import cv2
from functools import lru_cache
import logging
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)

# Constants for image processing
MAX_IMAGE_SIZE = 1920  # Maximum dimension
JPEG_QUALITY = 85     # JPEG compression quality
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
MIME_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp'
}

class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass

class ImageProcessingError(Exception):
    """Raised when image processing fails."""
    pass

def validate_image(
    image_data: Union[bytes, str],
    max_size: int = MAX_FILE_SIZE
) -> bytes:
    """Validate image data and format.
    
    Args:
        image_data: Raw image bytes or base64 string
        max_size: Maximum allowed file size in bytes
        
    Returns:
        bytes: Validated image data
        
    Raises:
        ImageValidationError: If validation fails
    """
    try:
        # Convert base64 to bytes if needed
        if isinstance(image_data, str):
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            image_data = base64.b64decode(image_data)
        
        # Check file size
        if len(image_data) > max_size:
            raise ImageValidationError(f"Image exceeds maximum size of {max_size} bytes")
        
        # Validate image format using multiple methods
        mime_type = magic.from_buffer(image_data, mime=True)
        if not mime_type.startswith('image/'):
            raise ImageValidationError(f"Invalid image format: {mime_type}")
        
        # Additional security check with imghdr
        img_format = imghdr.what(None, image_data)
        if not img_format:
            raise ImageValidationError("Cannot determine image format")
        
        return image_data
        
    except Exception as e:
        logger.error("Image validation failed", error=str(e))
        raise ImageValidationError(f"Image validation failed: {str(e)}")

def optimize_image(
    image_data: bytes,
    max_dimension: int = MAX_IMAGE_SIZE,
    quality: int = JPEG_QUALITY
) -> Tuple[bytes, Dict[str, int]]:
    """Optimize image for storage and processing.
    
    Args:
        image_data: Raw image bytes
        max_dimension: Maximum allowed dimension
        quality: JPEG compression quality
        
    Returns:
        Tuple containing:
        - Optimized image bytes
        - Metadata dictionary with dimensions
    """
    try:
        # Open image
        with Image.open(io.BytesIO(image_data)) as img:
            # Convert color mode if needed
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            
            # Auto-orient image based on EXIF
            img = ImageOps.exif_transpose(img)
            
            # Calculate new dimensions
            width, height = img.size
            if max(width, height) > max_dimension:
                ratio = max_dimension / max(width, height)
                new_size = tuple(int(dim * ratio) for dim in (width, height))
                img = img.resize(new_size, Image.LANCZOS)
            
            # Optimize
            output = io.BytesIO()
            img.save(
                output,
                format='JPEG',
                quality=quality,
                optimize=True
            )
            
            return output.getvalue(), {
                'width': img.width,
                'height': img.height,
                'original_size': len(image_data),
                'optimized_size': output.tell()
            }
            
    except Exception as e:
        logger.error("Image optimization failed", error=str(e))
        raise ImageProcessingError(f"Image optimization failed: {str(e)}")

@lru_cache(maxsize=1000)
def calculate_image_hash(image_data: bytes) -> str:
    """Calculate perceptual hash of image for similarity comparison."""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        # Resize to 32x32 and calculate difference hash
        resized = cv2.resize(img, (32, 32))
        diff = resized[1:, :] > resized[:-1, :]
        return str(sum([2**i for (i, v) in enumerate(diff.flatten()) if v]))
        
    except Exception as e:
        logger.error("Hash calculation failed", error=str(e))
        return hashlib.sha256(image_data).hexdigest()

def extract_metadata(image_data: bytes) -> Dict[str, any]:
    """Extract image metadata including EXIF if available."""
    try:
        metadata = {}
        with Image.open(io.BytesIO(image_data)) as img:
            # Basic properties
            metadata.update({
                'format': img.format,
                'mode': img.mode,
                'width': img.width,
                'height': img.height,
                'hash': calculate_image_hash(image_data)
            })
            
            # Extract EXIF data if available
            if hasattr(img, '_getexif') and img._getexif():
                exif = {
                    ExifTags.TAGS[k]: v
                    for k, v in img._getexif().items()
                    if k in ExifTags.TAGS
                }
                metadata['exif'] = {
                    k: str(v) for k, v in exif.items()
                    if k in {'DateTime', 'Make', 'Model', 'Orientation'}
                }
            
            return metadata
            
    except Exception as e:
        logger.error("Metadata extraction failed", error=str(e))
        return {'error': str(e)}

def convert_for_ai_processing(
    image_data: bytes,
    target_size: Tuple[int, int] = (512, 512)
) -> str:
    """Convert image to format suitable for AI processing."""
    try:
        # Validate and optimize
        image_data = validate_image(image_data)
        image_data, _ = optimize_image(image_data)
        
        # Convert to RGB and resize
        with Image.open(io.BytesIO(image_data)) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img = ImageOps.fit(
                img,
                target_size,
                method=Image.LANCZOS
            )
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            return base64.b64encode(buffer.getvalue()).decode()
            
    except Exception as e:
        logger.error("AI conversion failed", error=str(e))
        raise ImageProcessingError(f"AI conversion failed: {str(e)}")

def compare_images(image1: bytes, image2: bytes) -> float:
    """Compare two images and return similarity score (0-1)."""
    try:
        hash1 = calculate_image_hash(image1)
        hash2 = calculate_image_hash(image2)
        
        # Calculate Hamming distance
        distance = bin(int(hash1) ^ int(hash2)).count('1')
        max_distance = 256  # Maximum possible distance
        
        return 1 - (distance / max_distance)
        
    except Exception as e:
        logger.error("Image comparison failed", error=str(e))
        return 0.0

def process_video_frame(
    frame: np.ndarray,
    max_dimension: int = MAX_IMAGE_SIZE
) -> bytes:
    """Process video frame for analysis."""
    try:
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        img = Image.fromarray(frame_rgb)
        
        # Optimize
        output = io.BytesIO()
        img.save(
            output,
            format='JPEG',
            quality=JPEG_QUALITY,
            optimize=True
        )
        
        return output.getvalue()
        
    except Exception as e:
        logger.error("Frame processing failed", error=str(e))
        raise ImageProcessingError(f"Frame processing failed: {str(e)}")

# Usage example:
"""
from app.utils.image_helpers import validate_image, optimize_image, convert_for_ai_processing

async def process_upload(image_data: bytes) -> str:
    try:
        # Validate and optimize image
        validated_data = validate_image(image_data)
        optimized_data, metadata = optimize_image(validated_data)
        
        # Convert for AI processing
        ai_ready_data = convert_for_ai_processing(optimized_data)
        
        return ai_ready_data
        
    except ImageValidationError as e:
        logger.error("Image validation failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except ImageProcessingError as e:
        logger.error("Image processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
"""