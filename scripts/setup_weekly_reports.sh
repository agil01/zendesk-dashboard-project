#!/bin/bash
# Setup script for automating weekly Zendesk reports
# This script configures a cron job to run every Monday at 8:00 AM CST

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_SCRIPT="$SCRIPT_DIR/generate_weekly_reports.py"

echo "=========================================="
echo "Weekly Zendesk Reports - Setup"
echo "=========================================="
echo ""

# Check if script exists
if [ ! -f "$REPORT_SCRIPT" ]; then
    echo "❌ Error: Report script not found at $REPORT_SCRIPT"
    exit 1
fi

# Make script executable
chmod +x "$REPORT_SCRIPT"

# Create cron entry
# Note: CST is UTC-6 (standard time) or UTC-5 (daylight time)
# For 8:00 AM CST during standard time, use 14:00 UTC
# For 8:00 AM CDT during daylight time, use 13:00 UTC
# Using 13:00 UTC to account for daylight saving time (most of the year)

CRON_ENTRY="0 13 * * 1 cd $SCRIPT_DIR && /usr/bin/python3 $REPORT_SCRIPT >> $HOME/Desktop/weekly_reports.log 2>&1"

echo "Proposed cron entry:"
echo "$CRON_ENTRY"
echo ""

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "generate_weekly_reports.py"; then
    echo "⚠️  A cron entry for this script already exists."
    echo ""
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    # Remove old entry
    crontab -l 2>/dev/null | grep -v "generate_weekly_reports.py" | crontab -
fi

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo ""
echo "✅ Cron job installed successfully!"
echo ""
echo "Schedule: Every Monday at 8:00 AM CST/CDT"
echo "Reports will be saved to: ~/Desktop/Weekly_Zendesk_Reports/"
echo "Logs will be saved to: ~/Desktop/weekly_reports.log"
echo ""
echo "To view your cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -v 'generate_weekly_reports.py' | crontab -"
echo ""
echo "To test the script manually:"
echo "  $REPORT_SCRIPT"
echo ""
echo "=========================================="
