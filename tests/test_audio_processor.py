"""Tests for audio processor"""

import pytest
from app.services.audio_processor import AudioProcessor


@pytest.mark.asyncio
async def test_process_chunk():
    """Test audio chunk processing"""
    processor = AudioProcessor()
    
    # Create dummy audio data
    audio_data = b'\x00' * 1024
    
    result = await processor.process_chunk(audio_data, "test_call_123")
    
    assert result is not None
    assert len(result) > 0


@pytest.mark.asyncio
async def test_validate_audio():
    """Test audio validation"""
    processor = AudioProcessor()
    
    # Valid audio
    valid_audio = b'\x00' * 1024
    assert processor._validate_audio(valid_audio) is True
    
    # Invalid audio (empty)
    assert processor._validate_audio(b"") is False
    
    # Invalid audio (too large)
    large_audio = b'\x00' * (processor.chunk_size * 3)
    assert processor._validate_audio(large_audio) is False


def test_chunk_audio():
    """Test audio chunking"""
    processor = AudioProcessor()
    
    # Create large audio data
    audio_data = b'\x00' * 10000
    
    chunks = processor.chunk_audio(audio_data, chunk_size=1024)
    
    assert len(chunks) > 0
    assert sum(len(chunk) for chunk in chunks) == len(audio_data)

