# Deployment Instructions for Audio Bridge

## Prerequisites

- Server access (IP: 135.181.27.156)
- Supabase database credentials
- Asterisk ARI credentials
- Local machine with SSH access

## Option 1: Automated Deployment (Recommended)

### From Your Local Machine

1. **Make scripts executable:**
   ```bash
   chmod +x scripts/remote_deploy.sh
   chmod +x scripts/deploy.sh
   ```

2. **Run remote deployment:**
   ```bash
   ./scripts/remote_deploy.sh
   ```

   This will:
   - Upload all application files to the server
   - Run the deployment script on the server
   - Set up systemd service
   - Configure firewall

3. **SSH into server and configure:**
   ```bash
   ssh root@135.181.27.156
   # Password: sufugERFPFWkbUcsfn4J
   ```

4. **Edit .env file:**
   ```bash
   nano /opt/audio-bridge/.env
   ```
   
   Update these values:
   - `DATABASE_URL` - Your Supabase connection string (with URL-encoded password)
   - `ASTERISK_HOST` - Your Asterisk server IP/hostname
   - `ASTERISK_PASSWORD` - Your ARI password
   - `ASTERISK_WS_URL` - WebSocket URL (update host if not localhost)

5. **Test database connection:**
   ```bash
   cd /opt/audio-bridge
   sudo -u audio-bridge venv/bin/python test_supabase_connection.py
   ```

6. **Start the service:**
   ```bash
   systemctl start audio-bridge
   systemctl enable audio-bridge
   systemctl status audio-bridge
   ```

7. **Check logs:**
   ```bash
   journalctl -u audio-bridge -f
   ```

8. **Test the API:**
   ```bash
   curl http://localhost:8000/api/health
   ```

## Option 2: Manual Deployment

### Step 1: Connect to Server

```bash
ssh root@135.181.27.156
# Password: worldalt2121
```

### Step 2: Install System Dependencies

```bash
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl wget build-essential python3-dev libpq-dev
```

### Step 3: Upload Application

From your local machine:

```bash
# Using scp
scp -r . root@135.181.27.156:/opt/audio-bridge/

# Or using rsync (better, excludes unnecessary files)
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='.git' \
      --exclude='*.db' --exclude='*.pyc' \
      . root@135.181.27.156:/opt/audio-bridge/
```

### Step 4: Set Up Application on Server

```bash
# Create application directory
mkdir -p /opt/audio-bridge
cd /opt/audio-bridge

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
nano .env
# (Add your configuration - see .env template below)
```

### Step 5: Create Systemd Service

```bash
cat > /etc/systemd/system/audio-bridge.service << 'EOF'
[Unit]
Description=Audio Bridge FastAPI Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/audio-bridge
Environment="PATH=/opt/audio-bridge/venv/bin"
ExecStart=/opt/audio-bridge/venv/bin/python /opt/audio-bridge/run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=audio-bridge

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable audio-bridge
systemctl start audio-bridge
```

### Step 6: Configure Firewall

```bash
ufw allow 8000/tcp
ufw allow 22/tcp
ufw status
```

## Environment Variables (.env)

Create `/opt/audio-bridge/.env` with:

```env
# Application
DEBUG=False
ENVIRONMENT=production
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Database - Supabase (URL-encode special characters in password!)
DATABASE_URL=postgresql://postgres.yjwmkutjgffqamfaazcq:Newyork1%4024@aws-0-us-west-2.pooler.supabase.com:5432/postgres

# Asterisk ARI Configuration
ASTERISK_HOST=localhost  # Or your Asterisk server IP
ASTERISK_PORT=8088
ASTERISK_USERNAME=asterisk
ASTERISK_PASSWORD=your_ari_password_here
ASTERISK_WS_URL=ws://localhost:8088/ari/events?app=audio-bridge&subscribeAll=true
ASTERISK_APP_NAME=audio-bridge
ENABLE_WEBSOCKET_MONITOR=True
USE_POLLING_MONITOR=False

# CORS
CORS_ORIGINS=*

# Audio Processing
AUDIO_CHUNK_SIZE=4096
AUDIO_SAMPLE_RATE=8000
AUDIO_CHANNELS=1
AUDIO_FORMAT=PCM

# Storage
AUDIO_STORAGE_PATH=./audio_storage
```

**Important:** If your password contains special characters (like `@`, `:`, `#`), URL-encode them:
- `@` → `%40`
- `:` → `%3A`
- `#` → `%23`
- etc.

## Verification Steps

### 1. Check Service Status

```bash
systemctl status audio-bridge
```

Should show: `Active: active (running)`

### 2. Check Logs

```bash
# Follow logs in real-time
journalctl -u audio-bridge -f

# View last 50 lines
journalctl -u audio-bridge -n 50
```

### 3. Test API Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# List calls
curl http://localhost:8000/api/calls?limit=5
```

### 4. Test Database Connection

```bash
cd /opt/audio-bridge
source venv/bin/activate
python test_supabase_connection.py
```

### 5. Access Dashboard

Open in browser:
```
http://135.181.27.156:8000
```

### 6. Test WebSocket

The dashboard should automatically connect to the WebSocket endpoint.

## Troubleshooting

### Service Won't Start

```bash
# Check detailed error
journalctl -u audio-bridge -n 100 --no-pager

# Check if .env file exists
ls -la /opt/audio-bridge/.env

# Test Python script manually
cd /opt/audio-bridge
source venv/bin/activate
python run.py
```

### Database Connection Fails

1. Verify DATABASE_URL in .env
2. Check password is URL-encoded
3. Test connection:
   ```bash
   python test_supabase_connection.py
   ```
4. Check Supabase firewall allows your server IP

### Asterisk Connection Fails

1. Verify ARI is enabled on Asterisk
2. Test ARI connection:
   ```bash
   curl http://ASTERISK_HOST:8088/ari/asterisk/info -u asterisk:PASSWORD
   ```
3. Check ASTERISK_HOST in .env (use IP if not localhost)
4. Update ASTERISK_WS_URL with correct host

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process or change PORT in .env
```

### Permission Issues

```bash
# Fix ownership
chown -R root:root /opt/audio-bridge
chmod +x /opt/audio-bridge/run.py
```

## Service Management Commands

```bash
# Start service
systemctl start audio-bridge

# Stop service
systemctl stop audio-bridge

# Restart service
systemctl restart audio-bridge

# Check status
systemctl status audio-bridge

# View logs
journalctl -u audio-bridge -f

# Disable auto-start
systemctl disable audio-bridge

# Enable auto-start
systemctl enable audio-bridge
```

## Updating the Application

1. **Stop service:**
   ```bash
   systemctl stop audio-bridge
   ```

2. **Backup current version:**
   ```bash
   cp -r /opt/audio-bridge /opt/audio-bridge.backup
   ```

3. **Upload new code:**
   ```bash
   # From local machine
   rsync -avz --exclude='venv' --exclude='__pycache__' \
         . root@135.181.27.156:/opt/audio-bridge/
   ```

4. **Update dependencies (if needed):**
   ```bash
   cd /opt/audio-bridge
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Start service:**
   ```bash
   systemctl start audio-bridge
   ```

## Security Considerations

1. **Change default passwords** after first login
2. **Use SSH keys** instead of password authentication
3. **Restrict firewall** to only necessary ports
4. **Use non-root user** for running the service (deployment script creates `audio-bridge` user)
5. **Keep .env file secure** - don't commit to git
6. **Regular updates** - keep system and dependencies updated

## Monitoring

### Check Service Health

```bash
# Service status
systemctl is-active audio-bridge

# API health
curl http://localhost:8000/api/health

# Database connection
cd /opt/audio-bridge && python test_supabase_connection.py
```

### Log Monitoring

```bash
# Real-time logs
journalctl -u audio-bridge -f

# Error logs only
journalctl -u audio-bridge -p err

# Logs from today
journalctl -u audio-bridge --since today
```

## Next Steps After Deployment

1. ✅ Verify service is running
2. ✅ Test database connection
3. ✅ Test API endpoints
4. ✅ Configure Asterisk dialplan (if not already done)
5. ✅ Test call detection
6. ✅ Verify dashboard shows calls
7. ✅ Set up monitoring/alerting (optional)
8. ✅ Configure backup strategy (optional)

