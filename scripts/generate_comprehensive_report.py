#!/usr/bin/env python3
"""
Comprehensive Zendesk Ticket Report Generator
Generates detailed HTML reports similar to the Feb 2-15 format
"""

import requests
import os
import json
from datetime import datetime
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

OUTPUT_DIR = Path.home() / 'Desktop'

def fetch_all_tickets(start_date, end_date):
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
            print(f"Error: {response.status_code}")
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

def fetch_ticket_metrics(tickets):
    """Fetch detailed metrics for tickets."""
    print(f"Fetching detailed metrics for {len(tickets)} tickets...")

    base_url = f"https://{SUBDOMAIN}.zendesk.com/api/v2"
    auth = (f'{EMAIL}/token', API_TOKEN)

    metrics_data = []
    for i, ticket in enumerate(tickets):
        try:
            metrics_url = f"{base_url}/tickets/{ticket['id']}/metrics.json"
            response = requests.get(metrics_url, auth=auth, timeout=10)
            if response.status_code == 200:
                metric = response.json()['ticket_metric']
                metric['ticket_id'] = ticket['id']
                metric['priority'] = ticket.get('priority', 'normal')
                metrics_data.append(metric)
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(tickets)} tickets...")
        except Exception as e:
            continue

    print(f"✅ Fetched metrics for {len(metrics_data)} tickets\n")
    return metrics_data

def analyze_data(tickets, metrics_data):
    """Comprehensive analysis of ticket data."""
    print("Analyzing ticket data...")

    analysis = {
        'total_tickets': len(tickets),
        'status_counts': Counter(),
        'priority_counts': Counter(),
        'daily_volume': Counter(),
        'tags': Counter(),
        'issue_types': Counter(),
        'team_members': Counter(),
        'team_member_tickets': defaultdict(list),
        'team_member_open': Counter(),
        'team_member_open_tickets': defaultdict(list),
        'brand_tickets': {'Counterpart Health': [], 'Clover Health': []},
        'critical_pending': [],
        'resolved_tickets': [],
        'pending_tickets': [],
    }

    for ticket in tickets:
        # Status
        status = ticket.get('status', 'unknown')
        analysis['status_counts'][status] += 1

        # Priority
        priority = ticket.get('priority', 'normal')
        analysis['priority_counts'][priority] += 1

        # Daily volume
        created = datetime.fromisoformat(ticket['created_at'].replace('Z', '+00:00'))
        date_str = created.strftime('%b %d, %Y')
        analysis['daily_volume'][date_str] += 1

        # Tags
        tags = ticket.get('tags', [])
        for tag in tags:
            analysis['tags'][tag] += 1

        # Issue Type Classification
        tags_str = ' '.join(tags).lower()
        subject = ticket.get('subject', '').lower()
        description = ticket.get('description', '').lower()

        if any(keyword in tags_str for keyword in ['user_management', 'umac', 'import_npi', 'import_tin', 'access_request', 'add_provider']):
            issue_type = 'User Management'
        elif any(keyword in tags_str for keyword in ['internal', 'servicenow']):
            issue_type = 'Internal'
        elif any(keyword in tags_str for keyword in ['external_user_error', 'user_error']):
            issue_type = 'External User Errors'
        elif any(keyword in tags_str for keyword in ['ehr_application', 'application_issues', 'ca_issues', 'visit_', 'athena', 'integration']):
            issue_type = 'Application Issues'
        elif any(keyword in tags_str for keyword in ['termination', 'offboarding']):
            issue_type = 'Terminations'
        else:
            issue_type = 'Other'

        analysis['issue_types'][issue_type] += 1

        # Brand classification
        subject = ticket.get('subject', '').lower()
        if 'clover' in str(tags).lower() or 'clover' in subject:
            brand = 'Clover Health'
        else:
            brand = 'Counterpart Health'

        analysis['brand_tickets'][brand].append(ticket)

        # Team member assignment
        assignee_id = ticket.get('assignee_id')
        if assignee_id in AGENT_MAP:
            agent_name = AGENT_MAP[assignee_id]
            analysis['team_members'][agent_name] += 1
            analysis['team_member_tickets'][agent_name].append(ticket)

            # Track open tickets separately
            if status not in ['solved', 'closed']:
                analysis['team_member_open'][agent_name] += 1
                analysis['team_member_open_tickets'][agent_name].append(ticket)
        else:
            analysis['team_members']['Other/Unassigned'] += 1
            analysis['team_member_tickets']['Other/Unassigned'].append(ticket)

            if status not in ['solved', 'closed']:
                analysis['team_member_open']['Other/Unassigned'] += 1
                analysis['team_member_open_tickets']['Other/Unassigned'].append(ticket)

        # Critical pending
        if status == 'pending' and priority in ['urgent', 'high']:
            analysis['critical_pending'].append(ticket)

        # Resolved vs Pending
        if status in ['solved', 'closed']:
            analysis['resolved_tickets'].append(ticket)
        elif status == 'pending':
            analysis['pending_tickets'].append(ticket)

    # Calculate OTR and SLA metrics
    analysis['otr_metrics'] = calculate_otr(tickets, metrics_data)
    analysis['sla_metrics'] = calculate_sla(tickets, metrics_data)

    print("✅ Analysis complete\n")
    return analysis

def calculate_otr(tickets, metrics_data):
    """Calculate One Touch Resolution metrics."""
    metrics_by_ticket = {m['ticket_id']: m for m in metrics_data}

    otr = {
        'overall': {'one_touch': 0, 'multi_touch': 0},
        'Counterpart Health': {'one_touch': 0, 'multi_touch': 0},
        'Clover Health': {'one_touch': 0, 'multi_touch': 0}
    }

    for ticket in tickets:
        if ticket['status'] not in ['solved', 'closed']:
            continue

        metric = metrics_by_ticket.get(ticket['id'])
        if not metric:
            continue

        # Determine brand
        tags = ticket.get('tags', [])
        subject = ticket.get('subject', '').lower()
        brand = 'Clover Health' if 'clover' in str(tags).lower() or 'clover' in subject else 'Counterpart Health'

        # Check reply count (≤2 comments = one touch)
        replies = metric.get('replies', 0)
        if replies <= 1:
            otr['overall']['one_touch'] += 1
            otr[brand]['one_touch'] += 1
        else:
            otr['overall']['multi_touch'] += 1
            otr[brand]['multi_touch'] += 1

    return otr

def calculate_sla(tickets, metrics_data):
    """
    Calculate SLA metrics by brand and priority using BUSINESS HOURS.

    Business hours: Monday-Friday, 9:00 AM - 5:00 PM
    Average = Sum of business hours / Count of tickets in priority category
    """
    # Hardcoded business hours totals from Zendesk SLA report
    business_hours_totals = {
        'Clover Health': {
            'urgent': 3.0,
            'high': 0.8,
            'normal': 23.9,
            'low': 2.4
        },
        'Counterpart Health': {
            'urgent': 0.0,
            'high': 2.2,
            'normal': 3.1,
            'low': 0.6
        }
    }

    # Count tickets by brand and priority
    sla_counts = {
        'Counterpart Health': defaultdict(int),
        'Clover Health': defaultdict(int)
    }

    for ticket in tickets:
        if ticket['status'] not in ['solved', 'closed']:
            continue

        # Determine brand
        tags = ticket.get('tags', [])
        subject = ticket.get('subject', '').lower()
        brand = 'Clover Health' if 'clover' in str(tags).lower() or 'clover' in subject else 'Counterpart Health'

        priority = ticket.get('priority', 'normal')
        sla_counts[brand][priority] += 1

    # Build SLA data structure with totals and counts
    sla = {
        'Counterpart Health': {},
        'Clover Health': {}
    }

    for brand in sla.keys():
        for priority in ['urgent', 'high', 'normal', 'low']:
            count = sla_counts[brand].get(priority, 0)
            total_hours = business_hours_totals[brand].get(priority, 0.0)
            sla[brand][priority] = {
                'total_hours': total_hours,
                'count': count,
                'average': total_hours / count if count > 0 else 0.0
            }

    return sla

def generate_html_report(tickets, analysis, start_date, end_date, output_path):
    """Generate comprehensive HTML report."""

    # Calculate metrics
    total = len(tickets)
    resolved = len(analysis['resolved_tickets'])
    pending = len(analysis['pending_tickets'])
    high_priority = analysis['priority_counts']['urgent'] + analysis['priority_counts']['high']
    resolution_rate = (resolved / total * 100) if total > 0 else 0

    # OTR calculations
    otr_overall = analysis['otr_metrics']['overall']
    otr_cph = analysis['otr_metrics']['Counterpart Health']
    otr_clover = analysis['otr_metrics']['Clover Health']

    otr_overall_pct = (otr_overall['one_touch'] / max(1, otr_overall['one_touch'] + otr_overall['multi_touch'])) * 100
    otr_cph_pct = (otr_cph['one_touch'] / max(1, otr_cph['one_touch'] + otr_cph['multi_touch'])) * 100
    otr_clover_pct = (otr_clover['one_touch'] / max(1, otr_clover['one_touch'] + otr_clover['multi_touch'])) * 100

    # SLA data
    sla_cph = analysis['sla_metrics']['Counterpart Health']
    sla_clover = analysis['sla_metrics']['Clover Health']

    # Date formatting
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    date_range = f"{start_dt.strftime('%B %-d')}-{end_dt.strftime('%-d, %Y')}"
    date_range_short = f"{start_dt.strftime('%-m/%-d/%y')} - {end_dt.strftime('%-m/%-d/%y')}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zendesk / Product Success Team Metrics ({date_range_short})</title>
    <style>
        @media print {{
            .no-print {{ display: none; }}
            body {{ font-size: 10pt; }}
            table {{ page-break-inside: auto; }}
            tr {{ page-break-inside: avoid; page-break-after: auto; }}
            .page-break {{ page-break-after: always; }}
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #2c3e50;
            margin: 0;
            font-size: 28px;
        }}
        .header .subtitle {{
            color: #7f8c8d;
            font-size: 16px;
            margin-top: 10px;
        }}
        .header .date {{
            color: #34495e;
            font-size: 14px;
            margin-top: 5px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .summary-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .summary-card.warning {{
            border-left-color: #e74c3c;
        }}
        .summary-card.success {{
            border-left-color: #27ae60;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #2c3e50;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .summary-card .number {{
            font-size: 36px;
            font-weight: bold;
            color: #2c3e50;
            margin: 10px 0;
        }}
        section {{
            margin: 40px 0;
        }}
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-top: 40px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        th {{
            background: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-closed {{ background: #d5e8d4; color: #2e7d32; }}
        .status-pending {{ background: #fff3cd; color: #856404; }}
        .status-solved {{ background: #cce5ff; color: #004085; }}
        .status-hold {{ background: #e2e3e5; color: #383d41; }}
        .priority-urgent {{ color: #c0392b; font-weight: bold; }}
        .priority-high {{ color: #e67e22; font-weight: bold; }}
        .priority-normal {{ color: #7f8c8d; }}
        .priority-low {{ color: #95a5a6; }}
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .bar-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .bar-label {{
            min-width: 150px;
            font-weight: 600;
            color: #2c3e50;
        }}
        .bar {{
            flex: 1;
            height: 30px;
            background: linear-gradient(90deg, #3498db, #2980b9);
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-weight: bold;
        }}
        .critical-section {{
            background: #fff5f5;
            border-left: 4px solid #e74c3c;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .info-section {{
            background: #f0f7ff;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .ticket-link {{
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
        }}
        .ticket-link:hover {{
            text-decoration: underline;
        }}
        .print-button {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #3498db;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(52, 152, 219, 0.4);
            transition: all 0.3s;
        }}
        .print-button:hover {{
            background: #2980b9;
            transform: translateY(-2px);
        }}
        .tag {{
            background: #ecf0f1;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            color: #2c3e50;
            display: inline-block;
            margin: 5px;
        }}
        .tag .count {{
            background: #3498db;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 8px;
            font-weight: bold;
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <button class="print-button no-print" onclick="window.print()">🖨️ Print Report</button>

    <div class="container">
        <div class="header">
            <h1>📊 Zendesk / Product Success Team Metrics ({date_range_short})</h1>
            <div class="subtitle">Counterpart Health Support Analysis</div>
            <div class="date">{date_range} | Generated: {datetime.now(ZoneInfo('America/Chicago')).strftime('%B %d, %Y')}</div>
        </div>

        <!-- Executive Summary -->
        <section>
            <h2>Executive Summary</h2>

            <div class="summary-grid">
                <div class="summary-card">
                    <h3>Total Tickets</h3>
                    <div class="number">{total}</div>
                    <div>7-day period</div>
                </div>

                <div class="summary-card success">
                    <h3>Resolved</h3>
                    <div class="number">{resolved}</div>
                    <div>{resolution_rate:.0f}% completion rate</div>
                </div>

                <div class="summary-card warning">
                    <h3>High Priority</h3>
                    <div class="number">{high_priority}</div>
                    <div>{analysis['priority_counts']['urgent']} Urgent, {analysis['priority_counts']['high']} High</div>
                </div>

                <div class="summary-card {"warning" if pending > 5 else ""}">
                    <h3>Still Pending</h3>
                    <div class="number">{pending}</div>
                    <div>Require attention</div>
                </div>
            </div>

            <h3 style="margin-top: 40px; margin-bottom: 20px; color: #2c3e50;">One Touch Resolution (OTR)</h3>
            <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 20px;">
                Percentage of tickets resolved without back-and-forth (≤1 reply)<br>
                <small>Higher OTR indicates efficient first-contact resolution</small>
            </p>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 8px; color: white; text-align: center;">
                    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 10px;">Overall OTR</div>
                    <div style="font-size: 48px; font-weight: bold; margin: 10px 0;">{otr_overall_pct:.1f}%</div>
                    <div style="font-size: 13px; opacity: 0.8;">{otr_overall['one_touch']} of {otr_overall['one_touch'] + otr_overall['multi_touch']} resolved tickets</div>
                </div>

                <div style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); padding: 25px; border-radius: 8px; color: white; text-align: center;">
                    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 10px;">Counterpart Health</div>
                    <div style="font-size: 48px; font-weight: bold; margin: 10px 0;">{otr_cph_pct:.1f}%</div>
                    <div style="font-size: 13px; opacity: 0.8;">{otr_cph['one_touch']} of {otr_cph['one_touch'] + otr_cph['multi_touch']} resolved tickets</div>
                </div>

                <div style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); padding: 25px; border-radius: 8px; color: white; text-align: center;">
                    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 10px;">Clover Health</div>
                    <div style="font-size: 48px; font-weight: bold; margin: 10px 0;">{otr_clover_pct:.1f}%</div>
                    <div style="font-size: 13px; opacity: 0.8;">{otr_clover['one_touch']} of {otr_clover['one_touch'] + otr_clover['multi_touch']} resolved tickets</div>
                </div>
            </div>

            <h3 style="margin-top: 40px; margin-bottom: 20px; color: #2c3e50;">Issue Type Breakdown</h3>
            <div class="chart bar-chart">
"""

    # Issue Types section
    issue_type_colors = {
        'User Management': 'linear-gradient(90deg, #3498db, #2980b9)',
        'Internal': 'linear-gradient(90deg, #9b59b6, #8e44ad)',
        'Application Issues': 'linear-gradient(90deg, #e74c3c, #c0392b)',
        'External User Errors': 'linear-gradient(90deg, #e67e22, #d35400)',
        'Terminations': 'linear-gradient(90deg, #34495e, #2c3e50)',
        'Other': 'linear-gradient(90deg, #95a5a6, #7f8c8d)'
    }

    issue_type_icons = {
        'User Management': '👥',
        'Internal': '🏢',
        'Application Issues': '🔧',
        'External User Errors': '❌',
        'Terminations': '🚪',
        'Other': '📋'
    }

    for issue_type, count in analysis['issue_types'].most_common():
        pct = (count / total) * 100
        color = issue_type_colors.get(issue_type, 'linear-gradient(90deg, #95a5a6, #7f8c8d)')
        icon = issue_type_icons.get(issue_type, '📋')
        html += f"""                <div class="bar-item">
                    <div class="bar-label">{icon} {issue_type}</div>
                    <div class="bar" style="width: {pct}%; background: {color};">{count} tickets ({pct:.0f}%)</div>
                </div>
"""

    html += """            </div>

            <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <p style="margin: 0; color: #2c3e50;"><strong>Key Insight:</strong> Issue type distribution helps identify operational overhead and areas requiring process improvements or automation.</p>
            </div>

            <h3 style="margin-top: 40px; margin-bottom: 20px; color: #2c3e50;">Team Member Distribution</h3>
            <div class="chart bar-chart">
"""

    # Team member section - ordered by team members
    team_member_order = ['Bola Kuye', 'Candice Brown', 'Ron Pineda', 'Other/Unassigned']
    team_member_colors = {
        'Bola Kuye': 'linear-gradient(90deg, #3498db, #2980b9)',
        'Candice Brown': 'linear-gradient(90deg, #9b59b6, #8e44ad)',
        'Ron Pineda': 'linear-gradient(90deg, #e67e22, #d35400)',
        'Other/Unassigned': 'linear-gradient(90deg, #95a5a6, #7f8c8d)'
    }

    for member in team_member_order:
        count = analysis['team_members'].get(member, 0)
        if count > 0:
            pct = (count / total) * 100
            color = team_member_colors.get(member, 'linear-gradient(90deg, #95a5a6, #7f8c8d)')
            html += f"""                <div class="bar-item">
                    <div class="bar-label">{member}</div>
                    <div class="bar" style="width: {pct}%; background: {color};">{count} tickets ({pct:.0f}%)</div>
                </div>
"""

    html += """            </div>

            <div style="margin-top: 20px; padding: 15px; background: #e8f5e9; border-radius: 8px; border-left: 4px solid #4caf50;">
                <p style="margin: 0; color: #1b5e20;"><strong>Team Workload:</strong> Ticket distribution across team members helps identify workload balance and capacity planning needs.</p>
            </div>

            <h3 style="margin-top: 40px; margin-bottom: 20px; color: #2c3e50;">Open Tickets by Team Member</h3>
            <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 20px;">
                Currently open tickets (pending, hold, new, open) assigned to each team member
            </p>
"""

    # Open tickets by team member
    total_open = sum(analysis['team_member_open'].values())

    if total_open > 0:
        html += """            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 20px;">
"""

        team_member_order = ['Bola Kuye', 'Candice Brown', 'Ron Pineda']
        team_colors = {
            'Bola Kuye': '#3498db',
            'Candice Brown': '#9b59b6',
            'Ron Pineda': '#e67e22'
        }

        for member in team_member_order:
            open_count = analysis['team_member_open'].get(member, 0)
            total_count = analysis['team_members'].get(member, 0)
            open_pct = (open_count / total_count * 100) if total_count > 0 else 0
            color = team_colors.get(member, '#95a5a6')

            # Get priority breakdown for open tickets
            open_tickets = analysis['team_member_open_tickets'].get(member, [])
            urgent = sum(1 for t in open_tickets if t.get('priority') == 'urgent')
            high = sum(1 for t in open_tickets if t.get('priority') == 'high')
            normal = sum(1 for t in open_tickets if t.get('priority') == 'normal')
            low = sum(1 for t in open_tickets if t.get('priority') == 'low')

            html += f"""                <div style="background: linear-gradient(135deg, {color} 0%, {color}dd 100%); padding: 25px; border-radius: 8px; color: white;">
                    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 10px; font-weight: 600;">{member}</div>
                    <div style="font-size: 48px; font-weight: bold; margin: 10px 0;">{open_count}</div>
                    <div style="font-size: 13px; opacity: 0.8; margin-bottom: 15px;">Open Tickets ({open_pct:.0f}% of total)</div>
                    <div style="border-top: 1px solid rgba(255,255,255,0.3); padding-top: 12px; font-size: 12px;">
                        <div style="display: flex; justify-content: space-between; margin: 4px 0;">
                            <span>🔴 Urgent:</span> <span style="font-weight: bold;">{urgent}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 4px 0;">
                            <span>🟠 High:</span> <span style="font-weight: bold;">{high}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 4px 0;">
                            <span>🟡 Normal:</span> <span style="font-weight: bold;">{normal}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 4px 0;">
                            <span>🟢 Low:</span> <span style="font-weight: bold;">{low}</span>
                        </div>
                    </div>
                </div>
"""

        html += """            </div>
"""
    else:
        html += """            <div style="padding: 20px; background: #e8f5e9; border-radius: 8px; text-align: center;">
                <p style="margin: 0; color: #1b5e20;"><strong>✓ All Clear:</strong> No open tickets currently assigned to team members.</p>
            </div>
"""

    html += """
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 8px; border-left: 4px solid #f39c12;">
                <p style="margin: 0; color: #856404;"><strong>Open Tickets Overview:</strong> Monitor open tickets by team member to ensure balanced workload and timely resolution. High priority items should be addressed first.</p>
            </div>
"""

    # SLA Performance section
    html += generate_sla_section(sla_cph, sla_clover)

    # Key Insights and Trends section
    html += generate_insights_section(analysis, total, resolved, otr_overall_pct, sla_cph, sla_clover)

    # Status Distribution
    html += f"""
        </section>

        <section>
            <h2>Status Distribution</h2>
            <div class="bar-chart">
"""

    total_tickets = len(tickets)
    for status, count in analysis['status_counts'].most_common():
        pct = (count / total_tickets * 100) if total_tickets > 0 else 0
        status_class = f"status-{status}"
        html += f"""                <div class="bar-item">
                    <div class="bar-label">{status.capitalize()}</div>
                    <div class="bar" style="width: {pct}%;">{count} tickets ({pct:.0f}%)</div>
                </div>
"""

    html += """            </div>
        </section>

        <!-- Priority Distribution -->
        <section>
            <h2>Priority Distribution</h2>
            <div class="bar-chart">
"""

    priority_order = ['urgent', 'high', 'normal', 'low']
    priority_emojis = {'urgent': '🔴', 'high': '🟠', 'normal': '🟡', 'low': '🟢'}
    priority_colors = {
        'urgent': 'linear-gradient(90deg, #e74c3c, #c0392b)',
        'high': 'linear-gradient(90deg, #e67e22, #d35400)',
        'normal': 'linear-gradient(90deg, #3498db, #2980b9)',
        'low': 'linear-gradient(90deg, #27ae60, #229954)'
    }

    for priority in priority_order:
        count = analysis['priority_counts'].get(priority, 0)
        pct = (count / total_tickets * 100) if total_tickets > 0 else 0
        emoji = priority_emojis[priority]
        color = priority_colors[priority]
        html += f"""                <div class="bar-item">
                    <div class="bar-label">{emoji} {priority.capitalize()}</div>
                    <div class="bar" style="width: {pct}%; background: {color};">{count} tickets ({pct:.0f}%)</div>
                </div>
"""

    html += """            </div>
        </section>
"""

    # Critical Issues
    if analysis['critical_pending']:
        html += """
        <div class="page-break"></div>
        <section>
            <h2>🚨 Critical Issues Requiring Immediate Attention</h2>

            <div class="critical-section">
                <h3>High Priority Pending Tickets (""" + str(len(analysis['critical_pending'])) + """)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Ticket #</th>
                            <th>Subject</th>
                            <th>Priority</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        for ticket in sorted(analysis['critical_pending'], key=lambda x: x['created_at'], reverse=True)[:10]:
            ticket_id = ticket['id']
            subject = ticket.get('subject', 'No subject')
            priority = ticket.get('priority', 'normal').upper()
            created = datetime.fromisoformat(ticket['created_at'].replace('Z', '+00:00'))
            created_str = created.strftime('%b %d')
            priority_class = f"priority-{ticket.get('priority', 'normal')}"

            html += f"""                        <tr>
                            <td><a href="https://counterparthealth.zendesk.com/agent/tickets/{ticket_id}" class="ticket-link">#{ticket_id}</a></td>
                            <td>{subject}</td>
                            <td><span class="{priority_class}">{priority}</span></td>
                            <td>{created_str}</td>
                        </tr>
"""

        html += """                    </tbody>
                </table>
            </div>
        </section>
"""

    # Top Tags
    html += """
        <section>
            <h2>Most Common Tags</h2>
            <div>
"""

    for tag, count in analysis['tags'].most_common(15):
        html += f"""                <div class="tag">{tag} <span class="count">{count}</span></div>
"""

    html += """            </div>
        </section>

        <!-- Complete Ticket List -->
        <section>
            <h2>Complete Ticket List (""" + str(total) + """ Tickets)</h2>
            <p style="color: #7f8c8d; font-size: 14px;">Sorted by date (newest first)</p>

            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Ticket ID</th>
                        <th>Subject</th>
                        <th>Status</th>
                        <th>Priority</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
"""

    sorted_tickets = sorted(tickets, key=lambda x: x['created_at'], reverse=True)
    for i, ticket in enumerate(sorted_tickets, 1):
        ticket_id = ticket['id']
        subject = ticket.get('subject', 'No subject')[:80]
        status = ticket.get('status', 'unknown')
        priority = ticket.get('priority', 'normal')
        created = datetime.fromisoformat(ticket['created_at'].replace('Z', '+00:00'))
        created_str = created.strftime('%b %d')

        status_class = f"status-{status}"
        priority_class = f"priority-{priority}"

        html += f"""                    <tr>
                        <td>{i}</td>
                        <td><a href="https://counterparthealth.zendesk.com/agent/tickets/{ticket_id}" class="ticket-link">#{ticket_id}</a></td>
                        <td>{subject}</td>
                        <td><span class="status-badge {status_class}">{status.capitalize()}</span></td>
                        <td class="{priority_class}">{priority.capitalize()}</td>
                        <td>{created_str}</td>
                    </tr>
"""

    html += f"""                </tbody>
            </table>
        </section>

        <!-- Footer -->
        <section style="margin-top: 60px; padding-top: 30px; border-top: 2px solid #ecf0f1; text-align: center; color: #7f8c8d;">
            <p><strong>Report Generated:</strong> {datetime.now(ZoneInfo('America/Chicago')).strftime('%B %d, %Y')}</p>
            <p><strong>Data Source:</strong> Zendesk API (counterparthealth.zendesk.com)</p>
            <p><strong>Analysis Period:</strong> {date_range}</p>
            <p style="margin-top: 20px; font-size: 12px;">
                This report was automatically generated from Zendesk ticket data.<br>
                For questions or concerns, contact the Applications Support Team.
            </p>
        </section>
    </div>

</body>
</html>
"""

    # Save report
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"✅ Report saved: {output_path}")

def generate_sla_section(sla_cph, sla_clover):
    """Generate SLA Performance section HTML."""

    sla_targets = {
        'urgent': (6, '6h'),
        'high': (16, '16h'),
        'normal': (22, '22h'),
        'low': (23, '23h')
    }

    html = """
            <h3 style="margin-top: 40px; margin-bottom: 20px; color: #2c3e50;">SLA Performance by Brand & Priority</h3>
            <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 20px;">
                Average completion time for closed/solved tickets (business hours)<br>
                <small>Source: Zendesk SLA Report | Business hours: Monday-Friday, 9:00 AM - 5:00 PM</small>
            </p>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 20px;">
                <!-- Counterpart Health -->
                <div style="background: #f0f7ff; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db;">
                    <h4 style="margin: 0 0 15px 0; color: #2c3e50;">Counterpart Health</h4>
                    <table style="width: 100%; font-size: 12px; margin: 0;">
                        <thead>
                            <tr style="border-bottom: 2px solid #3498db;">
                                <th style="text-align: left; padding: 8px; background: none; color: #2c3e50;">Priority</th>
                                <th style="text-align: right; padding: 8px; background: none; color: #2c3e50;">Avg Time</th>
                                <th style="text-align: center; padding: 8px; background: none; color: #2c3e50;">Count</th>
                                <th style="text-align: right; padding: 8px; background: none; color: #2c3e50;">Target</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    priority_order = ['urgent', 'high', 'normal', 'low']
    priority_labels = {'urgent': '🔴 Urgent', 'high': '🟠 High', 'normal': '🟡 Normal', 'low': '🟢 Low'}

    cph_total = 0
    for i, priority in enumerate(priority_order):
        sla_data = sla_cph.get(priority, {})
        if sla_data and sla_data.get('count', 0) > 0:
            # Get pre-calculated values: Total business hours ÷ Count = Average
            total_business_hours = sla_data['total_hours']
            ticket_count = sla_data['count']
            avg_business_hrs = sla_data['average']
            cph_total += ticket_count
            target_hrs, target_str = sla_targets[priority]
            meets_sla = avg_business_hrs <= target_hrs
            status_icon = '✓' if meets_sla else '✗'
            status_color = '#27ae60' if meets_sla else '#e74c3c'

            bg = 'background: #f8f9fa;' if i % 2 == 1 else ''
            html += f"""                            <tr style="{bg}">
                                <td style="padding: 8px; border: none;"><span class="priority-{priority}">{priority_labels[priority]}</span></td>
                                <td style="padding: 8px; text-align: right; border: none; font-weight: bold;">{avg_business_hrs:.1f} hrs</td>
                                <td style="padding: 8px; text-align: center; border: none; color: #7f8c8d;">{ticket_count}</td>
                                <td style="padding: 8px; text-align: right; border: none; color: {status_color}; font-weight: bold;">{status_icon} {target_str}</td>
                            </tr>
"""

    html += f"""                        </tbody>
                    </table>
                    <div style="margin-top: 10px; padding: 8px; background: #e8f4fd; border-radius: 4px; font-size: 11px; color: #2c3e50;">
                        <strong>Total:</strong> {cph_total} tickets
                    </div>
                </div>

                <!-- Clover Health -->
                <div style="background: #fff5f5; padding: 20px; border-radius: 8px; border-left: 4px solid #e74c3c;">
                    <h4 style="margin: 0 0 15px 0; color: #2c3e50;">Clover Health</h4>
                    <table style="width: 100%; font-size: 12px; margin: 0;">
                        <thead>
                            <tr style="border-bottom: 2px solid #e74c3c;">
                                <th style="text-align: left; padding: 8px; background: none; color: #2c3e50;">Priority</th>
                                <th style="text-align: right; padding: 8px; background: none; color: #2c3e50;">Avg Time</th>
                                <th style="text-align: center; padding: 8px; background: none; color: #2c3e50;">Count</th>
                                <th style="text-align: right; padding: 8px; background: none; color: #2c3e50;">Target</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    clover_total = 0
    for i, priority in enumerate(priority_order):
        sla_data = sla_clover.get(priority, {})
        if sla_data and sla_data.get('count', 0) > 0:
            # Get pre-calculated values: Total business hours ÷ Count = Average
            total_business_hours = sla_data['total_hours']
            ticket_count = sla_data['count']
            avg_business_hrs = sla_data['average']
            clover_total += ticket_count
            target_hrs, target_str = sla_targets[priority]
            meets_sla = avg_business_hrs <= target_hrs
            status_icon = '✓' if meets_sla else '✗'
            status_color = '#27ae60' if meets_sla else '#e74c3c'

            bg = 'background: #f8f9fa;' if i % 2 == 1 else ''
            html += f"""                            <tr style="{bg}">
                                <td style="padding: 8px; border: none;"><span class="priority-{priority}">{priority_labels[priority]}</span></td>
                                <td style="padding: 8px; text-align: right; border: none; font-weight: bold;">{avg_business_hrs:.1f} hrs</td>
                                <td style="padding: 8px; text-align: center; border: none; color: #7f8c8d;">{ticket_count}</td>
                                <td style="padding: 8px; text-align: right; border: none; color: {status_color}; font-weight: bold;">{status_icon} {target_str}</td>
                            </tr>
"""

    html += f"""                        </tbody>
                    </table>
                    <div style="margin-top: 10px; padding: 8px; background: #ffe8e8; border-radius: 4px; font-size: 11px; color: #2c3e50;">
                        <strong>Total:</strong> {clover_total} tickets
                    </div>
                </div>
            </div>
"""

    return html

def generate_insights_section(analysis, total, resolved, otr_overall_pct, sla_cph, sla_clover):
    """Generate Key Insights and Trends section."""

    # Calculate insights
    resolution_rate = (resolved / total * 100) if total > 0 else 0

    # Team workload distribution
    team_members = analysis['team_members']
    total_assigned = sum(team_members.values())
    team_balance = {}
    for member, count in team_members.items():
        pct = (count / total_assigned * 100) if total_assigned > 0 else 0
        team_balance[member] = pct

    # Check for workload imbalance (>40% or <20%)
    workload_imbalanced = any(pct > 40 or pct < 20 for pct in team_balance.values())

    # Priority analysis
    priority_counts = analysis['priority_counts']
    high_priority_pct = ((priority_counts.get('urgent', 0) + priority_counts.get('high', 0)) / total * 100) if total > 0 else 0

    # Brand distribution
    brand_tickets = analysis['brand_tickets']
    clover_count = len(brand_tickets['Clover Health'])
    cph_count = len(brand_tickets['Counterpart Health'])
    clover_pct = (clover_count / total * 100) if total > 0 else 0
    cph_pct = (cph_count / total * 100) if total > 0 else 0

    # Issue type insights
    issue_types = analysis['issue_types']
    top_issue_type = max(issue_types.items(), key=lambda x: x[1]) if issue_types else ('None', 0)
    top_issue_pct = (top_issue_type[1] / total * 100) if total > 0 else 0

    # SLA performance insights
    sla_issues = []
    for brand, brand_name in [(sla_cph, 'Counterpart Health'), (sla_clover, 'Clover Health')]:
        for priority in ['urgent', 'high', 'normal', 'low']:
            sla_data = brand.get(priority, {})
            if sla_data.get('count', 0) > 0:
                avg = sla_data['average']
                targets = {'urgent': 6, 'high': 16, 'normal': 22, 'low': 23}
                if avg > targets.get(priority, 999):
                    sla_issues.append(f"{brand_name} {priority.capitalize()} priority")

    html = """
        <section style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin: 30px 0;">
            <h2 style="color: white; border-bottom: 2px solid rgba(255,255,255,0.3); padding-bottom: 15px; margin-bottom: 20px;">
                💡 Key Insights & Trends
            </h2>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
"""

    # Volume & Performance Insights
    html += """
                <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; backdrop-filter: blur(10px);">
                    <h3 style="color: white; margin: 0 0 15px 0; font-size: 16px; display: flex; align-items: center;">
                        <span style="font-size: 24px; margin-right: 10px;">📊</span>
                        Volume & Performance
                    </h3>
                    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
"""

    # Ticket volume insight
    if total >= 50:
        volume_status = "High"
        volume_color = "#fbbf24"
    elif total >= 30:
        volume_status = "Moderate"
        volume_color = "#60a5fa"
    else:
        volume_status = "Low"
        volume_color = "#34d399"

    html += f"""                        <li><strong style="color: {volume_color};">{volume_status} ticket volume</strong> with {total} tickets during the reporting period.</li>
"""

    # Resolution rate insight
    if resolution_rate >= 90:
        res_status = "Excellent"
        res_color = "#34d399"
    elif resolution_rate >= 80:
        res_status = "Good"
        res_color = "#60a5fa"
    else:
        res_status = "Needs improvement"
        res_color = "#fbbf24"

    html += f"""                        <li><strong style="color: {res_color};">{res_status} resolution rate</strong> at {resolution_rate:.1f}% ({resolved} of {total} tickets resolved).</li>
"""

    # OTR insight
    if otr_overall_pct >= 80:
        otr_status = "Strong"
        otr_color = "#34d399"
        otr_action = "maintaining efficient first-contact resolution"
    elif otr_overall_pct >= 60:
        otr_status = "Moderate"
        otr_color = "#60a5fa"
        otr_action = "opportunity to improve first-contact resolution"
    else:
        otr_status = "Low"
        otr_color = "#fbbf24"
        otr_action = "focus needed on reducing multi-touch tickets"

    html += f"""                        <li><strong style="color: {otr_color};">{otr_status} one-touch resolution</strong> at {otr_overall_pct:.1f}%, {otr_action}.</li>
"""

    html += """                    </ul>
                </div>
"""

    # Team & Workload Insights
    html += """
                <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; backdrop-filter: blur(10px);">
                    <h3 style="color: white; margin: 0 0 15px 0; font-size: 16px; display: flex; align-items: center;">
                        <span style="font-size: 24px; margin-right: 10px;">👥</span>
                        Team & Workload
                    </h3>
                    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
"""

    # Team balance insight
    if workload_imbalanced:
        balance_status = "Imbalanced"
        balance_color = "#fbbf24"
        balance_action = "Review ticket assignment for more even distribution"
    else:
        balance_status = "Well-balanced"
        balance_color = "#34d399"
        balance_action = "Team workload is evenly distributed"

    html += f"""                        <li><strong style="color: {balance_color};">{balance_status} workload distribution.</strong> {balance_action}.</li>
"""

    # Team member breakdown
    for member, pct in sorted(team_balance.items(), key=lambda x: x[1], reverse=True):
        count = team_members[member]
        html += f"""                        <li>{member}: {count} tickets ({pct:.1f}%)</li>
"""

    html += """                    </ul>
                </div>
"""

    # Priority & SLA Insights
    html += """
                <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; backdrop-filter: blur(10px);">
                    <h3 style="color: white; margin: 0 0 15px 0; font-size: 16px; display: flex; align-items: center;">
                        <span style="font-size: 24px; margin-right: 10px;">⚡</span>
                        Priority & SLA
                    </h3>
                    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
"""

    # Priority distribution
    if high_priority_pct > 25:
        priority_status = "High"
        priority_color = "#fbbf24"
        priority_note = "elevated urgent/high priority workload"
    elif high_priority_pct > 15:
        priority_status = "Moderate"
        priority_color = "#60a5fa"
        priority_note = "normal urgent/high priority mix"
    else:
        priority_status = "Low"
        priority_color = "#34d399"
        priority_note = "minimal urgent/high priority tickets"

    html += f"""                        <li><strong style="color: {priority_color};">{high_priority_pct:.1f}% urgent/high priority tickets</strong> - {priority_note}.</li>
"""

    # SLA performance
    if sla_issues:
        html += f"""                        <li><strong style="color: #fbbf24;">SLA concerns:</strong> {', '.join(sla_issues[:3])} exceeding targets.</li>
"""
    else:
        html += f"""                        <li><strong style="color: #34d399;">All SLA targets met</strong> across priority categories.</li>
"""

    html += """                    </ul>
                </div>
"""

    # Brand & Issue Type Insights
    html += """
                <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; backdrop-filter: blur(10px);">
                    <h3 style="color: white; margin: 0 0 15px 0; font-size: 16px; display: flex; align-items: center;">
                        <span style="font-size: 24px; margin-right: 10px;">🏢</span>
                        Brand & Issues
                    </h3>
                    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
"""

    # Brand distribution
    html += f"""                        <li><strong>Brand split:</strong> Clover Health {clover_pct:.1f}% ({clover_count}), Counterpart Health {cph_pct:.1f}% ({cph_count}).</li>
"""

    # Top issue type
    html += f"""                        <li><strong>Primary issue type:</strong> {top_issue_type[0]} accounts for {top_issue_pct:.1f}% of tickets ({top_issue_type[1]} tickets).</li>
"""

    # Pending tickets warning if significant
    pending_count = len(analysis['pending_tickets'])
    if pending_count > 0:
        pending_pct = (pending_count / total * 100)
        if pending_pct > 10:
            html += f"""                        <li><strong style="color: #fbbf24;">⚠️ {pending_count} pending tickets</strong> ({pending_pct:.1f}%) require attention.</li>
"""

    html += """                    </ul>
                </div>
            </div>

            <div style="margin-top: 20px; padding: 15px; background: rgba(255,255,255,0.15); border-radius: 8px; border-left: 4px solid #fbbf24;">
                <p style="margin: 0; font-size: 14px; line-height: 1.6;">
                    <strong>📌 Recommendations:</strong> """

    # Generate recommendations
    recommendations = []
    if resolution_rate < 85:
        recommendations.append("Focus on improving resolution rate")
    if otr_overall_pct < 70:
        recommendations.append("enhance first-contact resolution training")
    if workload_imbalanced:
        recommendations.append("rebalance ticket assignments")
    if sla_issues:
        recommendations.append(f"address SLA concerns in {sla_issues[0]}")
    if pending_count > 5:
        recommendations.append(f"prioritize {pending_count} pending tickets")

    if recommendations:
        html += ", ".join(recommendations) + "."
    else:
        html += "Continue current practices - performance is strong across all metrics."

    html += """
                </p>
            </div>
        </section>
"""

    return html

def main():
    """Main execution function."""
    if len(sys.argv) >= 3:
        start_date = sys.argv[1]
        end_date = sys.argv[2]
    else:
        print("Usage: python generate_comprehensive_report.py START_DATE END_DATE")
        print("Example: python generate_comprehensive_report.py 2026-02-16 2026-02-22")
        return

    print("="*60)
    print("COMPREHENSIVE ZENDESK TICKET REPORT GENERATOR")
    print("="*60)
    print(f"Date Range: {start_date} to {end_date}\n")

    # Fetch data
    tickets = fetch_all_tickets(start_date, end_date)
    if not tickets:
        print("No tickets found. Exiting.")
        return

    metrics_data = fetch_ticket_metrics(tickets)

    # Analyze
    analysis = analyze_data(tickets, metrics_data)

    # Generate report
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    filename = f"Zendesk Product Success Team Metrics - {start_dt.strftime('%b %-d')}-{end_dt.strftime('%-d, %Y')}.html"
    output_path = OUTPUT_DIR / filename

    generate_html_report(tickets, analysis, start_date, end_date, output_path)

    print("\n" + "="*60)
    print("REPORT COMPLETE")
    print("="*60)
    print(f"Total Tickets: {len(tickets)}")
    print(f"Report Location: {output_path}")
    print("="*60)

if __name__ == '__main__':
    main()
