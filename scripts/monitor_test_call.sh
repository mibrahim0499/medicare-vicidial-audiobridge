#!/bin/bash
# Monitor both Asterisk and FastAPI backend during a test call
# Run this on the backend server (or use separate terminals)

echo "=========================================="
echo "Test Call Monitoring"
echo "=========================================="
echo ""
echo "This script will monitor:"
echo "  1. Asterisk logs (on autodialer server)"
echo "  2. FastAPI backend logs (on backend server)"
echo ""
echo "Make a test call from VICIdial now..."
echo ""
echo "Press Ctrl+C to stop monitoring"
echo ""

# Colors for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Monitoring FastAPI Backend Logs ===${NC}"
echo "Looking for:"
echo "  - Call start events"
echo "  - Recording started"
echo "  - Audio chunks received"
echo ""
echo "Run this command on backend server:"
echo "  journalctl -u audio-bridge.service -f | grep -E 'call|recording|audio|chunk|ERROR|WARNING'"
echo ""
echo "Or if running manually:"
echo "  tail -f /path/to/logs/app.log | grep -E 'call|recording|audio|chunk'"
echo ""
echo -e "${YELLOW}=== Monitoring Asterisk Logs ===${NC}"
echo "Run this on autodialer server:"
echo "  asterisk -rvvvvv | grep -E 'Stasis|Dial|audio-bridge|917'"
echo ""
echo "Or check full logs:"
echo "  tail -f /var/log/asterisk/full | grep -E 'Stasis|Dial|audio-bridge|917'"
echo ""


