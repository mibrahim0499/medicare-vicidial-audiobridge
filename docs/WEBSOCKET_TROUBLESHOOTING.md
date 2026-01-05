# WebSocket Connection Troubleshooting Guide

## Problem: Connection Refused on Port 8088

If you're seeing "Connection refused" errors when trying to connect to the Asterisk WebSocket, this guide will help you fix it.

## Root Cause

Port 8088 is not accessible from your local machine. This can be due to:
1. **Firewall blocking port 8088** on the VICIdial server
2. **Asterisk HTTP server not bound to 0.0.0.0** (only listening on localhost)
3. **Network security groups** (if using cloud hosting)
4. **Router/NAT configuration** (if server is behind a router)

## Solution Steps

### Step 1: Run the Fix Script on VICIdial Server

**On your VICIdial server** (via SSH):

```bash
# Copy the script to your server
scp scripts/fix_websocket_access.sh root@autodialer1.worldatlantus.com:/tmp/

# Then run it
sudo bash /tmp/fix_websocket_access.sh
```

This script will:
- ✅ Verify Asterisk HTTP configuration
- ✅ Ensure bindaddr is 0.0.0.0 (not just localhost)
- ✅ Configure firewall rules
- ✅ Restart Asterisk
- ✅ Test the connection

### Step 2: Verify Configuration

**On the server**, check these files:

#### Check `/etc/asterisk/http.conf`:
```bash
sudo cat /etc/asterisk/http.conf | grep -E "enabled|bindaddr|bindport"
```

Should show:
```
enabled=yes
bindaddr=0.0.0.0
bindport=8088
```

#### Check `/etc/asterisk/ari.conf`:
```bash
sudo cat /etc/asterisk/ari.conf | grep -E "enabled|password"
```

Should show:
```
enabled = yes
password = YOUR_PASSWORD
```

### Step 3: Check Firewall

**On the server**, verify port 8088 is open:

```bash
# Check if port is listening
sudo netstat -tlnp | grep 8088
# OR
sudo ss -tlnp | grep 8088

# Check firewall (UFW)
sudo ufw status | grep 8088

# Check firewall (firewalld)
sudo firewall-cmd --list-ports | grep 8088
```

### Step 4: Test from Server

**On the server**, test locally:

```bash
# Test HTTP endpoint
curl -u asterisk:YOUR_PASSWORD http://localhost:8088/ari/asterisk/info

# Test WebSocket (if you have wscat installed)
wscat -c ws://localhost:8088/ari/events -a asterisk:YOUR_PASSWORD
```

### Step 5: Test from Your Local Machine

**On your local machine**:

```bash
# Test HTTP endpoint
curl -u asterisk:YOUR_PASSWORD http://autodialer1.worldatlantus.com:8088/ari/asterisk/info

# If this fails, port 8088 is not accessible from outside
```

## Alternative Solutions

### Option 1: Use Polling Monitor (No WebSocket Required)

If WebSocket access cannot be configured, you can use the polling-based monitor instead:

**Update your `.env` file:**

```env
USE_POLLING_MONITOR=true
ENABLE_WEBSOCKET_MONITOR=false
```

This will use HTTP polling instead of WebSocket, which only requires HTTP access (port 8088).

### Option 2: SSH Tunnel (Temporary Solution)

Create an SSH tunnel to forward port 8088:

```bash
ssh -L 8088:localhost:8088 root@autodialer1.worldatlantus.com
```

Then update `.env`:
```env
ASTERISK_HOST=localhost
ASTERISK_PORT=8088
ASTERISK_WS_URL=ws://localhost:8088/ari/events
```

### Option 3: VPN or Network Configuration

If you have VPN access or can configure network security groups:
- Add your local machine's IP to allowed sources
- Configure port forwarding if behind NAT
- Update cloud security group rules

## Verification

After fixing, restart your FastAPI application:

```bash
cd /Users/pc/Documents/Sales-Prompt-App/marsons-projects/phase1-audio-bridge
source venv/bin/activate
python run.py
```

You should see:
```
✅ Connected to Asterisk event WebSocket
```

Instead of:
```
⚠️  Cannot connect to Asterisk WebSocket (connection refused)
```

## Still Having Issues?

1. **Check Asterisk logs:**
   ```bash
   sudo tail -f /var/log/asterisk/full | grep -i ari
   ```

2. **Verify network connectivity:**
   ```bash
   ping autodialer1.worldatlantus.com
   telnet autodialer1.worldatlantus.com 8088
   ```

3. **Check if Asterisk is running:**
   ```bash
   sudo systemctl status asterisk
   ```

4. **Review firewall logs:**
   ```bash
   sudo tail -f /var/log/ufw.log  # For UFW
   sudo journalctl -u firewalld   # For firewalld
   ```

## Summary

The WebSocket connection requires:
- ✅ Asterisk HTTP server enabled and bound to 0.0.0.0
- ✅ Port 8088 open in firewall
- ✅ Network access from your machine to the server
- ✅ Correct ARI credentials

If WebSocket cannot be configured, use the polling monitor as an alternative.

