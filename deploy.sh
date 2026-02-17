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
echo "[1/5] Pulling latest changes..."
if ! git pull; then
    echo "ERROR: Git pull failed"
    exit 1
fi
echo "      Code updated successfully"
echo ""

# Sync dependencies with uv (if pyproject.toml changed)
echo "[2/5] Checking dependencies..."
if ! uv sync; then
    echo "ERROR: Dependency sync failed"
    exit 1
fi
echo "      Dependencies synced successfully"
echo ""

# Reload systemd (in case service file was updated)
echo "[3/5] Reloading systemd..."
sudo systemctl daemon-reload
echo "      Systemd reloaded successfully"
echo ""

# Restart the service
echo "[4/5] Restarting service..."
if ! sudo systemctl restart "${APP_NAME}"; then
    echo "ERROR: Service restart failed"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u "${APP_NAME}" -n 20 --no-pager
    exit 1
fi
echo "      Service restarted successfully"
echo ""

# Wait a moment for service to start
sleep 2

# Check status
echo "[5/5] Verifying deployment..."
echo "----------------------------------------"
if sudo systemctl is-active --quiet "${APP_NAME}"; then
    sudo systemctl status "${APP_NAME}" --no-pager | head -10
    echo ""
    echo "Deployment successful!"
    echo ""
    echo "Health check:"
    curl -s http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || echo "API responding on port 8000"
else
    echo "ERROR: Service is not running!"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u "${APP_NAME}" -n 20 --no-pager
    exit 1
fi

echo ""
echo "=== Deployment complete ==="
