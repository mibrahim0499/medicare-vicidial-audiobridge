# How to Run the Fix Script

## Step-by-Step Instructions

### Option 1: Copy Script to Server and Run (Recommended)

**On your local machine:**

1. Copy the script to your VICIdial server:
```bash
scp scripts/apply_stasis_fix.sh root@autodialer1.worldatlantus.com:/tmp/
```

2. **SSH to your VICIdial server:**
```bash
ssh root@autodialer1.worldatlantus.com
```

3. **Make the script executable:**
```bash
chmod +x /tmp/apply_stasis_fix.sh
```

4. **Run the script:**
```bash
/tmp/apply_stasis_fix.sh
```

### Option 2: Create Script Directly on Server

**SSH to your server first:**
```bash
ssh root@autodialer1.worldatlantus.com
```

Then create the script file:
```bash
nano /tmp/apply_stasis_fix.sh
```

Copy and paste the script content, then:
- Press `Ctrl+X` to exit
- Press `Y` to save
- Press `Enter` to confirm

Make it executable and run:
```bash
chmod +x /tmp/apply_stasis_fix.sh
/tmp/apply_stasis_fix.sh
```

### Option 3: Run Commands Manually (If Script Fails)

If the script doesn't work, you can run the commands manually:

```bash
# 1. Backup
cp /etc/asterisk/extensions-vicidial.conf /root/extensions-vicidial.conf.backup

# 2. Create Stasis routing file
cat > /etc/asterisk/extensions_audio_bridge.conf << 'EOF'
; Audio Bridge Stasis Routing
[audio-bridge-outbound]
exten => s,1,NoOp(Routing to Stasis: ${UNIQUEID})
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()
EOF

# 3. Include in main extensions.conf
echo "" >> /etc/asterisk/extensions.conf
echo "; Audio Bridge Stasis Routing" >> /etc/asterisk/extensions.conf
echo "#include \"extensions_audio_bridge.conf\"" >> /etc/asterisk/extensions.conf

# 4. Edit the dialplan file
nano /etc/asterisk/extensions-vicidial.conf
# Find line 171 (Dial line) and add this line AFTER it (before Hangup):
#                     3. Goto(audio-bridge-outbound,s,1)     [Added for Stasis routing]

# 5. Reload dialplan
asterisk -rx "dialplan reload"
```

## Quick Copy-Paste Commands

**Run these commands one by one on your VICIdial server:**

```bash
# 1. Create the Stasis routing context
cat > /etc/asterisk/extensions_audio_bridge.conf << 'EOF'
; Audio Bridge Stasis Routing
[audio-bridge-outbound]
exten => s,1,NoOp(Routing to Stasis: ${UNIQUEID})
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()
EOF

# 2. Include it in main extensions.conf
echo "" >> /etc/asterisk/extensions.conf
echo "; Audio Bridge Stasis Routing" >> /etc/asterisk/extensions.conf
echo "#include \"extensions_audio_bridge.conf\"" >> /etc/asterisk/extensions.conf

# 3. Backup the dialplan
cp /etc/asterisk/extensions-vicidial.conf /root/extensions-vicidial.conf.backup

# 4. Edit the dialplan (you'll need to do this manually)
nano /etc/asterisk/extensions-vicidial.conf
# In nano: Go to line 171, add this line AFTER the Dial() line:
#                     3. Goto(audio-bridge-outbound,s,1)     [Added for Stasis routing]
# Save: Ctrl+X, then Y, then Enter

# 5. Reload dialplan
asterisk -rx "dialplan reload"

# 6. Verify it worked
asterisk -rx "dialplan show _9X.@vicidial-auto-external"
```

## Troubleshooting

**If you get "Permission denied":**
- Make sure you're running as root: `sudo su -` or `ssh root@...`

**If the script doesn't exist:**
- Check the path: `ls -la /tmp/apply_stasis_fix.sh`
- Or create it manually using Option 2 above

**If you get errors:**
- Check the file exists: `ls -la /etc/asterisk/extensions-vicidial.conf`
- Check permissions: `ls -la /etc/asterisk/`

