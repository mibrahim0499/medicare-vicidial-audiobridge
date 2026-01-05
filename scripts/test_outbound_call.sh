#!/bin/bash
# Test script to make an outbound call and monitor SIP logs
# Run this on your VICIdial server via SSH

echo "=========================================="
echo "Testing Outbound Call with Valid DID"
echo "=========================================="
echo ""

# Test number (different USA number - example)
TEST_NUMBER="12025551234"  # Change this to a different USA number you want to test

echo "Test Number: $TEST_NUMBER"
echo ""

# Method 1: Test via Asterisk CLI (if you have direct access)
echo "Method 1: Testing via Asterisk CLI"
echo "-----------------------------------"
echo "Connect to Asterisk CLI:"
echo "  sudo asterisk -rvvvvv"
echo ""
echo "Then run this command to make a test call:"
echo "  channel originate Local/9${TEST_NUMBER}@default extension s@default"
echo ""
echo "OR use this simpler method:"
echo "  dialplan reload"
echo "  channel originate Local/9${TEST_NUMBER}@default application Wait 30"
echo ""

# Method 2: Monitor SIP logs in real-time
echo "Method 2: Monitor SIP Logs"
echo "---------------------------"
echo "In another terminal, SSH to your server and run:"
echo "  sudo tail -f /var/log/asterisk/full | grep -E '(denovo|SIP|503|200|INVITE|ACK)'"
echo ""

# Method 3: Test via VICIdial Manual Dial
echo "Method 3: Test via VICIdial Manual Dial"
echo "----------------------------------------"
echo "1. Log into VICIdial web interface"
echo "2. Go to Agent Interface"
echo "3. Click 'Manual Dial'"
echo "4. Enter number: ${TEST_NUMBER}"
echo "5. Click 'Dial'"
echo ""

echo "=========================================="
echo "What to Look For in the Logs:"
echo "=========================================="
echo ""
echo "SUCCESS indicators:"
echo "  - SIP/2.0 200 OK (instead of 503)"
echo "  - 'Reason' header missing or shows success"
echo "  - Call connects and rings"
echo ""
echo "FAILURE indicators:"
echo "  - SIP/2.0 503 Service Unavailable"
echo "  - Reason: Q.850;cause=41"
echo "  - CONGESTION errors"
echo ""
echo "=========================================="

