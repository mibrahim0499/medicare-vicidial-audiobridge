#!/bin/bash
# Script to configure Asterisk ARI for VICIdial integration

echo "Configuring Asterisk ARI for Audio Streaming Bridge..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root or with sudo"
    exit 1
fi

ASTERISK_CONFIG_DIR="/etc/asterisk"
ARI_CONFIG_FILE="$ASTERISK_CONFIG_DIR/ari.conf"

# Create or update ARI configuration
if [ ! -f "$ARI_CONFIG_FILE" ]; then
    echo "Creating ARI configuration file..."
    cat > "$ARI_CONFIG_FILE" << EOF
[general]
enabled = yes
pretty = yes
allowed_origins = *

[asterisk]
type = user
read_only = no
password = $(openssl rand -base64 12)
EOF
    echo "ARI configuration created at $ARI_CONFIG_FILE"
    echo "Please note the generated password and update your .env file"
else
    echo "ARI configuration already exists at $ARI_CONFIG_FILE"
    echo "Checking if [asterisk] user section is configured..."
    
    # Check if [asterisk] section exists and is not commented
    if ! grep -q "^\[asterisk\]" "$ARI_CONFIG_FILE"; then
        echo "Adding [asterisk] user section..."
        cat >> "$ARI_CONFIG_FILE" << EOF

[asterisk]
type = user
read_only = no
password = $(openssl rand -base64 12)
EOF
        echo "ARI user section added. Please note the generated password above."
    else
        # Check if password is set (not commented)
        if ! grep -q "^password = " "$ARI_CONFIG_FILE"; then
            echo "Password not set. Adding password to [asterisk] section..."
            # Add password line after [asterisk] section
            sed -i '/^\[asterisk\]/a password = '"$(openssl rand -base64 12)" "$ARI_CONFIG_FILE"
            echo "Password added. Please note the generated password above."
        else
            echo "ARI user section already configured."
            echo "Current password:"
            grep "^password = " "$ARI_CONFIG_FILE" | head -1
        fi
    fi
fi

# Enable HTTP server in http.conf
HTTP_CONFIG_FILE="$ASTERISK_CONFIG_DIR/http.conf"
if [ -f "$HTTP_CONFIG_FILE" ]; then
    echo "Checking HTTP configuration..."
    if ! grep -q "enabled=yes" "$HTTP_CONFIG_FILE"; then
        echo "Enabling HTTP server..."
        sed -i 's/enabled=no/enabled=yes/g' "$HTTP_CONFIG_FILE"
    fi
    
    if ! grep -q "bindaddr" "$HTTP_CONFIG_FILE"; then
        echo "bindaddr=0.0.0.0" >> "$HTTP_CONFIG_FILE"
    fi
    
    if ! grep -q "bindport" "$HTTP_CONFIG_FILE"; then
        echo "bindport=8088" >> "$HTTP_CONFIG_FILE"
    fi
else
    echo "Creating HTTP configuration..."
    cat > "$HTTP_CONFIG_FILE" << EOF
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
EOF
fi

# Restart Asterisk
echo "Restarting Asterisk..."
systemctl restart asterisk

echo "Asterisk ARI configuration complete!"
echo "Please verify the ARI password in $ARI_CONFIG_FILE and update your .env file"

