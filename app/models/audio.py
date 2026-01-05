"""Audio stream models"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AudioStreamBase(BaseModel):
    """Base audio stream model"""
    call_id: str = Field(..., description="Associated call ID")
    stream_id: str = Field(..., description="Unique stream identifier")
    format: str = Field(..., description="Audio format (PCM, G711_ULAW, etc.)")
    sample_rate: int = Field(8000, description="Sample rate in Hz")
    channels: int = Field(1, description="Number of audio channels")
    start_time: Optional[datetime] = Field(None, description="Stream start timestamp")


class AudioStreamCreate(AudioStreamBase):
    """Audio stream creation model"""
    pass


class AudioStream(AudioStreamBase):
    """Audio stream model with ID"""
    id: Optional[int] = Field(None, description="Database ID")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Record update timestamp")
    
    class Config:
        from_attributes = True


class AudioChunk(BaseModel):
    """Audio chunk model for streaming"""
    call_id: str = Field(..., description="Associated call ID")
    stream_id: str = Field(..., description="Associated stream ID")
    chunk_index: int = Field(..., description="Chunk sequence number")
    timestamp: datetime = Field(..., description="Chunk timestamp")
    data: bytes = Field(..., description="Audio data bytes")
    size: int = Field(..., description="Chunk size in bytes")
    
    class Config:
        from_attributes = True

