# Asterisk Connection Setup Guide

## Current Status

**Audio Bridge Server**: 135.181.27.156 ✅ Running
**Asterisk Server**: ❓ Unknown (needs to be configured)

## Issue

The Audio Bridge app is trying to connect to `localhost:8088` but Asterisk is not on this server. Asterisk is likely on your VICIdial server (different IP address).

## Solution: Configure Asterisk Server IP

### Step 1: Find Your Asterisk/VICIdial Server IP

Your Asterisk server is likely on a different machine. You need to know:
- The IP address of your VICIdial/Asterisk server
- The ARI password configured on that server

### Step 2: Update .env File on Audio Bridge Server

SSH to the audio-bridge server:

```bash
ssh root@135.181.27.156
# Password: worldalt2121

nano /opt/audio-bridge/.env
```

Update these lines:

```env
# Change from localhost to your Asterisk server IP
ASTERISK_HOST=YOUR_ASTERISK_SERVER_IP
ASTERISK_PORT=8088
ASTERISK_USERNAME=asterisk
ASTERISK_PASSWORD=YOUR_ACTUAL_ARI_PASSWORD  # Replace placeholder

# Update WebSocket URL with correct IP
ASTERISK_WS_URL=ws://YOUR_ASTERISK_SERVER_IP:8088/ari/events?app=audio-bridge&subscribeAll=true
```

**Example:**
```env
ASTERISK_HOST=192.168.1.100
ASTERISK_PASSWORD=MySecurePassword123
ASTERISK_WS_URL=ws://192.168.1.100:8088/ari/events?app=audio-bridge&subscribeAll=true
```

### Step 3: Restart Audio Bridge Service

```bash
systemctl restart audio-bridge
systemctl status audio-bridge
```

### Step 4: Verify Connection

Check the logs:

```bash
journalctl -u audio-bridge -f
```

You should see:
- ✅ "Connected to Asterisk WebSocket" (success)
- ❌ "Connection refused" (still wrong IP/password)

### Step 5: Test ARI Connection

From the audio-bridge server, test the connection:

```bash
# Test if ARI is accessible
curl -u asterisk:YOUR_PASSWORD http://YOUR_ASTERISK_IP:8088/ari/asterisk/info
```

If this works, the Audio Bridge app should be able to connect.

## Setting Up ARI on Asterisk Server (If Not Done)

If ARI is not configured on your Asterisk server, you need to:

### On Your Asterisk/VICIdial Server:

1. **Create ARI configuration:**

```bash
nano /etc/asterisk/ari.conf
```

Add:
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

2. **Configure HTTP server:**

```bash
nano /etc/asterisk/http.conf
```

Add:
```ini
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
```

3. **Restart Asterisk:**

```bash
systemctl restart asterisk
```

4. **Open firewall (if needed):**

```bash
ufw allow 8088/tcp
```

5. **Test ARI:**

```bash
curl -u asterisk:YOUR_PASSWORD http://localhost:8088/ari/asterisk/info
```

## Troubleshooting

### Connection Refused

- Check Asterisk server IP is correct
- Verify port 8088 is open on Asterisk server firewall
- Check ARI is enabled on Asterisk server
- Verify ARI password matches

### Authentication Failed

- Check ARI password in `/etc/asterisk/ari.conf` on Asterisk server
- Verify password in `.env` matches exactly
- Check username is `asterisk`

### WebSocket Connection Fails

- Verify `ASTERISK_WS_URL` has correct IP
- Check firewall allows WebSocket connections
- Verify Asterisk HTTP server is bound to `0.0.0.0` (not just localhost)

## Quick Checklist

- [ ] Know your Asterisk server IP address
- [ ] Know your ARI password
- [ ] Updated `.env` with correct `ASTERISK_HOST`
- [ ] Updated `.env` with correct `ASTERISK_PASSWORD`
- [ ] Updated `.env` with correct `ASTERISK_WS_URL`
- [ ] Restarted audio-bridge service
- [ ] Verified connection in logs
- [ ] Tested ARI endpoint manually

## Next Steps After Configuration

Once connected, the Audio Bridge will:
- Monitor Asterisk events in real-time
- Detect when calls start/end
- Stream audio from active calls
- Display calls on the dashboard

