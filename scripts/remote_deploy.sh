#!/bin/bash
# Remote deployment script - runs from local machine
# This script will upload the application and run deployment on remote server

set -e

# Server configuration
SERVER_IP="135.181.27.156"
SERVER_USER="root"
SERVER_PASS="worldalt2121"
APP_DIR="/opt/audio-bridge"
LOCAL_DIR="."

echo "=========================================="
echo "Remote Deployment Script"
echo "=========================================="

# Check if sshpass is installed (for password-based SSH)
if ! command -v sshpass &> /dev/null; then
    echo "Installing sshpass..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install hudochenkov/sshpass/sshpass
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install -y sshpass
    fi
fi

# Check if rsync is available
if ! command -v rsync &> /dev/null; then
    echo "Error: rsync is required but not installed"
    exit 1
fi

echo "Step 1: Testing SSH connection..."
# Test SSH connection first
if ! sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${SERVER_USER}@${SERVER_IP}" "echo 'Connection successful'" 2>/dev/null; then
    echo "ERROR: Cannot connect to server. Please verify:"
    echo "  - Server IP: $SERVER_IP"
    echo "  - Username: $SERVER_USER"
    echo "  - Password is correct"
    echo "  - Server is accessible from your network"
    echo ""
    echo "You can try connecting manually:"
    echo "  ssh ${SERVER_USER}@${SERVER_IP}"
    exit 1
fi

echo "Step 2: Uploading application files to server..."
# Upload files using rsync over SSH
if ! sshpass -p "$SERVER_PASS" rsync -avz --progress \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.db' \
    --exclude='*.pyc' \
    --exclude='.env' \
    "$LOCAL_DIR/" "${SERVER_USER}@${SERVER_IP}:${APP_DIR}/"; then
    echo "ERROR: File upload failed"
    exit 1
fi

echo ""
echo "Step 3: Running deployment script on server..."
# Run deployment script on remote server
if ! sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no "${SERVER_USER}@${SERVER_IP}" << 'ENDSSH'
cd /opt/audio-bridge
chmod +x scripts/deploy.sh
bash scripts/deploy.sh
ENDSSH
then
    echo "ERROR: Deployment script failed on server"
    echo "You can SSH to the server and run it manually:"
    echo "  ssh ${SERVER_USER}@${SERVER_IP}"
    echo "  cd /opt/audio-bridge && bash scripts/deploy.sh"
    exit 1
fi

echo ""
echo "=========================================="
echo "Remote deployment initiated!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. SSH into server:"
echo "   ssh ${SERVER_USER}@${SERVER_IP}"
echo ""
echo "2. Edit .env file:"
echo "   nano ${APP_DIR}/.env"
echo ""
echo "3. Test database connection:"
echo "   cd ${APP_DIR}"
echo "   sudo -u audio-bridge venv/bin/python test_supabase_connection.py"
echo ""
echo "4. Start the service:"
echo "   systemctl start audio-bridge"
echo "   systemctl status audio-bridge"
echo ""

