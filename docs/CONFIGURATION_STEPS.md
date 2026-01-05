# Configuration Steps for Phase 1

## Step 1: Configure Asterisk ARI on VICIdial Server

You need to configure Asterisk REST Interface (ARI) on your VICIdial server to enable real-time call monitoring and audio streaming.

### Option A: Using the Setup Script (Recommended)

**On your VICIdial server**, run:

```bash
# Copy the script to your VICIdial server
# Then run:
sudo bash setup_asterisk_ari.sh
```

This script will:
- Create `/etc/asterisk/ari.conf` with ARI configuration
- Configure `/etc/asterisk/http.conf` for HTTP server
- Generate a secure password
- Restart Asterisk

**Important:** Note the generated password from the script output!

### Option B: Manual Configuration

**On your VICIdial server**, edit these files:

#### 1. Create/Edit `/etc/asterisk/ari.conf`:

```ini
[general]
enabled = yes
pretty = yes
allowed_origins = *

[asterisk]
type = user
read_only = no
password = YOUR_SECURE_PASSWORD_HERE
```

**Replace `YOUR_SECURE_PASSWORD_HERE` with a strong password!**

#### 2. Create/Edit `/etc/asterisk/http.conf`:

```ini
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
```

#### 3. Restart Asterisk:

```bash
sudo systemctl restart asterisk
```

#### 4. Verify ARI is running:

```bash
# Check if HTTP server is listening
sudo netstat -tlnp | grep 8088

# Or test the ARI endpoint
curl -u asterisk:YOUR_PASSWORD http://localhost:8088/ari/asterisk/info
```

## Step 2: Configure .env File

**On your development machine** (where FastAPI app runs):

1. Copy the example file:
   ```bash
   cd phase1-audio-bridge
   cp .env.example .env
   ```

2. Edit `.env` with your VICIdial server details:

   ```env
   # Asterisk ARI Configuration
   ASTERISK_HOST=your_vicidial_server_ip_or_hostname
   ASTERISK_PORT=8088
   ASTERISK_USERNAME=asterisk
   ASTERISK_PASSWORD=YOUR_SECURE_PASSWORD_FROM_STEP_1
   ASTERISK_WS_URL=ws://your_vicidial_server_ip:8088/ari/events
   ```

   **Replace:**
   - `your_vicidial_server_ip_or_hostname` with your actual VICIdial server IP or hostname
   - `YOUR_SECURE_PASSWORD_FROM_STEP_1` with the password you set in Step 1

## Step 3: Test the Connection

Test if your FastAPI app can connect to Asterisk ARI:

```bash
cd phase1-audio-bridge
source venv/bin/activate
python scripts/test_ari_connection.py
```

**Expected output:**
```
Testing Asterisk ARI Connection...
Host: your_server:8088
Username: asterisk
--------------------------------------------------
1. Connecting to ARI...
   ✓ Connected successfully
2. Getting active channels...
   ✓ Found X active channels
--------------------------------------------------
ARI connection test completed successfully!
```

If you see errors, check:
- Firewall settings (port 8088 must be accessible)
- ARI password matches in both `ari.conf` and `.env`
- Asterisk is running: `sudo systemctl status asterisk`
- Network connectivity between your dev machine and VICIdial server

## Step 4: Start the FastAPI Application

Once the connection test passes:

```bash
cd phase1-audio-bridge
source venv/bin/activate
python run.py
```

Or:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Step 5: Access the Dashboard

Open your browser:
```
http://localhost:8000
```

Or directly:
```
http://localhost:8000/static/index.html
```

## Step 6: Test with a Real Call

1. Make a test call through VICIdial
2. In the dashboard, enter the Call ID
3. Click "Connect" to stream audio
4. Verify audio chunks are being received

## Troubleshooting

### Connection Refused
- Check firewall: `sudo ufw allow 8088/tcp`
- Verify Asterisk is running: `sudo systemctl status asterisk`
- Check ARI is enabled: `sudo asterisk -rx "ari show config"`

### Authentication Failed
- Verify password matches in both `ari.conf` and `.env`
- Check username is "asterisk" (default)
- Restart Asterisk after changing password

### No Channels Found
- Make sure there's an active call
- Check VICIdial is making calls successfully
- Verify SIP trunk is configured

### WebSocket Connection Issues
- Check `ASTERISK_WS_URL` in `.env` uses correct IP/hostname
- Verify port 8088 is accessible
- Check browser console for errors

## Next Steps After Configuration

Once everything is configured and tested:
1. ✅ Verify audio streaming works end-to-end
2. ✅ Test with multiple concurrent calls
3. ✅ Monitor dashboard for real-time metrics
4. ✅ Review call logs in database
5. ✅ Proceed to Phase 2 (AI Processing Layer)

