# How to Configure Asterisk ARI - Step by Step Guide

## Important: You DON'T Configure ARI in the VICIdial Web Panel

The VICIdial admin panel you're looking at is for managing:
- Campaigns
- Users
- Lists
- Scripts
- etc.

**Asterisk ARI configuration is done at the Linux server level**, not through the web interface.

## What You Need

1. **SSH/Terminal access** to your VICIdial server
   - Server: `autodialer1.worldatlantus.com` (from your screenshot)
   - You need root or sudo access

2. **Access to the server's command line** (not the web panel)

## Step-by-Step Instructions

### Step 1: Connect to Your VICIdial Server via SSH

Open a terminal/command prompt on your computer and connect:

```bash
ssh root@autodialer1.worldatlantus.com
# OR
ssh your_username@autodialer1.worldatlantus.com
```

**If you don't have SSH access:**
- Contact your server administrator
- Or use a tool like PuTTY (Windows) or Terminal (Mac/Linux)

### Step 2: Navigate to Asterisk Configuration Directory

Once connected via SSH:

```bash
cd /etc/asterisk
ls -la
```

You should see files like:
- `ari.conf` (may or may not exist)
- `http.conf`
- `extensions.conf`
- etc.

### Step 3: Configure ARI (Choose One Method)

#### Method A: Use Our Setup Script (Easiest)

1. **Copy the setup script to your server:**

   On your local machine (where you have the project):
   ```bash
   cd /Users/pc/Documents/Sales-Prompt-App/marsons-projects/phase1-audio-bridge
   scp scripts/setup_asterisk_ari.sh root@autodialer1.worldatlantus.com:/tmp/
   ```

2. **On the server, run the script:**
   ```bash
   sudo bash /tmp/setup_asterisk_ari.sh
   ```

3. **Note the password** that gets generated!

#### Method B: Manual Configuration

1. **Create/Edit ARI configuration:**

   ```bash
   sudo nano /etc/asterisk/ari.conf
   ```

   Add this content:
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
   
   Save and exit (Ctrl+X, then Y, then Enter)

2. **Configure HTTP server:**

   ```bash
   sudo nano /etc/asterisk/http.conf
   ```

   Make sure it has:
   ```ini
   [general]
   enabled=yes
   bindaddr=0.0.0.0
   bindport=8088
   ```

   Save and exit

3. **Restart Asterisk:**

   ```bash
   sudo systemctl restart asterisk
   # OR if that doesn't work:
   sudo service asterisk restart
   ```

### Step 4: Verify ARI is Working

Test if ARI is accessible:

```bash
# Check if port 8088 is listening
sudo netstat -tlnp | grep 8088

# Test ARI endpoint (replace YOUR_PASSWORD)
curl -u asterisk:YOUR_PASSWORD http://localhost:8088/ari/asterisk/info
```

If you see JSON output, ARI is working!

### Step 5: Update Your .env File

Back on your local machine (where FastAPI runs):

1. **Copy the example file:**
   ```bash
   cd /Users/pc/Documents/Sales-Prompt-App/marsons-projects/phase1-audio-bridge
   cp .env.example .env
   ```

2. **Edit .env file:**
   ```bash
   nano .env
   # OR use any text editor
   ```

3. **Update these values:**
   ```env
   ASTERISK_HOST=autodialer1.worldatlantus.com
   ASTERISK_PORT=8088
   ASTERISK_USERNAME=asterisk
   ASTERISK_PASSWORD=YOUR_PASSWORD_FROM_STEP_3
   ASTERISK_WS_URL=ws://autodialer1.worldatlantus.com:8088/ari/events
   ```

### Step 6: Test Connection

On your local machine:

```bash
cd /Users/pc/Documents/Sales-Prompt-App/marsons-projects/phase1-audio-bridge
source venv/bin/activate
python scripts/test_ari_connection.py
```

## Common Questions

### Q: Do I need to do anything in the VICIdial web panel?
**A:** No! ARI configuration is separate from VICIdial web settings.

### Q: I don't have SSH access. What do I do?
**A:** Contact your server administrator or hosting provider to:
- Get SSH access
- Or ask them to configure ARI for you (give them the setup script)

### Q: How do I know if ARI is already configured?
**A:** Check if the file exists:
```bash
cat /etc/asterisk/ari.conf
```

### Q: What if port 8088 is already in use?
**A:** You can change the port in `http.conf` and update your `.env` file accordingly.

### Q: Do I need to restart VICIdial?
**A:** No, just restart Asterisk. VICIdial will continue working.

## Troubleshooting

### "Permission denied" error
- Make sure you're using `sudo` before commands
- Or login as root user

### "Connection refused" when testing
- Check firewall: `sudo ufw allow 8088/tcp`
- Verify Asterisk is running: `sudo systemctl status asterisk`
- Check if ARI is enabled: `sudo asterisk -rx "ari show config"`

### "Authentication failed"
- Double-check password matches in both `ari.conf` and `.env`
- Make sure username is "asterisk" (default)

## Summary

**What you're doing:**
1. SSH into server → Configure Asterisk files → Restart Asterisk
2. Update `.env` file on your local machine
3. Test connection

**What you're NOT doing:**
- Configuring anything in the VICIdial web admin panel
- Changing VICIdial settings
- Modifying campaigns or users

The VICIdial web panel is for managing your call center operations. Asterisk ARI is a separate server-level feature that enables our FastAPI app to monitor calls.

