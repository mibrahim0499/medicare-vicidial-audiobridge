#!/bin/bash
# Direct fix for adding Stasis routing to VICIdial outbound calls
# Run this on your VICIdial server

echo "=========================================="
echo "Adding Stasis Routing to VICIdial Dialplan"
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
BACKUP_FILE="$BACKUP_DIR/extensions.conf.backup.$(date +%Y%m%d_%H%M%S)"

if [ -f "/etc/asterisk/extensions.conf" ]; then
    cp /etc/asterisk/extensions.conf "$BACKUP_FILE"
    echo "✓ Backed up to: $BACKUP_FILE"
fi

echo ""
echo "Step 1: Checking current dialplan..."
echo "------------------------------------"

# Check extension 6000 (should work)
echo "Extension 6000 configuration:"
asterisk -rx "dialplan show 6000@default" 2>/dev/null | head -20
echo ""

# Check the actual extension that was called
echo "Checking dialplan for outbound pattern..."
asterisk -rx "dialplan show default" 2>/dev/null | grep -E "exten.*9|Dial.*denovo" | head -10
echo ""

echo "Step 2: Checking VICIdial dialplan generation..."
echo "------------------------------------------------"

# VICIdial typically uses AST_VDauto_dial.pl or similar
VICI_SCRIPTS="/usr/share/astguiclient"
if [ -d "$VICI_SCRIPTS" ]; then
    echo "VICIdial scripts directory found"
    echo "Looking for dialplan generation scripts..."
    find "$VICI_SCRIPTS" -name "*dial*.pl" -o -name "*exten*.pl" 2>/dev/null | head -5
    echo ""
fi

echo "Step 3: Creating Stasis routing macro..."
echo "----------------------------------------"

# Create a custom extensions file for Stasis routing
STASIS_EXTENSIONS="/etc/asterisk/extensions_audio_bridge.conf"

cat > "$STASIS_EXTENSIONS" << 'STASIS_EOF'
; Audio Bridge Stasis Routing Configuration
; This file provides Stasis routing for VICIdial calls

[macro-audio-bridge-stasis]
; Macro to route calls to Stasis application
; Usage: Macro(audio-bridge-stasis,${UNIQUEID},${CALL_ID})
exten => s,1,NoOp(Routing call ${ARG1} to Stasis audio-bridge)
exten => s,n,Stasis(audio-bridge,${ARG1},${ARG2})
exten => s,n,Return()

[audio-bridge-outbound]
; Context for outbound calls after they're answered
exten => s,1,NoOp(Outbound call answered - routing to Stasis)
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()

STASIS_EOF

chmod 644 "$STASIS_EXTENSIONS"
echo "✓ Created: $STASIS_EXTENSIONS"
echo ""

echo "Step 4: Instructions for VICIdial Integration..."
echo "-------------------------------------------------"
echo ""
echo "VICIdial generates dialplans dynamically. You need to modify the"
echo "dialplan generation to route calls to Stasis after Dial() completes."
echo ""
echo "METHOD 1: Modify Dial() command (Recommended)"
echo "---------------------------------------------"
echo "Find where VICIdial generates the Dial() command for outbound calls."
echo "Change from:"
echo "  Dial(SIP/denovo/\${EXTEN:1},,tToR)"
echo ""
echo "To:"
echo "  Dial(SIP/denovo/\${EXTEN:1},,tToR(b(audio-bridge-outbound^s^1)))"
echo ""
echo "This will route to audio-bridge-outbound context when call is answered."
echo ""
echo "METHOD 2: Add priority after Dial()"
echo "------------------------------------"
echo "After the Dial() line, add:"
echo "  exten => <pattern>,n,Goto(audio-bridge-outbound,s,1)"
echo ""
echo "METHOD 3: Use GoSub (if Dial() doesn't support 'b' option)"
echo "----------------------------------------------------------"
echo "  exten => <pattern>,n,Dial(SIP/denovo/\${EXTEN:1},,tToR)"
echo "  exten => <pattern>,n,GoSub(audio-bridge-outbound,s,1)"
echo ""
echo "Step 5: Include the new extensions file..."
echo "------------------------------------------"

# Check if extensions.conf includes other files
if [ -f "/etc/asterisk/extensions.conf" ]; then
    if ! grep -q "extensions_audio_bridge.conf" /etc/asterisk/extensions.conf; then
        echo "" >> /etc/asterisk/extensions.conf
        echo "; Audio Bridge Stasis Routing" >> /etc/asterisk/extensions.conf
        echo "#include \"extensions_audio_bridge.conf\"" >> /etc/asterisk/extensions.conf
        echo "✓ Added include to extensions.conf"
    else
        echo "✓ Already included in extensions.conf"
    fi
else
    echo "⚠ extensions.conf not found - you may need to create it or include manually"
fi

echo ""
echo "Step 6: Finding VICIdial dialplan generation location..."
echo "--------------------------------------------------------"

# Common VICIdial dialplan generation locations
echo "Checking common VICIdial dialplan files:"
for file in \
    "/usr/share/astguiclient/AST_VDauto_dial.pl" \
    "/usr/share/astguiclient/AST_VDadapt.pl" \
    "/etc/asterisk/extensions.conf" \
    "/etc/asterisk/extensions_vicidial.conf"; do
    if [ -f "$file" ]; then
        echo "  Found: $file"
        # Check if it contains Dial commands
        if grep -q "Dial.*denovo\|Dial.*SIP" "$file" 2>/dev/null; then
            echo "    → Contains Dial() commands - may need modification"
            echo "    → Check line: $(grep -n "Dial.*denovo\|Dial.*SIP" "$file" | head -1)"
        fi
    fi
done

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Find where VICIdial generates the Dial() command"
echo "2. Modify it to route to Stasis after answer (see methods above)"
echo "3. Reload dialplan: asterisk -rx 'dialplan reload'"
echo "4. Test with a call and check for 'StasisStart' in logs"
echo ""
echo "To check if Stasis routing is working:"
echo "  asterisk -rx 'dialplan show audio-bridge-outbound'"
echo ""
echo "To test, make a call and check bridge logs for:"
echo "  'Call started: <call_id>'"
echo "  'Started recording for call <call_id>'"
echo ""

