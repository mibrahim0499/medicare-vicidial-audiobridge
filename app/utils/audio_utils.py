"""Audio utility functions"""

import logging
from typing import Tuple, Optional
from app.config import settings

logger = logging.getLogger(__name__)


def detect_audio_format(audio_data: bytes) -> str:
    """Detect audio format from data"""
    # Simple detection based on common formats
    # In production, use proper format detection libraries
    
    if len(audio_data) == 0:
        return "unknown"
    
    # Check for WAV header
    if audio_data[:4] == b"RIFF":
        return "WAV"
    
    # Check for G.711 μ-law (common in telephony)
    # This is a simplified check
    return settings.AUDIO_FORMAT


def validate_audio_parameters(sample_rate: int, channels: int) -> bool:
    """Validate audio parameters"""
    if sample_rate <= 0 or sample_rate > 48000:
        logger.warning(f"Invalid sample rate: {sample_rate}")
        return False
    
    if channels < 1 or channels > 2:
        logger.warning(f"Invalid channel count: {channels}")
        return False
    
    return True


def calculate_duration(data_size: int, sample_rate: int, channels: int, bit_depth: int = 16) -> float:
    """Calculate audio duration from data size"""
    bytes_per_sample = (bit_depth // 8) * channels
    samples = data_size / bytes_per_sample
    duration = samples / sample_rate
    return duration

