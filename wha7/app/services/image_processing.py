"""Image processing service for the Wha7 application.

This service handles all image-related operations including:
- Image validation and optimization
- Storage management in Azure Blob Storage
- Video frame extraction and processing
- Format standardization across different input sources
"""

from typing import Optional, List, Tuple
from fastapi import UploadFile
import aiohttp
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
import cv2
import numpy as np
from io import BytesIO
import base64
from PIL import Image
import tempfile
import os

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class ImageProcessingService:
    """Service for handling all image-related operations."""
    
    def __init__(self):
        """Initialize service with Azure Blob Storage connection."""
        self.blob_service = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING
        )
        self.container_name = settings.BLOB_CONTAINER_NAME
    
    async def process_upload(
        self,
        image: UploadFile,
        optimize: bool = True
    ) -> Tuple[str, str]:
        """Process an uploaded image file.
        
        Returns:
            Tuple[str, str]: (blob_url, base64_data)
            - blob_url: URL for stored image
            - base64_data: Base64 encoded image for AI processing
        """
        try:
            # Read and validate image
            contents = await image.read()
            img = Image.open(BytesIO(contents))
            
            # Optimize if requested
            if optimize:
                img = self._optimize_image(img)
            
            # Prepare for storage and AI processing
            blob_path = f"uploads/{image.filename}"
            base64_data = self._image_to_base64(img)
            
            # Store in Azure
            blob_url = await self._store_in_azure(
                blob_path,
                img
            )
            
            return blob_url, base64_data
            
        except Exception as e:
            logger.error("Image upload processing failed", error=e)
            raise
    
    async def process_video_frames(
        self,
        video_url: str,
        max_frames: int = 5
    ) -> List[str]:
        """Extract and process unique frames from video.
        
        Returns:
            List[str]: List of base64 encoded frames
        """
        try:
            # Download video to temporary file
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as response:
                    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                        tmp.write(await response.read())
                        temp_path = tmp.name
            
            try:
                # Process video frames
                frames = self._extract_unique_frames(
                    temp_path,
                    max_frames
                )
                
                # Convert frames to base64
                return [self._image_to_base64(frame) for frame in frames]
                
            finally:
                # Clean up temporary file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error("Video frame extraction failed", error=e)
            raise
    
    async def process_url(self, url: str) -> str:
        """Process image from URL.
        
        Returns:
            str: Base64 encoded image data
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.read()
                    
            img = Image.open(BytesIO(data))
            return self._image_to_base64(img)
            
        except Exception as e:
            logger.error("URL image processing failed", error=e)
            raise
    
    def _optimize_image(self, img: Image.Image) -> Image.Image:
        """Optimize image for storage and processing."""
        # Set maximum dimensions while maintaining aspect ratio
        MAX_SIZE = 1200
        ratio = min(MAX_SIZE/max(img.size), 1)
        if ratio < 1:
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.LANCZOS)
        
        return img
    
    def _image_to_base64(self, img: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        return base64.b64encode(buffer.getvalue()).decode()
    
    async def _store_in_azure(
        self,
        blob_path: str,
        img: Image.Image
    ) -> str:
        """Store image in Azure Blob Storage."""
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        async with self.blob_service:
            container = self.blob_service.get_container_client(
                self.container_name
            )
            
            # Ensure container exists
            try:
                await container.create_container()
            except ResourceExistsError:
                pass
            
            # Upload image
            blob_client = container.get_blob_client(blob_path)
            await blob_client.upload_blob(
                buffer,
                overwrite=True
            )
            
            return blob_client.url
    
    def _extract_unique_frames(
        self,
        video_path: str,
        max_frames: int
    ) -> List[Image.Image]:
        """Extract unique frames from video."""
        video = cv2.VideoCapture(video_path)
        frames = []
        last_frame = None
        
        while len(frames) < max_frames:
            ret, frame = video.read()
            if not ret:
                break
                
            # Convert to PIL Image
            frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            # Check if frame is unique
            if last_frame is None or self._frames_are_different(last_frame, frame):
                frames.append(frame)
                last_frame = frame
        
        video.release()
        return frames
    
    def _frames_are_different(
        self,
        frame1: Image.Image,
        frame2: Image.Image,
        threshold: float = 0.1
    ) -> bool:
        """Check if two frames are significantly different."""
        # Convert to numpy arrays
        arr1 = np.array(frame1)
        arr2 = np.array(frame2)
        
        # Calculate difference
        diff = np.mean(np.abs(arr1 - arr2))
        return diff > threshold * 255

# Initialize service
async def get_image_service() -> ImageProcessingService:
    """Get initialized image processing service."""
    return ImageProcessingService()