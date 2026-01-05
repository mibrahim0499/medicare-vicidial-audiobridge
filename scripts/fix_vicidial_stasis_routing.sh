#!/bin/bash
# Script to add Stasis routing to VICIdial outbound calls
# This modifies the dialplan to route calls to Stasis after they're answered

echo "=========================================="
echo "Fixing VICIdial Dialplan for Stasis Routing"
echo "=========================================="
echo ""

# Backup original extensions.conf
BACKUP_FILE="/etc/asterisk/extensions.conf.backup.$(date +%Y%m%d_%H%M%S)"
if [ -f "/etc/asterisk/extensions.conf" ]; then
    cp /etc/asterisk/extensions.conf "$BACKUP_FILE"
    echo "✓ Backed up extensions.conf to: $BACKUP_FILE"
else
    echo "⚠ extensions.conf not found, will create new one"
fi

echo ""
echo "Step 1: Checking current dialplan..."
echo "------------------------------------"

# Check extension 6000 to see how it's configured
echo "Extension 6000 (test extension):"
asterisk -rx "dialplan show 6000@default" 2>/dev/null | head -15
echo ""

# Check if there's a custom extensions file for VICIdial
VICI_EXTENSIONS="/etc/asterisk/extensions_vicidial.conf"
if [ -f "$VICI_EXTENSIONS" ]; then
    echo "Found VICIdial extensions file: $VICI_EXTENSIONS"
    echo "Checking for outbound call patterns..."
    grep -E "exten.*_9\.|exten.*9X|Dial.*denovo" "$VICI_EXTENSIONS" | head -10
    echo ""
fi

echo "Step 2: Creating dialplan modification..."
echo "----------------------------------------"

# Create a custom extensions file that will be included
CUSTOM_EXTENSIONS="/etc/asterisk/extensions_audio_bridge.conf"

cat > "$CUSTOM_EXTENSIONS" << 'EOF'
; Audio Bridge Stasis Routing
; This file adds Stasis routing for outbound calls
; Include this in extensions.conf with: #include "extensions_audio_bridge.conf"

[audio-bridge-outbound]
; Route outbound calls to Stasis after they're answered
; This context should be called from the main dialplan after Dial() completes

exten => s,1,NoOp(Outbound call answered, routing to Stasis)
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()

[audio-bridge-inbound]
; For inbound calls if needed
exten => s,1,NoOp(Inbound call, routing to Stasis)
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()

EOF

echo "✓ Created custom extensions file: $CUSTOM_EXTENSIONS"
echo ""

echo "Step 3: Instructions for VICIdial integration..."
echo "------------------------------------------------"
echo ""
echo "VICIdial uses dynamically generated dialplans. To add Stasis routing:"
echo ""
echo "OPTION A: Modify VICIdial's dialplan generation script"
echo "  1. Find the script that generates outbound dialplan (usually in /usr/share/astguiclient/)"
echo "  2. Add Stasis routing after the Dial() command"
echo ""
echo "OPTION B: Use Asterisk dialplan priority continuation"
echo "  1. Modify the outbound extension to continue to audio-bridge-outbound context"
echo "  2. After Dial() completes, route to: Goto(audio-bridge-outbound,s,1)"
echo ""
echo "OPTION C: Use Dial() application options"
echo "  1. Modify Dial() to use 'b' option to execute macro/GoSub on answer"
echo "  2. Create a macro that routes to Stasis"
echo ""
echo "The recommended approach is to modify VICIdial's dialplan generation"
echo "to add this line after Dial() completes:"
echo "  exten => <pattern>,n,Goto(audio-bridge-outbound,s,1)"
echo ""
echo "OR use Dial() with 'b' option:"
echo "  Dial(SIP/denovo/\${EXTEN:1},,tToR(b(audio-bridge-stasis^s^1)))"
echo ""
echo "And create a macro:"
echo "  [macro-audio-bridge-stasis]"
echo "  exten => s,1,Stasis(audio-bridge,\${ARG1},\${ARG2})"
echo ""

echo "Step 4: Testing..."
echo "-----------------"
echo ""
echo "After making changes:"
echo "  1. Reload dialplan: asterisk -rx 'dialplan reload'"
echo "  2. Test with extension 6000 first"
echo "  3. Then test with outbound call"
echo "  4. Check bridge logs for 'StasisStart' events"
echo ""

