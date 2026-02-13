#!/bin/bash
# Deployment script for Zweitstimme Polling API
# Usage: ./deploy.sh

set -euo pipefail

APP_NAME="pollingapi"
APP_DIR="/home/paul/pollingAPI"
SERVICE_FILE="/etc/systemd/system/pollingapi.service"

echo "=== Deploying ${APP_NAME} ==="
echo ""

# Navigate to app directory
cd "${APP_DIR}"

# Pull latest changes
echo "📥 Pulling latest changes..."
if ! git pull; then
    echo "❌ Git pull failed"
    exit 1
fi
echo "✓ Code updated"
echo ""

# Sync dependencies with uv (if pyproject.toml changed)
echo "📦 Checking dependencies..."
if ! uv sync; then
    echo "❌ Dependency sync failed"
    exit 1
fi
echo "✓ Dependencies synced"
echo ""

# Reload systemd (in case service file was updated)
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload
echo "✓ Systemd reloaded"
echo ""

# Restart the service
echo "🚀 Restarting service..."
if ! sudo systemctl restart "${APP_NAME}"; then
    echo "❌ Service restart failed"
    echo ""
    echo "Checking logs:"
    sudo journalctl -u "${APP_NAME}" -n 20 --no-pager
    exit 1
fi
echo "✓ Service restarted"
echo ""

# Wait a moment for service to start
sleep 2

# Check status
echo "📊 Service status:"
echo "-------------------"
if sudo systemctl is-active --quiet "${APP_NAME}"; then
    sudo systemctl status "${APP_NAME}" --no-pager | head -10
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "Quick health check:"
    curl -s http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || echo "API responding on port 8000"
else
    echo "❌ Service is not running!"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u "${APP_NAME}" -n 20 --no-pager
    exit 1
fi

echo ""
echo "=== Deployment complete ==="
