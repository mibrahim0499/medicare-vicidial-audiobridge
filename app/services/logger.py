"""Data logging service for call metadata and audio streams"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import settings
from app.database.models import Call as DBCall, AudioStream as DBAudioStream, AudioChunk as DBAudioChunk
from app.models.call import CallStatus
from app.utils.supabase_storage import upload_audio_chunk

logger = logging.getLogger(__name__)


class LoggingService:
    """Service for logging call data and audio streams"""
    
    def __init__(self):
        pass
    
    async def log_call(self, call_data: Dict[str, Any]) -> Optional[int]:
        """Log call metadata to database"""
        try:
            from app.database.connection import AsyncSessionLocal
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                # Check if call_id already exists (e.g., duplicate channel events)
                result = await session.execute(
                    select(DBCall).where(DBCall.call_id == call_data.get("call_id"))
                )
                existing = result.scalar_one_or_none()
                if existing:
                    # Update in-place
                    existing.channel_id = call_data.get("channel_id", existing.channel_id)
                    existing.caller_number = call_data.get("caller_number", existing.caller_number)
                    existing.callee_number = call_data.get("callee_number", existing.callee_number)
                    existing.status = call_data.get("status", existing.status)
                    if not existing.start_time:
                        existing.start_time = call_data.get("start_time", datetime.utcnow())
                    existing.updated_at = datetime.utcnow()
                    await session.commit()
                    logger.info(f"Updated existing call: {call_data.get('call_id')}")
                    return existing.id
                else:
                    db_call = DBCall(
                        call_id=call_data.get("call_id"),
                        channel_id=call_data.get("channel_id"),
                        caller_number=call_data.get("caller_number"),
                        callee_number=call_data.get("callee_number"),
                        campaign_id=call_data.get("campaign_id"),
                        status=call_data.get("status", CallStatus.INITIATING),
                        start_time=call_data.get("start_time", datetime.utcnow()),
                        created_at=datetime.utcnow()
                    )
                    session.add(db_call)
                    await session.commit()
                    await session.refresh(db_call)
                    logger.info(f"Logged call: {call_data.get('call_id')}")
                    return db_call.id
        except Exception as e:
            logger.error(f"Error logging call: {e}")
            return None
    
    async def update_call_status(
        self,
        call_id: str,
        status: CallStatus,
        duration: Optional[int] = None
    ) -> bool:
        """Update call status"""
        try:
            from sqlalchemy import select
            from app.database.connection import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(DBCall).where(DBCall.call_id == call_id)
                )
                db_call = result.scalar_one_or_none()
                
                if db_call:
                    db_call.status = status
                    db_call.updated_at = datetime.utcnow()
                    
                    if status == CallStatus.COMPLETED:
                        db_call.end_time = datetime.utcnow()
                        if duration:
                            db_call.duration = duration
                    
                    await session.commit()
                    logger.info(f"Updated call {call_id} status to {status}")
                    return True
                else:
                    logger.warning(f"Call {call_id} not found for status update")
                    return False
        except Exception as e:
            logger.error(f"Error updating call status: {e}")
            return False
    
    async def log_audio_stream(self, stream_data: Dict[str, Any]) -> Optional[int]:
        """Log audio stream metadata"""
        try:
            from app.database.connection import AsyncSessionLocal
            from sqlalchemy import select
            async with AsyncSessionLocal() as session:
                call_id = stream_data.get("call_id")
                
                # Ensure the call exists in the database first
                if call_id:
                    result = await session.execute(
                        select(DBCall).where(DBCall.call_id == call_id)
                    )
                    db_call = result.scalar_one_or_none()
                    
                    if not db_call:
                        # Create the call if it doesn't exist
                        db_call = DBCall(
                            call_id=call_id,
                            channel_id=stream_data.get("channel_id"),
                            status="active",
                            start_time=stream_data.get("start_time", datetime.utcnow()),
                            created_at=datetime.utcnow()
                        )
                        session.add(db_call)
                        await session.flush()  # Flush to get the ID without committing yet
                
                db_stream = DBAudioStream(
                    call_id=call_id,
                    stream_id=stream_data.get("stream_id"),
                    format=stream_data.get("format", "PCM"),
                    sample_rate=stream_data.get("sample_rate", settings.AUDIO_SAMPLE_RATE),
                    channels=stream_data.get("channels", settings.AUDIO_CHANNELS),
                    start_time=stream_data.get("start_time", datetime.utcnow()),
                    created_at=datetime.utcnow()
                )
                session.add(db_stream)
                await session.commit()
                await session.refresh(db_stream)
                logger.info(f"Logged audio stream: {stream_data.get('stream_id')}")
                return db_stream.id
        except Exception as e:
            logger.error(f"Error logging audio stream: {e}")
            return None
    
    async def log_audio_chunk(self, call_id: str, chunk_data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Log audio chunk data to Supabase Storage and database"""
        try:
            if not settings.LOG_AUDIO_STREAMS:
                return True
            
            # Upload to Supabase Storage
            storage_url = None
            chunk_index = metadata.get("chunk_index", 0) if metadata else 0
            storage_path = f"{call_id}/chunk_{chunk_index}.raw"
            
            try:
                storage_url = await upload_audio_chunk(
                    bucket=settings.SUPABASE_STORAGE_BUCKET,
                    path=storage_path,
                    data=chunk_data,
                    content_type="application/octet-stream"
                )
                if not storage_url:
                    logger.warning(f"Failed to upload chunk to Supabase Storage for call {call_id}, chunk {chunk_index}")
                    # Continue to save metadata even if upload fails
            except Exception as upload_error:
                logger.error(f"Error uploading chunk to Supabase Storage: {upload_error}")
                # Continue to save metadata even if upload fails
            
            # Log to database if metadata provided
            if metadata:
                from app.database.connection import AsyncSessionLocal
                from sqlalchemy import select
                async with AsyncSessionLocal() as session:
                    stream_id = metadata.get("stream_id", call_id)
                    
                    # Ensure the call exists first
                    result = await session.execute(
                        select(DBCall).where(DBCall.call_id == call_id)
                    )
                    db_call = result.scalar_one_or_none()
                    
                    if not db_call:
                        # Create the call if it doesn't exist
                        db_call = DBCall(
                            call_id=call_id,
                            status="active",
                            start_time=datetime.utcnow(),
                            created_at=datetime.utcnow()
                        )
                        session.add(db_call)
                        await session.flush()
                    
                    # Ensure the audio stream exists in database (create if not)
                    result = await session.execute(
                        select(DBAudioStream).where(DBAudioStream.stream_id == stream_id)
                    )
                    db_stream = result.scalar_one_or_none()
                    
                    if not db_stream:
                        # Create the stream if it doesn't exist
                        db_stream = DBAudioStream(
                            call_id=call_id,
                            stream_id=stream_id,
                            format=settings.AUDIO_FORMAT,
                            sample_rate=settings.AUDIO_SAMPLE_RATE,
                            channels=settings.AUDIO_CHANNELS,
                            start_time=datetime.utcnow(),
                            created_at=datetime.utcnow()
                        )
                        session.add(db_stream)
                        await session.flush()  # Flush to get the ID without committing yet
                    
                    # Store Storage URL in data_path field (or None if upload failed)
                    db_chunk = DBAudioChunk(
                        call_id=call_id,
                        stream_id=stream_id,
                        chunk_index=chunk_index,
                        timestamp=datetime.utcnow(),
                        data_path=storage_url,  # Store Supabase Storage URL
                        size=len(chunk_data),
                        created_at=datetime.utcnow()
                    )
                    session.add(db_chunk)
                    await session.commit()
                    logger.debug(f"Logged audio chunk {chunk_index} for call {call_id} to database")
            
            return True
        except Exception as e:
            logger.error(f"Error logging audio chunk: {e}")
            return False
    
    async def get_call_history(self, limit: int = 100) -> list:
        """Get call history"""
        try:
            from sqlalchemy import select
            from app.database.connection import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(DBCall).order_by(DBCall.created_at.desc()).limit(limit)
                )
                calls = result.scalars().all()
                
                return [{
                    "call_id": call.call_id,
                    "channel_id": call.channel_id,
                    "caller_number": call.caller_number,
                    "callee_number": call.callee_number,
                    "status": call.status,
                    "start_time": call.start_time.isoformat() if call.start_time else None,
                    "end_time": call.end_time.isoformat() if call.end_time else None,
                    "duration": call.duration
                } for call in calls]
        except Exception as e:
            logger.error(f"Error getting call history: {e}")
            return []

