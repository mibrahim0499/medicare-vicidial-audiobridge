# Audio Bridge - Real-Time Call Monitoring & Streaming System

A production-ready FastAPI application for real-time call monitoring, audio streaming, and recording integration with Asterisk/VICIdial systems. Features WebSocket-based live audio streaming, automatic recording via snoop channels, and cloud storage integration with Supabase.

## 🚀 Features

- **Real-Time Call Monitoring** - Monitor active calls via Asterisk ARI (Asterisk REST Interface)
- **Live Audio Streaming** - WebSocket-based real-time audio streaming to web dashboard
- **Intelligent Recording** - Automatic recording using snoop channels (works with Dial() bridges)
- **VICIdial Integration** - Seamless integration with VICIdial without dialplan modifications
- **MeetMe Conference Support** - Automatic carrier channel movement to MeetMe conferences
- **Cloud Storage** - Audio chunks stored in Supabase Storage for scalability
- **REST API** - Complete REST API for call management and metadata
- **Web Dashboard** - Real-time monitoring dashboard with live audio visualization

## 📋 Table of Contents

- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Code Structure](#code-structure)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## 🏗️ Architecture

### System Components

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Asterisk      │──────│  Audio Bridge    │──────│   Supabase      │
│   (ARI/Stasis)  │      │   (FastAPI)      │      │  (DB + Storage) │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                │
                                │ WebSocket
                                ▼
                        ┌──────────────────┐
                        │   Web Dashboard  │
                        │   (index.html)   │
                        └──────────────────┘
```

### Core Services

1. **Asterisk Monitor Service** - Monitors call events and manages recordings
2. **ARI Client** - Interfaces with Asterisk REST API
3. **Logger Service** - Handles database and storage operations
4. **WebSocket Manager** - Manages real-time audio streaming connections
5. **Audio Processor** - Processes and formats audio chunks

## 🔄 How It Works

### Call Detection & Recording Flow

1. **Channel Detection**
   - Asterisk channel enters Stasis application (`audio-bridge`)
   - Monitor service receives `StasisStart` event via WebSocket
   - System identifies channel type (agent/carrier) and context

2. **Recording Strategy**
   - **For Dial() Bridges** (VICIdial default):
     - Creates a "snoop channel" to monitor the original channel
     - Starts recording on snoop channel (in Stasis, recordable)
     - Original channel continues in Dial() bridge unaffected
   - **For Stasis Channels**:
     - Direct recording on the channel
   - **For MeetMe Conferences**:
     - Detects MeetMe room from channel variables
     - Moves carrier channel to MeetMe conference
     - VICIdial handles MeetMe recording

3. **Audio Processing**
   - Audio chunks retrieved from Asterisk recordings
   - Processed through AudioProcessor for format conversion
   - Uploaded to Supabase Storage bucket
   - Metadata stored in Supabase database

4. **Real-Time Streaming**
   - Chunks broadcast via WebSocket to connected clients
   - Dashboard receives and plays audio in real-time
   - Supports multiple concurrent connections

### Snoop Channel Recording

**The Challenge:** VICIdial uses `Dial()` which creates bridges that aren't Stasis-managed. Redirecting channels to Stasis would disrupt active calls.

**The Solution:** ARI snoop channels can monitor and record channels even when they're in Dial() bridges. The snoop channel:
- Is in Stasis (can be recorded)
- Doesn't affect the original channel
- Receives audio from both directions (spy: "both")

**Implementation:** See `app/services/asterisk_monitor.py`:
- Lines 1054-1090: Snoop channel creation for Dial() bridges
- Lines 1333-1366: Polling mechanism for missed channels

### MeetMe Integration

The system automatically detects MeetMe conferences and ensures proper integration:

1. **Room Detection** - Extracts MeetMe room number from:
   - Channel variables (`MEETME_ROOMNUM`, `CONFBRIDGE`, etc.)
   - Channel name patterns (e.g., `Local/8600051@default`)
   - Dialplan context/exten

2. **Channel Movement** - Uses ARI to move carrier channel to MeetMe:
   ```python
   await ari_client.add_channel_to_meetme(carrier_channel_id, meetme_room)
   ```

3. **VICIdial Compatibility** - Sets `DIALSTATUS=ANSWER` so VICIdial shows call as LIVE

**Implementation:** See `app/services/asterisk_monitor.py` lines 276-286, 333-344, 371-384

## 📦 Prerequisites

- Python 3.9+
- Asterisk 13+ with ARI enabled
- PostgreSQL database (Supabase recommended)
- Supabase account (for Storage)
- Node.js (optional, for development)

## 🛠️ Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd phase1-audio-bridge
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
nano .env  # Or use your preferred editor
```

## ⚙️ Configuration

### Required Environment Variables

```env
# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres.user:password@host:5432/postgres

# Supabase Storage
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_STORAGE_BUCKET=audio-bucket

# Asterisk ARI
ASTERISK_HOST=your-asterisk-server.com
ASTERISK_PORT=8088
ASTERISK_USERNAME=asterisk
ASTERISK_PASSWORD=your-ari-password
ASTERISK_WS_URL=ws://your-asterisk-server.com:8088/ari/events?app=audio-bridge&subscribeAll=true
ASTERISK_APP_NAME=audio-bridge
ENABLE_WEBSOCKET_MONITOR=true
```

### Optional Configuration

```env
# Audio Processing
AUDIO_CHUNK_SIZE=4096
AUDIO_SAMPLE_RATE=8000
AUDIO_CHANNELS=1
AUDIO_FORMAT=PCM

# Logging
LOG_LEVEL=INFO
LOG_AUDIO_STREAMS=true

# Server
HOST=0.0.0.0
PORT=8000
```

### Supabase Setup

1. **Create Storage Bucket:**
   - Go to Supabase Dashboard → Storage
   - Create bucket named `audio-bucket` (or your preferred name)
   - Set as public if needed, or configure policies

2. **Get Service Role Key:**
   - Dashboard → Settings → API
   - Copy `service_role` key (not `anon` key)
   - Add to `.env` as `SUPABASE_KEY`

### Asterisk ARI Setup

Enable ARI on your Asterisk server:

1. **Create `/etc/asterisk/ari.conf`:**
   ```ini
   [general]
   enabled = yes
   pretty = yes
   allowed_origins = *
   
   [asterisk]
   type = user
   read_only = no
   password = your_secure_password
   ```

2. **Configure `/etc/asterisk/http.conf`:**
   ```ini
   [general]
   enabled=yes
   bindaddr=0.0.0.0
   bindport=8088
   ```

3. **Restart Asterisk:**
   ```bash
   sudo systemctl restart asterisk
   ```

See `docs/ASTERISK_CONNECTION_SETUP.md` for detailed instructions.

## 🚀 Usage

### Start Development Server

```bash
python run.py
# Or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access Dashboard

- Web Dashboard: `http://localhost:8000/static/index.html`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### Production Deployment

See `docs/DEPLOYMENT_INSTRUCTIONS.md` for production deployment guide.

## 📚 API Documentation

### REST Endpoints

#### Health Check
```http
GET /api/health
```
Returns service health status.

#### List Calls
```http
GET /api/calls?limit=50
```
Returns list of calls with metadata.

#### Get Call Details
```http
GET /api/calls/{call_id}
```
Returns detailed information about a specific call.

#### Ingest Audio Stream
```http
POST /api/stream/audio/{call_id}
Content-Type: application/octet-stream
X-Ingest-Token: your-token (optional)
```
Alternative endpoint for ingesting audio streams.

### WebSocket Endpoints

#### Audio Stream
```
ws://localhost:8000/ws/audio/{call_id}
```
Real-time audio streaming WebSocket connection for a specific call.

**Message Format:**
- Server → Client: JSON with base64-encoded audio chunks
- Client → Server: Connection management messages

## 📁 Code Structure

```
phase1-audio-bridge/
├── app/
│   ├── api/                    # API endpoints
│   │   ├── websocket.py       # WebSocket streaming
│   │   ├── calls.py           # REST API for calls
│   │   └── health.py          # Health check
│   │
│   ├── services/               # Core business logic
│   │   ├── asterisk_monitor.py    # Main monitoring service
│   │   ├── asterisk_client.py     # ARI client wrapper
│   │   ├── logger.py              # Database & storage
│   │   └── audio_processor.py     # Audio processing
│   │
│   ├── database/               # Database layer
│   │   ├── connection.py      # DB connection setup
│   │   └── models.py          # SQLAlchemy models
│   │
│   ├── utils/                  # Utilities
│   │   ├── supabase_storage.py    # Supabase Storage client
│   │   └── audio_utils.py         # Audio utilities
│   │
│   ├── models/                 # Pydantic models
│   │   ├── call.py
│   │   └── audio.py
│   │
│   ├── config.py               # Configuration management
│   └── main.py                 # FastAPI application
│
├── static/
│   └── index.html              # Web dashboard
│
├── scripts/                    # Deployment & utility scripts
│   ├── deploy.sh
│   ├── setup_asterisk_ari.sh
│   └── ...
│
├── docs/                       # Documentation
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

### Key Files Explained

**`app/services/asterisk_monitor.py`** (Main Monitoring Service)
- Monitors Asterisk events via WebSocket
- Handles call lifecycle (start, recording, end)
- Creates snoop channels for Dial() bridge recording
- Integrates with MeetMe conferences
- Polling mechanism for missed channels

**`app/services/asterisk_client.py`** (ARI Client)
- Wraps Asterisk REST API calls
- Channel, bridge, and recording management
- Snoop channel creation
- MeetMe conference operations

**`app/services/logger.py`** (Data Logging)
- Stores call metadata in database
- Uploads audio chunks to Supabase Storage
- Manages chunk metadata and relationships

**`app/utils/supabase_storage.py`** (Storage Client)
- Supabase Storage client initialization
- Async upload operations
- Public URL generation

**`app/api/websocket.py`** (WebSocket Manager)
- Manages WebSocket connections
- Broadcasts audio chunks to clients
- Connection lifecycle management

**`static/index.html`** (Web Dashboard)
- Real-time call monitoring interface
- WebSocket client for audio streaming
- Audio visualization and playback

## 🔧 Database Schema

### Tables

**calls** - Call metadata
- `call_id` (primary key)
- `channel_id`, `caller_number`, `callee_number`
- `status`, `start_time`, `end_time`, `duration`

**audio_streams** - Audio stream metadata
- `stream_id` (primary key)
- `call_id` (foreign key)
- `format`, `sample_rate`, `channels`

**audio_chunks** - Audio chunk metadata
- `id` (primary key)
- `call_id`, `stream_id` (foreign keys)
- `chunk_index`, `data_path` (Supabase Storage URL)
- `size`, `timestamp`

## 🚢 Deployment

### Production Setup

1. **Server Requirements:**
   - Ubuntu 20.04+ or similar
   - Python 3.9+
   - PostgreSQL client libraries

2. **Deploy Code:**
   ```bash
   rsync -avz --exclude='venv' --exclude='.env' ./ user@server:/opt/audio-bridge/
   ```

3. **Setup Systemd Service:**
   ```bash
   sudo cp scripts/audio-bridge.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable audio-bridge
   sudo systemctl start audio-bridge
   ```

4. **Configure Nginx:**
   ```bash
   sudo cp scripts/nginx.conf /etc/nginx/sites-available/audio-bridge
   sudo ln -s /etc/nginx/sites-available/audio-bridge /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

See `docs/DEPLOYMENT_INSTRUCTIONS.md` for complete deployment guide.

## 🐛 Troubleshooting

### Common Issues

**No audio chunks being uploaded**
```bash
# Check Supabase credentials
grep SUPABASE .env

# Check logs for upload errors
journalctl -u audio-bridge | grep -i "upload\|supabase"
```

**Calls not appearing in dashboard**
```bash
# Verify WebSocket connection
journalctl -u audio-bridge | grep -i "websocket\|stasis"

# Check ARI connection
curl -u asterisk:password http://asterisk-server:8088/ari/asterisk/info
```

**Recordings not starting**
```bash
# Check snoop channel creation
journalctl -u audio-bridge | grep -i "snoop"

# Verify channel events
journalctl -u audio-bridge | grep -i "channel.*created\|channel.*entered"
```

### Debug Mode

Enable debug logging in `.env`:
```env
LOG_LEVEL=DEBUG
DEBUG=true
```

### Check Service Status

```bash
systemctl status audio-bridge
journalctl -u audio-bridge -f  # Follow logs
```

## 🔒 Security Considerations

- **Supabase Service Role Key**: Keep secure, never commit to git
- **ARI Password**: Strong password, restricted access
- **Environment Variables**: Use `.env` file (not committed)
- **WebSocket**: Consider adding authentication tokens
- **Storage Bucket**: Configure appropriate access policies

## 📝 Recent Changes

### Supabase Storage Integration (Latest)

- Migrated from filesystem storage to Supabase Storage
- Audio chunks now stored in cloud bucket
- Database `data_path` field stores Storage URLs
- Improved scalability and reliability

**Migration Notes:**
- Backward compatible (existing file paths still work)
- Requires Supabase Storage bucket setup
- See Configuration section for setup instructions

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Uses [Asterisk ARI](https://docs.asterisk.org/Configuration/Interfaces/Asterisk-REST-Interface-ARI/)
- Storage powered by [Supabase](https://supabase.com/)

## 📞 Support

For issues and questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review documentation in `docs/` directory
3. Check service logs: `journalctl -u audio-bridge -f`

---

**Version:** 1.0.0  
**Last Updated:** January 2025
