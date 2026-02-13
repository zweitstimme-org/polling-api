# Deployment Guide

Complete deployment documentation for the Zweitstimme Polling API on Ubuntu VPS.

## Overview

This FastAPI application is deployed as a production service with the following architecture:

- **Application**: FastAPI with Gunicorn + Uvicorn workers
- **Process Management**: systemd service
- **Reverse Proxy**: Nginx
- **SSL/TLS**: Let's Encrypt (Certbot)
- **Package Manager**: uv
- **User**: Runs as `paul` user
- **Port**: localhost:8000 (internal)

## Prerequisites

- Ubuntu VPS (20.04+)
- Domain: `api.fasttrack29.com` (or your domain)
- Root/sudo access
- Git repository cloned to `/home/paul/pollingAPI`

## Installation Steps

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, git, nginx, certbot
sudo apt install -y python3 python3-pip git nginx certbot python3-certbot-nginx

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone Repository

```bash
cd /home/paul
git clone https://github.com/yourusername/pollingAPI.git
cd pollingAPI
```

### 3. Setup Python Environment

```bash
# Sync dependencies
uv sync

# Verify gunicorn is installed
/home/paul/pollingAPI/.venv/bin/gunicorn --version
```

### 4. Create Log Directory

```bash
mkdir -p /home/paul/pollingAPI/data/logs
```

### 5. Configure Environment

Create `.env` file if needed:

```bash
nano /home/paul/pollingAPI/.env
```

Example:
```
DATABASE_URL=sqlite:///home/paul/pollingAPI/data/polling.db
API_SECRET=your-production-secret-key
```

## Systemd Service Configuration

### Create Service File

Create `/etc/systemd/system/pollingapi.service`:

```ini
[Unit]
Description=Zweitstimme Polling API
After=network.target

[Service]
Type=exec
User=paul
Group=paul
WorkingDirectory=/home/paul/pollingAPI

ExecStart=/home/paul/pollingAPI/.venv/bin/gunicorn \
    -k uvicorn.workers.UvicornWorker \
    pollingapi.main:app \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --timeout 120 \
    --max-requests 10000 \
    --access-logfile /home/paul/pollingAPI/data/logs/access.log \
    --error-logfile /home/paul/pollingAPI/data/logs/error.log

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Important**: Comments must be on separate lines in systemd files, not inline.

### Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable pollingapi

# Start service
sudo systemctl start pollingapi

# Check status
sudo systemctl status pollingapi
```

### Service Management Commands

```bash
# Start
sudo systemctl start pollingapi

# Stop
sudo systemctl stop pollingapi

# Restart (after code updates)
sudo systemctl restart pollingapi

# View logs
sudo journalctl -u pollingapi -f

# View recent logs
sudo journalctl -u pollingapi -n 50
```

## Nginx Configuration

### Create Nginx Site Config

Create `/etc/nginx/sites-available/pollingapi`:

```nginx
upstream pollingapi {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.fasttrack29.com;
    
    location / {
        proxy_pass http://pollingapi;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Enable Site

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/pollingapi /etc/nginx/sites-enabled/

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default
```

## SSL/TLS with Let's Encrypt

### Obtain Certificate

```bash
# Run certbot with nginx plugin
sudo certbot --nginx -d api.fasttrack29.com

# Follow prompts:
# - Enter email
# - Agree to terms
# - Choose whether to redirect HTTP to HTTPS (recommended: yes)
```

### Verify Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Check renewal timer
sudo systemctl status certbot.timer
```

Certbot automatically sets up a systemd timer to renew certificates.

## Deployment Workflow

### Manual Deployment

When you make changes to the repository:

```bash
cd /home/paul/pollingAPI
git pull

# If dependencies changed
uv sync

# Restart service
sudo systemctl restart pollingapi

# Check status
sudo systemctl status pollingapi
```

### Automated Deployment

Use the provided `deploy.sh` script:

```bash
# Make script executable
chmod +x /home/paul/pollingAPI/deploy.sh

# Run deployment
./deploy.sh
```

This script will:
1. Pull latest changes
2. Sync dependencies with uv
3. Reload systemd
4. Restart the service
5. Verify health check

## File Structure

```
/home/paul/pollingAPI/
├── .venv/                    # Python virtual environment
├── data/
│   ├── polling.db           # SQLite database
│   └── logs/                # Application logs
│       ├── access.log       # Gunicorn access logs
│       └── error.log        # Gunicorn error logs
├── deploy.sh                # Deployment script
├── src/
│   └── pollingapi/          # Application code
└── .env                     # Environment variables (optional)
```

## Monitoring and Logs

### Application Logs

```bash
# Gunicorn access logs
tail -f /home/paul/pollingAPI/data/logs/access.log

# Gunicorn error logs
tail -f /home/paul/pollingAPI/data/logs/error.log

# Systemd journal
sudo journalctl -u pollingapi -f
```

### Nginx Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/access.log

# Error logs
sudo tail -f /var/log/nginx/error.log
```

### Health Check

```bash
# Test API is responding
curl http://127.0.0.1:8000/health

# Test through nginx
curl https://api.fasttrack29.com/health
```

## Troubleshooting

### Service Won't Start

```bash
# Check for syntax errors in service file
sudo systemd-analyze verify /etc/systemd/system/pollingapi.service

# View detailed error
sudo journalctl -u pollingapi -n 50 --no-pager

# Try running manually
sudo -u paul /home/paul/pollingAPI/.venv/bin/gunicorn \
    -k uvicorn.workers.UvicornWorker \
    pollingapi.main:app \
    --bind 127.0.0.1:8000 \
    --workers 1
```

### 502 Bad Gateway (Nginx)

```bash
# Check if service is running
sudo systemctl status pollingapi

# Verify port is listening
sudo netstat -tlnp | grep 8000

# Check nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Permission Denied

```bash
# Fix ownership
sudo chown -R paul:paul /home/paul/pollingAPI

# Ensure log directory exists
mkdir -p /home/paul/pollingAPI/data/logs
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Renew manually
sudo certbot renew

# Test nginx config
sudo nginx -t
```

## Security Considerations

1. **Firewall**: Ensure only ports 80 and 443 are open to the public
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

2. **Environment Variables**: Keep sensitive data in `.env` file, not in code

3. **Regular Updates**: Keep system and dependencies updated
   ```bash
   sudo apt update && sudo apt upgrade -y
   cd /home/paul/pollingAPI && uv sync --upgrade
   ```

4. **Backups**: Regularly backup the SQLite database
   ```bash
   cp /home/paul/pollingAPI/data/polling.db /backup/polling-$(date +%Y%m%d).db
   ```

## Updates and Maintenance

### Update Application Code

```bash
cd /home/paul/pollingAPI
./deploy.sh
```

### Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
sudo systemctl restart pollingapi
```

### Renew SSL Certificate

Certificates auto-renew, but to force renewal:

```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

## Support

For issues or questions:
- Check logs: `sudo journalctl -u pollingapi -f`
- Health endpoint: `https://api.fasttrack29.com/health`
- API documentation: `https://api.fasttrack29.com/docs`
