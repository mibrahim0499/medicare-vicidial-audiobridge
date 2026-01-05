# Nginx Setup Guide for Audio Bridge

## Overview

Nginx acts as a reverse proxy, allowing you to:
- Access the app via a domain name (e.g., `https://audio-bridge.yourdomain.com`)
- Use standard ports (80/443) instead of 8000
- Set up SSL/HTTPS with Let's Encrypt
- Handle WebSocket connections properly

## Current Setup

After deployment, nginx is already configured and running. You can access the app via:

- **HTTP**: `http://135.181.27.156` (port 80)
- **Direct**: `http://135.181.27.156:8000` (still works)

## Setting Up a Domain Name

### Step 1: Point Your Domain to the Server

1. Go to your domain registrar (GoDaddy, Namecheap, etc.)
2. Add an A record:
   - **Type**: A
   - **Name**: `audio-bridge` (or `@` for root domain)
   - **Value**: `135.181.27.156`
   - **TTL**: 3600 (or default)

Example:
- Domain: `yourdomain.com`
- Subdomain: `audio-bridge.yourdomain.com` → `135.181.27.156`

### Step 2: Update Nginx Configuration

SSH into the server:

```bash
ssh root@135.181.27.156
# Password: worldalt2121
```

Edit nginx config:

```bash
nano /etc/nginx/sites-available/audio-bridge
```

Update the `server_name` line:

```nginx
server {
    listen 80;
    server_name audio-bridge.yourdomain.com;  # Change this to your domain
    # ... rest of config
}
```

Test and reload:

```bash
nginx -t
systemctl reload nginx
```

### Step 3: Set Up SSL with Let's Encrypt (Recommended)

Install Certbot:

```bash
apt-get update
apt-get install -y certbot python3-certbot-nginx
```

Get SSL certificate:

```bash
certbot --nginx -d audio-bridge.yourdomain.com
```

Follow the prompts:
- Enter your email
- Agree to terms
- Choose whether to redirect HTTP to HTTPS (recommended: Yes)

Certbot will automatically:
- Get the certificate
- Update nginx config
- Set up auto-renewal

### Step 4: Verify SSL

Visit your domain:
```
https://audio-bridge.yourdomain.com
```

You should see a padlock icon in the browser.

## Manual Nginx Configuration

If you need to customize the nginx config:

```bash
nano /etc/nginx/sites-available/audio-bridge
```

Key settings:

1. **Domain name**: Update `server_name`
2. **SSL certificates**: Update paths after getting certificates
3. **WebSocket**: Already configured for `/ws` endpoint
4. **File upload size**: `client_max_body_size 50M` (for audio)

After editing:

```bash
# Test configuration
nginx -t

# Reload if test passes
systemctl reload nginx
```

## Testing Nginx

### Check Status

```bash
systemctl status nginx
```

### Test Configuration

```bash
nginx -t
```

### View Logs

```bash
# Access logs
tail -f /var/log/nginx/access.log

# Error logs
tail -f /var/log/nginx/error.log
```

### Test Endpoints

```bash
# Health check through nginx
curl http://localhost/api/health

# Or with domain
curl http://audio-bridge.yourdomain.com/api/health
```

## Troubleshooting

### Nginx Won't Start

```bash
# Check syntax
nginx -t

# Check error logs
tail -50 /var/log/nginx/error.log

# Check if port 80 is in use
netstat -tlnp | grep :80
```

### 502 Bad Gateway

This means nginx can't reach the FastAPI app. Check:

1. **Is the app running?**
   ```bash
   systemctl status audio-bridge
   ```

2. **Is it listening on port 8000?**
   ```bash
   netstat -tlnp | grep :8000
   ```

3. **Check app logs:**
   ```bash
   journalctl -u audio-bridge -n 50
   ```

### WebSocket Not Working

1. Check nginx config has WebSocket settings for `/ws`
2. Verify the app is running
3. Check browser console for WebSocket errors
4. Test WebSocket connection:
   ```bash
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
        http://localhost/ws
   ```

### Domain Not Resolving

1. **Check DNS propagation:**
   ```bash
   dig audio-bridge.yourdomain.com
   # or
   nslookup audio-bridge.yourdomain.com
   ```

2. **Wait for DNS propagation** (can take up to 48 hours, usually 1-2 hours)

3. **Test locally:**
   ```bash
   # Add to /etc/hosts for testing
   echo "135.181.27.156 audio-bridge.yourdomain.com" >> /etc/hosts
   ```

## SSL Certificate Renewal

Let's Encrypt certificates expire every 90 days. Certbot sets up auto-renewal, but you can test it:

```bash
# Test renewal
certbot renew --dry-run

# Manual renewal
certbot renew
```

Check auto-renewal is set up:

```bash
systemctl status certbot.timer
```

## Security Recommendations

1. **Use HTTPS**: Always use SSL certificates in production
2. **Restrict access**: Use firewall rules to limit access if needed
3. **Keep updated**: Regularly update nginx and system packages
4. **Monitor logs**: Check nginx logs regularly for suspicious activity

## Current Access Methods

After deployment, you can access the app via:

1. **Through nginx (HTTP)**: `http://135.181.27.156`
2. **Direct (port 8000)**: `http://135.181.27.156:8000`
3. **With domain**: `http://your-domain.com` (after DNS setup)
4. **With SSL**: `https://your-domain.com` (after SSL setup)

## Next Steps

1. ✅ Nginx is configured and running
2. ⚠️ Set up domain name (optional but recommended)
3. ⚠️ Set up SSL certificate (recommended for production)
4. ✅ Test all endpoints through nginx
5. ✅ Verify WebSocket connections work

