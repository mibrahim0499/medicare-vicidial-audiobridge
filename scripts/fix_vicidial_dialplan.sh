#!/bin/bash
# Fix VICIdial dialplan to route calls to Stasis
# Run this on your VICIdial server

echo "=========================================="
echo "Fixing VICIdial Dialplan for Stasis Routing"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root or with sudo"
    exit 1
fi

# Backup
BACKUP_DIR="/root/asterisk_backups"
mkdir -p "$BACKUP_DIR"
VICI_DIALPLAN="/etc/asterisk/extensions-vicidial.conf"
BACKUP_FILE="$BACKUP_DIR/extensions-vicidial.conf.backup.$(date +%Y%m%d_%H%M%S)"

if [ -f "$VICI_DIALPLAN" ]; then
    cp "$VICI_DIALPLAN" "$BACKUP_FILE"
    echo "✓ Backed up to: $BACKUP_FILE"
else
    echo "⚠ $VICI_DIALPLAN not found!"
    exit 1
fi

echo ""
echo "Step 1: Checking extension 6000 (working example)..."
echo "---------------------------------------------------"
asterisk -rx "dialplan show 6000@default" 2>/dev/null | head -15
echo ""

echo "Step 2: Creating Stasis routing context..."
echo "------------------------------------------"

# Create the Stasis routing context
STASIS_EXTENSIONS="/etc/asterisk/extensions_audio_bridge.conf"

cat > "$STASIS_EXTENSIONS" << 'EOF'
; Audio Bridge Stasis Routing Configuration
; This context routes calls to Stasis application

[audio-bridge-outbound]
; Route outbound calls to Stasis when answered
exten => s,1,NoOp(Routing call ${UNIQUEID} to Stasis audio-bridge)
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()

EOF

chmod 644 "$STASIS_EXTENSIONS"
echo "✓ Created: $STASIS_EXTENSIONS"
echo ""

echo "Step 3: Including Stasis extensions in main config..."
echo "-----------------------------------------------------"

# Check if extensions.conf includes it
MAIN_EXTENSIONS="/etc/asterisk/extensions.conf"
if [ -f "$MAIN_EXTENSIONS" ]; then
    if ! grep -q "extensions_audio_bridge.conf" "$MAIN_EXTENSIONS"; then
        echo "" >> "$MAIN_EXTENSIONS"
        echo "; Audio Bridge Stasis Routing" >> "$MAIN_EXTENSIONS"
        echo "#include \"extensions_audio_bridge.conf\"" >> "$MAIN_EXTENSIONS"
        echo "✓ Added include to extensions.conf"
    else
        echo "✓ Already included in extensions.conf"
    fi
else
    echo "⚠ extensions.conf not found - you may need to include manually"
fi

echo ""
echo "Step 4: Modifying VICIdial dialplan..."
echo "--------------------------------------"

# Check current dialplan around line 170-172
echo "Current dialplan (lines 168-175):"
sed -n '168,175p' "$VICI_DIALPLAN"
echo ""

# Check if Stasis routing is already added
if grep -q "audio-bridge-outbound\|Stasis.*audio-bridge" "$VICI_DIALPLAN"; then
    echo "⚠ Stasis routing already appears to be in dialplan"
    echo "Current relevant lines:"
    grep -n "audio-bridge\|Stasis" "$VICI_DIALPLAN" | head -5
    echo ""
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Find the Dial line and add Stasis routing after it
# We need to add a priority between Dial() and Hangup()

# Method: Add a new priority after Dial() that routes to Stasis
# The pattern is: _9X. at line 170-172

# Check the exact format
DIAL_LINE=$(grep -n "Dial(SIP/denovo" "$VICI_DIALPLAN" | head -1)
if [ -z "$DIAL_LINE" ]; then
    echo "⚠ Could not find Dial() line in $VICI_DIALPLAN"
    echo "Please check the file manually"
    exit 1
fi

echo "Found Dial() line: $DIAL_LINE"
echo ""

# Get line numbers
DIAL_LINE_NUM=$(echo "$DIAL_LINE" | cut -d: -f1)
HANGUP_LINE_NUM=$((DIAL_LINE_NUM + 1))

echo "Dial() is at line $DIAL_LINE_NUM"
echo "Hangup() is at line $HANGUP_LINE_NUM"
echo ""

# Create a temporary file with the modification
TMP_FILE=$(mktemp)

# Copy everything up to Dial line
sed -n "1,${DIAL_LINE_NUM}p" "$VICI_DIALPLAN" > "$TMP_FILE"

# Add Stasis routing after Dial (before Hangup)
echo "                    3. Goto(audio-bridge-outbound,s,1)     [Added for Stasis routing]" >> "$TMP_FILE"

# Copy Hangup line and everything after
sed -n "${HANGUP_LINE_NUM},\$p" "$VICI_DIALPLAN" >> "$TMP_FILE"

# Backup and replace
cp "$VICI_DIALPLAN" "${VICI_DIALPLAN}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$TMP_FILE" "$VICI_DIALPLAN"
rm "$TMP_FILE"

echo "✓ Modified dialplan to route to Stasis after Dial()"
echo ""

echo "Step 5: Verifying changes..."
echo "----------------------------"
echo "Modified dialplan (lines 168-175):"
sed -n '168,175p' "$VICI_DIALPLAN"
echo ""

echo "Step 6: Reloading dialplan..."
echo "-----------------------------"
asterisk -rx "dialplan reload" 2>/dev/null
echo "✓ Dialplan reloaded"
echo ""

echo "Step 7: Verifying Stasis context exists..."
echo "-----------------------------------------"
asterisk -rx "dialplan show audio-bridge-outbound" 2>/dev/null
echo ""

echo "Step 8: Checking updated outbound dialplan..."
echo "--------------------------------------------"
asterisk -rx "dialplan show _9X.@vicidial-auto-external" 2>/dev/null | head -10
echo ""

echo "=========================================="
echo "Fix Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Make a test call to an American number"
echo "2. Check your bridge logs for:"
echo "   - 'Call started: <call_id>'"
echo "   - 'Started recording for call <call_id>'"
echo "3. Check the dashboard at http://localhost:8000"
echo ""
echo "If it doesn't work, check:"
echo "  - Bridge logs for errors"
echo "  - Asterisk logs: tail -f /var/log/asterisk/full | grep -i stasis"
echo "  - Verify dialplan: asterisk -rx 'dialplan show _9X.@vicidial-auto-external'"
echo ""

