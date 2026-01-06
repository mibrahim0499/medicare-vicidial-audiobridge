"""Supabase Storage utility for uploading audio chunks"""

import logging
import asyncio
from typing import Optional
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

# Global Supabase client instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Initialize and return Supabase client"""
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.warning("Supabase URL or KEY not configured. Storage uploads will be disabled.")
        return None
    
    try:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


async def upload_audio_chunk(
    bucket: str,
    path: str,
    data: bytes,
    content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload audio chunk to Supabase Storage and return public URL
    
    Args:
        bucket: Storage bucket name
        path: Storage path (e.g., "call_id/chunk_0.raw")
        data: Audio chunk binary data
        content_type: MIME type (default: application/octet-stream)
    
    Returns:
        Public URL to the uploaded file, or None if upload failed
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not available, cannot upload chunk")
        return None
    
    try:
        # Run synchronous Supabase operations in executor since client is synchronous
        loop = asyncio.get_event_loop()
        storage_api = client.storage.from_(bucket)
        
        # Upload file to Supabase Storage
        # The Supabase client may have issues with file_options format
        # Try different approaches to handle version differences
        def do_upload():
            # Method 1: Try with file_options where all values are strings
            try:
                return storage_api.upload(
                    path=path,
                    file=data,
                    file_options={"content-type": content_type, "upsert": "true"}
                )
            except (TypeError, AttributeError, ValueError) as e1:
                error_msg = str(e1).lower()
                if "bool" in error_msg or "encode" in error_msg:
                    # Method 2: Try without upsert option
                    try:
                        return storage_api.upload(
                            path=path,
                            file=data,
                            file_options={"content-type": content_type}
                        )
                    except Exception as e2:
                        # Method 3: Try without file_options entirely
                        logger.debug(f"Trying upload without file_options: {e2}")
                        return storage_api.upload(path=path, file=data)
                else:
                    raise e1
        
        response = await loop.run_in_executor(None, do_upload)
        
        # The upload method can return different types:
        # - dict with 'path' key on success
        # - True/False boolean on some versions
        # - raises exception on error
        
        # Check response type and handle accordingly
        if isinstance(response, dict):
            # Standard response format
            if response.get("path") or "path" in str(response):
                # Get public URL
                public_url = await loop.run_in_executor(
                    None,
                    lambda: storage_api.get_public_url(path)
                )
                logger.debug(f"Uploaded chunk to {bucket}/{path}: {public_url}")
                return public_url
            else:
                logger.error(f"Upload response missing 'path' key: {response}")
                return None
        elif isinstance(response, bool):
            # Boolean response - True means success
            if response:
                # Get public URL
                public_url = await loop.run_in_executor(
                    None,
                    lambda: storage_api.get_public_url(path)
                )
                logger.debug(f"Uploaded chunk to {bucket}/{path}: {public_url}")
                return public_url
            else:
                logger.error(f"Upload returned False for {bucket}/{path}")
                return None
        else:
            # Unknown response type - try to get URL anyway if no exception was raised
            logger.warning(f"Unexpected upload response type {type(response)}: {response}, attempting to get URL")
            try:
                public_url = await loop.run_in_executor(
                    None,
                    lambda: storage_api.get_public_url(path)
                )
                logger.debug(f"Got URL despite unexpected response: {public_url}")
                return public_url
            except Exception as url_error:
                logger.error(f"Failed to get URL after upload: {url_error}")
                return None
            
    except Exception as e:
        logger.error(f"Error uploading chunk to Supabase Storage ({bucket}/{path}): {e}", exc_info=True)
        return None

