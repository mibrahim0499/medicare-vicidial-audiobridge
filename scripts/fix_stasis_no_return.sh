#!/bin/bash
# Fix: Remove Return() from audio-bridge-outbound so channel stays in Stasis
# This keeps the recording active for the entire call duration
# Run this on the autodialer server as root

AUDIO_BRIDGE_EXT="/etc/asterisk/extensions_audio_bridge.conf"

echo "=========================================="
echo "Fixing Stasis to Keep Channel Active"
echo "=========================================="
echo ""

# Backup
if [ -f "$AUDIO_BRIDGE_EXT" ]; then
    BACKUP_FILE="${AUDIO_BRIDGE_EXT}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$AUDIO_BRIDGE_EXT" "$BACKUP_FILE"
    echo "✓ Backed up to: $BACKUP_FILE"
    echo ""
fi

# Show current state
echo "=== Current audio-bridge-outbound context ==="
if [ -f "$AUDIO_BRIDGE_EXT" ]; then
    sed -n '/\[audio-bridge-outbound\]/,/^\[/p' "$AUDIO_BRIDGE_EXT" | head -10
else
    echo "File not found, will create it"
fi
echo ""

# Create/update the context WITHOUT Return()
# The channel should stay in Stasis and be handled by the ARI application
cat > "$AUDIO_BRIDGE_EXT" << 'EOF'
; Audio Bridge Stasis Routing
; IMPORTANT: Channel stays in Stasis - ARI application handles lifecycle

[audio-bridge-outbound]
exten => s,1,NoOp(Routing to Stasis: ${UNIQUEID})
 same => n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
 ; NOTE: No Return() - channel stays in Stasis until call ends or ARI handles it
 ; The ARI application will manage the channel lifecycle
EOF

chmod 644 "$AUDIO_BRIDGE_EXT"
echo "✓ Updated $AUDIO_BRIDGE_EXT"
echo ""

# Show updated state
echo "=== Updated audio-bridge-outbound context ==="
sed -n '/\[audio-bridge-outbound\]/,/^\[/p' "$AUDIO_BRIDGE_EXT" | head -10
echo ""

echo "=== Reloading dialplan ==="
asterisk -rx "dialplan reload" 2>/dev/null || asterisk -rx "dialplan reload"
echo "✓ Reloaded"
echo ""

echo "=========================================="
echo "✓ Fix complete!"
echo "=========================================="
echo ""
echo "Now the channel will:"
echo "  1. Enter Stasis when carrier answers"
echo "  2. Stay in Stasis for the entire call duration"
echo "  3. Recording will continue until call ends"
echo "  4. ARI application manages channel lifecycle"
echo ""
echo "IMPORTANT: Make sure your ARI application handles channel"
echo "           lifecycle properly (bridging, continuing, etc.)"


