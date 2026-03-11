# Systemd Timer Setup

This runs the polling pipeline daily at 6am UTC.

## Installation

```bash
# Copy service and timer files
sudo cp pollingapi-scheduler.service /etc/systemd/system/
sudo cp pollingapi-scheduler.timer /etc/systemd/system/

# Enable and start
sudo systemctl enable --now pollingapi-scheduler.timer

# Check status
sudo systemctl status pollingapi-scheduler.timer

# View next run time
sudo systemctl list-timers
```

## Manual Run

```bash
# Run pipeline manually
sudo systemctl start pollingapi-scheduler.service

# View logs
sudo journalctl -u pollingapi-scheduler.service -f
```

## Configuration

To change the run time, edit `pollingapi-scheduler.timer`:
```
OnCalendar=*-*-* 06:00:00  # Change hour here
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart pollingapi-scheduler.timer
```
