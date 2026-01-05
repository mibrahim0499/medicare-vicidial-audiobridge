#!/bin/bash
# Script to fix WebSocket access on VICIdial server

echo "=========================================="
echo "Fixing Asterisk ARI WebSocket Access"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Please run as root or with sudo"
    exit 1
fi

echo "Step 1: Checking Asterisk HTTP configuration..."
HTTP_CONFIG="/etc/asterisk/http.conf"

if [ -f "$HTTP_CONFIG" ]; then
    echo "Current http.conf settings:"
    grep -E "^enabled|^bindaddr|^bindport" "$HTTP_CONFIG" || echo "Settings not found"
    echo ""
    
    # Ensure bindaddr is 0.0.0.0 (not just localhost)
    if ! grep -q "^bindaddr=0.0.0.0" "$HTTP_CONFIG"; then
        echo "⚠️  bindaddr is not set to 0.0.0.0. Updating..."
        sed -i 's/^bindaddr=.*/bindaddr=0.0.0.0/' "$HTTP_CONFIG" 2>/dev/null || \
        sed -i '/^\[general\]/a bindaddr=0.0.0.0' "$HTTP_CONFIG"
        echo "✅ Updated bindaddr to 0.0.0.0"
    fi
    
    # Ensure port is 8088
    if ! grep -q "^bindport=8088" "$HTTP_CONFIG"; then
        echo "⚠️  bindport is not 8088. Updating..."
        sed -i 's/^bindport=.*/bindport=8088/' "$HTTP_CONFIG" 2>/dev/null || \
        sed -i '/^bindaddr/a bindport=8088' "$HTTP_CONFIG"
        echo "✅ Updated bindport to 8088"
    fi
    
    # Ensure enabled is yes
    if ! grep -q "^enabled=yes" "$HTTP_CONFIG"; then
        echo "⚠️  HTTP server not enabled. Enabling..."
        sed -i 's/^enabled=no/enabled=yes/' "$HTTP_CONFIG" 2>/dev/null || \
        sed -i '/^\[general\]/a enabled=yes' "$HTTP_CONFIG"
        echo "✅ Enabled HTTP server"
    fi
else
    echo "⚠️  http.conf not found. Creating..."
    cat > "$HTTP_CONFIG" << EOF
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
EOF
    echo "✅ Created http.conf"
fi

echo ""
echo "Step 2: Checking firewall rules..."
if command -v ufw &> /dev/null; then
    echo "UFW firewall detected"
    if ufw status | grep -q "8088/tcp"; then
        echo "✅ Port 8088 is already allowed"
    else
        echo "⚠️  Port 8088 not in firewall rules. Adding..."
        ufw allow 8088/tcp
        echo "✅ Added firewall rule for port 8088"
    fi
elif command -v firewall-cmd &> /dev/null; then
    echo "firewalld detected"
    if firewall-cmd --list-ports | grep -q "8088"; then
        echo "✅ Port 8088 is already allowed"
    else
        echo "⚠️  Port 8088 not in firewall rules. Adding..."
        firewall-cmd --permanent --add-port=8088/tcp
        firewall-cmd --reload
        echo "✅ Added firewall rule for port 8088"
    fi
elif command -v iptables &> /dev/null; then
    echo "iptables detected"
    if iptables -L -n | grep -q "8088"; then
        echo "✅ Port 8088 rule exists"
    else
        echo "⚠️  Adding iptables rule for port 8088..."
        iptables -A INPUT -p tcp --dport 8088 -j ACCEPT
        echo "✅ Added iptables rule"
        echo "⚠️  Note: Make this permanent with: iptables-save > /etc/iptables/rules.v4"
    fi
else
    echo "⚠️  No firewall tool detected. Please manually configure firewall to allow port 8088"
fi

echo ""
echo "Step 3: Verifying Asterisk is listening on port 8088..."
sleep 2
if netstat -tlnp 2>/dev/null | grep -q ":8088" || ss -tlnp 2>/dev/null | grep -q ":8088"; then
    echo "✅ Asterisk is listening on port 8088"
    netstat -tlnp 2>/dev/null | grep ":8088" || ss -tlnp 2>/dev/null | grep ":8088"
else
    echo "⚠️  Asterisk is not listening on port 8088"
    echo "   This might be normal if Asterisk hasn't restarted yet"
fi

echo ""
echo "Step 4: Restarting Asterisk..."
systemctl restart asterisk 2>/dev/null || service asterisk restart 2>/dev/null || /etc/init.d/asterisk restart 2>/dev/null

echo ""
echo "Step 5: Waiting for Asterisk to start..."
sleep 3

echo ""
echo "Step 6: Testing ARI endpoint..."
if curl -s -u asterisk:$(grep "^password" /etc/asterisk/ari.conf 2>/dev/null | head -1 | awk '{print $3}') http://localhost:8088/ari/asterisk/info > /dev/null 2>&1; then
    echo "✅ ARI HTTP endpoint is working"
else
    echo "⚠️  ARI HTTP endpoint test failed"
    echo "   Check Asterisk logs: tail -f /var/log/asterisk/full"
fi

echo ""
echo "=========================================="
echo "Configuration Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test from your local machine:"
echo "   curl -u asterisk:PASSWORD http://autodialer1.worldatlantus.com:8088/ari/asterisk/info"
echo ""
echo "2. If still not accessible, check:"
echo "   - Server firewall (external firewall rules)"
echo "   - Network security groups (if cloud server)"
echo "   - Router port forwarding (if behind NAT)"
echo ""
echo "3. Test WebSocket connection:"
echo "   Use a WebSocket client to connect to:"
echo "   ws://autodialer1.worldatlantus.com:8088/ari/events"
echo ""

