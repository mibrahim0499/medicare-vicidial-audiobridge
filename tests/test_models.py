"""Tests for data models"""

import pytest
from datetime import datetime
from app.models.call import Call, CallStatus, CallCreate, CallUpdate
from app.models.audio import AudioStream, AudioStreamCreate, AudioChunk


def test_call_model():
    """Test Call model"""
    call = Call(
        call_id="test_123",
        channel_id="PJSIP/1001-00000001",
        caller_number="+1234567890",
        callee_number="+0987654321",
        status=CallStatus.ACTIVE,
        start_time=datetime.utcnow()
    )
    
    assert call.call_id == "test_123"
    assert call.status == CallStatus.ACTIVE


def test_call_create():
    """Test CallCreate model"""
    call_data = CallCreate(
        call_id="test_123",
        caller_number="+1234567890",
        status=CallStatus.INITIATING
    )
    
    assert call_data.call_id == "test_123"
    assert call_data.status == CallStatus.INITIATING


def test_call_update():
    """Test CallUpdate model"""
    update = CallUpdate(
        status=CallStatus.COMPLETED,
        duration=300
    )
    
    assert update.status == CallStatus.COMPLETED
    assert update.duration == 300


def test_audio_stream():
    """Test AudioStream model"""
    stream = AudioStream(
        call_id="test_123",
        stream_id="stream_456",
        format="PCM",
        sample_rate=8000,
        channels=1
    )
    
    assert stream.call_id == "test_123"
    assert stream.format == "PCM"
    assert stream.sample_rate == 8000


def test_audio_chunk():
    """Test AudioChunk model"""
    chunk = AudioChunk(
        call_id="test_123",
        stream_id="stream_456",
        chunk_index=0,
        timestamp=datetime.utcnow(),
        data=b'\x00' * 1024,
        size=1024
    )
    
    assert chunk.call_id == "test_123"
    assert chunk.size == 1024
    assert len(chunk.data) == 1024

