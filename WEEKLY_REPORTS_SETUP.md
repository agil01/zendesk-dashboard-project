# Weekly Zendesk Reports - Automation Guide

Automatically generate and deliver weekly ticket reports for Candice Brown, Ron Pineda, and Bola Kuye every Monday at 8:00 AM CST.

---

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
cd ~/zendesk-dashboard-project/scripts
./setup_weekly_reports.sh
```

This will:
- Configure a cron job to run every Monday at 8:00 AM CST
- Save reports to `~/Desktop/Weekly_Zendesk_Reports/`
- Log output to `~/Desktop/weekly_reports.log`

### Option 2: Manual Test Run

```bash
cd ~/zendesk-dashboard-project/scripts
./generate_weekly_reports.py
```

This generates reports immediately without scheduling.

---

## What Gets Generated

Each Monday at 8:00 AM CST, the system automatically creates:

**For Each Agent (Candice, Ron, Bola):**
- HTML report with ticket summary
- Statistics dashboard
- Complete ticket list with priorities
- Saved to: `~/Desktop/Weekly_Zendesk_Reports/[Agent_Name]_Weekly_Report_YYYY-MM-DD.html`

**Team Comparative Summary:**
- Side-by-side comparison of all three agents
- Workload distribution visualization
- Team totals and averages
- Insights and recommendations
- Priority actions
- Saved to: `~/Desktop/Weekly_Zendesk_Reports/TEAM_SUMMARY_Comparative_Report_YYYY-MM-DD.html`

**Example Files:**
```
~/Desktop/Weekly_Zendesk_Reports/
├── TEAM_SUMMARY_Comparative_Report_2026-02-24.html  ⭐ NEW!
├── Candice_Brown_Weekly_Report_2026-02-24.html
├── Ron_Pineda_Weekly_Report_2026-02-24.html
└── Bola_Kuye_Weekly_Report_2026-02-24.html
```

---

## Features

### Individual Agent Reports Include:
- ✅ Total open tickets count
- ✅ Priority breakdown (Urgent, High, Normal, Low)
- ✅ Status breakdown (Pending, On Hold)
- ✅ Average ticket age
- ✅ Oldest ticket age
- ✅ Complete ticket list with:
  - Ticket ID
  - Priority (color-coded)
  - Subject
  - Status
  - Days open

### Team Comparative Summary Includes:
- 📊 **Workload Distribution** - Visual bar chart comparing ticket counts
- 📈 **Side-by-Side Comparison** - All agents in one table
- 🎯 **Team Totals** - Combined statistics across all agents
- 💡 **Insights & Recommendations** - Automated alerts for:
  - High urgent ticket counts
  - Workload imbalances
  - Aged tickets requiring attention
- ⚡ **Priority Actions** - Actionable recommendations for team
- 📉 **Agent Highlights** - Notable items for each agent

### Automation Features:
- 🔄 Runs automatically every Monday at 8:00 AM CST
- 📊 Generates 4 reports total (3 individual + 1 comparative)
- 💾 Saves to Desktop for easy access
- 📝 Logs all activity for troubleshooting
- 🖨️ Print-ready HTML format
- 🔔 Smart alerts for workload imbalances and urgent tickets

---

## Schedule Details

**When:** Every Monday at 8:00 AM CST/CDT
**Cron Schedule:** `0 13 * * 1` (13:00 UTC = 8:00 AM CDT)

> **Note:** The time automatically adjusts for daylight saving time since it's configured in UTC.

---

## Management Commands

### View Current Cron Jobs
```bash
crontab -l
```

### Remove Automated Reports
```bash
crontab -l | grep -v 'generate_weekly_reports.py' | crontab -
```

### View Recent Logs
```bash
tail -f ~/Desktop/weekly_reports.log
```

### Test Script Manually
```bash
cd ~/zendesk-dashboard-project/scripts
./generate_weekly_reports.py
```

---

## Email Delivery (Optional)

To automatically email the reports, use the email-enabled version:

### 1. Install Required Package
```bash
pip3 install --user python-dotenv
```

### 2. Configure Email Settings

Create `~/zendesk-dashboard-project/scripts/.env`:
```bash
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO_CANDICE=candice.brown@counterparthealth.com
EMAIL_TO_RON=ron.pineda@counterparthealth.com
EMAIL_TO_BOLA=bola.kuye@counterparthealth.com
```

### 3. Use Email-Enabled Script

Edit cron job to use `generate_weekly_reports_email.py` instead:
```bash
crontab -e
```

Change:
```
0 13 * * 1 cd $HOME/zendesk-dashboard-project/scripts && /usr/bin/python3 generate_weekly_reports_email.py
```

---

## Troubleshooting

### Reports Not Generating?

**1. Check if cron job is installed:**
```bash
crontab -l | grep weekly
```

**2. Check logs:**
```bash
cat ~/Desktop/weekly_reports.log
```

**3. Test script manually:**
```bash
cd ~/zendesk-dashboard-project/scripts
./generate_weekly_reports.py
```

**4. Verify Python path:**
```bash
which python3
```

### Reports Generated But Not Received?

**1. Check output directory:**
```bash
ls -la ~/Desktop/Weekly_Zendesk_Reports/
```

**2. Verify permissions:**
```bash
ls -la ~/zendesk-dashboard-project/scripts/generate_weekly_reports.py
```

Should show: `-rwxr-xr-x` (executable)

### Wrong Time Zone?

If reports run at wrong time:
```bash
# Remove current cron job
crontab -l | grep -v 'generate_weekly_reports.py' | crontab -

# Re-run setup
cd ~/zendesk-dashboard-project/scripts
./setup_weekly_reports.sh
```

---

## Customization

### Change Schedule

Edit cron schedule (run `crontab -e`):

```bash
# Every Monday at 8:00 AM CST
0 13 * * 1 [command]

# Every day at 8:00 AM CST
0 13 * * * [command]

# Every Friday at 5:00 PM CST
0 22 * * 5 [command]
```

**Cron Format:**
```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sun=0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23, in UTC)
└─────────── Minute (0-59)
```

### Add/Remove Agents

Edit `~/zendesk-dashboard-project/scripts/generate_weekly_reports.py`:

```python
AGENTS = {
    'Candice Brown': '21761242009371',
    'Ron Pineda': '21761363093147',
    'Bola Kuye': '39948397141915',
    # Add new agent:
    # 'New Agent': 'agent_id_here'
}
```

### Change Output Location

Edit the script:
```python
OUTPUT_DIR = Path.home() / 'Desktop' / 'Weekly_Zendesk_Reports'
# Change to:
OUTPUT_DIR = Path('/path/to/your/reports/folder')
```

---

## System Requirements

- **OS:** macOS or Linux
- **Python:** 3.9+
- **Packages:** requests (already installed)
- **Permissions:** Cron access

---

## FAQ

**Q: Can I get reports on different days?**
A: Yes, edit the cron schedule. See Customization section.

**Q: Can I send reports to Slack instead?**
A: Yes, modify the script to use Slack webhooks instead of file output.

**Q: How do I stop the automation?**
A: Run: `crontab -l | grep -v 'generate_weekly_reports.py' | crontab -`

**Q: Can I include more details in reports?**
A: Yes, edit `generate_html_report()` function in the script.

**Q: Will this work when my computer is off?**
A: No, cron requires the computer to be running. For 24/7 operation, deploy to a server.

---

## Next Steps

1. ✅ Run setup: `./setup_weekly_reports.sh`
2. ✅ Test manually: `./generate_weekly_reports.py`
3. ✅ Wait for Monday 8:00 AM or check logs
4. ✅ Review reports in `~/Desktop/Weekly_Zendesk_Reports/`

**Optional:**
- Configure email delivery
- Customize report format
- Add additional agents
- Change schedule

---

## Support

For issues or questions:
1. Check logs: `cat ~/Desktop/weekly_reports.log`
2. Test manually: `./generate_weekly_reports.py`
3. Review cron: `crontab -l`

---

**Last Updated:** February 23, 2026
**Version:** 1.0
**Status:** Production Ready
