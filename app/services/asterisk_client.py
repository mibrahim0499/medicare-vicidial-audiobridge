"""Asterisk ARI client for real-time call monitoring and audio capture"""

import aiohttp
import asyncio
import logging
import json
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from app.config import settings
from app.models.call import Call, CallStatus
from app.services.logger import LoggingService

logger = logging.getLogger(__name__)


class AsteriskARIClient:
    """Client for Asterisk REST Interface (ARI)"""
    
    def __init__(self):
        self.base_url = f"http://{settings.ASTERISK_HOST}:{settings.ASTERISK_PORT}/ari"
        self.asterisk_http_url = f"http://{settings.ASTERISK_HOST}:{settings.ASTERISK_PORT}"
        self.auth = aiohttp.BasicAuth(settings.ASTERISK_USERNAME, settings.ASTERISK_PASSWORD)
        self.session: Optional[aiohttp.ClientSession] = None
        self.event_handlers: Dict[str, Callable] = {}
        self.active_channels: Dict[str, Dict[str, Any]] = {}
        self.logging_service = LoggingService()
    
    async def connect(self):
        """Initialize ARI connection"""
        if not self.session:
            self.session = aiohttp.ClientSession(auth=self.auth)
            logger.info(f"ARI client connected to {self.base_url}")
    
    async def disconnect(self):
        """Close ARI connection"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("ARI client disconnected")
    
    async def get_channels(self) -> list:
        """Get list of active channels"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.get(f"{self.base_url}/channels") as response:
                if response.status == 200:
                    channels = await response.json()
                    return channels
                else:
                    logger.error(f"Failed to get channels: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting channels: {e}")
            return []
    
    async def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get specific channel information"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.get(f"{self.base_url}/channels/{channel_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Channel {channel_id} not found: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting channel {channel_id}: {e}")
            return None
    
    async def get_channel_variable(self, channel_id: str, variable: str) -> Optional[str]:
        """Get a channel variable value"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.get(
                f"{self.base_url}/channels/{channel_id}/variable",
                params={"variable": variable}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("value")
                else:
                    return None
        except Exception as e:
            logger.error(f"Error getting channel variable {variable} for {channel_id}: {e}")
            return None
    
    async def add_channel_to_meetme(self, channel_id: str, meetme_room: str, options: str = "") -> bool:
        """Add a channel to a MeetMe conference by continuing in dialplan with MeetMe application"""
        if not self.session:
            await self.connect()
        
        try:
            # Get channel info to find the dialplan context
            channel_info = await self.get_channel(channel_id)
            if not channel_info:
                logger.error(f"Cannot get channel info for {channel_id}")
                return False
            
            # Try to get the dialplan context from the channel
            dialplan = channel_info.get("dialplan", {})
            context = dialplan.get("context", "default")
            
            # VICIdial typically uses "default" context for MeetMe
            # We'll try to continue in a context that should have MeetMe configured
            # Common VICIdial contexts: "default" (most common), or the channel's current context, then "meetme"
            
            # Try common VICIdial MeetMe contexts (default first, as "meetme" context may not exist)
            possible_contexts = ["default", context, "meetme"]
            
            for try_context in possible_contexts:
                # Continue channel in dialplan with MeetMe application
                # The extension should be the MeetMe room number
                params = {
                    "context": try_context,
                    "extension": meetme_room,
                    "priority": 1
                }
                
                async with self.session.post(
                    f"{self.base_url}/channels/{channel_id}/continue",
                    params=params
                ) as response:
                    # HTTP 200 and 204 both indicate success for continue operation
                    if response.status in (200, 204):
                        logger.info(f"Continued channel {channel_id} to MeetMe room {meetme_room} in context {try_context} (status: {response.status})")
                        return True
                    elif response.status == 400:
                        # Try next context
                        continue
                    elif response.status == 409:
                        # Channel no longer in Stasis (already continued) - this is actually success
                        logger.info(f"Channel {channel_id} already continued (no longer in Stasis), assuming success")
                        return True
                    else:
                        error_text = await response.text()
                        logger.warning(f"Failed to continue channel {channel_id} to MeetMe in context {try_context}: {response.status} - {error_text}")
            
            # If continue didn't work, try redirect
            logger.info(f"Trying redirect method for MeetMe room {meetme_room}")
            params = {
                "context": "meetme",
                "extension": meetme_room,
                "priority": 1
            }
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/redirect",
                params=params
            ) as response:
                if response.status == 200:
                    logger.info(f"Redirected channel {channel_id} to MeetMe room {meetme_room}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to redirect channel {channel_id} to MeetMe: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error adding channel {channel_id} to MeetMe {meetme_room}: {e}")
            return False
    
    async def set_channel_variable(self, channel_id: str, variable: str, value: str) -> bool:
        """Set a channel variable"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "variable": variable,
                "value": value
            }
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/variable",
                params=params
            ) as response:
                if response.status == 200:
                    return True
                else:
                    return False
        except Exception as e:
            logger.error(f"Error setting channel variable {variable} for {channel_id}: {e}")
            return False
    
    async def continue_channel_to_meetme(self, channel_id: str, meetme_room: str, options: str = "") -> bool:
        """Continue a channel in dialplan to execute MeetMe application
        
        This method continues a channel that is in Stasis to join a MeetMe conference.
        It tries to continue the channel in dialplan with the MeetMe room as the extension.
        """
        if not self.session:
            await self.connect()
        
        try:
            # Get channel info to find the dialplan context
            channel_info = await self.get_channel(channel_id)
            if not channel_info:
                logger.error(f"Cannot get channel info for {channel_id}")
                return False
            
            # Try to get the dialplan context from the channel
            dialplan = channel_info.get("dialplan", {})
            context = dialplan.get("context", "default")
            
            # VICIdial typically uses "default" context for MeetMe
            # The extension should be the MeetMe room number
            # Try common VICIdial MeetMe contexts (default first, as "meetme" context may not exist)
            possible_contexts = ["default", context, "meetme"]
            
            for try_context in possible_contexts:
                # Continue channel in dialplan with MeetMe application
                # The extension should be the MeetMe room number
                params = {
                    "context": try_context,
                    "extension": meetme_room,
                    "priority": 1
                }
                
                async with self.session.post(
                    f"{self.base_url}/channels/{channel_id}/continue",
                    params=params
                ) as response:
                    # HTTP 200 and 204 both indicate success for continue operation
                    if response.status in (200, 204):
                        logger.info(f"Continued channel {channel_id} to MeetMe room {meetme_room} in context {try_context} (status: {response.status})")
                        return True
                    elif response.status == 400:
                        # Try next context
                        continue
                    elif response.status == 409:
                        # Channel no longer in Stasis (already continued) - this is actually success
                        logger.info(f"Channel {channel_id} already continued (no longer in Stasis), assuming success")
                        return True
                    else:
                        error_text = await response.text()
                        logger.warning(f"Failed to continue channel {channel_id} to MeetMe in context {try_context}: {response.status} - {error_text}")
            
            # If continue didn't work, fallback to add_channel_to_meetme which tries redirect
            logger.info(f"Continue method failed, trying redirect method for MeetMe room {meetme_room}")
            return await self.add_channel_to_meetme(channel_id, meetme_room, options)
        except Exception as e:
            logger.error(f"Error continuing channel {channel_id} to MeetMe: {e}")
            return False
    
    async def start_bridge_recording(self, bridge_id: str, name: str, format: str = "wav") -> bool:
        """Start recording a bridge (required when channels are in a bridge)"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "name": name,
                "format": format,
                "maxDurationSeconds": 0,
                "maxSilenceSeconds": 0,
                "ifExists": "overwrite",
                "beep": "false",
                "terminateOn": "#"
            }
            
            async with self.session.post(
                f"{self.base_url}/bridges/{bridge_id}/record",
                params=params
            ) as response:
                if response.status in (200, 201):
                    try:
                        payload = await response.json()
                    except Exception:
                        payload = None
                    
                    logger.info(
                        f"Started recording bridge {bridge_id} as {name} "
                        f"(status={response.status}, payload={payload})"
                    )
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to start bridge recording: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error starting bridge recording: {e}")
            return False
    
    async def create_snoop_channel(self, channel_id: str, app: str, spy: str = "both", whisper: str = "none") -> Optional[str]:
        """Create a snoop channel to monitor/record another channel (works even when channel is in Dial() bridge)"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "app": app,
                "spy": spy,  # "none", "in", "out", "both" - controls what audio the snoop channel hears
                "whisper": whisper  # "none", "in", "out", "both" - controls what audio the snooped channel hears
            }
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/snoop",
                params=params
            ) as response:
                if response.status in (200, 201):
                    channel_data = await response.json()
                    snoop_channel_id = channel_data.get("id")
                    logger.info(f"✅ Created snoop channel {snoop_channel_id} for channel {channel_id}")
                    return snoop_channel_id
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to create snoop channel for {channel_id}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error creating snoop channel: {e}")
            return None
    
    async def start_recording(self, channel_id: str, name: str, format: str = "wav") -> bool:
        """Start recording a channel"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "name": name,
                "format": format,
                "maxDurationSeconds": 0,
                "maxSilenceSeconds": 0,
                "ifExists": "overwrite",
                # ARI expects query params as str/int/float; use string for booleans
                "beep": "false",
                "terminateOn": "#"
            }
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/record",
                params=params
            ) as response:
                # ARI may return 200 (OK) or 201 (Created/Queued) when starting a recording
                if response.status in (200, 201):
                    try:
                        payload = await response.json()
                    except Exception:
                        payload = None

                    logger.info(
                        f"Started recording channel {channel_id} as {name} "
                        f"(status={response.status}, payload={payload})"
                    )

                    # #region agent log
                    try:
                        with open("/Users/pc/Documents/marsons-projects/phase1-audio-bridge/.cursor/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H2",
                                "location": "app/services/asterisk_client.py:start_recording",
                                "message": "Started recording via ARI",
                                "data": {
                                    "channel_id": channel_id,
                                    "name": name,
                                    "status": response.status,
                                    "payload_present": payload is not None,
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion agent log

                    return True

                # Treat anything else as an error
                error_text = await response.text()
                logger.error(f"Failed to start recording: {response.status} - {error_text}")

                # #region agent log
                try:
                    with open("/Users/pc/Documents/marsons-projects/phase1-audio-bridge/.cursor/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "pre-fix",
                            "hypothesisId": "H2",
                            "location": "app/services/asterisk_client.py:start_recording",
                            "message": "Failed to start recording via ARI",
                            "data": {
                                "channel_id": channel_id,
                                "name": name,
                                "status": response.status,
                            },
                            "timestamp": int(time.time() * 1000),
                        }) + "\n")
                except Exception:
                    pass
                # #endregion agent log

                return False
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return False
    
    async def originate_channel(self, endpoint: str, app: str, channel_id: str = None, caller_id: str = None, timeout: int = 30) -> Optional[str]:
        """Originate a new channel to dial an endpoint and enter Stasis"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "endpoint": endpoint,
                "app": app,
                "timeout": str(timeout)
            }
            
            if channel_id:
                params["channelId"] = channel_id
            if caller_id:
                params["callerId"] = caller_id
            
            async with self.session.post(
                f"{self.base_url}/channels",
                params=params
            ) as response:
                if response.status == 200:
                    channel_data = await response.json()
                    new_channel_id = channel_data.get("id")
                    logger.info(f"Originated channel {new_channel_id} to {endpoint}")
                    return new_channel_id
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to originate channel to {endpoint}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error originating channel to {endpoint}: {e}")
            return None
    
    async def create_bridge(self, bridge_type: str = "mixing") -> Optional[str]:
        """Create a bridge for mixing channels"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "type": bridge_type
            }
            
            async with self.session.post(
                f"{self.base_url}/bridges",
                params=params
            ) as response:
                if response.status == 200:
                    bridge_data = await response.json()
                    bridge_id = bridge_data.get("id")
                    logger.info(f"Created bridge {bridge_id}")
                    return bridge_id
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create bridge: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error creating bridge: {e}")
            return None
    
    async def get_bridge(self, bridge_id: str) -> Optional[Dict[str, Any]]:
        """Get bridge information including channels"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.get(f"{self.base_url}/bridges/{bridge_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Bridge {bridge_id} not found: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting bridge {bridge_id}: {e}")
            return None
    
    async def get_channel_bridge(self, channel_id: str) -> Optional[str]:
        """Get the bridge ID that a channel is currently in"""
        if not self.session:
            await self.connect()
        
        try:
            # Get channel info - it should have bridge information
            channel_info = await self.get_channel(channel_id)
            if channel_info:
                # Check if channel has bridge information
                bridge_id = channel_info.get("bridge", {}).get("id") if isinstance(channel_info.get("bridge"), dict) else None
                if bridge_id:
                    return bridge_id
                
                # Alternative: list all bridges and find which one contains this channel
                async with self.session.get(f"{self.base_url}/bridges") as response:
                    if response.status == 200:
                        bridges = await response.json()
                        for bridge in bridges:
                            bridge_channels = bridge.get("channels", [])
                            for ch in bridge_channels:
                                ch_id = ch.get("id") if isinstance(ch, dict) else ch
                                if ch_id == channel_id:
                                    return bridge.get("id")
            return None
        except Exception as e:
            logger.error(f"Error getting bridge for channel {channel_id}: {e}")
            return None
    
    async def is_channel_in_bridge(self, bridge_id: str, channel_id: str) -> bool:
        """Check if a channel is in a bridge"""
        bridge_info = await self.get_bridge(bridge_id)
        if bridge_info:
            channels = bridge_info.get("channels", [])
            # Handle both dict and string channel representations
            channel_ids = []
            for ch in channels:
                if isinstance(ch, dict):
                    channel_ids.append(ch.get("id"))
                elif isinstance(ch, str):
                    channel_ids.append(ch)
            return channel_id in channel_ids
        return False
    
    async def add_channel_to_bridge(self, bridge_id: str, channel_id: str) -> bool:
        """Add a channel to a bridge"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.post(
                f"{self.base_url}/bridges/{bridge_id}/addChannel",
                params={"channel": channel_id}
            ) as response:
                # 200 (OK) and 204 (No Content) are both success responses
                if response.status in (200, 204):
                    logger.info(f"Added channel {channel_id} to bridge {bridge_id} (status: {response.status})")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to add channel {channel_id} to bridge {bridge_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error adding channel {channel_id} to bridge {bridge_id}: {e}")
            return False
    
    async def remove_channel_from_bridge(self, bridge_id: str, channel_id: str) -> bool:
        """Remove a channel from a bridge"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.post(
                f"{self.base_url}/bridges/{bridge_id}/removeChannel",
                params={"channel": channel_id}
            ) as response:
                if response.status in (200, 204):
                    logger.info(f"Removed channel {channel_id} from bridge {bridge_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to remove channel {channel_id} from bridge {bridge_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error removing channel {channel_id} from bridge {bridge_id}: {e}")
            return False
    
    async def dial_channel(self, channel_id: str, endpoint: str, timeout: int = 30) -> bool:
        """Dial an endpoint from a channel in Stasis (for outbound calls) - only works if channel is in 'Down' state"""
        if not self.session:
            await self.connect()
        
        try:
            params = {
                "endpoint": endpoint,
                "timeout": str(timeout)
            }
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/dial",
                params=params
            ) as response:
                if response.status == 200:
                    logger.info(f"Dialing {endpoint} from channel {channel_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to dial {endpoint} from channel {channel_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error dialing channel {channel_id} to {endpoint}: {e}")
            return False
    
    async def redirect_channel_to_stasis(self, channel_id: str, app: str = None, app_args: list = None) -> bool:
        """Redirect a channel to Stasis application"""
        if not self.session:
            await self.connect()
        
        if not app:
            app = settings.ASTERISK_APP_NAME
        
        try:
            # First, try to remove channel from any bridge it's in (may fail for Dial() bridges)
            bridge_id = await self.get_channel_bridge(channel_id)
            if bridge_id:
                removal_success = await self.remove_channel_from_bridge(bridge_id, channel_id)
                if removal_success:
                    logger.info(f"Removed channel {channel_id} from bridge {bridge_id} before redirecting to Stasis")
                    # Wait a moment for the removal to complete
                    await asyncio.sleep(0.1)
                else:
                    logger.debug(f"Could not remove channel {channel_id} from bridge {bridge_id} (may be Dial() bridge), attempting redirect anyway")
            
            # Redirect to Stasis using the redirect endpoint
            # Note: This might work even if channel is still in a Dial() bridge
            # Format: endpoint should be the Stasis app name
            params = {
                "endpoint": f"Stasis/{app}"
            }
            if app_args:
                # appArgs should be comma-separated
                params["appArgs"] = ",".join(str(arg) for arg in app_args)
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/redirect",
                params=params
            ) as response:
                if response.status in (200, 204):
                    logger.info(f"Redirected channel {channel_id} to Stasis application {app}")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to redirect channel to Stasis: {response.status} - {error_text}")
                    # Try alternative: use externalMedia source
                    return await self._redirect_to_stasis_alternative(channel_id, app, app_args)
        except Exception as e:
            logger.error(f"Error redirecting channel to Stasis: {e}")
            return False
    
    async def _redirect_to_stasis_alternative(self, channel_id: str, app: str, app_args: list = None) -> bool:
        """Alternative method: Use externalMedia to redirect to Stasis"""
        try:
            # Use externalMedia source pointing to Stasis
            params = {
                "app": app
            }
            if app_args:
                params["appArgs"] = ",".join(str(arg) for arg in app_args)
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/externalMedia",
                params=params
            ) as response:
                if response.status in (200, 204):
                    logger.info(f"Redirected channel {channel_id} to Stasis using externalMedia")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Alternative redirect also failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error in alternative redirect: {e}")
            return False
    
    async def execute_mixmonitor_via_ari(self, channel_id: str, recording_file: str = None) -> bool:
        """Execute MixMonitor on a channel via ARI by redirecting to a dialplan context"""
        if not self.session:
            await self.connect()
        
        try:
            # Get channel info
            channel_info = await self.get_channel(channel_id)
            if not channel_info:
                logger.warning(f"Cannot get channel info for {channel_id}")
                return False
            
            channel_name = channel_info.get("name", channel_id)
            
            # Create recording file path if not provided
            if not recording_file:
                recording_file = f"/var/spool/asterisk/monitor/call-{channel_id}.wav"
            
            
            logger.warning(f"Cannot execute MixMonitor via ARI for channel {channel_id} - channel not in Stasis")
            return False
            
        except Exception as e:
            logger.error(f"Error executing MixMonitor via ARI: {e}")
            return False
    
    async def continue_channel_in_dialplan(self, channel_id: str, context: str = None, extension: str = None, priority: int = 1) -> bool:
        """Continue a channel in dialplan after Stasis (allows call to proceed while recording)"""
        if not self.session:
            await self.connect()
        
        try:
            params = {}
            if context:
                params["context"] = context
            if extension:
                params["extension"] = extension
            if priority:
                params["priority"] = str(priority)
            
            async with self.session.post(
                f"{self.base_url}/channels/{channel_id}/continue",
                params=params if params else None
            ) as response:
                if response.status == 200:
                    logger.debug(f"Continued channel {channel_id} in dialplan")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to continue channel in dialplan: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error continuing channel in dialplan: {e}")
            return False
    
    async def stop_recording(self, name: str) -> bool:
        """Stop recording by name"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.post(f"{self.base_url}/recordings/live/{name}/stop") as response:
                if response.status == 200:
                    logger.info(f"Stopped recording {name}")
                    return True
                else:
                    logger.error(f"Failed to stop recording: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return False
    
    async def get_recording_state(self, name: str) -> Optional[Dict[str, Any]]:
        """Get recording state information"""
        if not self.session:
            await self.connect()
        
        try:
            async with self.session.get(f"{self.base_url}/recordings/live/{name}") as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None  # Recording doesn't exist yet
                else:
                    return None
        except Exception:
            return None
    
    async def get_live_recording(self, name: str, wait_for_ready: bool = True) -> Optional[bytes]:
        """Get live recording data with retry logic for queued recordings"""
        if not self.session:
            await self.connect()
        
        # Wait for recording to be ready if it's queued
        if wait_for_ready:
            max_wait = 5  # Wait up to 5 seconds
            wait_interval = 0.5  # Check every 500ms
            waited = 0
            
            logger.info(f"Waiting for recording {name} to be ready...")
            while waited < max_wait:
                state = await self.get_recording_state(name)
                if state:
                    recording_state = state.get("state", "")
                    if waited == 0:  # Log state on first check
                        logger.info(f"Recording {name} initial state: {recording_state}")
                    if recording_state == "recording":
                        logger.info(f"Recording {name} is now active")
                        break  # Recording is active, proceed
                    elif recording_state in ("done", "failed"):
                        logger.warning(f"Recording {name} is in state {recording_state}")
                        return None
                    # If still "queued", wait a bit more
                
                await asyncio.sleep(wait_interval)
                waited += wait_interval
            
            if waited >= max_wait:
                logger.warning(f"Recording {name} did not become ready within {max_wait} seconds, proceeding anyway")
        
        try:
            async with self.session.get(
                f"{self.base_url}/recordings/live/{name}",
                params={"maxDuration": 0}
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    logger.debug(f"Fetched live recording {name}: {len(data)} bytes")
                    return data
                elif response.status == 404:
                    # Recording not available yet, return None (will retry next iteration)
                    logger.debug(f"Recording {name} not found (404), will retry")
                    return None
                else:
                    logger.warning(f"Failed to get live recording {name}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting live recording: {e}")
            return None
    
    async def monitor_channel_events(self, callback: Callable):
        """Monitor channel events via WebSocket"""
        # Convert HTTP URL to WebSocket URL
        ws_url = settings.ASTERISK_WS_URL
        if ws_url.startswith("http://"):
            ws_url = ws_url.replace("http://", "ws://")
        elif ws_url.startswith("https://"):
            ws_url = ws_url.replace("https://", "wss://")
        elif not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
            # If no protocol, assume ws://
            ws_url = f"ws://{ws_url}"
        
        logger.info(f"Connecting to Asterisk WebSocket: {ws_url}")
        
        ws_session = None
        try:
            # Create a new session for WebSocket
            ws_session = aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(settings.ASTERISK_USERNAME, settings.ASTERISK_PASSWORD),
                timeout=aiohttp.ClientTimeout(total=30, connect=10)
            )
            
            async with ws_session.ws_connect(
                ws_url,
                timeout=aiohttp.ClientTimeout(total=30, connect=10)
            ) as ws:
                logger.info("✅ Connected to Asterisk event WebSocket")
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            if isinstance(msg.data, str):
                                import json
                                event = json.loads(msg.data)
                            else:
                                event = msg.data if isinstance(msg.data, dict) else await msg.json()
                            await callback(event)
                        except Exception as e:
                            logger.error(f"Error processing event: {e}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        error = ws.exception()
                        logger.error(f"WebSocket error: {error}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        logger.warning("WebSocket connection closed by server")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning("WebSocket connection closed")
                        break
        except aiohttp.ClientConnectorError as e:
            logger.warning(f"⚠️  Cannot connect to Asterisk WebSocket (connection refused). "
                         f"This is normal if WebSocket is not accessible from this machine. "
                         f"HTTP API will still work. Error: {e}")
            raise
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  WebSocket connection timeout. Server may be unreachable.")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Error connecting to Asterisk WebSocket: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket connection: {e}")
            raise
        finally:
            if ws_session:
                await ws_session.close()
    
    async def handle_channel_event(self, event: Dict[str, Any]):
        """Handle channel events from Asterisk"""
        event_type = event.get("type")
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        
        if not channel_id:
            return
        
        if event_type == "StasisStart":
            # New channel detected
            call_id = channel.get("name", channel_id)
            await self._handle_call_start(call_id, channel)
        
        elif event_type == "ChannelStateChange":
            state = channel.get("state")
            if state == "Up":
                await self._handle_call_active(channel_id, channel)
        
        elif event_type == "ChannelDestroyed":
            await self._handle_call_end(channel_id, channel)
    
    async def _handle_call_start(self, call_id: str, channel: Dict[str, Any]):
        """Handle call start event"""
        caller_number = channel.get("caller", {}).get("number", "")
        callee_number = channel.get("dialplan", {}).get("exten", "")
        
        call_data = {
            "call_id": call_id,
            "channel_id": channel.get("id"),
            "caller_number": caller_number,
            "callee_number": callee_number,
            "status": CallStatus.INITIATING,
            "start_time": datetime.utcnow()
        }
        
        await self.logging_service.log_call(call_data)
        self.active_channels[call_id] = channel
        
        logger.info(f"Call started: {call_id} - {caller_number} -> {callee_number}")
    
    async def _handle_call_active(self, channel_id: str, channel: Dict[str, Any]):
        """Handle call active event"""
        call_id = channel.get("name", channel_id)
        
        if call_id in self.active_channels:
            await self.logging_service.update_call_status(call_id, CallStatus.ACTIVE)
            logger.info(f"Call active: {call_id}")
    
    async def _handle_call_end(self, channel_id: str, channel: Dict[str, Any]):
        """Handle call end event"""
        # Try multiple ways to find the call_id
        call_id = channel.get("name", channel_id)
        
        # If call_id not found in active_channels, try to find by channel_id
        if call_id not in self.active_channels:
            # Search for matching channel_id in active_channels
            for stored_call_id, stored_channel in self.active_channels.items():
                if stored_channel.get("id") == channel_id:
                    call_id = stored_call_id
                    break
        
        # Also try channel_id directly as call_id (fallback)
        if call_id not in self.active_channels and channel_id in self.active_channels:
            call_id = channel_id
        
        if call_id in self.active_channels:
            duration = channel.get("duration", 0)
            await self.logging_service.update_call_status(
                call_id,
                CallStatus.COMPLETED,
                duration=duration
            )
            del self.active_channels[call_id]
            logger.info(f"Call ended: {call_id} - Duration: {duration}s")
        else:
            # Try to update by channel_id if we can find it in the database
            logger.warning(f"Call end event for channel {channel_id} but call_id {call_id} not in active_channels. Attempting database lookup...")
            # Try to find call by channel_id in database
            try:
                from sqlalchemy import select
                from app.database.connection import AsyncSessionLocal
                # Import ORM Call model (aliased as DBCall for clarity)
                from app.database.models import Call as DBCall
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(DBCall).where(
                            (DBCall.channel_id == channel_id) | 
                            (DBCall.call_id == call_id) |
                            (DBCall.call_id == channel_id)
                        ).where(DBCall.status == CallStatus.ACTIVE)
                    )
                    db_call = result.scalar_one_or_none()
                    if db_call:
                        duration = channel.get("duration", 0)
                        await self.logging_service.update_call_status(
                            db_call.call_id,
                            CallStatus.COMPLETED,
                            duration=duration
                        )
                        logger.info(f"Call ended (via DB lookup): {db_call.call_id} - Duration: {duration}s")
            except Exception as e:
                logger.error(f"Error updating call status via database lookup: {e}")
    
    async def start_meetme_mixmonitor_via_ami(self, meetme_room: str, recording_file: str = None) -> bool:
        """Start MixMonitor on a MeetMe conference room using AMI (Asterisk Manager Interface)"""
        try:
            import socket
            
            # Create recording file path if not provided
            if not recording_file:
                recording_file = f"/var/spool/asterisk/monitor/meetme-{meetme_room}-{int(time.time())}.wav"
            
            # AMI typically runs on port 5038
            ami_host = settings.ASTERISK_HOST
            ami_port = 5038  # Default AMI port
            ami_user = settings.ASTERISK_USERNAME
            ami_pass = settings.ASTERISK_PASSWORD
            
            logger.info(f"Attempting to connect to AMI at {ami_host}:{ami_port} to start MixMonitor on MeetMe room {meetme_room}")
            
            # Try to connect to AMI via TCP socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)  # 5 second timeout
                sock.connect((ami_host, ami_port))
                
                # Send AMI login
                login_msg = f"Action: Login\r\nUsername: {ami_user}\r\nSecret: {ami_pass}\r\n\r\n"
                sock.sendall(login_msg.encode())
                
                # Read response
                response = sock.recv(4096).decode()
                if "Success" not in response and "Authentication accepted" not in response:
                    logger.warning(f"AMI login may have failed: {response[:200]}")
                    sock.close()
                    return False
                
                # Execute MixMonitor command on MeetMe room
                # Format: MixMonitor(meetme-{room},b)
                # The 'b' option records both directions
                command = f"Action: Command\r\nCommand: meetme list {meetme_room}\r\n\r\n"
                sock.sendall(command.encode())
                
                # Check if room exists
                list_response = sock.recv(4096).decode()
                if "No such conference" in list_response or "No active conferences" in list_response:
                    logger.warning(f"MeetMe room {meetme_room} not found or empty")
                    sock.close()
                    return False
                
                # Start MixMonitor on the MeetMe room
                # Note: MixMonitor needs to be executed on a channel, not directly on MeetMe
                # We need to find a channel in the MeetMe room and execute MixMonitor on it
                # For now, we'll use the MeetMe admin command to start recording
                # Actually, MixMonitor can't be executed directly on MeetMe - it needs to be on a channel
                # So we need to find channels in the MeetMe room and execute MixMonitor on them
                
                logger.info(f"MeetMe room {meetme_room} exists, but MixMonitor must be executed on individual channels")
                logger.info(f"MixMonitor should be started via dialplan when channels join MeetMe")
                
                # Logout
                sock.sendall(b"Action: Logoff\r\n\r\n")
                sock.close()
                
                return False  # Can't execute MixMonitor directly on MeetMe via AMI
                
            except socket.error as e:
                logger.warning(f"Could not connect to AMI at {ami_host}:{ami_port}: {e}")
                logger.info(f"AMI connection failed - MixMonitor must be configured in dialplan")
                return False
            except Exception as e:
                logger.error(f"Error executing MixMonitor via AMI: {e}")
                return False
                
        except ImportError:
            logger.warning("socket module not available for AMI connection")
            return False
        except Exception as e:
            logger.error(f"Error starting MixMonitor on MeetMe room {meetme_room}: {e}")
            return False

