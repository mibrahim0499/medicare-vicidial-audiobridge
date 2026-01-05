"""SQLAlchemy database models"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base


class Call(Base):
    """Call database model"""
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, unique=True, index=True, nullable=False)
    channel_id = Column(String, index=True)
    caller_number = Column(String)
    callee_number = Column(String)
    campaign_id = Column(String)
    status = Column(String, nullable=False, default="initiating")
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration = Column(Integer)  # Duration in seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    audio_streams = relationship("AudioStream", back_populates="call")


class AudioStream(Base):
    """Audio stream database model"""
    __tablename__ = "audio_streams"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, ForeignKey("calls.call_id"), nullable=False, index=True)
    stream_id = Column(String, unique=True, index=True, nullable=False)
    format = Column(String, nullable=False)
    sample_rate = Column(Integer, nullable=False)
    channels = Column(Integer, nullable=False)
    start_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="audio_streams")
    chunks = relationship("AudioChunk", back_populates="stream")


class AudioChunk(Base):
    """Audio chunk database model"""
    __tablename__ = "audio_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, ForeignKey("calls.call_id"), nullable=False, index=True)
    stream_id = Column(String, ForeignKey("audio_streams.stream_id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_path = Column(String)  # Path to stored audio file
    size = Column(Integer, nullable=False)  # Size in bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    stream = relationship("AudioStream", back_populates="chunks")

