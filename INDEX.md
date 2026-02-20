# Zendesk Dashboard Project - Index

**Project**: Zendesk Real-Time Ticket Dashboard
**Version**: 1.0.0
**Status**: ✅ Active & Verified
**Location**: `~/zendesk-dashboard-project`

---

## 📚 Documentation

| Document | Purpose | Best For |
|----------|---------|----------|
| **[QUICKSTART.md](QUICKSTART.md)** | Get started in 60 seconds | First-time users |
| **[README.md](README.md)** | Complete documentation | Reference & deep-dive |
| **[SKILL.md](SKILL.md)** | Skill integration guide | Sharing & automation |
| **[INDEX.md](INDEX.md)** | This file - navigation hub | Finding what you need |

---

## 🚀 Quick Launch

### Most Common Actions

```bash
# 1. Start Web Dashboard (RECOMMENDED)
cd ~/zendesk-dashboard-project
./scripts/start-dashboard.sh
# Opens: http://localhost:8080

# 2. Start Terminal Monitor
cd ~/zendesk-dashboard-project
./scripts/start_monitor.sh

# 3. Generate Daily Report
cd ~/zendesk-dashboard-project/scripts
python3 zendesk_daily_summary.py
```

---

## 📁 Project Structure

```
zendesk-dashboard-project/
│
├── 📄 README.md                    # Full documentation
├── 📄 QUICKSTART.md                # 60-second setup guide
├── 📄 SKILL.md                     # Skill integration guide
├── 📄 INDEX.md                     # This file
├── 📄 requirements.txt             # Python dependencies
├── 📄 .gitignore                   # Git ignore rules
├── 🔧 verify-setup.sh              # Setup verification script
│
├── 📁 config/
│   ├── config.env                  # Your credentials (git-ignored)
│   └── config.example.env          # Template for sharing
│
├── 📁 scripts/
│   ├── zendesk_server.py           # Web dashboard server
│   ├── zendesk_monitor.py          # Terminal monitor
│   ├── zendesk_daily_summary.py    # Report generator
│   ├── start-dashboard.sh          # Web dashboard launcher
│   └── start_monitor.sh            # Terminal monitor launcher
│
└── 📁 docs/
    └── (future documentation)
```

---

## 🛠️ Tools Reference

### 1. Web Dashboard (`zendesk_server.py`)

**Purpose**: Real-time browser-based monitoring

**Launch**:
```bash
./scripts/start-dashboard.sh
```

**Access**: http://localhost:8080

**Features**:
- Auto-refresh (30s default)
- Visual metrics cards
- Urgent ticket alerts
- Clickable Zendesk links
- Pause/resume controls

**When to use**:
- Continuous monitoring
- Team visibility (share URL)
- Executive demos

---

### 2. Terminal Monitor (`zendesk_monitor.py`)

**Purpose**: Command-line real-time dashboard

**Launch**:
```bash
./scripts/start_monitor.sh [interval_seconds]
```

**Features**:
- Live ASCII dashboard
- Sound alerts
- Status change tracking
- Top requesters analysis

**When to use**:
- No GUI environment
- Quick status checks
- Development/debugging

---

### 3. Daily Summary (`zendesk_daily_summary.py`)

**Purpose**: Generate markdown reports

**Launch**:
```bash
python3 scripts/zendesk_daily_summary.py
```

**Output**: `zendesk_summary_YYYYMMDD.md`

**When to use**:
- Daily reporting
- Email summaries
- Documentation
- Historical records

---

## ⚙️ Configuration

### Main Config File: `config/config.env`

```bash
ZENDESK_SUBDOMAIN=counterparthealth
ZENDESK_EMAIL=anthony.gil@counterparthealth.com
ZENDESK_API_TOKEN=your_token_here
REFRESH_INTERVAL=30
SERVER_PORT=8080
```

### Edit Configuration

```bash
nano ~/zendesk-dashboard-project/config/config.env
```

### Get New API Token

1. Login to Zendesk
2. Admin → Channels → API
3. Enable Token Access
4. Add API Token
5. Update `config/config.env`

---

## 🔧 Common Tasks

### Verify Setup

```bash
cd ~/zendesk-dashboard-project
./verify-setup.sh
```

### Stop Web Server

```bash
kill $(lsof -ti:8080)
```

### Check if Server Running

```bash
lsof -ti:8080
```

### Share with Team

```bash
# Find your IP
ifconfig | grep "inet " | grep -v 127.0.0.1

# Share: http://YOUR_IP:8080
```

### Update Dependencies

```bash
pip3 install -r requirements.txt --upgrade
```

### Backup Configuration

```bash
cp config/config.env config/config.env.backup
```

---

## 📊 What Each Tool Shows

### Web Dashboard View

```
┌────────────────────────────────────────┐
│ 📊 Key Metrics                         │
│ • Total Tickets: 16                    │
│ • Resolution Rate: 62.5%               │
│ • Urgent: 4 (4 active)                 │
│ • Open: 6                              │
├────────────────────────────────────────┤
│ 🔥 Priority Breakdown                  │
│ 🔴 Urgent: 4                           │
│ 🟡 Normal: 11                          │
│ 🟢 Low: 1                              │
├────────────────────────────────────────┤
│ 🔴 Active Urgent Tickets               │
│ #4010 - Lindsay Orrok                  │
│ #4009 - Suleika Rosario                │
│ #4004 - Precious Raymundo              │
│ #4002 - Aiza Cruz                      │
├────────────────────────────────────────┤
│ 📋 Recent Tickets (Last 10)            │
│ [Detailed ticket list...]              │
└────────────────────────────────────────┘
```

### Terminal Monitor View

```
================================================================================
🎯 ZENDESK REAL-TIME MONITOR - counterparthealth.zendesk.com
⏰ Last Update: 2026-02-19 14:30:45
================================================================================

📊 OVERVIEW (Last 24 Hours)
├─ Total Tickets: 16
├─ New: 1 | Open: 4 | Pending: 1
└─ Solved: 10 | Closed: 0

🔥 PRIORITY DISTRIBUTION
├─ 🔴 Urgent: 4
├─ ⚪ High: 0
├─ 🟡 Normal: 11
└─ 🟢 Low: 1

🚨 NEW TICKETS DETECTED (1)
├─ [4010] Counterpart Assistant Access Request...
│  Priority: URGENT | Created: 07:57 PM UTC
```

---

## 🤝 Sharing & Collaboration

### Share Project with Teammate

1. **Copy project folder**
   ```bash
   cp -r ~/zendesk-dashboard-project /shared/location/
   ```

2. **Teammate setup**
   ```bash
   cd /shared/location/zendesk-dashboard-project
   cp config/config.example.env config/config.env
   nano config/config.env  # Add their credentials
   ./verify-setup.sh
   ```

3. **Run dashboard**
   ```bash
   ./scripts/start-dashboard.sh
   ```

### Network Sharing

```bash
# Start server (accessible to local network)
./scripts/start-dashboard.sh

# Share URL: http://YOUR_IP:8080
# Find IP: ifconfig | grep "inet " | grep -v 127.0.0.1
```

**Security Note**: Only share on trusted networks

---

## 🔍 Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Port 8080 in use | `kill $(lsof -ti:8080)` |
| No data showing | Check `config/config.env` credentials |
| Authentication failed | Regenerate API token in Zendesk |
| Dashboard not loading | Check browser console (F12) |
| Server won't start | Run `./verify-setup.sh` |

**Full Troubleshooting**: See [README.md - Troubleshooting](README.md#troubleshooting)

---

## 📈 Usage Patterns

### For Daily Monitoring

```bash
# Morning: Start web dashboard
./scripts/start-dashboard.sh
# Leave running all day, check periodically

# Evening: Generate summary
python3 scripts/zendesk_daily_summary.py
```

### For Incident Response

```bash
# Quick check
./scripts/start_monitor.sh

# If issues found, switch to web dashboard
./scripts/start-dashboard.sh
```

### For Reporting

```bash
# Generate daily summary
python3 scripts/zendesk_daily_summary.py

# Create executive report
# Open web dashboard, print to PDF (Cmd+P)
```

---

## 🎯 Next Steps

### Getting Started (First Time)
1. ✅ Read [QUICKSTART.md](QUICKSTART.md)
2. ✅ Run `./verify-setup.sh`
3. ✅ Launch `./scripts/start-dashboard.sh`

### Daily Usage
1. Start dashboard in morning
2. Monitor throughout day
3. Generate summary at end of day

### Customization
1. Read [README.md - Customization](README.md#customization)
2. Modify time windows, metrics, or alerts
3. Add integrations (Slack, etc.)

### Sharing
1. Read [SKILL.md](SKILL.md)
2. Share project folder with team
3. Set up network access if needed

---

## 📞 Quick Help

**Can't find something?**
- Check this INDEX.md (you are here)
- See [QUICKSTART.md](QUICKSTART.md) for basics
- See [README.md](README.md) for details
- See [SKILL.md](SKILL.md) for sharing

**Something not working?**
- Run `./verify-setup.sh`
- Check [README.md - Troubleshooting](README.md#troubleshooting)
- Verify credentials in `config/config.env`

**Want to customize?**
- See [README.md - Customization](README.md#customization)
- All scripts are in `scripts/` directory
- Config in `config/config.env`

---

## 📌 Bookmarks

### Essential URLs
- **Dashboard**: http://localhost:8080
- **API Test**: http://localhost:8080/api/tickets
- **Zendesk**: https://counterparthealth.zendesk.com

### Essential Files
- **Config**: `~/zendesk-dashboard-project/config/config.env`
- **Logs**: `/private/tmp/claude-*/tasks/*.output`
- **Reports**: Generated in current directory

### Essential Commands
```bash
# Start dashboard
~/zendesk-dashboard-project/scripts/start-dashboard.sh

# Stop server
kill $(lsof -ti:8080)

# Verify setup
~/zendesk-dashboard-project/verify-setup.sh
```

---

## 📝 Version Info

| Item | Value |
|------|-------|
| **Version** | 1.0.0 |
| **Created** | 2026-02-19 |
| **Status** | ✅ Active |
| **Python** | 3.9+ |
| **Platform** | macOS, Linux, Windows (WSL) |

---

**🎉 You're all set! Start with [QUICKSTART.md](QUICKSTART.md) for a 60-second tour.**
