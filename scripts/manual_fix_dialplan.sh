#!/bin/bash
# Manual fix for dialplan - more reliable method
# Run this on your VICIdial server

VICI_DIALPLAN="/etc/asterisk/extensions-vicidial.conf"

echo "Checking current file..."
sed -n '169,174p' "$VICI_DIALPLAN"
echo ""

# Backup
cp "$VICI_DIALPLAN" "$VICI_DIALPLAN.backup.$(date +%Y%m%d_%H%M%S)"

# Use a more reliable method - replace the Hangup line with Goto + Hangup
# First, let's see the exact format
echo "Current Dial line:"
grep -n "Dial(SIP/denovo" "$VICI_DIALPLAN"
echo ""

echo "Current Hangup line:"
grep -n "Hangup()" "$VICI_DIALPLAN" | head -1
echo ""

# Method: Insert line after Dial, before Hangup
# Find the line number of Hangup after Dial
DIAL_LINE=$(grep -n "Dial(SIP/denovo/\${EXTEN:1},,tToR)" "$VICI_DIALPLAN" | head -1 | cut -d: -f1)
HANGUP_LINE=$(sed -n "${DIAL_LINE},\$p" "$VICI_DIALPLAN" | grep -n "Hangup()" | head -1 | cut -d: -f1)
HANGUP_LINE=$((DIAL_LINE + HANGUP_LINE - 1))

echo "Dial is at line: $DIAL_LINE"
echo "Hangup is at line: $HANGUP_LINE"
echo ""

# Create temp file
TMP_FILE=$(mktemp)

# Copy everything up to and including Dial line
sed -n "1,${DIAL_LINE}p" "$VICI_DIALPLAN" > "$TMP_FILE"

# Add the Goto line with proper spacing (match the format)
echo "                    3. Goto(audio-bridge-outbound,s,1)     [Added for Stasis routing]" >> "$TMP_FILE"

# Copy Hangup and everything after
sed -n "${HANGUP_LINE},\$p" "$VICI_DIALPLAN" >> "$TMP_FILE"

# Replace original
cp "$TMP_FILE" "$VICI_DIALPLAN"
rm "$TMP_FILE"

echo "✓ Modified dialplan"
echo ""
echo "Verifying changes (lines 169-175):"
sed -n '169,175p' "$VICI_DIALPLAN"
echo ""

echo "Reloading dialplan..."
asterisk -rx "dialplan reload" 2>/dev/null
echo "✓ Reloaded"
echo ""

echo "Verifying in Asterisk:"
asterisk -rx "dialplan show _9X.@vicidial-auto-external" 2>/dev/null | head -10
echo ""

