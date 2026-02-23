# Zendesk Real-Time Ticket Dashboard

A comprehensive suite of tools for monitoring, reporting, and analyzing Zendesk support tickets in real-time.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Tools Included](#tools-included)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

---

## Overview

This project provides multiple interfaces for monitoring Zendesk tickets:
- **🤖 MCP Server**: AI-powered Zendesk integration for Claude Code (NEW!)
- **Web Dashboard**: Real-time browser-based monitoring with auto-refresh
- **Terminal Monitor**: Command-line dashboard with live updates and alerts
- **Daily Reports**: Automated markdown and HTML reports
- **Executive Summaries**: Print-ready reports for stakeholders

---

## Features

### ✨ Key Capabilities

- **🤖 AI Integration**: Natural language Zendesk queries via Claude Code MCP
- **Real-time Monitoring**: Auto-refreshing dashboards (configurable intervals)
- **Visual Analytics**: Interactive charts showing ticket trends by hour and channel distribution
- **Visual Alerts**: Instant notifications for new urgent tickets
- **Priority Tracking**: Color-coded priority levels (Urgent, High, Normal, Low)
- **Status Analytics**: Track resolution rates and ticket status
- **Channel Insights**: Visualize ticket sources (API, Email, Web, Mobile, Chat)
- **Executive Reporting**: Professional print-ready reports
- **Multi-Interface**: MCP, web, terminal, and document outputs
- **Easy Sharing**: Share with team members via local network

---

## Quick Start

### 1. One-Time Setup
```bash
cd ~/zendesk-dashboard-project
pip3 install -r requirements.txt
cp config/config.example.env config/config.env
# Edit config/config.env with your credentials
```

### 2. **NEW!** Use with Claude Code MCP
The easiest way to interact with Zendesk - use natural language:
```
Show me all urgent Zendesk tickets
Search Zendesk for "access request"
Create a summary of today's tickets
```

**Setup Guide**: See [MCP_QUICKSTART.md](MCP_QUICKSTART.md) ✨

### 3. Or Start Web Dashboard
```bash
cd scripts
python3 zendesk_server.py
# Open http://localhost:8080
```

### 4. Or Start Terminal Monitor
```bash
cd scripts
./start_monitor.sh
```

---

## Tools Included

### 1. **🤖 MCP Server** (NEW!)

AI-powered Zendesk integration for Claude Code.

**Features:**
- Natural language queries
- Real-time ticket data
- Automated report generation
- Smart search and filtering
- Ticket monitoring and alerts

**Usage:**
```
Just ask Claude in natural language:
- "Show urgent Zendesk tickets"
- "Search for access requests"
- "Generate today's ticket summary"
```

**Setup:**
See [MCP_QUICKSTART.md](MCP_QUICKSTART.md) for installation and usage.

---

### 2. **Web Dashboard** (`zendesk_server.py`)

Real-time web interface with professional UI.

**Features:**
- Auto-refresh every 30 seconds (configurable)
- Visual metrics cards
- Interactive charts:
  - Tickets by Hour of Day (line chart)
  - Tickets by Channel (doughnut chart with API, Email, Web, etc.)
- Active urgent tickets list
- Clickable links to Zendesk
- Pause/resume controls
- Custom refresh intervals

**Usage:**
```bash
python3 scripts/zendesk_server.py
```

Access at: http://localhost:8080

**Configuration:**
- Port: Set `SERVER_PORT` in config.env
- Refresh: Set `REFRESH_INTERVAL` in config.env

---

### 3. **Terminal Monitor** (`zendesk_monitor.py`)

Command-line real-time dashboard.

**Features:**
- Live terminal interface
- Sound alerts for new tickets
- Status and priority change tracking
- Top requesters analysis
- Saves state on exit

**Usage:**
```bash
# Using launcher script
./scripts/start_monitor.sh

# Direct with custom interval (60 seconds)
./scripts/start_monitor.sh 60

# Manual
python3 scripts/zendesk_monitor.py
```

**Stop:** Press `Ctrl+C`

**Output:** Creates `zendesk_monitor_log.json` on exit

---

### 4. **Daily Summary Generator** (`zendesk_daily_summary.py`)

Generate markdown reports of daily tickets.

**Features:**
- Summary statistics
- Priority/status breakdown
- Full ticket details
- Formatted for readability

**Usage:**
```bash
python3 scripts/zendesk_daily_summary.py
```

**Output:** `zendesk_summary_YYYYMMDD.md`

---

### 5. **Weekly Agent Reports** (`generate_weekly_reports.py`)

Automated weekly reports for individual agents and team comparative analysis.

**Features:**
- Individual agent reports (Candice, Ron, Bola)
- Team comparative summary with workload distribution
- Visual bar charts comparing agent ticket loads
- Automated insights and recommendations
- Priority actions based on team metrics
- Scheduled automation via cron (Monday 8:00 AM CST)

**Usage:**
```bash
# Generate reports now
python3 scripts/generate_weekly_reports.py

# Setup automated Monday delivery
./scripts/setup_weekly_reports.sh
```

**Output:** 4 HTML reports in `~/Desktop/Weekly_Zendesk_Reports/`
- 3 individual agent reports
- 1 team comparative summary

**Documentation:** See [WEEKLY_REPORTS_SETUP.md](WEEKLY_REPORTS_SETUP.md)

---

### 6. **Executive Summary Generator** (`generate_executive_summary.py`)

Comprehensive executive summary reports for any date range.

**Features:**
- High-level KPIs and metrics
- Team performance analysis
- SLA compliance tracking
- Brand distribution (Clover Health vs Counterpart Health)
- Channel analysis
- One-touch resolution metrics
- Automated insights and trends
- Strategic recommendations
- Print-ready HTML format

**Usage:**
```bash
# Generate for specific date range
python3 scripts/generate_executive_summary.py 2026-02-16 2026-02-22

# Generate for last week (automatic)
python3 scripts/generate_executive_summary.py
```

**Output:** HTML report in `~/Desktop/Claude Files/`

**Documentation:** See [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)

---

## Installation

### Prerequisites
- Python 3.9+
- pip (Python package manager)
- Internet connection

### Step-by-Step

1. **Clone or Copy Project**
```bash
cd ~
# Project is already in ~/zendesk-dashboard-project
```

2. **Install Dependencies**
```bash
cd zendesk-dashboard-project
pip3 install -r requirements.txt
```

3. **Configure Credentials**
```bash
cp config/config.example.env config/config.env
nano config/config.env  # or use your preferred editor
```

4. **Make Scripts Executable**
```bash
chmod +x scripts/*.sh
```

---

## Configuration

### Environment Variables

Edit `config/config.env`:

```bash
# Zendesk Connection
ZENDESK_SUBDOMAIN=counterparthealth     # Your Zendesk subdomain
ZENDESK_EMAIL=your.email@company.com    # Your Zendesk email
ZENDESK_API_TOKEN=your_token_here       # Your API token

# Dashboard Settings
REFRESH_INTERVAL=30                      # Auto-refresh interval (seconds)
SERVER_PORT=8080                         # Web server port
```

### Getting Your API Token

1. Log into Zendesk
2. Go to **Admin** → **Channels** → **API**
3. Enable **Token Access**
4. Click **Add API Token**
5. Copy the token to `config/config.env`

### Loading Configuration

All scripts automatically load from `config/config.env`. To use manually:

```bash
source config/config.env
python3 scripts/zendesk_server.py
```

---

## Usage

### Web Dashboard

**Start Server:**
```bash
cd ~/zendesk-dashboard-project/scripts
python3 zendesk_server.py
```

**Access:**
- Local: http://localhost:8080
- Network: http://YOUR_IP:8080 (share with team)

**Controls:**
- 🔄 **Refresh Now**: Immediate update
- ⏸️ **Pause Auto-Refresh**: Stop/resume updates
- ⏱️ **Change Interval**: Adjust refresh timing

**Features:**
- Green pulsing dot = Live connection
- Red banner alerts = New tickets detected
- Click ticket ID = Open in Zendesk

---

### Terminal Monitor

**Start:**
```bash
cd ~/zendesk-dashboard-project/scripts
./start_monitor.sh
```

**Custom Interval:**
```bash
./start_monitor.sh 60  # Refresh every 60 seconds
```

**What You'll See:**
- 📊 Overview: Total, open, pending, solved counts
- 🔥 Priority: Breakdown by urgency
- 🚨 New Tickets: Alerts with sound
- 📝 Status Changes: Real-time updates
- 🔴 Active Urgent: List of open urgent tickets

**Stop:** Press `Ctrl+C`

---

### Daily Reports

**Generate Summary:**
```bash
cd ~/zendesk-dashboard-project/scripts
python3 zendesk_daily_summary.py
```

**Output Files:**
- `zendesk_summary_YYYYMMDD.md` - Markdown report
- Saved in current directory

**Contents:**
- Total ticket count
- Priority distribution
- Status breakdown
- Detailed ticket list with links

---

### Executive Reports

**Create Print-Ready Report:**
```bash
cd ~/zendesk-dashboard-project/scripts
python3 zendesk_daily_summary.py
# Then convert to HTML using your preferred method
```

**Or use the web dashboard:**
1. Start web server
2. Open browser to http://localhost:8080
3. Take screenshot or print page (Cmd+P / Ctrl+P)
4. Save as PDF

---

## Customization

### Modify Time Window

Change monitoring period in scripts:

```python
# In zendesk_monitor.py or zendesk_server.py
tickets = fetch_recent_tickets(hours=24)  # Change to 12, 48, 72, etc.
```

### Change Alert Thresholds

```python
# In zendesk_monitor.py
if stats['urgent'] > 3:  # Alert when more than 3 urgent tickets
    print(self.alert_sound)
```

### Add Custom Metrics

```python
# In calculate_stats() function
stats['custom_metric'] = len([t for t in tickets if t.get('custom_field')])
```

### Change Dashboard Colors

Edit CSS in `zendesk_server.py`:

```css
.urgent { color: #ef4444; }  /* Red */
.high { color: #f59e0b; }    /* Orange */
.normal { color: #3b82f6; }  /* Blue */
.low { color: #22c55e; }     /* Green */
```

### Export Formats

Add to `zendesk_daily_summary.py`:

```python
# JSON export
import json
with open('tickets.json', 'w') as f:
    json.dump(tickets, f, indent=2)

# CSV export
import csv
with open('tickets.csv', 'w') as f:
    writer = csv.DictWriter(f, fieldnames=['id', 'subject', 'status'])
    writer.writeheader()
    writer.writerows(tickets)
```

---

## Troubleshooting

### Web Dashboard Not Loading

**Issue:** Browser shows loading spinner indefinitely

**Solutions:**
1. Check server is running: `lsof -ti:8080`
2. Verify no CORS errors in browser console (F12)
3. Try different browser
4. Restart server: `kill $(lsof -ti:8080) && python3 scripts/zendesk_server.py`

---

### "Address Already in Use" Error

**Issue:** Server won't start on port 8080

**Solution:**
```bash
# Kill existing process
kill $(lsof -ti:8080)

# Or use different port
export SERVER_PORT=8081
python3 scripts/zendesk_server.py
```

---

### "Authentication Failed"

**Issue:** API calls return 401 error

**Solutions:**
1. Verify API token in `config/config.env`
2. Regenerate token in Zendesk (Admin → API)
3. Check email address is correct
4. Ensure token has proper permissions

---

### No Tickets Found

**Issue:** Dashboard shows 0 tickets

**Solutions:**
1. Verify tickets exist in Zendesk for today
2. Check time window in script (default: 24 hours)
3. Expand time window: `hours=48` in code
4. Test API manually:
```bash
curl -u "$ZENDESK_EMAIL/token:$ZENDESK_API_TOKEN" \
  "https://$ZENDESK_SUBDOMAIN.zendesk.com/api/v2/tickets.json"
```

---

### Terminal Monitor Not Updating

**Issue:** Monitor shows old data

**Solutions:**
1. Press `Ctrl+C` and restart
2. Check internet connection
3. Verify Zendesk API is accessible
4. Check `zendesk_monitor_log.json` for errors

---

## Security

### Best Practices

1. **Never Commit Credentials**
   - `config/config.env` is in `.gitignore`
   - Only share `config.example.env`

2. **Rotate API Tokens Regularly**
   ```bash
   # In Zendesk: Admin → API → Delete old token → Create new
   ```

3. **Use Environment Variables in Production**
   ```bash
   export ZENDESK_API_TOKEN=$(security find-generic-password -s zendesk -w)
   ```

4. **Restrict Network Access**
   ```python
   # In zendesk_server.py, change 'localhost' to '127.0.0.1'
   server = HTTPServer(('127.0.0.1', port), ZendeskProxyHandler)
   ```

5. **Use HTTPS in Production**
   - Deploy behind reverse proxy (nginx, Caddy)
   - Use SSL certificates

### Sharing with Team

**Safe Sharing:**
1. Share entire project directory (credentials excluded)
2. Each user creates their own `config/config.env`
3. Each user gets their own Zendesk API token

**Network Sharing:**
```bash
# Find your IP
ifconfig | grep "inet "

# Start server (accessible to network)
python3 scripts/zendesk_server.py
# Share: http://YOUR_IP:8080
```

**Security Note:** Only share on trusted networks (VPN, corporate network)

---

## Advanced Usage

### Automated Daily Reports

**Via Cron (macOS/Linux):**
```bash
# Edit crontab
crontab -e

# Add line (runs daily at 11:59 PM)
59 23 * * * cd ~/zendesk-dashboard-project/scripts && python3 zendesk_daily_summary.py
```

### Docker Deployment

**Create Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY scripts/ scripts/
CMD ["python3", "scripts/zendesk_server.py"]
```

**Build and Run:**
```bash
docker build -t zendesk-dashboard .
docker run -p 8080:8080 --env-file config/config.env zendesk-dashboard
```

### Integration with Slack

Add to `zendesk_monitor.py`:

```python
import requests

def send_slack_alert(message):
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    requests.post(webhook_url, json={'text': message})

# In detect_changes():
if changes['new_tickets']:
    send_slack_alert(f"🚨 {len(changes['new_tickets'])} new urgent tickets!")
```

---

## Project Structure

```
zendesk-dashboard-project/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignore rules
├── config/
│   ├── config.env           # Your credentials (git-ignored)
│   └── config.example.env   # Template for sharing
├── scripts/
│   ├── zendesk_server.py    # Web dashboard server
│   ├── zendesk_monitor.py   # Terminal monitor
│   ├── zendesk_daily_summary.py  # Report generator
│   └── start_monitor.sh     # Launcher script
└── docs/
    └── (future documentation)
```

---

## Contributing

### Adding New Features

1. Create feature branch
2. Test thoroughly
3. Update documentation
4. Submit for review

### Reporting Issues

Include:
- Error messages
- Steps to reproduce
- Environment (OS, Python version)
- Configuration (sanitized)

---

## Changelog

### Version 1.0.0 (2026-02-19)
- Initial release
- Web dashboard
- Terminal monitor
- Daily summary generator
- Executive reports
- Multi-format outputs

---

## Support

### Resources
- Zendesk API Docs: https://developer.zendesk.com/api-reference/
- Python Requests: https://requests.readthedocs.io/

### Getting Help
1. Check troubleshooting section
2. Review Zendesk API documentation
3. Check browser/terminal for error messages
4. Verify credentials and configuration

---

## License

Internal use - Counterpart Health

---

## Credits

**Built for**: Counterpart Health
**Date**: February 2026
**Version**: 1.0.0

---

## Quick Reference Card

### Most Common Commands

```bash
# Start web dashboard
python3 scripts/zendesk_server.py

# Start terminal monitor
./scripts/start_monitor.sh

# Generate daily report
python3 scripts/zendesk_daily_summary.py

# Check if server is running
lsof -ti:8080

# Stop server
kill $(lsof -ti:8080)

# View logs
tail -f /private/tmp/claude-*/tasks/*.output
```

### URLs

- **Dashboard**: http://localhost:8080
- **API Test**: http://localhost:8080/api/tickets

---

**Happy Monitoring! 🎯**
