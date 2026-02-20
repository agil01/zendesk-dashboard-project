# Zendesk Dashboard Skill

## Skill Overview

**Name**: Zendesk Real-Time Ticket Dashboard
**Purpose**: Monitor and report on Zendesk support tickets in real-time
**Type**: Project Skill
**Version**: 1.0.0

## Description

This skill provides comprehensive Zendesk ticket monitoring and reporting capabilities through multiple interfaces:

- **Web Dashboard**: Real-time browser-based monitoring
- **Terminal Monitor**: Command-line live dashboard
- **Report Generator**: Automated daily summaries
- **Executive Reports**: Print-ready stakeholder reports

## When to Use This Skill

Use this skill when you need to:

- ✅ Monitor Zendesk tickets in real-time
- ✅ Generate daily ticket summaries
- ✅ Create executive reports for stakeholders
- ✅ Track urgent ticket volumes and resolution rates
- ✅ Identify patterns in support requests
- ✅ Share live dashboard with team members

## Quick Invocation

### Command Format

```bash
# From anywhere on your system
~/zendesk-dashboard-project/scripts/start-dashboard.sh
```

### Alternative Commands

```bash
# Terminal monitor
~/zendesk-dashboard-project/scripts/start_monitor.sh

# Daily report
cd ~/zendesk-dashboard-project/scripts && python3 zendesk_daily_summary.py
```

## Skill Parameters

### Configuration Options

Edit `~/zendesk-dashboard-project/config/config.env`:

| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain | counterparthealth | any valid subdomain |
| `ZENDESK_EMAIL` | Your Zendesk email | anthony.gil@... | any valid email |
| `ZENDESK_API_TOKEN` | Your API token | (your token) | generate in Zendesk |
| `REFRESH_INTERVAL` | Auto-refresh seconds | 30 | 10-300 |
| `SERVER_PORT` | Web server port | 8080 | 1024-65535 |

### Runtime Options

```bash
# Custom refresh interval (terminal monitor)
~/zendesk-dashboard-project/scripts/start_monitor.sh 60

# Custom port (web dashboard)
SERVER_PORT=8081 ~/zendesk-dashboard-project/scripts/start-dashboard.sh
```

## Skill Outputs

### 1. Web Dashboard
- **URL**: http://localhost:8080
- **Format**: Interactive HTML
- **Updates**: Real-time auto-refresh
- **Features**: Clickable links, visual alerts, priority color-coding

### 2. Terminal Monitor
- **Output**: Terminal display
- **Format**: ASCII dashboard
- **Updates**: Auto-refresh with sound alerts
- **Log**: `zendesk_monitor_log.json` (on exit)

### 3. Daily Summary
- **File**: `zendesk_summary_YYYYMMDD.md`
- **Format**: Markdown
- **Content**: Statistics, ticket details, links

### 4. Executive Report
- **File**: `zendesk_executive_summary_print.html`
- **Format**: Print-ready HTML
- **Content**: Metrics, trends, recommendations

## Integration Examples

### Claude Code Skill Integration

```markdown
When user asks: "Show me today's Zendesk tickets"
Action: Launch ~/zendesk-dashboard-project/scripts/start-dashboard.sh
Result: Web dashboard opens with real-time data
```

### Automation Integration

```bash
# Daily cron job
59 23 * * * cd ~/zendesk-dashboard-project/scripts && python3 zendesk_daily_summary.py

# Slack integration (add webhook)
SLACK_WEBHOOK="https://hooks.slack.com/..." python3 zendesk_monitor.py
```

### API Integration

```python
# Use as module
import sys
sys.path.append('/Users/anthonygil/zendesk-dashboard-project/scripts')
from zendesk_server import ZendeskProxyHandler
```

## Sharing This Skill

### Share with Team Members

1. **Copy project folder**
   ```bash
   cp -r ~/zendesk-dashboard-project /shared/location/
   ```

2. **Share setup instructions**
   - Send `QUICKSTART.md`
   - Each user creates own `config/config.env`
   - Each user gets own Zendesk API token

3. **Network access (optional)**
   ```bash
   # Start server accessible to network
   python3 zendesk_server.py
   # Share: http://YOUR_IP:8080
   ```

### Version Control (GitHub, etc.)

```bash
cd ~/zendesk-dashboard-project
git init
git add .
git commit -m "Initial commit: Zendesk Dashboard Skill"
git remote add origin YOUR_REPO_URL
git push -u origin main
```

**Important**: `config/config.env` is git-ignored to protect credentials

## Customization Guide

### Modify Time Window

```python
# In scripts/zendesk_server.py or zendesk_monitor.py
# Change hours parameter
tickets = fetch_recent_tickets(hours=48)  # 48 hours instead of 24
```

### Add Custom Metrics

```python
# In calculate_stats() function
stats['access_requests'] = len([
    t for t in tickets
    if 'access' in t.get('subject', '').lower()
])
```

### Change Alert Conditions

```python
# In zendesk_monitor.py
if stats['urgent'] > 5 or stats['open'] > 20:
    send_alert()
```

### Custom Report Templates

```python
# In zendesk_daily_summary.py
def custom_template(tickets, stats):
    # Your custom report format
    return formatted_report
```

## Troubleshooting

See [README.md](README.md#troubleshooting) for detailed troubleshooting.

### Quick Fixes

```bash
# Server won't start (port in use)
kill $(lsof -ti:8080)

# No data showing
# Check credentials in config/config.env

# Updates not working
# Restart server: Ctrl+C then rerun script
```

## Skill Dependencies

```
Python 3.9+
requests>=2.31.0
```

Install with:
```bash
pip3 install -r ~/zendesk-dashboard-project/requirements.txt
```

## Skill Maintenance

### Update Credentials

```bash
nano ~/zendesk-dashboard-project/config/config.env
```

### Upgrade Skill

```bash
cd ~/zendesk-dashboard-project
git pull  # if using version control
```

### Backup Configuration

```bash
cp config/config.env config/config.env.backup
```

## Skill Metadata

```yaml
skill:
  name: zendesk-dashboard
  version: 1.0.0
  author: Counterpart Health
  created: 2026-02-19
  updated: 2026-02-19
  category: Monitoring & Reporting
  tags:
    - zendesk
    - monitoring
    - dashboard
    - support-tickets
    - real-time
    - reporting
  location: ~/zendesk-dashboard-project
  main_script: scripts/start-dashboard.sh
  config_file: config/config.env
```

## Support & Documentation

- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **Full Documentation**: [README.md](README.md)
- **Zendesk API Docs**: https://developer.zendesk.com/api-reference/

---

**Skill Status**: ✅ Active
**Last Verified**: 2026-02-19
**Compatibility**: macOS, Linux, Windows (with WSL)
