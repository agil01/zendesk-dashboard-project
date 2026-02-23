#!/usr/bin/env python3
"""
Zendesk Executive Summary Generator
Generates comprehensive executive summary reports for specified date ranges
"""

import requests
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict, Counter
import sys

# Configuration
SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
EMAIL = os.getenv('ZENDESK_EMAIL', 'anthony.gil@counterparthealth.com')
API_TOKEN = os.getenv('ZENDESK_API_TOKEN', '24ICYAgncoLX19UJ6A3nmuIpZLXU3CrERIpav7kv')

# Agent mapping
AGENT_MAP = {
    21761242009371: 'Candice Brown',
    21761363093147: 'Ron Pineda',
    39948397141915: 'Bola Kuye'
}

# Output directory
OUTPUT_DIR = Path.home() / 'Desktop' / 'Claude Files'

def fetch_tickets(start_date, end_date):
    """Fetch all tickets created within the date range."""
    print(f"Fetching tickets from {start_date} to {end_date}...")

    base_url = f"https://{SUBDOMAIN}.zendesk.com/api/v2"
    search_url = f"{base_url}/search.json"

    query = f'type:ticket created>={start_date} created<={end_date}'
    params = {'query': query, 'per_page': 100}

    auth = (f'{EMAIL}/token', API_TOKEN)
    all_tickets = []
    page = 1

    while True:
        response = requests.get(search_url, auth=auth, params=params, timeout=30)

        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text[:200]}")
            break

        data = response.json()
        results = data.get('results', [])
        all_tickets.extend(results)

        print(f"  Page {page}: Fetched {len(results)} tickets (Total: {len(all_tickets)})")

        if not data.get('next_page'):
            break

        params = {'query': query, 'per_page': 100, 'page': page + 1}
        page += 1

    print(f"✅ Total tickets fetched: {len(all_tickets)}\n")
    return all_tickets

def fetch_ticket_metrics(tickets, sample_size=20):
    """Fetch detailed metrics for a sample of tickets."""
    print(f"Fetching detailed metrics for {sample_size} tickets...")

    base_url = f"https://{SUBDOMAIN}.zendesk.com/api/v2"
    auth = (f'{EMAIL}/token', API_TOKEN)

    metrics_data = []
    for ticket in tickets[:sample_size]:
        try:
            metrics_url = f"{base_url}/tickets/{ticket['id']}/metrics.json"
            response = requests.get(metrics_url, auth=auth, timeout=10)
            if response.status_code == 200:
                metrics_data.append(response.json()['ticket_metric'])
        except Exception as e:
            continue

    print(f"✅ Fetched metrics for {len(metrics_data)} tickets\n")
    return metrics_data

def analyze_tickets(tickets, metrics_data):
    """Analyze ticket data and generate statistics."""
    print("Analyzing tickets...")

    analysis = {
        'total_tickets': len(tickets),
        'priority_dist': Counter(),
        'status_dist': Counter(),
        'channel_dist': Counter(),
        'brand_dist': Counter(),
        'agent_dist': Counter(),
        'type_dist': Counter(),
        'status_by_brand': defaultdict(Counter),
        'reply_times': [],
        'resolution_times': [],
        'resolution_by_priority': defaultdict(list),
        'sla_breaches': 0,
        'sla_met': 0,
        'resolution_ranges': Counter(),
        'one_touch': 0,
        'multi_touch': 0,
    }

    for ticket in tickets:
        # Priority and Status
        analysis['priority_dist'][ticket.get('priority', 'none')] += 1
        analysis['status_dist'][ticket.get('status', 'unknown')] += 1

        # Channel
        channel = ticket.get('via', {}).get('channel', 'unknown')
        analysis['channel_dist'][channel] += 1

        # Type
        ticket_type = ticket.get('type', 'question')
        analysis['type_dist'][ticket_type] += 1

        # Brand (from tags or content)
        tags = ticket.get('tags', [])
        subject = ticket.get('subject', '').lower()
        desc = ticket.get('description', '').lower()

        if 'clover_health' in tags or 'clover' in str(tags).lower() or 'clover' in subject or 'clover' in desc:
            brand = 'Clover Health'
            analysis['brand_dist']['Clover Health'] += 1
        else:
            brand = 'Counterpart Health'
            analysis['brand_dist']['Counterpart Health'] += 1

        # Status by brand
        status = ticket.get('status', 'unknown')
        analysis['status_by_brand'][brand][status] += 1

        # Agent
        assignee_id = ticket.get('assignee_id')
        if assignee_id in AGENT_MAP:
            analysis['agent_dist'][AGENT_MAP[assignee_id]] += 1
        else:
            analysis['agent_dist']['Other/Unassigned'] += 1

    # Process metrics
    # Create ticket priority map for SLA tracking
    ticket_priority_map = {t['id']: t.get('priority', 'normal') for t in tickets}

    for metric in metrics_data:
        ticket_id = metric.get('ticket_id')
        priority = ticket_priority_map.get(ticket_id, 'normal')

        # Reply time
        if metric.get('reply_time_in_minutes', {}).get('business'):
            analysis['reply_times'].append(metric['reply_time_in_minutes']['business'])

        # Resolution time
        if metric.get('first_resolution_time_in_minutes', {}).get('business'):
            resolution_time = metric['first_resolution_time_in_minutes']['business']
            analysis['resolution_times'].append(resolution_time)
            analysis['resolution_by_priority'][priority].append(resolution_time)

            # SLA targets (in minutes): Urgent: 240 (4hrs), High: 480 (8hrs), Normal: 1440 (24hrs), Low: 2880 (48hrs)
            sla_targets = {
                'urgent': 240,
                'high': 480,
                'normal': 1440,
                'low': 2880
            }

            target = sla_targets.get(priority, 1440)
            if resolution_time <= target:
                analysis['sla_met'] += 1
            else:
                analysis['sla_breaches'] += 1

            # Categorize resolution time ranges
            resolution_hours = resolution_time / 60
            if resolution_hours <= 4:
                analysis['resolution_ranges']['0-4 hours'] += 1
            elif resolution_hours <= 8:
                analysis['resolution_ranges']['4-8 hours'] += 1
            elif resolution_hours <= 24:
                analysis['resolution_ranges']['8-24 hours'] += 1
            elif resolution_hours <= 48:
                analysis['resolution_ranges']['24-48 hours'] += 1
            else:
                analysis['resolution_ranges']['48+ hours'] += 1

        # One touch resolution
        if metric.get('replies', 0) <= 1:
            analysis['one_touch'] += 1
        else:
            analysis['multi_touch'] += 1

    # Calculate averages
    analysis['avg_reply_time_minutes'] = sum(analysis['reply_times']) / len(analysis['reply_times']) if analysis['reply_times'] else 0
    analysis['avg_resolution_time_minutes'] = sum(analysis['resolution_times']) / len(analysis['resolution_times']) if analysis['resolution_times'] else 0

    print("✅ Analysis complete\n")
    return analysis

def generate_html_report(analysis, start_date, end_date, output_path):
    """Generate HTML executive summary report."""

    # Calculate SLA metrics
    total_sla_tracked = analysis['sla_met'] + analysis['sla_breaches']
    sla_compliance_rate = (analysis['sla_met'] / total_sla_tracked * 100) if total_sla_tracked > 0 else 0

    # Calculate avg resolution by priority
    resolution_by_priority_avg = {}
    for priority, times in analysis['resolution_by_priority'].items():
        if times:
            avg_minutes = sum(times) / len(times)
            resolution_by_priority_avg[priority] = {
                'minutes': round(avg_minutes, 2),
                'hours': round(avg_minutes / 60, 2),
                'count': len(times)
            }

    data = {
        'total_tickets': analysis['total_tickets'],
        'date_range': f'{start_date} to {end_date}',
        'priority_distribution': dict(analysis['priority_dist']),
        'status_distribution': dict(analysis['status_dist']),
        'channel_distribution': dict(analysis['channel_dist']),
        'brand_distribution': dict(analysis['brand_dist']),
        'agent_distribution': dict(analysis['agent_dist']),
        'type_distribution': dict(analysis['type_dist']),
        'status_by_brand': {brand: dict(statuses) for brand, statuses in analysis['status_by_brand'].items()},
        'avg_reply_time_minutes': round(analysis['avg_reply_time_minutes'], 2),
        'avg_reply_time_hours': round(analysis['avg_reply_time_minutes'] / 60, 2),
        'avg_resolution_time_minutes': round(analysis['avg_resolution_time_minutes'], 2),
        'avg_resolution_time_hours': round(analysis['avg_resolution_time_minutes'] / 60, 2),
        'one_touch_resolutions': analysis['one_touch'],
        'multi_touch_resolutions': analysis['multi_touch'],
        'one_touch_percentage': round((analysis['one_touch'] / max(1, analysis['one_touch'] + analysis['multi_touch'])) * 100, 1) if (analysis['one_touch'] + analysis['multi_touch']) > 0 else 0,
        'sla_met': analysis['sla_met'],
        'sla_breaches': analysis['sla_breaches'],
        'sla_compliance_rate': round(sla_compliance_rate, 1),
        'total_sla_tracked': total_sla_tracked,
        'resolution_ranges': dict(analysis['resolution_ranges']),
        'resolution_by_priority': resolution_by_priority_avg
    }

    resolved_count = data['status_distribution'].get('solved', 0) + data['status_distribution'].get('closed', 0)
    resolution_rate = (resolved_count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zendesk Executive Summary - {data['date_range']}</title>
    <style>
        @media print {{
            .no-print {{ display: none; }}
            body {{ margin: 0.5in; }}
        }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1e40af;
            border-bottom: 4px solid #1e40af;
            padding-bottom: 15px;
        }}
        h2 {{
            color: #2563eb;
            border-bottom: 2px solid #bfdbfe;
            padding-bottom: 8px;
            margin-top: 30px;
        }}
        .header-info {{
            background: linear-gradient(135deg, #1e40af 0%, #2563eb 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 2px solid #93c5fd;
        }}
        .stat-value {{
            font-size: 42px;
            font-weight: bold;
            color: #1e40af;
        }}
        .stat-label {{
            font-size: 13px;
            color: #6b7280;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .metric-row {{
            display: flex;
            justify-content: space-between;
            padding: 12px;
            margin: 8px 0;
            background: #f9fafb;
            border-left: 4px solid #2563eb;
            border-radius: 4px;
        }}
        .print-button {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            margin: 20px 0;
        }}
        .print-button:hover {{
            background: #1e40af;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}
        thead {{
            background: #1e40af;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-button no-print" onclick="window.print()">🖨️ Print Report</button>

        <h1>📊 Zendesk Executive Summary</h1>

        <div class="header-info">
            <p><strong>Reporting Period:</strong> {data['date_range']}</p>
            <p><strong>Report Generated:</strong> {datetime.now(ZoneInfo('America/Chicago')).strftime('%B %d, %Y at %I:%M %p CST')}</p>
            <p><strong>Total Tickets:</strong> {data['total_tickets']}</p>
        </div>

        <h2>📈 Key Performance Indicators</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{data['total_tickets']}</div>
                <div class="stat-label">Total Tickets</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{data['avg_reply_time_hours']:.1f}h</div>
                <div class="stat-label">Avg Reply Time</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{data['avg_resolution_time_hours']:.1f}h</div>
                <div class="stat-label">Avg Resolution</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{data['one_touch_percentage']:.0f}%</div>
                <div class="stat-label">One-Touch Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{resolved_count}</div>
                <div class="stat-label">Resolved</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{resolution_rate:.0f}%</div>
                <div class="stat-label">Resolution Rate</div>
            </div>
        </div>

        <h2>👥 Team Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Agent</th>
                    <th>Tickets</th>
                    <th>Percentage</th>
                </tr>
            </thead>
            <tbody>
"""

    agent_items = sorted([(name, count) for name, count in data['agent_distribution'].items() if 'Unassigned' not in name],
                         key=lambda x: x[1], reverse=True)

    for agent, count in agent_items:
        pct = (count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0
        html_content += f"""                <tr>
                    <td>{agent}</td>
                    <td>{count}</td>
                    <td>{pct:.1f}%</td>
                </tr>
"""

    html_content += """            </tbody>
        </table>

        <h2>📊 Detailed Metrics</h2>
"""

    # Priority distribution
    html_content += "        <h3>Priority Distribution</h3>\n"
    for priority, count in sorted(data['priority_distribution'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0
        html_content += f"""        <div class="metric-row">
            <span>{priority.capitalize()}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""

    # Status distribution
    html_content += "        <h3>Status Distribution</h3>\n"
    for status, count in sorted(data['status_distribution'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0
        html_content += f"""        <div class="metric-row">
            <span>{status.capitalize()}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""

    # Brand distribution
    html_content += "        <h3>Brand Distribution</h3>\n"
    for brand, count in sorted(data['brand_distribution'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0
        html_content += f"""        <div class="metric-row">
            <span>{brand}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""

    # Channel distribution
    html_content += "        <h3>Channel Distribution</h3>\n"
    for channel, count in sorted(data['channel_distribution'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0
        html_content += f"""        <div class="metric-row">
            <span>{channel.capitalize()}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""

    # Issue Types
    html_content += "        <h3>Issue Types</h3>\n"
    for issue_type, count in sorted(data['type_distribution'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / data['total_tickets'] * 100) if data['total_tickets'] > 0 else 0
        html_content += f"""        <div class="metric-row">
            <span>{issue_type.capitalize()}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""

    # Status by Brand
    html_content += "        <h3>Status by Brand</h3>\n"
    for brand in sorted(data['status_by_brand'].keys()):
        html_content += f"        <h4 style='margin-top: 20px; color: #374151;'>{brand}</h4>\n"
        brand_statuses = data['status_by_brand'][brand]
        brand_total = sum(brand_statuses.values())
        for status, count in sorted(brand_statuses.items(), key=lambda x: x[1], reverse=True):
            pct = (count / brand_total * 100) if brand_total > 0 else 0
            html_content += f"""        <div class="metric-row">
            <span>{status.capitalize()}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""


    # SLA Metrics by Resolution Time
    html_content += """
        <h3>SLA Metrics by Resolution Time</h3>
        <div class="stats-grid" style="margin: 20px 0;">
            <div class="stat-card">
                <div class="stat-value" style="color: #16a34a;">{sla_met}</div>
                <div class="stat-label">SLA Met</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #dc2626;">{sla_breaches}</div>
                <div class="stat-label">SLA Breached</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sla_compliance_rate:.1f}%</div>
                <div class="stat-label">Compliance Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_sla_tracked}</div>
                <div class="stat-label">Total Tracked</div>
            </div>
        </div>
""".format(
        sla_met=data['sla_met'],
        sla_breaches=data['sla_breaches'],
        sla_compliance_rate=data['sla_compliance_rate'],
        total_sla_tracked=data['total_sla_tracked']
    )

    # Resolution Time Ranges
    html_content += "        <h4 style='margin-top: 20px; color: #374151;'>Resolution Time Distribution</h4>\n"
    range_order = ['0-4 hours', '4-8 hours', '8-24 hours', '24-48 hours', '48+ hours']
    for time_range in range_order:
        count = data['resolution_ranges'].get(time_range, 0)
        pct = (count / data['total_sla_tracked'] * 100) if data['total_sla_tracked'] > 0 else 0
        html_content += f"""        <div class="metric-row">
            <span>{time_range}</span>
            <span>{count} ({pct:.1f}%)</span>
        </div>
"""

    # Resolution Time by Priority
    html_content += "        <h4 style='margin-top: 20px; color: #374151;'>Average Resolution Time by Priority</h4>\n"
    priority_order = ['urgent', 'high', 'normal', 'low']
    sla_targets_display = {
        'urgent': '4 hours',
        'high': '8 hours',
        'normal': '24 hours',
        'low': '48 hours'
    }

    if data['resolution_by_priority']:
        html_content += """        <table style="margin: 10px 0;">
            <thead>
                <tr>
                    <th>Priority</th>
                    <th>Avg Resolution Time</th>
                    <th>SLA Target</th>
                    <th>Tickets</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
"""
        for priority in priority_order:
            if priority in data['resolution_by_priority']:
                stats = data['resolution_by_priority'][priority]
                target_hours = {'urgent': 4, 'high': 8, 'normal': 24, 'low': 48}[priority]
                status_icon = '✅' if stats['hours'] <= target_hours else '⚠️'
                html_content += f"""                <tr>
                    <td>{priority.capitalize()}</td>
                    <td>{stats['hours']:.1f} hours</td>
                    <td>{sla_targets_display[priority]}</td>
                    <td>{stats['count']}</td>
                    <td style="text-align: center;">{status_icon}</td>
                </tr>
"""
        html_content += """            </tbody>
        </table>
"""
    else:
        html_content += """        <p style="color: #6b7280; font-style: italic;">No resolution data available for priority breakdown.</p>
"""

    html_content += f"""
        <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px;">
            <p><strong>Generated:</strong> {datetime.now(ZoneInfo('America/Chicago')).strftime('%B %d, %Y at %I:%M %p CST')}</p>
            <p><strong>Automated Executive Summary</strong></p>
        </div>
    </div>
</body>
</html>
"""

    # Save report
    with open(output_path, 'w') as f:
        f.write(html_content)

    print(f"✅ Report saved: {output_path}")

def main():
    """Main execution function."""
    # Parse command line arguments or use defaults
    if len(sys.argv) >= 3:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
    else:
        # Default to last week
        today = datetime.now()
        end_date = (today - timedelta(days=today.weekday() + 1)).strftime('%Y-%m-%d')  # Last Sunday
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=6)).strftime('%Y-%m-%d')  # Previous Monday

    print("="*60)
    print("ZENDESK EXECUTIVE SUMMARY GENERATOR")
    print("="*60)
    print(f"Date Range: {start_date} to {end_date}\n")

    # Fetch tickets
    tickets = fetch_tickets(start_date, end_date)

    if not tickets:
        print("No tickets found in date range. Exiting.")
        return

    # Fetch metrics
    metrics_data = fetch_ticket_metrics(tickets, sample_size=min(20, len(tickets)))

    # Analyze
    analysis = analyze_tickets(tickets, metrics_data)

    # Generate report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"Zendesk_Executive_Summary_{start_date}_to_{end_date}.html"
    output_path = OUTPUT_DIR / filename

    generate_html_report(analysis, start_date, end_date, output_path)

    print("\n" + "="*60)
    print("SUMMARY COMPLETE")
    print("="*60)
    print(f"Total Tickets: {analysis['total_tickets']}")
    print(f"Report Location: {output_path}")
    print("="*60)

if __name__ == '__main__':
    main()
