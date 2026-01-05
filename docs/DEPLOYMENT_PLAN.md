# Deployment Plan for Audio Bridge Server

## Server Information
- **IP Address**: 135.181.27.156
- **IPv6**: 2a01:4f9:c013:ecd4::/64
- **User**: root
- **Password**: worldalt2121
- **Root Password**: worldalt2121

## Deployment Steps Overview

### Phase 1: Server Preparation
1. ✅ SSH into server
2. ✅ Update system packages
3. ✅ Install Python 3.9+ and pip
4. ✅ Install git (if needed)
5. ✅ Create application user (optional, for security)
6. ✅ Set up firewall rules

### Phase 2: Application Deployment
1. ✅ Clone/upload application code
2. ✅ Create virtual environment
3. ✅ Install dependencies
4. ✅ Configure environment variables (.env)
5. ✅ Test database connection (Supabase)
6. ✅ Test Asterisk ARI connection

### Phase 3: Service Configuration
1. ✅ Create systemd service file
2. ✅ Enable and start service
3. ✅ Configure auto-start on boot
4. ✅ Set up log rotation

### Phase 4: Testing & Verification
1. ✅ Test API endpoints
2. ✅ Test WebSocket connection
3. ✅ Test call detection
4. ✅ Verify dashboard access
5. ✅ Monitor logs

## Detailed Instructions

### Step 1: Connect to Server

```bash
ssh root@135.181.27.156
# Password: worldalt2121
```

### Step 2: Run Deployment Script

The deployment script (`deploy.sh`) will:
- Install system dependencies
- Set up Python environment
- Deploy application code
- Configure systemd service
- Start the application

### Step 3: Configure Environment

Edit `/opt/audio-bridge/.env` with:
- Supabase DATABASE_URL
- Asterisk ARI credentials
- Other configuration

### Step 4: Start Service

```bash
systemctl start audio-bridge
systemctl enable audio-bridge
systemctl status audio-bridge
```

### Step 5: Verify Deployment

- Check service status: `systemctl status audio-bridge`
- Check logs: `journalctl -u audio-bridge -f`
- Test API: `curl http://localhost:8000/api/health`
- Access dashboard: `http://135.181.27.156:8000`

## Post-Deployment Checklist

- [ ] Service is running
- [ ] Database connection works
- [ ] Asterisk ARI connection works
- [ ] API endpoints respond
- [ ] WebSocket connections work
- [ ] Dashboard is accessible
- [ ] Logs are being written
- [ ] Firewall allows port 8000

## Troubleshooting

### Service won't start
- Check logs: `journalctl -u audio-bridge -n 50`
- Verify .env file exists and is correct
- Check Python path in systemd service

### Database connection fails
- Verify DATABASE_URL in .env
- Test connection: `python test_supabase_connection.py`
- Check Supabase firewall rules

### Asterisk connection fails
- Verify ARI credentials
- Check Asterisk ARI is enabled
- Test connection: `curl http://localhost:8088/ari/asterisk/info`

## Rollback Plan

If deployment fails:
1. Stop service: `systemctl stop audio-bridge`
2. Restore previous version from backup
3. Restart service: `systemctl start audio-bridge`

