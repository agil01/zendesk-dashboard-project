# Zendesk Executive Summary Generator

Generate comprehensive executive summary reports for any date range, analyzing ticket volume, team performance, SLA metrics, and trends.

---

## Quick Start

### Generate Summary for Specific Date Range

```bash
cd ~/zendesk-dashboard-project/scripts
./generate_executive_summary.py 2026-02-16 2026-02-22
```

### Generate Summary for Last Week (Automatic)

```bash
cd ~/zendesk-dashboard-project/scripts
./generate_executive_summary.py
```

If no dates are provided, the script automatically generates a summary for the previous week (Monday-Sunday).

---

## What Gets Generated

The executive summary includes:

### 📊 Key Performance Indicators
- Total ticket volume
- Average reply time (hours)
- Average resolution time (hours)
- One-touch resolution rate
- Resolved tickets count
- Overall resolution rate

### 🎯 Priority Distribution
- Urgent tickets
- High priority tickets
- Normal priority tickets
- Low priority tickets
- Visual breakdown with percentages

### 📋 Status Distribution
- Solved tickets
- Closed tickets
- Pending tickets
- Open tickets
- On-hold tickets

### 🏢 Brand Metrics
- Clover Health ticket volume
- Counterpart Health ticket volume
- Brand comparison and trends

### 👥 Team Performance
- Tickets handled per agent (Candice, Ron, Bola)
- Workload distribution
- Percentage breakdown
- Team balance analysis

### 📞 Channel Distribution
- Email tickets
- API tickets
- Web tickets
- Other channels

### ⚡ One-Touch Resolution
- One-touch resolution count
- Multi-touch resolution count
- One-touch resolution percentage
- Efficiency metrics

### ⏱️ SLA Performance
- Average first reply time
- Average resolution time
- SLA compliance status
- Performance vs targets

### 💡 Key Insights & Trends
- Volume analysis and trends
- Resolution rate assessment
- Priority mix evaluation
- Team workload distribution
- Channel preference insights
- Performance recommendations

---

## Output Format

**File Location:** `~/Desktop/Claude Files/Zendesk_Executive_Summary_[start-date]_to_[end-date].html`

**Features:**
- Professional HTML formatting
- Print-ready layout
- Visual charts and graphs
- Color-coded metrics
- Responsive design
- Easy sharing and distribution

---

## Usage Examples

### Last Week Summary
```bash
./generate_executive_summary.py
```

### Specific Week
```bash
./generate_executive_summary.py 2026-02-16 2026-02-22
```

### Custom Date Range
```bash
./generate_executive_summary.py 2026-02-01 2026-02-29
```

### Previous Month
```bash
./generate_executive_summary.py 2026-01-01 2026-01-31
```

---

## Report Contents

### Executive Overview Section
- Report period
- Generation timestamp
- Total tickets analyzed
- Key highlights

### Performance Metrics Section
- Visual stat cards for KPIs
- Color-coded indicators
- Comparison to targets
- Trend indicators

### Team Performance Section
- Agent-by-agent breakdown
- Workload comparison table
- Percentage distribution
- Balance analysis

### Detailed Metrics Section
- Priority distribution with percentages
- Status breakdown
- Brand comparison
- Channel analysis
- Visual progress bars

### Insights Section
- Automated trend detection
- Workload imbalance alerts
- SLA compliance status
- Efficiency recommendations

---

## Metrics Explained

### One-Touch Resolution
Tickets resolved with a single agent reply, indicating efficient first-contact problem solving.

**Target:** 80% or higher

### Average Reply Time
Time from ticket creation to first agent response.

**Target:** Under 4 hours (business hours)

### Average Resolution Time
Time from ticket creation to final resolution.

**Target:** Under 8 hours (business hours)

### Resolution Rate
Percentage of tickets fully resolved (solved or closed status).

**Target:** 80% or higher

---

## Sample Metrics Data

The script samples up to 20 tickets for detailed metrics analysis. This provides:
- Accurate reply time averages
- Resolution time statistics
- One-touch resolution rates
- SLA performance data

For larger datasets, the sample provides statistically significant insights while maintaining performance.

---

## Customization

### Change Output Directory

Edit the script:
```python
OUTPUT_DIR = Path.home() / 'Desktop' / 'Claude Files'
# Change to:
OUTPUT_DIR = Path('/path/to/your/reports/')
```

### Adjust Sample Size

Edit the script:
```python
metrics_data = fetch_ticket_metrics(tickets, sample_size=20)
# Change to:
metrics_data = fetch_ticket_metrics(tickets, sample_size=50)
```

### Add Custom Agents

Edit the AGENT_MAP in the script:
```python
AGENT_MAP = {
    21761242009371: 'Candice Brown',
    21761363093147: 'Ron Pineda',
    39948397841915: 'Bola Kuye',
    # Add new agent:
    # 12345678901234: 'New Agent Name'
}
```

---

## Troubleshooting

### No Tickets Found

**Issue:** Script reports "No tickets found in date range"

**Solutions:**
1. Verify date format is YYYY-MM-DD
2. Check date range includes ticket creation dates
3. Ensure Zendesk API credentials are valid

### Authentication Error

**Issue:** Error 401 or authentication failed

**Solutions:**
1. Verify ZENDESK_API_TOKEN environment variable
2. Check API token in script configuration
3. Ensure token has proper permissions

### Slow Performance

**Issue:** Script takes long time to complete

**Solutions:**
1. Reduce sample size for metrics
2. Use shorter date ranges
3. Check network connection to Zendesk

---

## Integration with Weekly Reports

This executive summary complements the weekly agent reports:

- **Weekly Reports:** Individual agent performance, ticket details
- **Executive Summary:** High-level overview, trends, team metrics

Use together for comprehensive support analytics:
1. Generate weekly reports every Monday (automated)
2. Generate executive summary weekly/monthly for management
3. Compare trends over time

---

## Automation (Optional)

### Monthly Summary on 1st of Month

Add to crontab:
```bash
# Executive summary on 1st of each month at 9:00 AM CST
0 14 1 * * cd $HOME/zendesk-dashboard-project/scripts && /usr/bin/python3 generate_executive_summary.py >> $HOME/Desktop/executive_summary.log 2>&1
```

### Weekly Summary Every Monday

Add to crontab:
```bash
# Executive summary every Monday at 9:00 AM CST
0 14 * * 1 cd $HOME/zendesk-dashboard-project/scripts && /usr/bin/python3 generate_executive_summary.py >> $HOME/Desktop/executive_summary.log 2>&1
```

---

## System Requirements

- **OS:** macOS or Linux
- **Python:** 3.9+
- **Packages:** requests (built-in)
- **Permissions:** Zendesk API access

---

## Best Practices

1. **Regular Cadence:** Generate weekly or monthly for trend tracking
2. **Date Consistency:** Use consistent day ranges (Mon-Sun, 1st-Last)
3. **Archive Reports:** Keep historical reports for comparison
4. **Share Insights:** Distribute to management and stakeholders
5. **Action Items:** Review recommendations and implement changes

---

## FAQ

**Q: Can I generate reports for any date range?**
A: Yes, any valid date range in YYYY-MM-DD format.

**Q: How accurate are the metrics?**
A: Very accurate. Sample-based metrics (reply time, resolution time) use statistical sampling for efficiency.

**Q: Can I export to PDF?**
A: Yes, use the print function in your browser and "Save as PDF".

**Q: How does this differ from weekly agent reports?**
A: Weekly reports focus on individual agent workloads. Executive summary focuses on team-wide trends and KPIs.

**Q: Can I customize the report format?**
A: Yes, edit the HTML template in the `generate_html_report()` function.

---

## Support

For issues or questions:
1. Check this documentation
2. Review script output for error messages
3. Verify API credentials and permissions
4. Check date range format

---

**Last Updated:** February 23, 2026
**Version:** 1.0
**Status:** Production Ready
