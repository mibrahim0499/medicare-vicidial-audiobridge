"""Background service to monitor Asterisk calls and stream audio"""

import asyncio
import logging
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from app.services.asterisk_client import AsteriskARIClient
from app.services.audio_processor import AudioProcessor
from app.services.logger import LoggingService
from app.api.websocket import manager
from app.config import settings
from app.models.call import CallStatus

logger = logging.getLogger(__name__)


class AsteriskMonitor:
    """Monitor Asterisk calls and stream audio"""
    
    def __init__(self):
        self.ari_client = AsteriskARIClient()
        self.audio_processor = AudioProcessor()
        self.logging_service = LoggingService()
        self.monitoring = False
        self.active_recordings: Dict[str, str] = {}  # call_id -> recording_name
        self.active_bridges: Dict[str, str] = {}  # call_id -> bridge_id (when channels are bridged)
        self.bridged_channels: Dict[str, str] = {}  # channel_id -> call_id (track channels that are part of bridges)
        self.dial_bridges: Dict[str, str] = {}  # bridge_id -> channel_id (track Dial() bridges and their carrier channels)
        self.pending_recordings: Dict[str, Dict] = {}  # channel_id -> {meetme_room, call_id} (channels waiting for Dial() bridge to be destroyed)
        self.snoop_channels: Dict[str, str] = {}  # original_channel_id -> snoop_channel_id (track snoop channels for recording)
    
    async def start(self):
        """Start monitoring Asterisk events"""
        from app.config import settings
        
        # Check if WebSocket monitoring is enabled
        if not settings.ENABLE_WEBSOCKET_MONITOR:
            logger.info("WebSocket monitoring is disabled. Using REST API only.")
            return
        
        try:
            await self.ari_client.connect()
            self.monitoring = True
            logger.info("Starting Asterisk monitoring...")
            
            # Start background polling task to check for channels that have left Dial() bridges
            asyncio.create_task(self._poll_pending_recordings())
            
            # Start event monitoring in a loop with retry logic
            retry_count = 0
            max_retries = 3
            
            while self.monitoring:
                try:
                    await self.ari_client.monitor_channel_events(self.handle_event)
                    retry_count = 0  # Reset on successful connection
                except Exception as e:
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = min(10 * retry_count, 60)  # Exponential backoff, max 60s
                        logger.warning(f"WebSocket connection lost (attempt {retry_count}/{max_retries}), "
                                     f"retrying in {wait_time} seconds: {e}")
                        await asyncio.sleep(wait_time)
                        if self.monitoring:
                            try:
                                await self.ari_client.connect()  # Reconnect
                            except Exception as reconnect_error:
                                logger.warning(f"Reconnection failed: {reconnect_error}")
                    else:
                        logger.error(f"Max retries ({max_retries}) reached. WebSocket monitoring disabled. "
                                   f"REST API endpoints will still work.")
                        self.monitoring = False
                        break
        except Exception as e:
            logger.error(f"Error starting Asterisk monitor: {e}")
            logger.info("Note: REST API endpoints will still work without WebSocket monitoring.")
            self.monitoring = False
    
    async def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        await self.ari_client.disconnect()
        logger.info("Stopped Asterisk monitoring")
    
    async def handle_event(self, event: Dict[str, Any]):
        """Handle Asterisk events"""
        try:
            event_type = event.get("type")
            
            # Debug: Log all bridge-related events to see what we're receiving
            if "bridge" in event_type.lower() or "Bridge" in str(event) or "bridge" in str(event).lower():
                logger.info(f"🔵 Bridge event received: {event_type}")
                logger.info(f"   Event data: {json.dumps(event, default=str)[:400]}")
            
            # Also log channel events that might be bridge-related
            if event_type in ["ChannelStateChange", "ChannelVarset"]:
                channel = event.get("channel", {})
                channel_name = channel.get("name", "")
                if "SIP/galax" in channel_name:
                    logger.info(f"🔵 Carrier channel event: {event_type} for {channel_name}")
            
            if event_type == "StasisStart":
                await self._handle_call_start(event)
            elif event_type == "StasisEnd":
                await self._handle_call_end(event)
            elif event_type == "ChannelCreated":
                await self._handle_channel_created(event)
            elif event_type == "ChannelStateChange":
                await self._handle_channel_state_change(event)
            elif event_type == "ChannelDestroyed":
                await self._handle_call_end(event)
            elif event_type == "RecordingFinished":
                await self._handle_recording_finished(event)
            elif event_type == "ChannelEnteredBridge":
                await self._handle_channel_joined_bridge(event)
            elif event_type == "ChannelJoinedBridge":
                # Some Asterisk versions use this name
                await self._handle_channel_joined_bridge(event)
            elif event_type == "ChannelLeftBridge":
                await self._handle_channel_left_bridge(event)
            elif event_type == "BridgeCreated":
                logger.info(f"Bridge created: {event.get('bridge', {}).get('id')}")
            elif event_type == "BridgeDestroyed":
                await self._handle_bridge_destroyed(event)
        except Exception as e:
            logger.error(f"Error handling event: {e}")
    
    async def _handle_call_start(self, event: Dict[str, Any]):
        """Handle call start event"""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        application = event.get("application")
        args = event.get("args") or []

        # Only handle events for our configured Stasis application
        if application and application != settings.ASTERISK_APP_NAME:
            logger.debug(
                f"Ignoring StasisStart for application {application} "
                f"(expected {settings.ASTERISK_APP_NAME})"
            )
            return
        
        # Check if this is a snoop channel - skip normal handling (snoop channels are handled separately)
        channel_name = channel.get("name", "")
        if "Snoop/" in channel_name:
            logger.debug(f"Skipping normal handling for snoop channel {channel_id} ({channel_name}) - already being recorded")
            return
        
        # Check if this channel is already part of a bridge (carrier channel we originated)
        if channel_id in self.bridged_channels:
            call_id = self.bridged_channels[channel_id]
            logger.info(f"Channel {channel_id} is part of bridge for call {call_id}, skipping individual recording")
            return
        
        # Check if this channel is already being recorded (e.g., via Stasis bridge)
        if channel_id in self.active_recordings:
            recording_name = self.active_recordings[channel_id]
            logger.info(f"Channel {channel_id} is already being recorded as {recording_name}, skipping duplicate recording")
            return

        # Prefer explicit call_id passed from dialplan: Stasis(audio-bridge,${UNIQUEID},${CALL_ID})
        call_id = None
        if isinstance(args, list) and args:
            if len(args) >= 2 and args[1]:
                call_id = args[1]
            else:
                call_id = args[0]

        # Fallbacks if args are not provided
        if not call_id:
            call_id = channel.get("name", channel_id)
        
        if not channel_id:
            return

        # #region agent log
        try:
            with open("/Users/pc/Documents/marsons-projects/phase1-audio-bridge/.cursor/debug.log", "a") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H1",
                    "location": "app/services/asterisk_monitor.py:_handle_call_start",
                    "message": "StasisStart handled",
                    "data": {
                        "application": application,
                        "args": args,
                        "channel_id": channel_id,
                        "call_id": call_id,
                    },
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # #endregion agent log
        
        # Log call start
        await self.ari_client.handle_channel_event(event)
        
        # Check initial channel state
        channel_state = channel.get("state", "")
        channel_name = channel.get("name", "")
        logger.info(f"Channel {channel_id} entered Stasis with state: {channel_state} (name: {channel_name})")
        
        # Check if this is a carrier channel (created by Dial() with b() option)
        # Carrier channels have pattern: SIP/galax-...
        is_carrier_channel = "SIP/galax" in channel_name or "SIP/galax" in str(channel_id)
        
        if is_carrier_channel:
            logger.info(f"Detected carrier channel {channel_id} entered Stasis")
            # This carrier channel was created by Dial() and entered Stasis (either via b() option or ARI redirect)
            # Check if we have pending MeetMe room info for this channel
            meetme_room = None
            if hasattr(self, 'pending_meetme_channels') and channel_id in self.pending_meetme_channels:
                meetme_room = self.pending_meetme_channels.pop(channel_id)
                logger.info(f"Found pending MeetMe room {meetme_room} for carrier channel {channel_id}")
            
            # If not found in pending, try to find from related channels
            if not meetme_room:
                # Check if there's a related channel in active_channels that has MeetMe room
                for active_ch_id, active_ch_data in self.ari_client.active_channels.items():
                    if active_ch_id != channel_id:
                        active_ch_name = active_ch_data.get("name", "")
                        if "Local/" in active_ch_name and "@" in active_ch_name:
                            parts = active_ch_name.split("/")
                            if len(parts) > 1:
                                local_part = parts[1].split("@")[0]
                                if local_part.isdigit() and len(local_part) >= 6:
                                    meetme_room = local_part
                                    logger.info(f"Found MeetMe room {meetme_room} from related channel {active_ch_id}")
                                    break
            
            # If not found, try to extract from channel variables
            if not meetme_room:
                # Check channel variables for MeetMe room
                possible_vars = ["MEETME_ROOMNUM", "CONFBRIDGE", "MEETME_ROOM", "CONFERENCE", "VICIDIAL_CONF", "CONFBRIDGE_NUM", "MEETME_CONF"]
                for var_name in possible_vars:
                    var_value = await self.ari_client.get_channel_variable(channel_id, var_name)
                    if var_value:
                        meetme_room = var_value
                        logger.info(f"Found MeetMe room from {var_name}: {meetme_room}")
                        break
            
            # If still not found, try to find from dialplan context
            # The original channel's context might have the MeetMe room (e.g., 8600051@default)
            if not meetme_room:
                dialplan_info = channel.get("dialplan", {})
                dialplan_context = dialplan_info.get("context", "")
                # Check if context contains a MeetMe room pattern
                # VICIdial might use context like "8600051@default" where 8600051 is the room
                if "@" in dialplan_context:
                    context_part = dialplan_context.split("@")[0]
                    if context_part.isdigit() and len(context_part) >= 6:
                        meetme_room = context_part
                        logger.info(f"Found MeetMe room from dialplan context: {meetme_room}")
            
            # If still not found, wait a bit and check active channels again
            if not meetme_room:
                await asyncio.sleep(0.5)
                for active_ch_id, active_ch_data in self.ari_client.active_channels.items():
                    if active_ch_id != channel_id:
                        active_ch_name = active_ch_data.get("name", "")
                        if "Local/" in active_ch_name and "@" in active_ch_name:
                            parts = active_ch_name.split("/")
                            if len(parts) > 1:
                                local_part = parts[1].split("@")[0]
                                if local_part.isdigit() and len(local_part) >= 6:
                                    meetme_room = local_part
                                    logger.info(f"Found MeetMe room {meetme_room} from related channel {active_ch_id} (after wait)")
                                    break
            
            if meetme_room:
                # Add carrier channel to MeetMe conference
                logger.info(f"Moving carrier channel {channel_id} to MeetMe room {meetme_room}")
                meetme_success = await self.ari_client.add_channel_to_meetme(channel_id, meetme_room)
                if meetme_success:
                    logger.info(f"Successfully moved carrier channel {channel_id} to MeetMe room {meetme_room}")
                    # Mark as handled
                    self.bridged_channels[channel_id] = call_id
                    return  # Exit early, carrier channel handled
                else:
                    logger.error(f"Failed to add carrier channel {channel_id} to MeetMe room {meetme_room}")
            else:
                logger.warning(f"Could not find MeetMe room for carrier channel {channel_id}, will wait for original channel")
                # Store this carrier channel to handle later when original channel is found
                self.bridged_channels[channel_id] = call_id
                return  # Exit early, will be handled when original channel enters Stasis
        
        # Check if this channel entered Stasis AFTER Dial() completed
        # If DIALSTATUS=ANSWER is set, it means Dial() completed successfully
        dialstatus = await self.ari_client.get_channel_variable(channel_id, "DIALSTATUS")
        dial_completed = False  # Flag to track if Dial() was already executed
        if dialstatus == "ANSWER":
            dial_completed = True
            logger.info(f"Channel {channel_id} entered Stasis after Dial() completed (DIALSTATUS=ANSWER)")
            # This means Dial() was used in dialplan, and carrier answered
            # We need to find the carrier channel and move it to MeetMe
            
            # Get the bridge this channel is in (Dial() creates a bridge)
            bridge_id = await self.ari_client.get_channel_bridge(channel_id)
            if bridge_id:
                logger.info(f"Channel {channel_id} is in bridge {bridge_id} (from Dial())")
                # Get bridge info to find the carrier channel
                bridge_info = await self.ari_client.get_bridge(bridge_id)
                if bridge_info:
                    bridge_channels = bridge_info.get("channels", [])
                    # Find the other channel (carrier channel)
                    carrier_channel_id = None
                    for ch in bridge_channels:
                        ch_id = ch.get("id") if isinstance(ch, dict) else ch
                        if ch_id != channel_id:
                            carrier_channel_id = ch_id
                            break
                    
                    if carrier_channel_id:
                        logger.info(f"Found carrier channel {carrier_channel_id} in Dial() bridge")
                        
                        # Detect MeetMe room from original channel
                        meetme_room = None
                        channel_name = channel.get("name", "")
                        if "Local/" in channel_name and "@" in channel_name:
                            parts = channel_name.split("/")
                            if len(parts) > 1:
                                local_part = parts[1].split("@")[0]
                                if local_part.isdigit() and len(local_part) >= 6:
                                    meetme_room = local_part
                                    logger.info(f"Extracted MeetMe room from channel name: {meetme_room}")
                        
                        if meetme_room:
                            # Add carrier channel to MeetMe conference
                            logger.info(f"Moving carrier channel {carrier_channel_id} from Dial() bridge to MeetMe room {meetme_room}")
                            meetme_success = await self.ari_client.add_channel_to_meetme(carrier_channel_id, meetme_room)
                            if meetme_success:
                                logger.info(f"Successfully moved carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                                self.active_bridges[call_id] = f"meetme_{meetme_room}"
                                # Mark carrier channel as handled
                                self.bridged_channels[carrier_channel_id] = call_id
                                return  # Exit early, call is handled
                            else:
                                logger.error(f"Failed to add carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                        else:
                            logger.warning(f"Could not detect MeetMe room for channel {channel_id}, cannot move carrier to MeetMe")
                    else:
                        logger.warning(f"Could not find carrier channel in bridge {bridge_id}")
                else:
                    logger.warning(f"Could not get bridge info for {bridge_id}")
            else:
                logger.info(f"Channel {channel_id} not in a bridge, may have already left Dial() bridge")
                # Try using BRIDGEPEER variable to find the carrier channel
                # BRIDGEPEER is set by Dial() and contains the channel ID of the other leg
                bridgepeer = await self.ari_client.get_channel_variable(channel_id, "BRIDGEPEER")
                if bridgepeer:
                    logger.info(f"Found BRIDGEPEER variable: {bridgepeer}, this is the carrier channel")
                    carrier_channel_id = bridgepeer
                    
                    # Detect MeetMe room from original channel
                    meetme_room = None
                    channel_name = channel.get("name", "")
                    if "Local/" in channel_name and "@" in channel_name:
                        parts = channel_name.split("/")
                        if len(parts) > 1:
                            local_part = parts[1].split("@")[0]
                            if local_part.isdigit() and len(local_part) >= 6:
                                meetme_room = local_part
                                logger.info(f"Extracted MeetMe room from channel name: {meetme_room}")
                    
                    if meetme_room:
                        # Add carrier channel to MeetMe conference
                        logger.info(f"Moving carrier channel {carrier_channel_id} (from BRIDGEPEER) to MeetMe room {meetme_room}")
                        meetme_success = await self.ari_client.add_channel_to_meetme(carrier_channel_id, meetme_room)
                        if meetme_success:
                            logger.info(f"Successfully moved carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                            self.active_bridges[call_id] = f"meetme_{meetme_room}"
                            # Mark carrier channel as handled
                            self.bridged_channels[carrier_channel_id] = call_id
                            return  # Exit early, call is handled
                        else:
                            logger.error(f"Failed to add carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                    else:
                        logger.warning(f"Could not detect MeetMe room for channel {channel_id}, cannot move carrier to MeetMe")
                else:
                    logger.info(f"No BRIDGEPEER variable found, Dial() may not have been used or bridge already destroyed")
                    # Try to find carrier channel by listing all active channels
                    # Look for a SIP/galax channel that was recently created and is in "Up" state
                    logger.info(f"Attempting to find carrier channel by listing active channels...")
                    try:
                        all_channels = await self.ari_client.get_channels()
                        carrier_channel_id = None
                        carrier_channel_info = None
                        
                        # Find a channel matching SIP/galax pattern that's in "Up" state
                        for ch in all_channels:
                            ch_id = ch.get("id", "")
                            ch_name = ch.get("name", "")
                            ch_state = ch.get("state", "")
                            
                            # Look for SIP/galax channels that are connected
                            if "SIP/galax" in ch_name and ch_state == "Up" and ch_id != channel_id:
                                # Check if this channel is not already in a bridge or MeetMe
                                ch_bridge = await self.ari_client.get_channel_bridge(ch_id)
                                if not ch_bridge:  # Not in a bridge, likely the carrier channel from Dial()
                                    carrier_channel_id = ch_id
                                    carrier_channel_info = ch
                                    logger.info(f"Found potential carrier channel: {ch_id} ({ch_name})")
                                    break
                        
                        if carrier_channel_id:
                            # Detect MeetMe room from original channel
                            meetme_room = None
                            channel_name = channel.get("name", "")
                            if "Local/" in channel_name and "@" in channel_name:
                                parts = channel_name.split("/")
                                if len(parts) > 1:
                                    local_part = parts[1].split("@")[0]
                                    if local_part.isdigit() and len(local_part) >= 6:
                                        meetme_room = local_part
                                        logger.info(f"Extracted MeetMe room from channel name: {meetme_room}")
                            
                            if meetme_room:
                                # Add carrier channel to MeetMe conference
                                logger.info(f"Moving carrier channel {carrier_channel_id} (found via channel list) to MeetMe room {meetme_room}")
                                meetme_success = await self.ari_client.add_channel_to_meetme(carrier_channel_id, meetme_room)
                                if meetme_success:
                                    logger.info(f"Successfully moved carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                                    self.active_bridges[call_id] = f"meetme_{meetme_room}"
                                    # Mark carrier channel as handled
                                    self.bridged_channels[carrier_channel_id] = call_id
                                    return  # Exit early, call is handled
                                else:
                                    logger.error(f"Failed to add carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                            else:
                                logger.warning(f"Could not detect MeetMe room for channel {channel_id}, cannot move carrier to MeetMe")
                        else:
                            logger.info(f"Could not find carrier channel in active channels list")
                    except Exception as e:
                        logger.error(f"Error while trying to find carrier channel: {e}")
            
            # If Dial() was completed but we couldn't find the carrier channel, log error and return
            # Don't originate a new channel as that would create a duplicate call
            if dial_completed:
                logger.error(f"Dial() was completed (DIALSTATUS=ANSWER) but could not find carrier channel. Cannot proceed without creating duplicate call.")
                return  # Exit early to prevent originating duplicate carrier channel
        
        # Try to detect MeetMe conference room number from channel variables
        # VICIdial typically uses variables like MEETME_ROOMNUM, CONFBRIDGE, or passes it in dialplan
        meetme_room = None
        possible_vars = ["MEETME_ROOMNUM", "CONFBRIDGE", "MEETME_ROOM", "CONFERENCE", "VICIDIAL_CONF", "CONFBRIDGE_NUM", "MEETME_CONF"]
        for var_name in possible_vars:
            var_value = await self.ari_client.get_channel_variable(channel_id, var_name)
            if var_value:
                meetme_room = var_value
                logger.info(f"Found MeetMe room number from {var_name}: {meetme_room}")
                break
        
        # If not found in variables, check channel name pattern
        # VICIdial channels often have pattern like "Local/8600051@default-..." where 8600051 is the MeetMe room
        if not meetme_room:
            channel_name = channel.get("name", "")
            # Pattern: Local/8600051@default-00000038;1 -> extract 8600051
            if "Local/" in channel_name and "@" in channel_name:
                parts = channel_name.split("/")
                if len(parts) > 1:
                    local_part = parts[1].split("@")[0]
                    # Check if it looks like a MeetMe room (numeric, typically 6-8 digits for VICIdial)
                    if local_part.isdigit() and len(local_part) >= 6:
                        meetme_room = local_part
                        logger.info(f"Extracted MeetMe room from channel name pattern: {meetme_room} (from {channel_name})")
        
        # If still not found, check dialplan context/extension (VICIdial might use extension as room number)
        if not meetme_room:
            dialplan_info = channel.get("dialplan", {})
            dialplan_context = dialplan_info.get("context", "")
            dialplan_exten = dialplan_info.get("exten", "")
            
            # VICIdial often uses the extension as the MeetMe room number
            # Check if context suggests this is a conference context
            if "conf" in dialplan_context.lower() or "meetme" in dialplan_context.lower():
                if dialplan_exten and dialplan_exten.isdigit():
                    meetme_room = dialplan_exten
                    logger.info(f"Using dialplan extension as MeetMe room: {meetme_room}")
        
        # Extract destination number from dialplan context
        # For outbound calls: dialplan.exten contains the number (e.g., "917786523395")
        dialplan_info = channel.get("dialplan", {})
        destination_exten = dialplan_info.get("exten", "")
        
        # If this is the original channel (Local/...) and we have a destination number,
        # DON'T originate a new channel - the dialplan's Dial() with b() option will create it
        # We should just wait for the carrier channel to enter Stasis
        if destination_exten and "Local/" in channel_name:
            logger.info(f"Original channel {channel_id} entered Stasis with destination {destination_exten}. "
                       f"Waiting for carrier channel to enter Stasis via Dial() b() option. "
                       f"Will not originate duplicate channel.")
            # Just continue the original channel to MeetMe and wait for carrier
            if meetme_room:
                logger.info(f"Continuing original channel {channel_id} to MeetMe room {meetme_room}")
                meetme_success = await self.ari_client.continue_channel_to_meetme(channel_id, meetme_room)
                if meetme_success:
                    logger.info(f"Successfully continued original channel {channel_id} to MeetMe room {meetme_room}")
                    self.active_bridges[call_id] = f"meetme_{meetme_room}"
                    # Store call info so we can handle carrier channel when it enters Stasis
                    return  # Exit early, wait for carrier channel to enter Stasis
            else:
                logger.warning(f"Could not detect MeetMe room for original channel {channel_id}")
            return  # Don't originate, wait for carrier
        
        # If we have a destination number, originate a new channel and add to MeetMe or bridge
        # Format: SIP/{number}@galax (strip leading 9 if present)
        # NOTE: This should only happen for non-VICIdial calls or if Dial() is not used
        if destination_exten:
            # Remove leading 9 if present (VICIdial pattern _9X.)
            phone_number = destination_exten[1:] if destination_exten.startswith("9") else destination_exten
            endpoint = f"SIP/{phone_number}@galax"
            
            logger.info(f"Originating carrier call from Stasis: {endpoint} (from exten: {destination_exten})")
            
            # If channel is already "Up", we need to originate a new channel
            if channel_state == "Up":
                logger.info(f"Channel {channel_id} is already in 'Up' state, originating new channel")
                
                # If we found a MeetMe room, FIRST continue the original channel to MeetMe, THEN handle carrier
                if meetme_room:
                    logger.info(f"Detected MeetMe conference room {meetme_room}, will add both channels to conference")
                    # Set DIALSTATUS=ANSWER BEFORE continuing to MeetMe (while channel is still in Stasis)
                    # VICIdial uses this variable to detect call as "LIVE CALL"
                    logger.info(f"Setting DIALSTATUS=ANSWER on original channel {channel_id} for VICIdial detection")
                    await self.ari_client.set_channel_variable(channel_id, "DIALSTATUS", "ANSWER")
                    
                    # FIRST: Continue the original channel in dialplan to join MeetMe room
                    logger.info(f"Continuing original channel {channel_id} to MeetMe room {meetme_room}")
                    meetme_success = await self.ari_client.continue_channel_to_meetme(channel_id, meetme_room)
                    if not meetme_success:
                        logger.error(f"Failed to continue channel {channel_id} to MeetMe room {meetme_room}")
                        # Fallback: try alternative method
                        logger.info(f"Trying alternative method to add channel to MeetMe")
                        meetme_success = await self.ari_client.add_channel_to_meetme(channel_id, meetme_room)
                        if not meetme_success:
                            logger.error(f"Failed to add original channel to MeetMe, falling back to ARI bridge")
                            meetme_room = None  # Fallback to ARI bridge
                        else:
                            logger.info(f"Successfully added original channel {channel_id} to MeetMe room {meetme_room} (via add_channel_to_meetme)")
                    else:
                        logger.info(f"Successfully continued channel {channel_id} to MeetMe room {meetme_room}")
                        # Set DIALSTATUS on original channel so VICIdial detects call as answered
                        await self.ari_client.set_channel_variable(channel_id, "DIALSTATUS", "ANSWER")
                        logger.info(f"Set DIALSTATUS=ANSWER on original channel {channel_id} for VICIdial detection")
                else:
                    logger.info(f"No MeetMe room detected, will create ARI bridge instead")
                    # Create a bridge
                    bridge_id = await self.ari_client.create_bridge("mixing")
                    if not bridge_id:
                        logger.error(f"Failed to create bridge for channel {channel_id}")
                        return
                    
                    # Add the existing channel to the bridge
                    bridge_success = await self.ari_client.add_channel_to_bridge(bridge_id, channel_id)
                    if not bridge_success:
                        logger.error(f"Failed to add channel {channel_id} to bridge {bridge_id}")
                        return
                
                # Originate a new channel to dial the carrier (it will enter Stasis automatically)
                carrier_channel_id = await self.ari_client.originate_channel(
                    endpoint=endpoint,
                    app=settings.ASTERISK_APP_NAME,
                    timeout=30
                )
                
                if not carrier_channel_id:
                    logger.error(f"Failed to originate channel to {endpoint}")
                    return
                
                # Track this channel as part of a bridge so we don't try to record it individually
                self.bridged_channels[carrier_channel_id] = call_id
                
                logger.info(f"Originated carrier channel {carrier_channel_id}, waiting for it to enter Stasis...")
                
                # Wait for the carrier channel to enter Stasis and connect
                max_wait = 30
                wait_count = 0
                carrier_connected = False
                while wait_count < max_wait:
                    await asyncio.sleep(0.5)
                    carrier_channel_info = await self.ari_client.get_channel(carrier_channel_id)
                    if carrier_channel_info:
                        carrier_state = carrier_channel_info.get("state", "")
                        if carrier_state == "Up":
                            carrier_connected = True
                            logger.info(f"Carrier channel {carrier_channel_id} is now connected (state: Up)")
                            break
                    wait_count += 0.5
                
                if carrier_connected:
                    if meetme_room:
                        # IMPORTANT: Do NOT record the channel if adding to MeetMe
                        # ARI channel recording blocks audio flow, causing "No audio available" when joining MeetMe
                        # VICIdial handles MeetMe recording via dialplan, so we skip ARI recording here
                        logger.info(f"Skipping ARI recording for MeetMe call (VICIdial handles MeetMe recording)")
                        
                        # Add carrier channel to MeetMe conference immediately (no recording delay)
                        logger.info(f"Adding carrier channel {carrier_channel_id} to MeetMe conference room {meetme_room}")
                        meetme_success = await self.ari_client.add_channel_to_meetme(carrier_channel_id, meetme_room)
                        if meetme_success:
                            logger.info(f"Successfully added carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                            
                            # DIALSTATUS was already set on original channel before continuing to MeetMe
                            logger.info(f"Call status variables set - VICIdial should detect call as LIVE")
                            
                            # Store MeetMe room for this call
                            self.active_bridges[call_id] = f"meetme_{meetme_room}"
                            logger.info(f"Call {call_id} is now active in MeetMe room {meetme_room} - both channels should be connected")
                        else:
                            logger.error(f"Failed to add carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                    else:
                        # Use ARI bridge (fallback if no MeetMe detected)
                        # Add carrier channel to the bridge
                        bridge_success = await self.ari_client.add_channel_to_bridge(bridge_id, carrier_channel_id)
                        if bridge_success:
                            logger.info(f"Added carrier channel {carrier_channel_id} to bridge {bridge_id}, verifying both channels are in bridge...")
                            
                            # Wait and verify both channels are actually in the bridge
                            max_verify_wait = 5
                            verify_count = 0
                            both_channels_in_bridge = False
                            while verify_count < max_verify_wait:
                                await asyncio.sleep(0.5)
                                local_in_bridge = await self.ari_client.is_channel_in_bridge(bridge_id, channel_id)
                                carrier_in_bridge = await self.ari_client.is_channel_in_bridge(bridge_id, carrier_channel_id)
                                
                                if local_in_bridge and carrier_in_bridge:
                                    both_channels_in_bridge = True
                                    logger.info(f"Verified: Both channels {channel_id} and {carrier_channel_id} are in bridge {bridge_id}")
                                    break
                                verify_count += 0.5
                            
                            if both_channels_in_bridge:
                                # Store bridge_id for this call
                                self.active_bridges[call_id] = bridge_id
                                
                                # Start bridge recording now that both channels are confirmed in the bridge
                                recording_name = f"recording_{call_id}"
                                logger.info(f"Recording bridge {bridge_id} for call {call_id} (both channels confirmed in bridge)")
                                success = await self.ari_client.start_bridge_recording(bridge_id, recording_name)
                                
                                if success:
                                    self.active_recordings[call_id] = recording_name
                                    logger.info(f"Started bridge recording for call {call_id}")
                                    
                                    # Wait a moment for recording to initialize
                                    await asyncio.sleep(1.0)
                                    
                                    # Log stream metadata and start streaming
                                    try:
                                        await self.logging_service.log_audio_stream(
                                            {
                                                "call_id": call_id,
                                                "stream_id": call_id,
                                                "format": settings.AUDIO_FORMAT,
                                                "sample_rate": settings.AUDIO_SAMPLE_RATE,
                                                "channels": settings.AUDIO_CHANNELS,
                                            }
                                        )
                                    except Exception as e:
                                        logger.warning(f"Could not log audio stream metadata for {call_id}: {e}")
                                    
                                    # Start streaming audio chunks
                                    asyncio.create_task(self._stream_audio(call_id, recording_name))
                                else:
                                    logger.error(f"Failed to start bridge recording for call {call_id}")
                            else:
                                logger.warning(f"Both channels not confirmed in bridge after {max_verify_wait}s. Local: {local_in_bridge}, Carrier: {carrier_in_bridge}")
                                # Still try to record, but log the warning
                                self.active_bridges[call_id] = bridge_id
                                recording_name = f"recording_{call_id}"
                                logger.info(f"Attempting bridge recording anyway for bridge {bridge_id}")
                                success = await self.ari_client.start_bridge_recording(bridge_id, recording_name)
                                
                                if success:
                                    self.active_recordings[call_id] = recording_name
                                    logger.info(f"Started bridge recording for call {call_id}")
                                    
                                    # Wait a moment for recording to initialize
                                    await asyncio.sleep(1.0)
                                    
                                    # Log stream metadata and start streaming
                                    try:
                                        await self.logging_service.log_audio_stream(
                                            {
                                                "call_id": call_id,
                                                "stream_id": call_id,
                                                "format": settings.AUDIO_FORMAT,
                                                "sample_rate": settings.AUDIO_SAMPLE_RATE,
                                                "channels": settings.AUDIO_CHANNELS,
                                            }
                                        )
                                    except Exception as e:
                                        logger.warning(f"Could not log audio stream metadata for {call_id}: {e}")
                                    
                                    # Start streaming audio chunks
                                    asyncio.create_task(self._stream_audio(call_id, recording_name))
                                else:
                                    logger.error(f"Failed to start bridge recording for call {call_id}")
                        else:
                            logger.error(f"Failed to add carrier channel {carrier_channel_id} to bridge {bridge_id}")
                else:
                    logger.warning(f"Carrier channel {carrier_channel_id} did not connect within {max_wait}s")
                    # Still try to record the single channel (even though it's in a bridge, might work)
                    recording_name = f"recording_{call_id}"
                    logger.info(f"Carrier not connected, attempting to record bridge {bridge_id} anyway")
                    success = await self.ari_client.start_bridge_recording(bridge_id, recording_name)
                    if success:
                        self.active_recordings[call_id] = recording_name
                        self.active_bridges[call_id] = bridge_id
                        logger.info(f"Started bridge recording for call {call_id} (carrier not yet connected)")
                        asyncio.create_task(self._stream_audio(call_id, recording_name))
                return  # Exit early since we handled bridge recording
            else:
                # Channel is in "Down" state, we can use dial() directly
                logger.info(f"Channel {channel_id} is in '{channel_state}' state, using dial()")
                dial_success = await self.ari_client.dial_channel(channel_id, endpoint, timeout=30)
                
                if not dial_success:
                    logger.error(f"Failed to dial {endpoint} from channel {channel_id}")
                    return
                
                # Wait for channel to be in "Up" state (call connected)
                max_wait = 30
                wait_count = 0
                while channel_state != "Up" and wait_count < max_wait:
                    await asyncio.sleep(0.5)
                    channel_info = await self.ari_client.get_channel(channel_id)
                    if channel_info:
                        new_state = channel_info.get("state", "")
                        if new_state != channel_state:
                            logger.info(f"Channel {channel_id} state changed: {channel_state} -> {new_state}")
                            channel_state = new_state
                    wait_count += 0.5
                
                if channel_state != "Up":
                    logger.warning(f"Channel {channel_id} not in 'Up' state after {max_wait}s (state: {channel_state}), proceeding anyway")
                else:
                    logger.info(f"Channel {channel_id} is now in 'Up' state (call connected), starting recording")
        else:
            # No destination number - might be inbound call or already connected
            logger.info(f"No destination number found in dialplan, assuming call already connected")
            # Wait a bit for channel to stabilize
            await asyncio.sleep(1.0)
        
        # Start recording - use bridge recording if channels are bridged, otherwise channel recording
        recording_name = f"recording_{call_id}"
        
        # Check if this call is using a bridge (shouldn't happen here, but just in case)
        if call_id in self.active_bridges:
            bridge_id = self.active_bridges[call_id]
            logger.info(f"Recording bridge {bridge_id} for call {call_id} (channels are bridged)")
            success = await self.ari_client.start_bridge_recording(bridge_id, recording_name)
        else:
            logger.info(f"Recording channel {channel_id} for call {call_id}")
        success = await self.ari_client.start_recording(channel_id, recording_name)
        
        if success:
            self.active_recordings[call_id] = recording_name
            logger.info(f"Started recording for call {call_id}")
            
            # Wait a moment for recording to initialize
            await asyncio.sleep(1.0)
            
            # Channel stays in Stasis for the entire call - ARI controls it
            logger.info(f"Channel {channel_id} will stay in Stasis for monitoring (recording active)")

            # Log stream metadata for observability
            try:
                await self.logging_service.log_audio_stream(
                    {
                        "call_id": call_id,
                        "stream_id": call_id,
                        "format": settings.AUDIO_FORMAT,
                        "sample_rate": settings.AUDIO_SAMPLE_RATE,
                        "channels": settings.AUDIO_CHANNELS,
                    }
                )
            except Exception as e:
                logger.warning(f"Could not log audio stream metadata for {call_id}: {e}")
            
            # Start streaming audio chunks
            asyncio.create_task(self._stream_audio(call_id, recording_name))
    
    async def _handle_channel_state_change(self, event: Dict[str, Any]):
        """Handle channel state change"""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        channel_name = channel.get("name", "")
        state = channel.get("state")
        
        # Check if this is a carrier channel that just went to "Ringing" or "Up" state
        # Try to redirect it to Stasis BEFORE it joins the Dial() bridge
        is_carrier_channel = "SIP/galax" in channel_name
        if is_carrier_channel and state in ["Ringing", "Up"]:
            # Check if this channel is already being tracked or recorded
            if channel_id not in self.active_recordings and channel_id not in self.pending_recordings:
                logger.info(f"Carrier channel {channel_id} ({channel_name}) just went to {state} state, attempting early redirect to Stasis")
                
                # Check if channel is already in a bridge
                bridge_id = await self.ari_client.get_channel_bridge(channel_id)
                if bridge_id:
                    logger.warning(f"Channel {channel_id} is already in bridge {bridge_id} at {state} state, cannot redirect to Stasis")
                else:
                    # Try to redirect immediately - channel might not be in bridge yet
                    logger.info(f"Attempting to redirect channel {channel_id} to Stasis (state: {state}, not in bridge)")
                    redirect_success = await self.ari_client.redirect_channel_to_stasis(
                        channel_id,
                        app=settings.ASTERISK_APP_NAME,
                        app_args=[channel_id, channel_id]
                    )
                    
                    if redirect_success:
                        logger.info(f"✅ Successfully redirected carrier channel {channel_id} to Stasis before Dial() bridge (from {state} state)")
                        # Wait a moment for channel to enter Stasis
                        await asyncio.sleep(0.5)
                        
                        # Start recording
                        recording_name = f"call_{channel_id}"
                        logger.info(f"Starting recording {recording_name} for call {channel_id}")
                        recording_success = await self.ari_client.start_recording(channel_id, recording_name)
                        
                        if recording_success:
                            logger.info(f"✅ Started recording {recording_name} for call {channel_id}")
                            self.active_recordings[channel_id] = recording_name
                            # Start streaming chunks
                            asyncio.create_task(self._stream_audio(channel_id, recording_name))
                        else:
                            logger.warning(f"Failed to start recording on carrier channel {channel_id} in Stasis")
                    else:
                        logger.warning(f"❌ Could not redirect carrier channel {channel_id} to Stasis in {state} state (may already be in Dial() bridge or channel not ready)")
        
        if state == "Up":
            await self.ari_client.handle_channel_event(event)
    
    async def _handle_channel_created(self, event: Dict[str, Any]):
        """Handle channel created event - try to redirect carrier channel to Stasis as early as possible"""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        channel_name = channel.get("name", "")
        state = channel.get("state", "")
        
        # Check if this is a carrier channel being created
        is_carrier_channel = "SIP/galax" in channel_name
        if is_carrier_channel:
            logger.info(f"Carrier channel {channel_id} ({channel_name}) created with state: {state}")
            
            # Check if channel is already being tracked or recorded
            if channel_id not in self.active_recordings and channel_id not in self.pending_recordings:
                # Try redirecting immediately if channel is already in a redirectable state
                if state in ["Ringing", "Up"]:
                    bridge_id = await self.ari_client.get_channel_bridge(channel_id)
                    if not bridge_id:
                        logger.info(f"Carrier channel {channel_id} is in {state} state at creation and not in bridge, attempting immediate redirect to Stasis")
                        
                        redirect_success = await self.ari_client.redirect_channel_to_stasis(
                            channel_id,
                            app=settings.ASTERISK_APP_NAME,
                            app_args=[channel_id, channel_id]
                        )
                        
                        if redirect_success:
                            logger.info(f"✅ Successfully redirected carrier channel {channel_id} to Stasis at creation time (state: {state})")
                            await asyncio.sleep(0.5)
                            
                            # Start recording
                            recording_name = f"call_{channel_id}"
                            recording_success = await self.ari_client.start_recording(channel_id, recording_name)
                            
                            if recording_success:
                                logger.info(f"✅ Started recording {recording_name} for call {channel_id}")
                                self.active_recordings[channel_id] = recording_name
                                asyncio.create_task(self._stream_audio(channel_id, recording_name))
                            else:
                                logger.warning(f"Failed to start recording on carrier channel {channel_id} in Stasis")
                        else:
                            logger.warning(f"❌ Could not redirect carrier channel {channel_id} to Stasis at creation (state: {state}, may already be in Dial() bridge)")
                    else:
                        logger.warning(f"Channel {channel_id} is already in bridge {bridge_id} at creation, cannot redirect")
                else:
                    # Channel is in "Down" state, wait a bit and check again
                    await asyncio.sleep(0.1)
                    
                    # Check channel state again
                    channel_info = await self.ari_client.get_channel(channel_id)
                    if channel_info:
                        current_state = channel_info.get("state", "")
                        bridge_id = await self.ari_client.get_channel_bridge(channel_id)
                        
                        if not bridge_id and current_state in ["Ringing", "Up"]:
                            logger.info(f"Carrier channel {channel_id} transitioned to {current_state} state after creation, attempting redirect to Stasis")
                            
                            redirect_success = await self.ari_client.redirect_channel_to_stasis(
                                channel_id,
                                app=settings.ASTERISK_APP_NAME,
                                app_args=[channel_id, channel_id]
                            )
                            
                            if redirect_success:
                                logger.info(f"✅ Successfully redirected carrier channel {channel_id} to Stasis after creation (state: {current_state})")
                                await asyncio.sleep(0.5)
                                
                                # Start recording
                                recording_name = f"call_{channel_id}"
                                recording_success = await self.ari_client.start_recording(channel_id, recording_name)
                                
                                if recording_success:
                                    logger.info(f"✅ Started recording {recording_name} for call {channel_id}")
                                    self.active_recordings[channel_id] = recording_name
                                    asyncio.create_task(self._stream_audio(channel_id, recording_name))
                                else:
                                    logger.warning(f"Failed to start recording on carrier channel {channel_id} in Stasis")
                            else:
                                logger.warning(f"❌ Could not redirect carrier channel {channel_id} to Stasis after creation (state: {current_state}, may already be in Dial() bridge)")
                        elif bridge_id:
                            logger.warning(f"Carrier channel {channel_id} is already in bridge {bridge_id} when created, cannot redirect")
                        else:
                            logger.debug(f"Carrier channel {channel_id} is still in {current_state} state, will try redirect on state change")
    
    async def _handle_call_end(self, event: Dict[str, Any]):
        """Handle call end event"""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        call_id = channel.get("name", channel_id)
        
        # Try to find call_id from active_recordings by channel_id or call_id
        found_call_id = None
        if call_id in self.active_recordings:
            found_call_id = call_id
        else:
            # Search through active_channels to find matching call_id
            for stored_call_id in self.ari_client.active_channels.keys():
                stored_channel = self.ari_client.active_channels.get(stored_call_id)
                if stored_channel and stored_channel.get("id") == channel_id:
                    found_call_id = stored_call_id
                    break
        
        # If still not found, try channel_id directly
        if not found_call_id and channel_id in self.active_recordings:
            found_call_id = channel_id
        
        # Stop recording if found
        if found_call_id and found_call_id in self.active_recordings:
            recording_name = self.active_recordings[found_call_id]
            await self.ari_client.stop_recording(recording_name)
            del self.active_recordings[found_call_id]
            logger.info(f"Stopped recording for call {found_call_id}")
        
        # Handle event (this will update call status)
        await self.ari_client.handle_channel_event(event)
    
    async def _handle_recording_finished(self, event: Dict[str, Any]):
        """Handle recording finished event"""
        recording = event.get("recording", {})
        recording_name = recording.get("name")
        logger.info(f"Recording finished: {recording_name}")
    
    async def _handle_channel_joined_bridge(self, event: Dict[str, Any]):
        """Handle channel joined bridge event - detect carrier channel and move to Stasis"""
        try:
            logger.info(f"ChannelJoinedBridge event received: {json.dumps(event, default=str)[:300]}")
            channel = event.get("channel", {})
            channel_id = channel.get("id")
            channel_name = channel.get("name", "")
            bridge = event.get("bridge", {})
            bridge_id = bridge.get("id")
            
            logger.info(f"Channel {channel_id} ({channel_name}) joined bridge {bridge_id}")
            
            if not channel_id:
                logger.warning("ChannelJoinedBridge event missing channel ID")
                return
            
            # Check if this is a carrier channel (SIP/galax pattern)
            is_carrier_channel = "SIP/galax" in channel_name or "SIP/galax" in str(channel_id)
            
            if is_carrier_channel:
                logger.info(f"Carrier channel {channel_id} ({channel_name}) joined bridge {bridge_id}")
                
                # This carrier channel was created by Dial() and joined a bridge
                # First, log the call to the database so it shows on dashboard
                # Get channel info to extract call details
                channel_info = await self.ari_client.get_channel(channel_id)
                if channel_info:
                    caller_number = channel_info.get("caller", {}).get("number", "")
                    callee_number = channel_info.get("connected", {}).get("number", "")
                    if not callee_number:
                        # Try to get from dialplan
                        dialplan = channel_info.get("dialplan", {})
                        callee_number = dialplan.get("exten", "")
                    
                    # Log the call
                    call_id = channel_id
                    call_data = {
                        "call_id": call_id,
                        "channel_id": channel_id,
                        "caller_number": caller_number or "0000000000",
                        "callee_number": callee_number or "unknown",
                        "status": "active",
                        "start_time": datetime.utcnow()
                    }
                    await self.logging_service.log_call(call_data)
                    logger.info(f"Logged call: {call_id} - {caller_number} -> {callee_number}")
                
                # We need to move it to Stasis so the backend can manage it
                # First, get the bridge info to find the original channel
                bridge_info = await self.ari_client.get_bridge(bridge_id)
                if bridge_info:
                    bridge_channels = bridge_info.get("channels", [])
                    
                    # Find the original channel (Local/ pattern)
                    original_channel_id = None
                    meetme_room = None
                    
                    for ch in bridge_channels:
                        ch_id = ch.get("id") if isinstance(ch, dict) else ch
                        if ch_id != channel_id:
                            # This is likely the original channel
                            ch_info = await self.ari_client.get_channel(ch_id)
                            if ch_info:
                                ch_name = ch_info.get("name", "")
                                if "Local/" in ch_name and "@" in ch_name:
                                    original_channel_id = ch_id
                                    # Extract MeetMe room from channel name
                                    parts = ch_name.split("/")
                                    if len(parts) > 1:
                                        local_part = parts[1].split("@")[0]
                                        if local_part.isdigit() and len(local_part) >= 6:
                                            meetme_room = local_part
                                            logger.info(f"Found original channel {original_channel_id} with MeetMe room {meetme_room}")
                                            break
                    
                    # The carrier channel is in a Dial() bridge, which is not Stasis-managed
                    # Strategy: Try to redirect to Stasis immediately (might work even if in Dial() bridge)
                    # If that fails, track the bridge and wait for it to be destroyed
                    if meetme_room:
                        # Track this Dial() bridge so we can handle it when destroyed (fallback)
                        bridge_class = bridge_info.get("bridge_class", "")
                        if bridge_class == "basic":  # Dial() bridges are "basic" class
                            self.dial_bridges[bridge_id] = channel_id
                            self.pending_recordings[channel_id] = {
                                "meetme_room": meetme_room,
                                "call_id": channel_id,
                                "bridge_id": bridge_id
                            }
                            logger.info(f"Tracked Dial() bridge {bridge_id} with carrier channel {channel_id}")
                        
                        # Use snoop channel to record the carrier channel (works even when channel is in Dial() bridge)
                        logger.info(f"Creating snoop channel for carrier channel {channel_id} (channel is in Dial() bridge)")
                        snoop_channel_id = await self.ari_client.create_snoop_channel(
                            channel_id,
                            app=settings.ASTERISK_APP_NAME,
                            spy="both",  # Record both incoming and outgoing audio
                            whisper="none"  # Don't let the snooped channel hear us
                        )
                        
                        if snoop_channel_id:
                            logger.info(f"✅ Created snoop channel {snoop_channel_id} for carrier channel {channel_id}")
                            self.snoop_channels[channel_id] = snoop_channel_id
                            
                            # Wait a moment for snoop channel to be ready
                            await asyncio.sleep(0.5)
                            
                            # Start recording on the snoop channel (which is in Stasis)
                            recording_name = f"call_{channel_id}"
                            logger.info(f"Starting recording {recording_name} on snoop channel {snoop_channel_id} for call {channel_id}")
                            recording_success = await self.ari_client.start_recording(snoop_channel_id, recording_name)
                            
                            if recording_success:
                                logger.info(f"✅ Started recording {recording_name} on snoop channel {snoop_channel_id} for call {channel_id}")
                                # Track recording by original channel ID, but record on snoop channel
                                self.active_recordings[channel_id] = recording_name
                                # Start streaming chunks - use original channel_id so active_recordings check works
                                asyncio.create_task(self._stream_audio(channel_id, recording_name))
                                # Clean up tracking since recording started
                                if bridge_id in self.dial_bridges:
                                    del self.dial_bridges[bridge_id]
                                if channel_id in self.pending_recordings:
                                    del self.pending_recordings[channel_id]
                            else:
                                logger.warning(f"Failed to start recording on snoop channel {snoop_channel_id}")
                                # Keep tracking for fallback when bridge is destroyed
                        else:
                            logger.warning(f"Could not create snoop channel for carrier channel {channel_id}, will try when bridge is destroyed")
                            # Keep tracking - will try again when bridge is destroyed or channel leaves bridge
                    else:
                        logger.warning(f"Could not find MeetMe room for carrier channel {channel_id}, cannot move to MeetMe")
        except Exception as e:
            logger.error(f"Error handling channel joined bridge event: {e}")
    
    async def _handle_channel_left_bridge(self, event: Dict[str, Any]):
        """Handle channel left bridge event - redirect carrier channel to Stasis when it leaves Dial() bridge"""
        try:
            bridge = event.get("bridge", {})
            bridge_id = bridge.get("id")
            channel = event.get("channel", {})
            channel_id = channel.get("id")
            channel_name = channel.get("name", "")
            
            logger.info(f"🔴 ChannelLeftBridge event received: channel {channel_id} ({channel_name}) left bridge {bridge_id}")
            logger.info(f"   Event data: {json.dumps(event, default=str)[:400]}")
            
            if not bridge_id or not channel_id:
                logger.debug(f"ChannelLeftBridge: Missing bridge_id or channel_id, skipping")
                return
            
            # Check if this is a carrier channel leaving a Dial() bridge we're tracking
            is_carrier_channel = "SIP/galax" in channel_name
            logger.debug(f"ChannelLeftBridge: is_carrier_channel={is_carrier_channel}, bridge_id in dial_bridges={bridge_id in self.dial_bridges}")
            
            if is_carrier_channel and bridge_id in self.dial_bridges:
                # Verify this is the channel we're tracking
                tracked_channel_id = self.dial_bridges[bridge_id]
                if tracked_channel_id == channel_id:
                    logger.info(f"Carrier channel {channel_id} left Dial() bridge {bridge_id}, redirecting to Stasis immediately")
                    
                    # Get pending recording info
                    if channel_id in self.pending_recordings:
                        pending_info = self.pending_recordings[channel_id]
                        meetme_room = pending_info.get("meetme_room")
                        call_id = pending_info.get("call_id", channel_id)
                        
                        # Clean up tracking
                        del self.dial_bridges[bridge_id]
                        
                        # Check if channel still exists and is in a valid state
                        channel_info = await self.ari_client.get_channel(channel_id)
                        if not channel_info:
                            logger.warning(f"Channel {channel_id} no longer exists when trying to redirect after leaving bridge")
                            # Clean up pending
                            if channel_id in self.pending_recordings:
                                del self.pending_recordings[channel_id]
                            return
                        
                        channel_state = channel_info.get("state", "")
                        logger.info(f"Channel {channel_id} state after leaving bridge: {channel_state}")
                        
                        # Immediately redirect to Stasis for recording (channel is now free from Dial() bridge)
                        logger.info(f"Redirecting carrier channel {channel_id} to Stasis for recording")
                        redirect_success = await self.ari_client.redirect_channel_to_stasis(
                            channel_id,
                            app=settings.ASTERISK_APP_NAME,
                            app_args=[channel_id, channel_id]
                        )
                        
                        if redirect_success:
                            logger.info(f"✅ Successfully redirected carrier channel {channel_id} to Stasis")
                            # Wait a moment for channel to enter Stasis
                            await asyncio.sleep(0.5)
                            
                            # Start recording
                            recording_name = f"call_{channel_id}"
                            logger.info(f"Starting recording {recording_name} for call {channel_id}")
                            recording_success = await self.ari_client.start_recording(channel_id, recording_name)
                            
                            if recording_success:
                                logger.info(f"✅ Started recording {recording_name} for call {channel_id}")
                                self.active_recordings[channel_id] = recording_name
                                # Start streaming chunks
                                asyncio.create_task(self._stream_audio(channel_id, recording_name))
                            else:
                                logger.warning(f"Failed to start recording on carrier channel {channel_id} in Stasis")
                        else:
                            logger.warning(f"Could not redirect carrier channel {channel_id} to Stasis (may already be destroyed or in MeetMe)")
                        
                        # Now move channel to MeetMe (for VICIdial compatibility)
                        if meetme_room:
                            logger.info(f"Moving carrier channel {channel_id} to MeetMe room {meetme_room}")
                            meetme_success = await self.ari_client.add_channel_to_meetme(channel_id, meetme_room)
                            
                            if meetme_success:
                                logger.info(f"✅ Successfully moved carrier channel {channel_id} to MeetMe room {meetme_room}")
                                self.bridged_channels[channel_id] = channel_id
                                if channel_id not in self.active_bridges:
                                    self.active_bridges[channel_id] = f"meetme_{meetme_room}"
                                
                                # Check if recording is still active after moving to MeetMe
                                if recording_success:
                                    await asyncio.sleep(0.5)
                                    recording_state = await self.ari_client.get_recording_state(recording_name)
                                    if recording_state:
                                        state = recording_state.get("state", "unknown")
                                        if state == "recording":
                                            logger.info(f"✅ Recording {recording_name} is still active after MeetMe move")
                                        else:
                                            logger.warning(f"⚠️ Recording {recording_name} is in state '{state}' after MeetMe move")
                            else:
                                logger.error(f"Failed to move carrier channel {channel_id} to MeetMe room {meetme_room}")
                        
                        # Clean up pending
                        if channel_id in self.pending_recordings:
                            del self.pending_recordings[channel_id]
        except Exception as e:
            logger.error(f"Error handling channel left bridge event: {e}", exc_info=True)
    
    async def _handle_bridge_destroyed(self, event: Dict[str, Any]):
        """Handle bridge destroyed event - try to redirect carrier channel to Stasis for recording"""
        try:
            bridge = event.get("bridge", {})
            bridge_id = bridge.get("id")
            
            if not bridge_id:
                return
            
            logger.info(f"🔴 BridgeDestroyed event received: bridge {bridge_id}")
            logger.info(f"   Event data: {json.dumps(event, default=str)[:400]}")
            
            # Check if this is a Dial() bridge we're tracking
            if bridge_id in self.dial_bridges:
                logger.info(f"   This is a tracked Dial() bridge!")
                carrier_channel_id = self.dial_bridges[bridge_id]
                logger.info(f"Dial() bridge {bridge_id} destroyed, carrier channel {carrier_channel_id} may be free")
                
                # Check if channel still exists (it might have been destroyed already)
                channel_info = await self.ari_client.get_channel(carrier_channel_id)
                if not channel_info:
                    logger.info(f"Channel {carrier_channel_id} no longer exists (likely already handled by ChannelLeftBridge or destroyed)")
                    # Clean up tracking
                    if bridge_id in self.dial_bridges:
                        del self.dial_bridges[bridge_id]
                    if carrier_channel_id in self.pending_recordings:
                        del self.pending_recordings[carrier_channel_id]
                    return
                
                # Get pending recording info
                if carrier_channel_id in self.pending_recordings:
                    pending_info = self.pending_recordings[carrier_channel_id]
                    meetme_room = pending_info.get("meetme_room")
                    call_id = pending_info.get("call_id", carrier_channel_id)
                    
                    # Clean up tracking
                    del self.dial_bridges[bridge_id]
                    
                    # Now that the Dial() bridge is destroyed, try to redirect channel to Stasis BEFORE moving to MeetMe
                    logger.info(f"Dial() bridge {bridge_id} destroyed, attempting to redirect carrier channel {carrier_channel_id} to Stasis for recording")
                    redirect_success = await self.ari_client.redirect_channel_to_stasis(
                        carrier_channel_id,
                        app=settings.ASTERISK_APP_NAME,
                        app_args=[carrier_channel_id, carrier_channel_id]
                    )
                    
                    if redirect_success:
                        logger.info(f"✅ Successfully redirected carrier channel {carrier_channel_id} to Stasis")
                        # Wait a moment for channel to enter Stasis
                        await asyncio.sleep(0.5)
                        
                        # Start recording
                        recording_name = f"call_{carrier_channel_id}"
                        logger.info(f"Starting recording {recording_name} for call {carrier_channel_id}")
                        recording_success = await self.ari_client.start_recording(carrier_channel_id, recording_name)
                        
                        if recording_success:
                            logger.info(f"✅ Started recording {recording_name} for call {carrier_channel_id}")
                            self.active_recordings[carrier_channel_id] = recording_name
                            # Start streaming chunks
                            asyncio.create_task(self._stream_audio(carrier_channel_id, recording_name))
                        else:
                            logger.warning(f"Failed to start recording on carrier channel {carrier_channel_id} in Stasis")
                    
                    # Now move channel to MeetMe (for VICIdial compatibility) - do this regardless of recording success
                    logger.info(f"Moving carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                    meetme_success = await self.ari_client.add_channel_to_meetme(carrier_channel_id, meetme_room)
                    
                    if meetme_success:
                        logger.info(f"✅ Successfully moved carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                        self.bridged_channels[carrier_channel_id] = carrier_channel_id
                        if carrier_channel_id not in self.active_bridges:
                            self.active_bridges[carrier_channel_id] = f"meetme_{meetme_room}"
                        
                        # IMPORTANT: Check if recording is still active after moving to MeetMe
                        # Moving to MeetMe may cause the channel to leave Stasis, stopping the recording
                        if recording_success:
                            await asyncio.sleep(0.5)  # Wait a moment for MeetMe move to complete
                            recording_state = await self.ari_client.get_recording_state(recording_name)
                            if recording_state:
                                state = recording_state.get("state", "unknown")
                                if state == "recording":
                                    logger.info(f"✅ Recording {recording_name} is still active after MeetMe move")
                                else:
                                    logger.warning(f"⚠️ Recording {recording_name} is in state '{state}' after MeetMe move - channel may have left Stasis")
                            else:
                                logger.warning(f"⚠️ Could not check recording state for {recording_name} after MeetMe move")
                    else:
                        logger.error(f"Failed to move carrier channel {carrier_channel_id} to MeetMe room {meetme_room}")
                    
                    # Clean up pending
                    if carrier_channel_id in self.pending_recordings:
                        del self.pending_recordings[carrier_channel_id]
        except Exception as e:
            logger.error(f"Error handling bridge destroyed event: {e}")
    
    async def _poll_pending_recordings(self):
        """Background task to periodically check if channels in pending_recordings have left their Dial() bridges"""
        logger.info("Starting background polling task for pending recordings")
        
        while self.monitoring:
            try:
                await asyncio.sleep(2)  # Check every 2 seconds
                
                if not self.pending_recordings:
                    continue
                
                # Check each pending recording
                pending_channels = list(self.pending_recordings.keys())
                logger.info(f"🔍 Polling: Checking {len(pending_channels)} pending channels: {pending_channels}")
                for channel_id in pending_channels:
                    try:
                        # Check if channel still exists
                        channel_info = await self.ari_client.get_channel(channel_id)
                        if not channel_info:
                            logger.info(f"🔍 Polling: Channel {channel_id} no longer exists, removing from pending")
                            if channel_id in self.pending_recordings:
                                del self.pending_recordings[channel_id]
                            continue
                        
                        # Check if channel is still in a Dial() bridge
                        bridge_id = await self.ari_client.get_channel_bridge(channel_id)
                        
                        if bridge_id and bridge_id in self.dial_bridges:
                            # Verify the bridge still exists (it might have been destroyed without us getting the event)
                            bridge_info = await self.ari_client.get_bridge(bridge_id)
                            if not bridge_info:
                                logger.info(f"🔍 Polling: Dial() bridge {bridge_id} no longer exists (destroyed without event), channel {channel_id} is free")
                                # Bridge was destroyed, treat as if channel left
                                bridge_id = None
                            else:
                                # Check if we already created a snoop channel for this channel
                                if channel_id not in self.snoop_channels and channel_id not in self.active_recordings:
                                    logger.info(f"🔍 Polling: Channel {channel_id} is still in Dial() bridge {bridge_id}, creating snoop channel for recording")
                                    # Create snoop channel to record this channel
                                    snoop_channel_id = await self.ari_client.create_snoop_channel(
                                        channel_id,
                                        app=settings.ASTERISK_APP_NAME,
                                        spy="both",
                                        whisper="none"
                                    )
                                    
                                    if snoop_channel_id:
                                        logger.info(f"✅ Created snoop channel {snoop_channel_id} for channel {channel_id} (via polling)")
                                        self.snoop_channels[channel_id] = snoop_channel_id
                                        await asyncio.sleep(0.5)
                                        
                                        # Start recording on snoop channel
                                        recording_name = f"call_{channel_id}"
                                        recording_success = await self.ari_client.start_recording(snoop_channel_id, recording_name)
                                        
                                        if recording_success:
                                            logger.info(f"✅ Started recording {recording_name} on snoop channel {snoop_channel_id} (via polling)")
                                            self.active_recordings[channel_id] = recording_name
                                            # Use original channel_id so active_recordings check works
                                            asyncio.create_task(self._stream_audio(channel_id, recording_name))
                                            # Clean up tracking
                                            if bridge_id in self.dial_bridges:
                                                del self.dial_bridges[bridge_id]
                                            if channel_id in self.pending_recordings:
                                                del self.pending_recordings[channel_id]
                                        else:
                                            logger.warning(f"Failed to start recording on snoop channel {snoop_channel_id} (via polling)")
                                else:
                                    logger.info(f"🔍 Polling: Channel {channel_id} is still in Dial() bridge {bridge_id}, snoop channel already exists or recording active")
                                continue
                        
                        # If channel is not in a bridge, or the bridge is not a Dial() bridge we're tracking
                        if not bridge_id or bridge_id not in self.dial_bridges:
                            logger.info(f"🔍 Polling detected: Channel {channel_id} has left Dial() bridge (or bridge destroyed)")
                            
                            # Get pending info
                            pending_info = self.pending_recordings.get(channel_id)
                            if not pending_info:
                                continue
                            
                            meetme_room = pending_info.get("meetme_room")
                            call_id = pending_info.get("call_id", channel_id)
                            
                            # Clean up tracking
                            if bridge_id and bridge_id in self.dial_bridges:
                                del self.dial_bridges[bridge_id]
                            
                            # Try to redirect to Stasis for recording
                            logger.info(f"Attempting to redirect channel {channel_id} to Stasis (detected via polling)")
                            redirect_success = await self.ari_client.redirect_channel_to_stasis(
                                channel_id,
                                app=settings.ASTERISK_APP_NAME,
                                app_args=[channel_id, channel_id]
                            )
                            
                            if redirect_success:
                                logger.info(f"✅ Successfully redirected channel {channel_id} to Stasis (via polling)")
                                await asyncio.sleep(0.5)
                                
                                # Start recording
                                recording_name = f"call_{channel_id}"
                                recording_success = await self.ari_client.start_recording(channel_id, recording_name)
                                
                                if recording_success:
                                    logger.info(f"✅ Started recording {recording_name} for call {channel_id} (via polling)")
                                    self.active_recordings[channel_id] = recording_name
                                    asyncio.create_task(self._stream_audio(channel_id, recording_name))
                                else:
                                    logger.warning(f"Failed to start recording on channel {channel_id} in Stasis (via polling)")
                            else:
                                logger.warning(f"Could not redirect channel {channel_id} to Stasis (via polling, may already be in MeetMe)")
                            
                            # Move to MeetMe if needed
                            if meetme_room:
                                logger.info(f"Moving channel {channel_id} to MeetMe room {meetme_room} (via polling)")
                                meetme_success = await self.ari_client.add_channel_to_meetme(channel_id, meetme_room)
                                if meetme_success:
                                    logger.info(f"✅ Successfully moved channel {channel_id} to MeetMe room {meetme_room} (via polling)")
                                    self.bridged_channels[channel_id] = call_id
                                    if channel_id not in self.active_bridges:
                                        self.active_bridges[channel_id] = f"meetme_{meetme_room}"
                            
                            # Clean up pending
                            if channel_id in self.pending_recordings:
                                del self.pending_recordings[channel_id]
                    except Exception as e:
                        logger.error(f"Error polling channel {channel_id}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error in polling task: {e}")
                await asyncio.sleep(5)  # Wait longer on error
    
    # Removed: All MixMonitor file monitoring methods - using ARI recording only
    
    async def _stream_audio(self, call_id: str, recording_name: str):
        """Stream audio chunks from recording"""
        chunk_index = 0
        consecutive_empty = 0
        max_empty_retries = 20  # Increased retries to handle delays after MeetMe move
        recording_state_checked = False
        
        logger.info(f"Starting audio stream for call {call_id}, recording {recording_name}")
        
        try:
            while call_id in self.active_recordings:
                # Check recording state periodically (every 10 chunks or on first attempt)
                if not recording_state_checked or chunk_index % 10 == 0:
                    recording_state = await self.ari_client.get_recording_state(recording_name)
                    if recording_state:
                        state = recording_state.get("state", "unknown")
                        if state == "recording":
                            if not recording_state_checked:
                                logger.info(f"✅ Recording {recording_name} is active and recording")
                                recording_state_checked = True
                        elif state in ("done", "failed"):
                            logger.warning(f"⚠️ Recording {recording_name} is in state '{state}', stopping stream")
                            break
                        elif chunk_index == 0:
                            logger.info(f"Recording {recording_name} state: {state}")
                
                # Get live recording data (only wait for ready on first attempt)
                wait_for_ready = (chunk_index == 0)
                audio_data = await self.ari_client.get_live_recording(recording_name, wait_for_ready=wait_for_ready)
                
                if audio_data and len(audio_data) > 0:
                    if chunk_index == 0 or chunk_index % 50 == 0:  # Log every 50th chunk to avoid spam
                        logger.info(f"Received audio data for {call_id}: {len(audio_data)} bytes (chunk {chunk_index})")
                    consecutive_empty = 0  # Reset counter on successful fetch
                    # Process audio chunk
                    processed_chunk = await self.audio_processor.process_chunk(audio_data, call_id)
                    
                    if processed_chunk:
                        # Log audio chunk
                        await self.logging_service.log_audio_chunk(
                            call_id,
                            processed_chunk,
                            {
                                "stream_id": call_id,
                                "chunk_index": chunk_index,
                                "source": "ari_recording"
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
                else:
                    # No audio data received
                    consecutive_empty += 1
                    if consecutive_empty == 1:
                        logger.debug(f"No audio data yet for {recording_name} (attempt {consecutive_empty}/{max_empty_retries})")
                    elif consecutive_empty >= max_empty_retries:
                        # Check recording state one more time before giving up
                        recording_state = await self.ari_client.get_recording_state(recording_name)
                        if recording_state:
                            state = recording_state.get("state", "unknown")
                            logger.warning(f"No audio data received for {call_id} after {max_empty_retries} attempts. Recording state: {state}")
                        else:
                            logger.warning(f"No audio data received for {call_id} after {max_empty_retries} attempts. Recording may not exist.")
                        break
                
                # Wait before next chunk
                await asyncio.sleep(0.1)  # 100ms intervals
                
        except Exception as e:
            logger.error(f"Error streaming audio for call {call_id}: {e}", exc_info=True)
        finally:
            logger.info(f"Audio stream ended for call {call_id}")
    
    # Removed: All MixMonitor file monitoring methods - using ARI recording only


# Global monitor instance
monitor = AsteriskMonitor()


async def start_monitor():
    """Start the Asterisk monitor"""
    await monitor.start()


async def stop_monitor():
    """Stop the Asterisk monitor"""
    await monitor.stop()

