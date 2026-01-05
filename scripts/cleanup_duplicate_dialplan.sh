#!/bin/bash
# Remove duplicate/invalid lines from extensions-vicidial.conf
# Run this on the autodialer server as root

VICI_DIALPLAN="/etc/asterisk/extensions-vicidial.conf"

echo "=========================================="
echo "Cleaning Up Duplicate Dialplan Lines"
echo "=========================================="
echo ""

# Backup
BACKUP_FILE="/etc/asterisk/extensions-vicidial.conf.backup.$(date +%Y%m%d_%H%M%S)"
cp "$VICI_DIALPLAN" "$BACKUP_FILE"
echo "✓ Backed up to: $BACKUP_FILE"
echo ""

# Show current problematic lines
echo "=== Current lines 99-110 ==="
sed -n '99,110p' "$VICI_DIALPLAN"
echo ""

# Find lines with invalid syntax "exten => n,"
echo "=== Finding duplicate lines with 'exten => n,' ==="
grep -n "exten => n," "$VICI_DIALPLAN" || echo "No invalid lines found"
echo ""

# Remove lines that match "exten => n," pattern (these are invalid duplicates)
if grep -q "exten => n," "$VICI_DIALPLAN"; then
    echo "⚠ Found invalid 'exten => n,' lines. Removing them..."
    # Create temp file without those lines
    grep -v "exten => n," "$VICI_DIALPLAN" > "${VICI_DIALPLAN}.tmp"
    mv "${VICI_DIALPLAN}.tmp" "$VICI_DIALPLAN"
    echo "✓ Removed duplicate lines"
else
    echo "✓ No duplicate lines found"
fi

echo ""
echo "=== After cleanup, lines 99-110 ==="
sed -n '99,110p' "$VICI_DIALPLAN"
echo ""

# Verify the correct format exists
echo "=== Verifying correct _9X. extension ==="
if grep -A 3 "exten => _9X.,1,AGI" "$VICI_DIALPLAN" | grep -q "same  => n,Dial"; then
    echo "✓ Correct format found:"
    grep -A 3 "exten => _9X.,1,AGI" "$VICI_DIALPLAN" | head -4
else
    echo "✗ Correct format not found!"
    exit 1
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
echo "✓ Cleanup complete!"
echo "=========================================="
echo ""
echo "The dialplan should now show only:"
echo "  1. AGI(...)"
echo "  2. Dial(SIP/...@galax,,tToRb(audio-bridge-outbound^s^1))"
echo "  3. Hangup()"
echo ""
echo "Note: 'same => n' is correct Asterisk syntax meaning"
echo "      'same extension, next priority'"


