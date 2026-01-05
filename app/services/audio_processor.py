"""Audio processing utilities for format conversion and validation"""

import numpy as np
import logging
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Handles audio format conversion and processing"""
    
    def __init__(self):
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.channels = settings.AUDIO_CHANNELS
        self.chunk_size = settings.AUDIO_CHUNK_SIZE
    
    async def process_chunk(self, audio_data: bytes, call_id: str) -> bytes:
        """Process an audio chunk - normalize format and validate"""
        try:
            # Detect format and convert if needed
            processed = await self._normalize_format(audio_data)
            
            # Validate audio data
            if not self._validate_audio(processed):
                logger.warning(f"Invalid audio chunk for call {call_id}")
                return b""
            
            return processed
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return b""
    
    async def _normalize_format(self, audio_data: bytes) -> bytes:
        """Normalize audio format to PCM"""
        # For now, assume input is already PCM or compatible
        # In production, add G.711 decode if needed
        return audio_data
    
    def _validate_audio(self, audio_data: bytes) -> bool:
        """Validate audio data"""
        if not audio_data or len(audio_data) == 0:
            return False
        
        # Check if data size is reasonable
        if len(audio_data) > self.chunk_size * 2:
            logger.warning(f"Audio chunk too large: {len(audio_data)} bytes")
            return False
        
        return True
    
    def g711_ulaw_to_pcm(self, ulaw_data: bytes) -> bytes:
        """Convert G.711 μ-law to PCM"""
        try:
            # G.711 μ-law to linear conversion
            ulaw_array = np.frombuffer(ulaw_data, dtype=np.uint8)
            pcm_array = self._ulaw_to_linear(ulaw_array)
            return pcm_array.tobytes()
        except Exception as e:
            logger.error(f"Error converting G.711 μ-law: {e}")
            return b""
    
    def g711_alaw_to_pcm(self, alaw_data: bytes) -> bytes:
        """Convert G.711 A-law to PCM"""
        try:
            # G.711 A-law to linear conversion
            alaw_array = np.frombuffer(alaw_data, dtype=np.uint8)
            pcm_array = self._alaw_to_linear(alaw_array)
            return pcm_array.tobytes()
        except Exception as e:
            logger.error(f"Error converting G.711 A-law: {e}")
            return b""
    
    def _ulaw_to_linear(self, ulaw: np.ndarray) -> np.ndarray:
        """Convert μ-law to linear PCM"""
        # μ-law decoding algorithm
        ulaw = ~ulaw
        sign = (ulaw & 0x80)
        exponent = (ulaw & 0x70) >> 4
        mantissa = ulaw & 0x0F
        
        linear = mantissa << (exponent + 3)
        linear = linear | 0x84 << exponent
        linear = linear ^ sign
        
        return linear.astype(np.int16)
    
    def _alaw_to_linear(self, alaw: np.ndarray) -> np.ndarray:
        """Convert A-law to linear PCM"""
        # A-law decoding algorithm
        alaw = alaw ^ 0x55
        
        sign = (alaw & 0x80)
        exponent = (alaw & 0x70) >> 4
        mantissa = alaw & 0x0F
        
        if exponent == 0:
            linear = (mantissa << 4) + 8
        else:
            linear = ((mantissa << 4) + 0x108) << (exponent - 1)
        
        linear = linear ^ sign
        
        return linear.astype(np.int16)
    
    def chunk_audio(self, audio_data: bytes, chunk_size: Optional[int] = None) -> list:
        """Split audio data into chunks"""
        if chunk_size is None:
            chunk_size = self.chunk_size
        
        chunks = []
        for i in range(0, len(audio_data), chunk_size):
            chunks.append(audio_data[i:i + chunk_size])
        
        return chunks

