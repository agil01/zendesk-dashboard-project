#!/usr/bin/env python3
"""
Weekly Agent Ticket Reports Generator
Generates comprehensive ticket reports for support agents every Monday at 8:00 AM CST
"""

import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Configuration
SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
EMAIL = os.getenv('ZENDESK_EMAIL', 'anthony.gil@counterparthealth.com')
API_TOKEN = os.getenv('ZENDESK_API_TOKEN', '24ICYAgncoLX19UJ6A3nmuIpZLXU3CrERIpav7kv')

# Agent IDs and names
AGENTS = {
    'Candice Brown': '21761242009371',
    'Ron Pineda': '21761363093147',
    'Bola Kuye': '39948397141915'
}

# Output directory
OUTPUT_DIR = Path.home() / 'Desktop' / 'Weekly_Zendesk_Reports'

def get_agent_tickets(agent_id):
    """Fetch all open tickets for an agent."""
    base_url = f"https://{SUBDOMAIN}.zendesk.com/api/v2"
    search_url = f"{base_url}/search.json"

    params = {
        'query': f'type:ticket assignee:{agent_id} status<solved',
        'sort_by': 'priority',
        'sort_order': 'desc'
    }

    response = requests.get(
        search_url,
        auth=(f"{EMAIL}/token", API_TOKEN),
        params=params,
        timeout=10
    )

    if response.status_code == 200:
        return response.json().get('results', [])
    return []

def get_ticket_details(ticket_id):
    """Get full ticket details including comments."""
    base_url = f"https://{SUBDOMAIN}.zendesk.com/api/v2"

    # Get ticket details
    ticket_url = f"{base_url}/tickets/{ticket_id}.json"
    ticket_response = requests.get(
        ticket_url,
        auth=(f"{EMAIL}/token", API_TOKEN),
        timeout=10
    )

    if ticket_response.status_code != 200:
        return None

    ticket = ticket_response.json().get('ticket', {})

    # Get comments
    comments_url = f"{base_url}/tickets/{ticket_id}/comments.json"
    comments_response = requests.get(
        comments_url,
        auth=(f"{EMAIL}/token", API_TOKEN),
        timeout=10
    )

    if comments_response.status_code == 200:
        ticket['comments'] = comments_response.json().get('comments', [])

    return ticket

def calculate_stats(tickets):
    """Calculate ticket statistics."""
    stats = {
        'total': len(tickets),
        'urgent': 0,
        'high': 0,
        'normal': 0,
        'low': 0,
        'pending': 0,
        'hold': 0,
        'ages': []
    }

    now = datetime.now(ZoneInfo('America/Chicago'))

    for ticket in tickets:
        priority = ticket.get('priority', 'normal')
        status = ticket.get('status', 'unknown')
        created = ticket.get('created_at', '')

        stats[priority] = stats.get(priority, 0) + 1
        stats[status] = stats.get(status, 0) + 1

        if created:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00')).astimezone(ZoneInfo('America/Chicago'))
            age_days = (now - created_dt).days
            stats['ages'].append(age_days)

    stats['avg_age'] = sum(stats['ages']) // len(stats['ages']) if stats['ages'] else 0
    stats['oldest'] = max(stats['ages']) if stats['ages'] else 0
    stats['newest'] = min(stats['ages']) if stats['ages'] else 0

    return stats

def generate_html_report(agent_name, tickets, stats):
    """Generate HTML report for an agent."""
    cst_now = datetime.now(ZoneInfo('America/Chicago'))
    date_str = cst_now.strftime('%Y-%m-%d')

    # Priority emoji mapping
    priority_emoji = {
        'urgent': '🔴',
        'high': '🟠',
        'normal': '🟡',
        'low': '🟢'
    }

    # Build ticket rows
    ticket_rows = []
    for ticket in tickets:
        ticket_id = ticket.get('id')
        subject = ticket.get('subject', 'No subject')
        priority = ticket.get('priority', 'normal')
        status = ticket.get('status', 'unknown')
        created = ticket.get('created_at', '')

        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00')).astimezone(ZoneInfo('America/Chicago'))
        days_open = (cst_now - created_dt).days

        bg_color = {
            'urgent': '#fee2e2',
            'high': '#fed7aa',
            'normal': '#fef9c3',
            'low': '#d1fae5'
        }.get(priority, '#fafafa')

        ticket_rows.append(f'''
            <tr style="background: {bg_color};">
                <td style="padding: 8px;">#{ticket_id}</td>
                <td style="padding: 8px;">{priority_emoji.get(priority, '⚪')} {priority.title()}</td>
                <td style="padding: 8px;">{subject[:60]}{'...' if len(subject) > 60 else ''}</td>
                <td style="padding: 8px;">{status.title()}</td>
                <td style="padding: 8px;">{days_open}</td>
            </tr>
        ''')

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Ticket Report - {agent_name}</title>
    <style>
        @media print {{
            .no-print {{ display: none; }}
            body {{ margin: 0.5in; }}
        }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
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
            border-bottom: 3px solid #1e40af;
            padding-bottom: 10px;
        }}
        .header-info {{
            background: #eff6ff;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #2563eb;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #eff6ff;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #bfdbfe;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #1e40af;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 13px;
        }}
        thead {{
            background: #1e40af;
            color: white;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
        }}
        .print-button {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            margin: 20px 0;
        }}
        .print-button:hover {{
            background: #1e40af;
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-button no-print" onclick="window.print()">🖨️ Print Report</button>

        <h1>📊 Weekly Ticket Report - {agent_name}</h1>

        <div class="header-info">
            <p><strong>Report Date:</strong> {cst_now.strftime('%A, %B %d, %Y at %I:%M %p CST')}</p>
            <p><strong>Total Open Tickets:</strong> {stats['total']}</p>
            <p><strong>Status:</strong> {stats.get('pending', 0)} Pending, {stats.get('hold', 0)} On Hold</p>
            <p><strong>Priority:</strong> {stats.get('urgent', 0)} Urgent, {stats.get('high', 0)} High, {stats.get('normal', 0)} Normal, {stats.get('low', 0)} Low</p>
        </div>

        <h2>Summary Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats['total']}</div>
                <div class="stat-label">Total Tickets</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['avg_age']}</div>
                <div class="stat-label">Avg Age (Days)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['oldest']}</div>
                <div class="stat-label">Oldest (Days)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('urgent', 0)}</div>
                <div class="stat-label">Urgent Issues</div>
            </div>
        </div>

        <h2>All Open Tickets</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Priority</th>
                    <th>Subject</th>
                    <th>Status</th>
                    <th>Days Open</th>
                </tr>
            </thead>
            <tbody>
                {''.join(ticket_rows)}
            </tbody>
        </table>

        <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px;">
            <p><strong>Generated:</strong> {cst_now.strftime('%B %d, %Y at %I:%M %p CST')}</p>
            <p><strong>Automated Weekly Report</strong></p>
        </div>
    </div>
</body>
</html>'''

    return html_content

def generate_comparative_report(all_agent_data):
    """Generate comparative summary report for all agents."""
    cst_now = datetime.now(ZoneInfo('America/Chicago'))
    date_str = cst_now.strftime('%Y-%m-%d')

    # Calculate totals
    total_tickets = sum(data['stats']['total'] for data in all_agent_data.values())
    total_urgent = sum(data['stats'].get('urgent', 0) for data in all_agent_data.values())
    total_high = sum(data['stats'].get('high', 0) for data in all_agent_data.values())

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Team Ticket Summary - Comparative Report</title>
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
            border-bottom: 3px solid #1e40af;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2563eb;
            margin-top: 30px;
            border-left: 4px solid #2563eb;
            padding-left: 15px;
        }}
        .header-info {{
            background: #eff6ff;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #2563eb;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #eff6ff;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #bfdbfe;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #1e40af;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        .comparison-table thead {{
            background: #1e40af;
            color: white;
        }}
        .comparison-table th {{
            padding: 12px;
            text-align: left;
        }}
        .comparison-table td {{
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .comparison-table tbody tr:hover {{
            background: #f9fafb;
        }}
        .agent-row {{
            background: #fafafa;
        }}
        .total-row {{
            background: #eff6ff;
            font-weight: bold;
            border-top: 2px solid #2563eb;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            color: white;
        }}
        .badge-urgent {{ background: #dc2626; }}
        .badge-high {{ background: #ea580c; }}
        .badge-normal {{ background: #ca8a04; }}
        .badge-low {{ background: #10b981; }}
        .chart-container {{
            background: #fafafa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin: 20px 0;
        }}
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .bar-label {{
            min-width: 120px;
            font-weight: 600;
            color: #374151;
        }}
        .bar-container {{
            flex: 1;
            background: #e5e7eb;
            border-radius: 4px;
            height: 30px;
            position: relative;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #2563eb);
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-weight: 600;
            font-size: 13px;
            transition: width 0.3s ease;
        }}
        .print-button {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            margin: 20px 0;
        }}
        .print-button:hover {{
            background: #1e40af;
        }}
        .alert-box {{
            background: #fef2f2;
            border: 2px solid #dc2626;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .warning-box {{
            background: #fef3c7;
            border: 2px solid #f59e0b;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <button class="print-button no-print" onclick="window.print()">🖨️ Print Report</button>

        <h1>📊 Team Ticket Summary - Comparative Report</h1>

        <div class="header-info">
            <p><strong>Report Date:</strong> {cst_now.strftime('%A, %B %d, %Y at %I:%M %p CST')}</p>
            <p><strong>Team Members:</strong> Candice Brown, Ron Pineda, Bola Kuye</p>
            <p><strong>Total Team Tickets:</strong> {total_tickets}</p>
        </div>

        <h2>Team Overview</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_tickets}</div>
                <div class="stat-label">Total Open Tickets</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_urgent}</div>
                <div class="stat-label">Urgent Issues</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_high}</div>
                <div class="stat-label">High Priority</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{round(total_tickets / len(AGENTS))}</div>
                <div class="stat-label">Avg Per Agent</div>
            </div>
        </div>

        <h2>Workload Distribution</h2>
        <div class="chart-container">
            <div class="bar-chart">'''

    # Add bar chart for each agent
    max_tickets = max(data['stats']['total'] for data in all_agent_data.values()) or 1

    for agent_name in ['Candice Brown', 'Ron Pineda', 'Bola Kuye']:
        data = all_agent_data[agent_name]
        count = data['stats']['total']
        percentage = (count / max_tickets) * 100

        html_content += f'''
                <div class="bar-row">
                    <div class="bar-label">{agent_name}</div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {percentage}%;">{count} tickets</div>
                    </div>
                </div>'''

    html_content += '''
            </div>
        </div>

        <h2>Detailed Comparison</h2>
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Agent</th>
                    <th>Total Tickets</th>
                    <th>Urgent</th>
                    <th>High</th>
                    <th>Normal</th>
                    <th>Low</th>
                    <th>Avg Age (Days)</th>
                    <th>Oldest (Days)</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>'''

    # Add rows for each agent
    for agent_name in ['Candice Brown', 'Ron Pineda', 'Bola Kuye']:
        data = all_agent_data[agent_name]
        stats = data['stats']

        # Workload indicator
        workload = "Normal"
        if stats['total'] > 12:
            workload = "⚠️ High"
        elif stats['total'] > 8:
            workload = "⚡ Above Avg"

        html_content += f'''
                <tr class="agent-row">
                    <td><strong>{agent_name}</strong></td>
                    <td>{stats['total']}</td>
                    <td><span class="badge badge-urgent">{stats.get('urgent', 0)}</span></td>
                    <td><span class="badge badge-high">{stats.get('high', 0)}</span></td>
                    <td><span class="badge badge-normal">{stats.get('normal', 0)}</span></td>
                    <td><span class="badge badge-low">{stats.get('low', 0)}</span></td>
                    <td>{stats['avg_age']}</td>
                    <td>{stats['oldest']}</td>
                    <td>{workload}</td>
                </tr>'''

    # Add total row
    total_normal = sum(data['stats'].get('normal', 0) for data in all_agent_data.values())
    total_low = sum(data['stats'].get('low', 0) for data in all_agent_data.values())
    all_ages = []
    for data in all_agent_data.values():
        all_ages.extend(data['stats']['ages'])
    avg_age = sum(all_ages) // len(all_ages) if all_ages else 0
    oldest = max(all_ages) if all_ages else 0

    html_content += f'''
                <tr class="total-row">
                    <td>TEAM TOTAL</td>
                    <td>{total_tickets}</td>
                    <td>{total_urgent}</td>
                    <td>{total_high}</td>
                    <td>{total_normal}</td>
                    <td>{total_low}</td>
                    <td>{avg_age}</td>
                    <td>{oldest}</td>
                    <td>-</td>
                </tr>
            </tbody>
        </table>

        <h2>Insights & Recommendations</h2>'''

    # Add alerts if needed
    if total_urgent > 5:
        html_content += f'''
        <div class="alert-box">
            <strong>🚨 HIGH URGENT COUNT:</strong> Team has {total_urgent} urgent tickets requiring immediate attention.
        </div>'''

    # Check for workload imbalance
    ticket_counts = [data['stats']['total'] for data in all_agent_data.values()]
    max_count = max(ticket_counts)
    min_count = min(ticket_counts)
    if max_count - min_count > 5:
        html_content += f'''
        <div class="warning-box">
            <strong>⚠️ WORKLOAD IMBALANCE:</strong> Significant difference in ticket distribution. Consider rebalancing workload.
        </div>'''

    # Agent-specific highlights
    html_content += '''
        <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3>Agent Highlights</h3>
            <ul>'''

    for agent_name in ['Candice Brown', 'Ron Pineda', 'Bola Kuye']:
        data = all_agent_data[agent_name]
        stats = data['stats']

        highlight = []
        if stats['total'] > 10:
            highlight.append(f"{stats['total']} tickets (above average)")
        if stats.get('urgent', 0) > 2:
            highlight.append(f"{stats.get('urgent', 0)} urgent issues")
        if stats['oldest'] > 60:
            highlight.append(f"oldest ticket {stats['oldest']} days old")

        if highlight:
            html_content += f'''
                <li><strong>{agent_name}:</strong> {', '.join(highlight)}</li>'''

    html_content += '''
            </ul>
        </div>

        <h2>Priority Actions</h2>
        <div style="background: #dbeafe; padding: 20px; border-radius: 8px; border-left: 4px solid #2563eb;">
            <ol>
                <li><strong>Urgent Tickets:</strong> Address {total_urgent} urgent issues across team</li>
                <li><strong>High Priority:</strong> Review {total_high} high priority tickets</li>
                <li><strong>Aged Tickets:</strong> Focus on tickets older than 30 days</li>
                <li><strong>Workload Balance:</strong> Monitor distribution and adjust as needed</li>
            </ol>
        </div>

        <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px;">
            <p><strong>Generated:</strong> {cst_now.strftime('%B %d, %Y at %I:%M %p CST')}</p>
            <p><strong>Automated Weekly Team Summary</strong></p>
        </div>
    </div>
</body>
</html>'''

    return html_content

def generate_reports():
    """Generate reports for all agents."""
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cst_now = datetime.now(ZoneInfo('America/Chicago'))
    date_str = cst_now.strftime('%Y-%m-%d')

    print(f"Generating weekly reports for {date_str}...")
    print("=" * 80)

    # Store all agent data for comparative report
    all_agent_data = {}

    for agent_name, agent_id in AGENTS.items():
        print(f"\nProcessing {agent_name}...")

        # Fetch tickets
        tickets = get_agent_tickets(agent_id)
        print(f"  Found {len(tickets)} open tickets")

        # Calculate stats
        stats = calculate_stats(tickets)

        # Store for comparative report
        all_agent_data[agent_name] = {
            'tickets': tickets,
            'stats': stats
        }

        # Generate HTML report
        html_content = generate_html_report(agent_name, tickets, stats)

        # Save report
        safe_name = agent_name.replace(' ', '_')
        filename = f"{safe_name}_Weekly_Report_{date_str}.html"
        filepath = OUTPUT_DIR / filename

        with open(filepath, 'w') as f:
            f.write(html_content)

        print(f"  ✅ Report saved: {filepath}")

    # Generate comparative summary report
    print(f"\nGenerating comparative team summary...")
    comparative_html = generate_comparative_report(all_agent_data)
    comparative_filepath = OUTPUT_DIR / f"TEAM_SUMMARY_Comparative_Report_{date_str}.html"

    with open(comparative_filepath, 'w') as f:
        f.write(comparative_html)

    print(f"  ✅ Team summary saved: {comparative_filepath}")

    print("\n" + "=" * 80)
    print(f"✅ All reports generated successfully!")
    print(f"📁 Reports saved to: {OUTPUT_DIR}")
    print(f"\n📊 Reports generated:")
    print(f"   - 3 individual agent reports")
    print(f"   - 1 comparative team summary")

if __name__ == "__main__":
    try:
        generate_reports()
    except Exception as e:
        print(f"❌ Error generating reports: {e}")
        import traceback
        traceback.print_exc()
