#!/bin/bash
# Deployment script for Audio Bridge application
# Run this script on the server as root

set -e  # Exit on error

APP_NAME="audio-bridge"
APP_DIR="/opt/${APP_NAME}"
SERVICE_USER="audio-bridge"
PYTHON_VERSION="3.9"

echo "=========================================="
echo "Audio Bridge Deployment Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root"
    exit 1
fi

# Step 1: Update system packages
print_status "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# Step 2: Install system dependencies
print_status "Installing system dependencies..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    build-essential \
    python3-dev \
    libpq-dev \
    nginx \
    ufw

# Step 3: Create application user (optional, for security)
print_status "Creating application user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$APP_DIR" "$SERVICE_USER"
    print_status "User $SERVICE_USER created"
else
    print_warning "User $SERVICE_USER already exists"
fi

# Step 4: Create application directory
print_status "Creating application directory..."
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/audio_storage"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# Step 5: Copy application files (assuming we're in the project directory)
print_status "Copying application files..."
if [ -d "." ] && [ -f "requirements.txt" ]; then
    # Copy all files except venv, __pycache__, .git
    rsync -av --exclude='venv' --exclude='__pycache__' --exclude='.git' \
          --exclude='*.db' --exclude='*.pyc' \
          . "$APP_DIR/"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
    print_status "Application files copied"
else
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Step 6: Create virtual environment
print_status "Creating Python virtual environment..."
cd "$APP_DIR"
sudo -u "$SERVICE_USER" python3 -m venv venv
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
print_status "Virtual environment created"

# Step 7: Install Python dependencies
print_status "Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install -r requirements.txt
print_status "Dependencies installed"

# Step 8: Create .env file template if it doesn't exist
if [ ! -f "$APP_DIR/.env" ]; then
    print_status "Creating .env file template..."
    cat > "$APP_DIR/.env" << 'EOF'
# Application
DEBUG=False
ENVIRONMENT=production
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Database - UPDATE WITH YOUR SUPABASE CREDENTIALS
DATABASE_URL=postgresql://postgres.yjwmkutjgffqamfaazcq:Newyork1%4024@aws-0-us-west-2.pooler.supabase.com:5432/postgres

# Asterisk ARI Configuration - UPDATE WITH YOUR ASTERISK SERVER DETAILS
ASTERISK_HOST=localhost
ASTERISK_PORT=8088
ASTERISK_USERNAME=asterisk
ASTERISK_PASSWORD=your_ari_password_here
ASTERISK_WS_URL=ws://localhost:8088/ari/events?app=audio-bridge&subscribeAll=true
ASTERISK_APP_NAME=audio-bridge
ENABLE_WEBSOCKET_MONITOR=True
USE_POLLING_MONITOR=False

# CORS
CORS_ORIGINS=*

# Audio Processing
AUDIO_CHUNK_SIZE=4096
AUDIO_SAMPLE_RATE=8000
AUDIO_CHANNELS=1
AUDIO_FORMAT=PCM

# Storage
AUDIO_STORAGE_PATH=./audio_storage
EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
    print_warning "Please edit $APP_DIR/.env with your actual credentials"
else
    print_status ".env file already exists"
fi

# Step 9: Create systemd service file
print_status "Creating systemd service..."
cat > "/etc/systemd/system/${APP_NAME}.service" << EOF
[Unit]
Description=Audio Bridge FastAPI Application
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$APP_NAME

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Reload systemd and enable service
print_status "Reloading systemd daemon..."
systemctl daemon-reload
systemctl enable "${APP_NAME}.service"
print_status "Service enabled (not started yet - configure .env first)"

# Step 11: Configure nginx
print_status "Configuring nginx reverse proxy..."
if [ -f "$APP_DIR/scripts/nginx.conf" ]; then
    cp "$APP_DIR/scripts/nginx.conf" "/etc/nginx/sites-available/${APP_NAME}"
    ln -sf "/etc/nginx/sites-available/${APP_NAME}" "/etc/nginx/sites-enabled/${APP_NAME}"
    
    # Remove default nginx site if it exists
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        rm /etc/nginx/sites-enabled/default
    fi
    
    # Test nginx configuration
    if nginx -t 2>/dev/null; then
        systemctl reload nginx
        print_status "Nginx configured and reloaded"
    else
        print_warning "Nginx configuration test failed, but continuing..."
    fi
else
    print_warning "Nginx config file not found, skipping nginx setup"
fi

# Step 12: Configure firewall
print_status "Configuring firewall..."
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
ufw allow 8000/tcp comment "Audio Bridge API (direct)"
ufw allow 22/tcp comment "SSH"
print_status "Firewall configured"

# Step 13: Summary
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit $APP_DIR/.env with your credentials:"
echo "   - Supabase DATABASE_URL"
echo "   - Asterisk ARI credentials"
echo ""
echo "2. Test database connection:"
echo "   cd $APP_DIR"
echo "   sudo -u $SERVICE_USER $APP_DIR/venv/bin/python test_supabase_connection.py"
echo ""
echo "3. Start the service:"
echo "   systemctl start $APP_NAME"
echo "   systemctl status $APP_NAME"
echo ""
echo "4. Check logs:"
echo "   journalctl -u $APP_NAME -f"
echo ""
echo "5. Test API:"
echo "   curl http://localhost:8000/api/health"
echo "   curl http://localhost/api/health  (through nginx)"
echo ""
echo "6. Access dashboard:"
echo "   http://135.181.27.156 (through nginx on port 80)"
echo "   http://135.181.27.156:8000 (direct access)"
echo ""
echo "7. Set up domain and SSL (optional):"
echo "   See: docs/NGINX_SETUP.md"
echo ""

