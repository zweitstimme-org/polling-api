# Systemd Setup

This runs the polling pipeline daily at 6am UTC via systemd timers.

## Files

| File | Purpose |
|------|---------|
| `pollingapi.service` | API server (runs continuously) |
| `pollingapi-scheduler.service` | Pipeline runner (triggered by timer) |
| `pollingapi-scheduler.timer` | Timer (runs daily at 6am) |

## Installation

```bash
# Copy all service files
sudo cp pollingapi.service /etc/systemd/system/
sudo cp pollingapi-scheduler.service /etc/systemd/system/
sudo cp pollingapi-scheduler.timer /etc/systemd/system/

# Enable and start API server
sudo systemctl enable --now pollingapi

# Enable and start scheduler
sudo systemctl enable --now pollingapi-scheduler.timer
```

## Commands

```bash
# Check timer status
sudo systemctl status pollingapi-scheduler.timer

# View next run time
sudo systemctl list-timers

# Run pipeline manually
sudo systemctl start pollingapi-scheduler.service

# View pipeline logs
tail -f /home/paul/pollingAPI/data/logs/pipeline.log
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
