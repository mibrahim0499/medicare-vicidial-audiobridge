#!/bin/bash
# Script to check and fix VICIdial dialplan for Stasis routing
# Run this on your VICIdial server

echo "=========================================="
echo "Checking VICIdial Dialplan Configuration"
echo "=========================================="
echo ""

# Check if we're on the VICIdial server
if [ ! -d "/usr/share/astguiclient" ]; then
    echo "ERROR: This script must be run on the VICIdial server"
    exit 1
fi

echo "Step 1: Checking current dialplan in Asterisk..."
echo "-----------------------------------------------"
echo ""
echo "Checking extension 6000 (test extension that should work):"
asterisk -rx "dialplan show 6000@default" 2>/dev/null | head -20
echo ""

echo "Checking for Stasis application in dialplan:"
asterisk -rx "dialplan show" 2>/dev/null | grep -i "stasis\|audio-bridge" | head -10
echo ""

echo "Step 2: Checking VICIdial dialplan files..."
echo "--------------------------------------------"
echo ""

# Check VICIdial dialplan location
VICI_DIALPLAN="/usr/share/astguiclient/AST_CRON_mix_recordings_BASIC.pl"
if [ -f "$VICI_DIALPLAN" ]; then
    echo "Found VICIdial script: $VICI_DIALPLAN"
fi

# Check for extensions_vicidial.conf or similar
echo "Looking for VICIdial dialplan files:"
find /etc/asterisk -name "*vicidial*" -o -name "*extensions*" 2>/dev/null | head -10
echo ""

echo "Step 3: Checking extension 6000 configuration..."
echo "-------------------------------------------------"
echo ""

# Check if extension 6000 exists and what it does
asterisk -rx "dialplan show 6000@default" 2>/dev/null | grep -A 5 "6000"
echo ""

echo "Step 4: Checking for outbound call patterns..."
echo "-----------------------------------------------"
echo ""

# Check for 9 + number pattern (outbound calls)
asterisk -rx "dialplan show default" 2>/dev/null | grep -E "exten.*_9\.|exten.*9X" | head -10
echo ""

echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. If extension 6000 shows Stasis routing, we can use that as a template"
echo "2. We need to modify the outbound call dialplan to route to Stasis after Dial()"
echo "3. VICIdial may need dialplan reload after changes"
echo ""
echo "To see the actual dialplan for a specific extension, run:"
echo "  asterisk -rx 'dialplan show 917786523395@default'"
echo ""
echo "To reload dialplan after making changes:"
echo "  asterisk -rx 'dialplan reload'"
echo ""

