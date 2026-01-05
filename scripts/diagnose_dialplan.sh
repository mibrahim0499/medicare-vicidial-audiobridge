#!/bin/bash
# Quick diagnostic script for dialplan issues
# Run this on your VICIdial server

echo "=========================================="
echo "Dialplan Diagnostic Script"
echo "=========================================="
echo ""

echo "1. Checking extension 6000 (should work with Stasis)..."
echo "------------------------------------------------------"
asterisk -rx "dialplan show 6000@default" 2>/dev/null
echo ""

echo "2. Checking for Stasis in dialplan..."
echo "--------------------------------------"
asterisk -rx "dialplan show" 2>/dev/null | grep -i "stasis\|audio-bridge" | head -10
if [ $? -ne 0 ]; then
    echo "   ⚠ No Stasis references found in dialplan"
fi
echo ""

echo "3. Checking the outbound extension pattern..."
echo "----------------------------------------------"
asterisk -rx "dialplan show 917786523395@default" 2>/dev/null | head -20
echo ""

echo "4. Finding VICIdial dialplan generation scripts..."
echo "--------------------------------------------------"
find /usr/share/astguiclient -name "*dial*.pl" -o -name "*exten*.pl" 2>/dev/null | head -5
echo ""

echo "5. Checking extensions files..."
echo "-------------------------------"
ls -la /etc/asterisk/extensions*.conf 2>/dev/null
echo ""

echo "6. Checking if extensions_audio_bridge.conf exists..."
echo "------------------------------------------------------"
if [ -f "/etc/asterisk/extensions_audio_bridge.conf" ]; then
    echo "   ✓ Found extensions_audio_bridge.conf"
    cat /etc/asterisk/extensions_audio_bridge.conf
else
    echo "   ⚠ extensions_audio_bridge.conf not found"
fi
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Compare extension 6000 (working) with outbound calls (not working)"
echo "The difference will show what needs to be added for Stasis routing."
echo ""

