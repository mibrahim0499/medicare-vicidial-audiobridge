#!/bin/bash
# Fix: Enter Stasis FIRST, then dial from ARI (client's recommendation)
# This is better than dialing first then entering Stasis
# Run this on the autodialer server as root

VICIDIAL_EXT="/etc/asterisk/extensions-vicidial.conf"

echo "=========================================="
echo "Fixing Dialplan: Stasis First, Then Dial from ARI"
echo "=========================================="
echo ""

# Backup
if [ -f "$VICIDIAL_EXT" ]; then
    BACKUP_FILE="${VICIDIAL_EXT}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$VICIDIAL_EXT" "$BACKUP_FILE"
    echo "✓ Backed up to: $BACKUP_FILE"
    echo ""
fi

# Show current _9X. pattern
echo "=== Current _9X. pattern ==="
sed -n '/^exten => _9X\./,/^exten =>/p' "$VICIDIAL_EXT" | head -5
echo ""

# Find the line number of the _9X. pattern
LINE_NUM=$(grep -n "^exten => _9X\." "$VICIDIAL_EXT" | head -1 | cut -d: -f1)

if [ -z "$LINE_NUM" ]; then
    echo "ERROR: Could not find _9X. pattern in $VICIDIAL_EXT"
    exit 1
fi

echo "Found _9X. pattern at line $LINE_NUM"
echo ""

# Read the current pattern to understand structure
AGI_LINE=$(sed -n "${LINE_NUM}p" "$VICIDIAL_EXT")
DIAL_LINE=$(sed -n "$((LINE_NUM + 1))p" "$VICIDIAL_EXT")
HANGUP_LINE=$(sed -n "$((LINE_NUM + 2))p" "$VICIDIAL_EXT")

echo "Current structure:"
echo "  Line $LINE_NUM: $AGI_LINE"
echo "  Line $((LINE_NUM + 1)): $DIAL_LINE"
echo "  Line $((LINE_NUM + 2)): $HANGUP_LINE"
echo ""

# Replace the pattern: Remove Dial() line, add Stasis() after AGI
# Pattern should be:
# exten => _9X.,1,AGI(...)
# same => n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})

echo "Updating dialplan..."
echo ""

# Remove the Dial line and replace with Stasis
# Keep AGI line, replace Dial with Stasis
sed -i "${LINE_NUM}a\\ same  => n,Stasis(audio-bridge,\${UNIQUEID},\${UNIQUEID})" "$VICIDIAL_EXT"
sed -i "$((LINE_NUM + 1))d" "$VICIDIAL_EXT"  # Remove old Dial line
sed -i "$((LINE_NUM + 1))d" "$VICIDIAL_EXT"  # Remove old Hangup line (if it was right after Dial)

echo "✓ Updated dialplan"
echo ""

# Show updated pattern
echo "=== Updated _9X. pattern ==="
sed -n '/^exten => _9X\./,/^exten =>/p' "$VICIDIAL_EXT" | head -5
echo ""

echo "=== Reloading dialplan ==="
asterisk -rx "dialplan reload" 2>/dev/null || asterisk -rx "dialplan reload"
echo "✓ Reloaded"
echo ""

echo "=========================================="
echo "✓ Fix complete!"
echo "=========================================="
echo ""
echo "New flow:"
echo "  1. Call comes in"
echo "  2. AGI script runs"
echo "  3. Enter Stasis immediately (before Dial)"
echo "  4. ARI receives StasisStart"
echo "  5. ARI extracts destination number and dials carrier"
echo "  6. Start recording"
echo "  7. Monitor audio"
echo ""
echo "The ARI application will now dial the carrier from Stasis,"
echo "which gives full control and avoids timing issues."
echo ""

