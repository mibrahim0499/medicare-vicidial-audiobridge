#!/bin/bash
# Script to properly configure existing ARI config file

echo "Fixing Asterisk ARI configuration..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root or with sudo"
    exit 1
fi

ASTERISK_CONFIG_DIR="/etc/asterisk"
ARI_CONFIG_FILE="$ASTERISK_CONFIG_DIR/ari.conf"

if [ ! -f "$ARI_CONFIG_FILE" ]; then
    echo "Error: ARI config file not found at $ARI_CONFIG_FILE"
    exit 1
fi

# Generate a secure password
NEW_PASSWORD=$(openssl rand -base64 12)

echo "Generated password: $NEW_PASSWORD"
echo ""
echo "Updating ARI configuration..."

# Backup the original file
cp "$ARI_CONFIG_FILE" "${ARI_CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "Backup created: ${ARI_CONFIG_FILE}.backup.*"

# Check if [asterisk] section exists
if grep -q "^\[asterisk\]" "$ARI_CONFIG_FILE"; then
    echo "[asterisk] section found. Updating password..."
    # Remove old password line if exists
    sed -i '/^password = /d' "$ARI_CONFIG_FILE"
    # Add new password after [asterisk] line
    sed -i '/^\[asterisk\]/a password = '"$NEW_PASSWORD" "$ARI_CONFIG_FILE"
    
    # Ensure type and read_only are set
    if ! grep -q "^type = user" "$ARI_CONFIG_FILE"; then
        sed -i '/^\[asterisk\]/a type = user' "$ARI_CONFIG_FILE"
    fi
    if ! grep -q "^read_only = no" "$ARI_CONFIG_FILE"; then
        sed -i '/^\[asterisk\]/a read_only = no' "$ARI_CONFIG_FILE"
    fi
else
    echo "[asterisk] section not found. Adding it..."
    cat >> "$ARI_CONFIG_FILE" << EOF

[asterisk]
type = user
read_only = no
password = $NEW_PASSWORD
EOF
fi

# Ensure general section has required settings
if ! grep -q "^enabled = yes" "$ARI_CONFIG_FILE"; then
    sed -i 's/^;enabled = yes/enabled = yes/' "$ARI_CONFIG_FILE"
    if ! grep -q "^enabled = yes" "$ARI_CONFIG_FILE"; then
        sed -i '/^\[general\]/a enabled = yes' "$ARI_CONFIG_FILE"
    fi
fi

if ! grep -q "^pretty = yes" "$ARI_CONFIG_FILE"; then
    sed -i '/^\[general\]/a pretty = yes' "$ARI_CONFIG_FILE"
fi

if ! grep -q "^allowed_origins = \*" "$ARI_CONFIG_FILE"; then
    sed -i '/^\[general\]/a allowed_origins = *' "$ARI_CONFIG_FILE"
fi

echo ""
echo "Configuration updated successfully!"
echo ""
echo "=========================================="
echo "ARI PASSWORD: $NEW_PASSWORD"
echo "=========================================="
echo ""
echo "Please copy this password and update your .env file:"
echo "ASTERISK_PASSWORD=$NEW_PASSWORD"
echo ""

# Restart Asterisk
echo "Restarting Asterisk..."
systemctl restart asterisk

echo ""
echo "Done! Test the connection with:"
echo "curl -u asterisk:$NEW_PASSWORD http://localhost:8088/ari/asterisk/info"

