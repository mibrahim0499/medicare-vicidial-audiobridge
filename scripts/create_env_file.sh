#!/bin/bash
# Create .env file on the server with correct Asterisk settings

ENV_FILE="/opt/phase1-audio-bridge/.env"

echo "=========================================="
echo "Creating .env file for Audio Bridge"
echo "=========================================="
echo ""

# Check if .env already exists
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  .env file already exists at: $ENV_FILE"
    echo ""
    echo "Current ARI settings:"
    grep -E "ASTERISK_" "$ENV_FILE" || echo "No ASTERISK settings found"
    echo ""
    read -p "Overwrite? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Backup existing
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✓ Backed up existing .env"
fi

# Create .env file
cat > "$ENV_FILE" << 'EOF'
# Application Configuration
APP_NAME=Audio Streaming Bridge
DEBUG=false
ENVIRONMENT=production

# Server
HOST=0.0.0.0
PORT=8000

# CORS
CORS_ORIGINS=*

# Database
DATABASE_URL=sqlite+aiosqlite:///./audio_bridge.db

# Asterisk ARI Configuration
ASTERISK_HOST=autodialer1.worldatlantus.com
ASTERISK_PORT=8088
ASTERISK_USERNAME=asterisk
ASTERISK_PASSWORD=worldalt2121

# ARI WebSocket URL (for event monitoring)
ASTERISK_WS_URL=ws://autodialer1.worldatlantus.com:8088/ari/events?app=audio-bridge&subscribeAll=true

# Stasis Application Name
ASTERISK_APP_NAME=audio-bridge

# Enable WebSocket monitoring
ENABLE_WEBSOCKET_MONITOR=true
USE_POLLING_MONITOR=false

# Audio Processing
AUDIO_CHUNK_SIZE=4096
AUDIO_SAMPLE_RATE=8000
AUDIO_CHANNELS=1
AUDIO_FORMAT=PCM

# WebSocket
WS_MAX_CONNECTIONS=2000
WS_HEARTBEAT_INTERVAL=30

# Logging
LOG_LEVEL=INFO
LOG_AUDIO_STREAMS=true

# Storage
AUDIO_STORAGE_PATH=./audio_storage

# Security (optional)
INGEST_AUTH_TOKEN=
EOF

chmod 600 "$ENV_FILE"
echo "✓ Created .env file at: $ENV_FILE"
echo ""
echo "Settings:"
echo "  ASTERISK_HOST=autodialer1.worldatlantus.com"
echo "  ASTERISK_PORT=8088"
echo "  ASTERISK_USERNAME=asterisk"
echo "  ASTERISK_PASSWORD=worldalt2121"
echo ""
echo "Next steps:"
echo "  1. Restart the service: systemctl restart audio-bridge.service"
echo "  2. Check logs: journalctl -u audio-bridge.service -f"
echo "  3. Test ARI connection: curl -u asterisk:worldalt2121 http://autodialer1.worldatlantus.com:8088/ari/applications"
echo ""

