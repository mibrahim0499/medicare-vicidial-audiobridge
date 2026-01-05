#!/bin/bash
# Fix missing Dial() and Hangup() in extensions-vicidial.conf
# Run this on the autodialer server as root

set -e

VICI_DIALPLAN="/etc/asterisk/extensions-vicidial.conf"
AUDIO_BRIDGE_EXT="/etc/asterisk/extensions_audio_bridge.conf"

echo "=========================================="
echo "Fixing Missing Dial() in VICIdial Dialplan"
echo "=========================================="
echo ""

# Backup
BACKUP_FILE="/etc/asterisk/extensions-vicidial.conf.backup.$(date +%Y%m%d_%H%M%S)"
cp "$VICI_DIALPLAN" "$BACKUP_FILE"
echo "✓ Backed up to: $BACKUP_FILE"
echo ""

# Check current state
echo "=== Current lines 168-173 ==="
sed -n '168,173p' "$VICI_DIALPLAN"
echo ""

# Check if Dial line already exists
if grep -q "Dial(SIP/\${EXTEN:1}@galax" "$VICI_DIALPLAN"; then
    echo "⚠ Dial() line already exists. Checking if it's correct..."
    grep -n "Dial(SIP/\${EXTEN:1}@galax" "$VICI_DIALPLAN" | head -1
    echo ""
fi

# Find the exact line number of the AGI line for _9X.
AGI_LINE=$(grep -n "exten => _9X.,1,AGI" "$VICI_DIALPLAN" | head -1 | cut -d: -f1)

if [ -z "$AGI_LINE" ]; then
    echo "ERROR: Could not find 'exten => _9X.,1,AGI' line"
    exit 1
fi

echo "Found AGI line at: $AGI_LINE"
echo ""

# Check what comes after AGI line
NEXT_LINE=$((AGI_LINE + 1))
echo "Line $NEXT_LINE (after AGI):"
sed -n "${NEXT_LINE}p" "$VICI_DIALPLAN"
echo ""

# Check if Dial already exists after AGI
if sed -n "${NEXT_LINE}p" "$VICI_DIALPLAN" | grep -q "Dial(SIP"; then
    echo "✓ Dial() line already exists at line $NEXT_LINE"
    echo "Checking if it has the correct 'b()' option..."
    
    if sed -n "${NEXT_LINE}p" "$VICI_DIALPLAN" | grep -q "b(audio-bridge-outbound"; then
        echo "✓ Dial() already has correct 'b()' option"
    else
        echo "⚠ Dial() exists but missing 'b()' option. Updating..."
        # Replace the Dial line to add b() option
        sed -i "${NEXT_LINE}s/Dial(SIP\/\${EXTEN:1}@galax,,tToR)/Dial(SIP\/\${EXTEN:1}@galax,,tToRb(audio-bridge-outbound^s^1))/" "$VICI_DIALPLAN"
        echo "✓ Updated Dial() line"
    fi
else
    echo "✗ Dial() line missing. Adding it..."
    # Insert Dial line after AGI
    sed -i "${AGI_LINE}a\ same  => n,Dial(SIP/\${EXTEN:1}@galax,,tToRb(audio-bridge-outbound^s^1))" "$VICI_DIALPLAN"
    echo "✓ Added Dial() line"
fi

# Check if Hangup exists
HANGUP_LINE=$(grep -n "exten => _9X." "$VICI_DIALPLAN" | grep -A 5 "AGI" | grep -n "Hangup()" | head -1 | cut -d: -f1)
if [ -z "$HANGUP_LINE" ]; then
    # Find the line after Dial
    DIAL_LINE=$(grep -n "Dial(SIP/\${EXTEN:1}@galax" "$VICI_DIALPLAN" | head -1 | cut -d: -f1)
    if [ -n "$DIAL_LINE" ]; then
        echo "✗ Hangup() line missing. Adding it..."
        sed -i "$((DIAL_LINE + 1))a\ same  => n,Hangup()" "$VICI_DIALPLAN"
        echo "✓ Added Hangup() line"
    fi
else
    echo "✓ Hangup() line already exists"
fi

echo ""
echo "=== Updated lines ==="
sed -n "${AGI_LINE},$((AGI_LINE + 5))p" "$VICI_DIALPLAN"
echo ""

# Fix audio-bridge-outbound context to use Return() instead of Hangup()
echo "=== Fixing audio-bridge-outbound context ==="
if [ -f "$AUDIO_BRIDGE_EXT" ]; then
    if grep -q "exten => s,n,Hangup()" "$AUDIO_BRIDGE_EXT"; then
        echo "⚠ Found Hangup() in audio-bridge-outbound, changing to Return()..."
        sed -i 's/exten => s,n,Hangup()/exten => s,n,Return()/' "$AUDIO_BRIDGE_EXT"
        echo "✓ Changed Hangup() to Return()"
    else
        echo "✓ audio-bridge-outbound already uses Return() or correct format"
    fi
    echo ""
    echo "Current audio-bridge-outbound context:"
    sed -n '/\[audio-bridge-outbound\]/,/^\[/p' "$AUDIO_BRIDGE_EXT" | head -5
else
    echo "⚠ $AUDIO_BRIDGE_EXT not found. Creating it..."
    cat > "$AUDIO_BRIDGE_EXT" << 'EOF'
; Audio Bridge Stasis Routing

[audio-bridge-outbound]
exten => s,1,NoOp(Routing to Stasis: ${UNIQUEID})
 same => n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
 same => n,Return()
EOF
    echo "✓ Created $AUDIO_BRIDGE_EXT"
fi

echo ""
echo "=== Reloading dialplan ==="
asterisk -rx "dialplan reload" 2>/dev/null || asterisk -rx "dialplan reload"
echo "✓ Reloaded"
echo ""

echo "=== Verifying in Asterisk ==="
asterisk -rx "dialplan show _9X.@vicidial-auto-external"
echo ""

echo "=========================================="
echo "✓ Fix complete!"
echo "=========================================="
echo ""
echo "Expected dialplan should show:"
echo "  1. AGI(...)"
echo "  2. Dial(SIP/...@galax,,tToRb(audio-bridge-outbound^s^1))"
echo "  3. Hangup()"
echo ""
echo "Now test a call - it should:"
echo "  1. Execute AGI"
echo "  2. Dial the carrier (SIP/galax)"
echo "  3. When carrier answers, route to Stasis via b() option"
echo "  4. Audio bridge will monitor and record"


