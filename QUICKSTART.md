# Quick Start Guide

Get up and running in 60 seconds.

## First Time Setup (One Time Only)

```bash
# 1. Navigate to project
cd ~/zendesk-dashboard-project

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Configure (credentials already set)
# Your config is ready in config/config.env
```

## Launch Dashboard (Every Time)

### Option 1: Web Dashboard (Recommended)
```bash
cd ~/zendesk-dashboard-project/scripts
python3 zendesk_server.py
```
Then open: **http://localhost:8080**

### Option 2: Terminal Monitor
```bash
cd ~/zendesk-dashboard-project/scripts
./start_monitor.sh
```

### Option 3: Generate Report
```bash
cd ~/zendesk-dashboard-project/scripts
python3 zendesk_daily_summary.py
```

## Stop Server

```bash
# Find and kill the server
kill $(lsof -ti:8080)
```

## Common Tasks

### Share Dashboard with Team
```bash
# Find your IP address
ifconfig | grep "inet " | grep -v 127.0.0.1

# Share this URL with your team:
# http://YOUR_IP:8080
```

### Change Refresh Interval
```bash
# Edit config/config.env
nano config/config.env
# Change REFRESH_INTERVAL=30 to desired seconds
```

### Update Credentials
```bash
# Edit config/config.env
nano config/config.env
# Update ZENDESK_EMAIL and ZENDESK_API_TOKEN
```

## That's It!

For detailed documentation, see [README.md](README.md)
