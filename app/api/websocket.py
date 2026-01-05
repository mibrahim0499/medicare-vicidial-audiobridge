"""WebSocket endpoints for audio streaming"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Header
from typing import Dict, Set
import json
import logging
import time
from datetime import datetime
from app.config import settings
from app.services.logger import LoggingService
from app.services.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)
router = APIRouter()

# Active WebSocket connections
active_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, call_id: str):
        """Connect a WebSocket for a specific call"""
        try:
            # Accept WebSocket with permissive origin checking
            await websocket.accept()
            if call_id not in self.active_connections:
                self.active_connections[call_id] = set()
            self.active_connections[call_id].add(websocket)
            logger.info(f"WebSocket connected for call_id: {call_id}")
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            try:
                await websocket.close(code=1008, reason=str(e))
            except Exception:
                pass
            raise
    
    def disconnect(self, websocket: WebSocket, call_id: str):
        """Disconnect a WebSocket"""
        if call_id in self.active_connections:
            self.active_connections[call_id].discard(websocket)
            if not self.active_connections[call_id]:
                del self.active_connections[call_id]
        logger.info(f"WebSocket disconnected for call_id: {call_id}")
    
    async def send_audio_chunk(self, call_id: str, chunk_data: bytes, metadata: dict):
        """Send audio chunk to all connected clients for a call"""
        if call_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[call_id]:
                try:
                    await connection.send_json({
                        "type": "audio_chunk",
                        "call_id": call_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "metadata": metadata,
                        "data_size": len(chunk_data)
                    })
                    await connection.send_bytes(chunk_data)
                except Exception as e:
                    logger.error(f"Error sending to WebSocket: {e}")
                    disconnected.add(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.disconnect(conn, call_id)
    
    async def send_message(self, call_id: str, message: dict):
        """Send JSON message to all connected clients for a call"""
        if call_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[call_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to WebSocket: {e}")
                    disconnected.add(connection)
            
            for conn in disconnected:
                self.disconnect(conn, call_id)


manager = ConnectionManager()


@router.websocket("/ws/audio/{call_id}")
async def websocket_audio_stream(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for receiving audio streams"""
    # Accept WebSocket connection (CORS is handled at HTTP level, WebSocket inherits it)
    try:
        await manager.connect(websocket, call_id)
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {e}")
        await websocket.close(code=1008, reason="Connection failed")
        return
    
    try:
        while True:
            # Receive messages from client (heartbeat, control messages, etc.)
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Ignore invalid JSON
                continue
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                continue
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, call_id)
    except Exception as e:
        logger.error(f"WebSocket error for call_id {call_id}: {e}")
        manager.disconnect(websocket, call_id)


@router.post("/api/stream/audio/{call_id}")
async def receive_audio_stream(
    call_id: str,
    audio_data: bytes,
    x_ingest_token: str = Header(default=None, alias="X-Ingest-Token"),
):
    """REST endpoint to receive audio stream data (alternative to WebSocket)"""
    try:
        # Optional lightweight auth guard for inbound media
        expected_token = settings.INGEST_AUTH_TOKEN
        if expected_token:
            if not x_ingest_token or x_ingest_token != expected_token:
                logger.warning("Rejected unauthorized audio stream request")

                # #region agent log
                try:
                    with open("/Users/pc/Documents/marsons-projects/phase1-audio-bridge/.cursor/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "pre-fix",
                            "hypothesisId": "H4",
                            "location": "app/api/websocket.py:receive_audio_stream",
                            "message": "Unauthorized audio stream attempt",
                            "data": {
                                "call_id": call_id,
                                "provided_token": bool(x_ingest_token),
                                "audio_size": len(audio_data) if audio_data is not None else 0,
                            },
                            "timestamp": int(time.time() * 1000),
                        }) + "\n")
                except Exception:
                    pass
                # #endregion agent log

                raise HTTPException(status_code=401, detail="Unauthorized")

        # Process and log the audio chunk
        processor = AudioProcessor()
        processed_chunk = await processor.process_chunk(audio_data, call_id)
        
        # Log the audio chunk
        logging_service = LoggingService()
        await logging_service.log_audio_chunk(call_id, processed_chunk)

        # #region agent log
        try:
            with open("/Users/pc/Documents/marsons-projects/phase1-audio-bridge/.cursor/debug.log", "a") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H4",
                    "location": "app/api/websocket.py:receive_audio_stream",
                    "message": "Received audio stream via HTTP",
                    "data": {
                        "call_id": call_id,
                        "raw_size": len(audio_data) if audio_data is not None else 0,
                        "processed_size": len(processed_chunk) if processed_chunk is not None else 0,
                    },
                    "timestamp": int(time.time() * 1000),
                }) + "\n")
        except Exception:
            pass
        # #endregion agent log
        
        # Broadcast to WebSocket clients
        await manager.send_audio_chunk(call_id, processed_chunk, {
            "format": "PCM",
            "sample_rate": settings.AUDIO_SAMPLE_RATE
        })
        
        return {"status": "received", "call_id": call_id, "size": len(audio_data)}
    except Exception as e:
        logger.error(f"Error receiving audio stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))
