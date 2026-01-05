#!/bin/bash
# Script to set up nginx for Audio Bridge
# Run this on the server after deployment

set -e

APP_NAME="audio-bridge"
APP_DIR="/opt/${APP_NAME}"

echo "=========================================="
echo "Setting up Nginx for Audio Bridge"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "Installing nginx..."
    apt-get update -qq
    apt-get install -y -qq nginx
fi

# Copy nginx config
if [ -f "$APP_DIR/scripts/nginx.conf" ]; then
    echo "Copying nginx configuration..."
    cp "$APP_DIR/scripts/nginx.conf" "/etc/nginx/sites-available/${APP_NAME}"
    
    # Create symlink
    if [ ! -L "/etc/nginx/sites-enabled/${APP_NAME}" ]; then
        ln -s "/etc/nginx/sites-available/${APP_NAME}" "/etc/nginx/sites-enabled/${APP_NAME}"
    fi
    
    # Remove default site
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        rm /etc/nginx/sites-enabled/default
    fi
    
    # Test configuration
    echo "Testing nginx configuration..."
    if nginx -t; then
        echo "Reloading nginx..."
        systemctl reload nginx
        systemctl enable nginx
        echo "✅ Nginx configured successfully!"
    else
        echo "❌ Nginx configuration test failed"
        exit 1
    fi
else
    echo "❌ Nginx config file not found at $APP_DIR/scripts/nginx.conf"
    exit 1
fi

# Configure firewall
echo "Configuring firewall..."
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
echo "✅ Firewall configured"

echo ""
echo "=========================================="
echo "Nginx setup complete!"
echo "=========================================="
echo ""
echo "You can now access the app via:"
echo "  - http://135.181.27.156 (through nginx)"
echo "  - http://135.181.27.156:8000 (direct)"
echo ""
echo "To set up a domain name and SSL:"
echo "  1. Point your domain to 135.181.27.156"
echo "  2. Edit /etc/nginx/sites-available/audio-bridge"
echo "  3. Update 'server_name' with your domain"
echo "  4. Run: certbot --nginx -d your-domain.com"
echo ""
echo "See docs/NGINX_SETUP.md for detailed instructions"

