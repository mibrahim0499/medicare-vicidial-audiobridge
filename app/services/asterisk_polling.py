"""Alternative polling-based approach for monitoring Asterisk calls when WebSocket is not available"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.services.asterisk_client import AsteriskARIClient
from app.services.audio_processor import AudioProcessor
from app.services.logger import LoggingService
from app.api.websocket import manager
from app.config import settings

logger = logging.getLogger(__name__)


class AsteriskPollingMonitor:
    """Poll-based monitor for Asterisk calls (alternative to WebSocket)"""
    
    def __init__(self):
        self.ari_client = AsteriskARIClient()
        self.audio_processor = AudioProcessor()
        self.logging_service = LoggingService()
        self.monitoring = False
        self.poll_interval = 2  # Poll every 2 seconds
        self.known_channels: Dict[str, Dict[str, Any]] = {}  # channel_id -> channel_info
        self.active_recordings: Dict[str, str] = {}  # call_id -> recording_name
        self.no_record_channels: Dict[str, bool] = {}  # channel_id -> cannot record (not in Stasis)
    
    async def start(self):
        """Start polling-based monitoring"""
        try:
            await self.ari_client.connect()
            self.monitoring = True
            logger.info("Starting Asterisk polling monitor...")
            
            while self.monitoring:
                try:
                    await self._poll_channels()
                    await asyncio.sleep(self.poll_interval)
                except Exception as e:
                    logger.error(f"Error in polling loop: {e}")
                    await asyncio.sleep(self.poll_interval)
        except Exception as e:
            logger.error(f"Error starting polling monitor: {e}")
            self.monitoring = False
    
    async def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        await self.ari_client.disconnect()
        logger.info("Stopped Asterisk polling monitor")
    
    async def _poll_channels(self):
        """Poll for active channels"""
        try:
            channels = await self.ari_client.get_channels()
            current_channel_ids = set()
            
            for channel in channels:
                channel_id = channel.get("id")
                if not channel_id:
                    continue
                
                current_channel_ids.add(channel_id)
                
                # Check if this is a new channel
                if channel_id not in self.known_channels:
                    await self._handle_new_channel(channel)
                
                # Update channel info
                self.known_channels[channel_id] = channel
                
                # Check channel state
                state = channel.get("state")
                if state == "Up" and channel_id not in self.active_recordings and not self.no_record_channels.get(channel_id):
                    await self._start_recording_for_channel(channel)
            
            # Check for removed channels
            removed_channels = set(self.known_channels.keys()) - current_channel_ids
            for channel_id in removed_channels:
                await self._handle_channel_removed(channel_id)
                del self.known_channels[channel_id]
                
        except Exception as e:
            logger.error(f"Error polling channels: {e}")
    
    async def _handle_new_channel(self, channel: Dict[str, Any]):
        """Handle a new channel"""
        channel_id = channel.get("id")
        call_id = channel.get("name", channel_id)
        
        logger.info(f"New channel detected: {channel_id} (call_id: {call_id})")
        
        # Log call start
        call_data = {
            "call_id": call_id,
            "channel_id": channel_id,
            "caller_number": channel.get("caller", {}).get("number", ""),
            "callee_number": channel.get("dialplan", {}).get("exten", ""),
            "status": "initiating",
            "start_time": datetime.utcnow()
        }
        
        await self.logging_service.log_call(call_data)
    
    async def _start_recording_for_channel(self, channel: Dict[str, Any]):
        """Start recording for an active channel"""
        channel_id = channel.get("id")
        call_id = channel.get("name", channel_id)
        
        if channel_id in self.active_recordings:
            return
        
        recording_name = f"recording_{call_id}"
        success = await self.ari_client.start_recording(channel_id, recording_name)
        
        if success:
            self.active_recordings[channel_id] = recording_name
            await self.logging_service.update_call_status(call_id, "active")
            logger.info(f"Started recording for call {call_id}")
            
            # Start streaming audio
            asyncio.create_task(self._stream_audio(call_id, recording_name))

        else:
            # Likely not a Stasis channel; avoid spamming attempts
            self.no_record_channels[channel_id] = True
            logger.info(f"Recording skipped for channel {channel_id} (likely not in Stasis)")
    
    async def _handle_channel_removed(self, channel_id: str):
        """Handle channel removal"""
        if channel_id in self.active_recordings:
            recording_name = self.active_recordings[channel_id]
            await self.ari_client.stop_recording(recording_name)
            
            # Find call_id from channel
            call_id = None
            for ch_id, rec_name in self.active_recordings.items():
                if rec_name == recording_name:
                    call_id = rec_name.replace("recording_", "")
                    break
            
            if call_id:
                await self.logging_service.update_call_status(call_id, "completed")
            
            del self.active_recordings[channel_id]
            logger.info(f"Stopped recording for channel {channel_id}")
    
    async def _stream_audio(self, call_id: str, recording_name: str):
        """Stream audio chunks from recording"""
        chunk_index = 0
        
        try:
            while call_id in [cid.replace("recording_", "") for cid in self.active_recordings.values()]:
                # Get live recording data
                audio_data = await self.ari_client.get_live_recording(recording_name)
                
                if audio_data and len(audio_data) > 0:
                    # Process audio chunk
                    processed_chunk = await self.audio_processor.process_chunk(audio_data, call_id)
                    
                    if processed_chunk:
                        # Log audio chunk
                        await self.logging_service.log_audio_chunk(
                            call_id,
                            processed_chunk,
                            {
                                "stream_id": call_id,
                                "chunk_index": chunk_index
                            }
                        )
                        
                        # Broadcast to WebSocket clients
                        await manager.send_audio_chunk(
                            call_id,
                            processed_chunk,
                            {
                                "format": settings.AUDIO_FORMAT,
                                "sample_rate": settings.AUDIO_SAMPLE_RATE,
                                "chunk_index": chunk_index
                            }
                        )
                        
                        chunk_index += 1
                
                # Wait before next chunk
                await asyncio.sleep(0.1)  # 100ms intervals
                
        except Exception as e:
            logger.error(f"Error streaming audio for call {call_id}: {e}")


# Global polling monitor instance
polling_monitor = AsteriskPollingMonitor()


async def start_polling_monitor():
    """Start the polling monitor"""
    await polling_monitor.start()


async def stop_polling_monitor():
    """Stop the polling monitor"""
    await polling_monitor.stop()

