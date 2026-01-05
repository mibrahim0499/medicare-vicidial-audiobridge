#!/bin/bash
# Simple fix: Add Stasis routing to VICIdial outbound calls
# Run this on your VICIdial server as root

set -e

VICI_DIALPLAN="/etc/asterisk/extensions-vicidial.conf"
STASIS_EXTENSIONS="/etc/asterisk/extensions_audio_bridge.conf"
MAIN_EXTENSIONS="/etc/asterisk/extensions.conf"

echo "=========================================="
echo "Adding Stasis Routing to VICIdial"
echo "=========================================="
echo ""

# Backup
BACKUP_DIR="/root/asterisk_backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/extensions-vicidial.conf.backup.$(date +%Y%m%d_%H%M%S)"
cp "$VICI_DIALPLAN" "$BACKUP_FILE"
echo "✓ Backed up to: $BACKUP_FILE"
echo ""

# Step 1: Create Stasis routing context
echo "Step 1: Creating Stasis routing context..."
cat > "$STASIS_EXTENSIONS" << 'EOF'
; Audio Bridge Stasis Routing
[audio-bridge-outbound]
exten => s,1,NoOp(Routing to Stasis: ${UNIQUEID})
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()
EOF
chmod 644 "$STASIS_EXTENSIONS"
echo "✓ Created $STASIS_EXTENSIONS"
echo ""

# Step 2: Include in main extensions.conf
echo "Step 2: Including in extensions.conf..."
if [ -f "$MAIN_EXTENSIONS" ]; then
    if ! grep -q "extensions_audio_bridge.conf" "$MAIN_EXTENSIONS"; then
        echo "" >> "$MAIN_EXTENSIONS"
        echo "; Audio Bridge Stasis Routing" >> "$MAIN_EXTENSIONS"
        echo "#include \"extensions_audio_bridge.conf\"" >> "$MAIN_EXTENSIONS"
        echo "✓ Added include"
    else
        echo "✓ Already included"
    fi
fi
echo ""

# Step 3: Modify the dialplan
echo "Step 3: Modifying dialplan..."
# Find the line with Dial() for _9X. pattern
# Current: line 171 has Dial(), line 172 has Hangup()
# We need to insert Stasis routing between them

# Use sed to insert after Dial line, before Hangup
sed -i.bak '/Dial(SIP\/denovo\/${EXTEN:1},,tToR)/a\                    3. Goto(audio-bridge-outbound,s,1)     [Added for Stasis routing]' "$VICI_DIALPLAN"

echo "✓ Modified dialplan"
echo ""

# Step 4: Show the changes
echo "Step 4: Verifying changes..."
echo "Modified section (lines 170-175):"
sed -n '170,175p' "$VICI_DIALPLAN"
echo ""

# Step 5: Reload
echo "Step 5: Reloading dialplan..."
asterisk -rx "dialplan reload" 2>/dev/null
echo "✓ Reloaded"
echo ""

# Step 6: Verify
echo "Step 6: Verifying..."
echo "Stasis context:"
asterisk -rx "dialplan show audio-bridge-outbound" 2>/dev/null | head -5
echo ""
echo "Outbound pattern:"
asterisk -rx "dialplan show _9X.@vicidial-auto-external" 2>/dev/null | head -8
echo ""

echo "=========================================="
echo "✓ Fix Applied Successfully!"
echo "=========================================="
echo ""
echo "Next: Make a test call and check bridge logs for 'Call started'"
echo ""

