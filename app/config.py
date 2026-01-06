"""Configuration management using Pydantic Settings"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Audio Streaming Bridge"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: str = "*"  # Can be "*" or comma-separated list
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./audio_bridge.db"
    
    # Asterisk ARI Configuration
    ASTERISK_HOST: str = "localhost"
    ASTERISK_PORT: int = 8088
    ASTERISK_USERNAME: str = "asterisk"
    ASTERISK_PASSWORD: str = ""
    # Full ARI events WebSocket URL, including Stasis application and subscribeAll
    # Example: ws://autodialer1.worldatlantus.com:8088/ari/events?app=audio-bridge&subscribeAll=true
    ASTERISK_WS_URL: str = "ws://localhost:8088/ari/events?app=audio-bridge&subscribeAll=true"
    # Name of the ARI Stasis application that dialplan channels will enter
    ASTERISK_APP_NAME: str = "audio-bridge"
    ENABLE_WEBSOCKET_MONITOR: bool = True  # Set to False to disable WebSocket event monitoring
    USE_POLLING_MONITOR: bool = False  # Use polling instead of WebSocket if WebSocket unavailable
    
    # Audio Processing
    AUDIO_CHUNK_SIZE: int = 4096  # bytes
    AUDIO_SAMPLE_RATE: int = 8000  # Hz
    AUDIO_CHANNELS: int = 1  # mono
    AUDIO_FORMAT: str = "PCM"  # PCM, G711_ULAW, G711_ALAW
    
    # WebSocket
    WS_MAX_CONNECTIONS: int = 2000
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_AUDIO_STREAMS: bool = True
    
    # Storage (legacy - kept for backward compatibility)
    AUDIO_STORAGE_PATH: str = "./audio_storage"
    
    # Supabase Storage
    SUPABASE_URL: str = ""  # Supabase project URL
    SUPABASE_KEY: str = ""  # Supabase service role key (for server-side operations)
    SUPABASE_STORAGE_BUCKET: str = "audio-bucket"  # Storage bucket name for audio chunks

    # Security
    # Optional shared secret used to protect inbound media/stream receive endpoints.
    # If left empty, auth for those endpoints is effectively disabled.
    INGEST_AUTH_TOKEN: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

