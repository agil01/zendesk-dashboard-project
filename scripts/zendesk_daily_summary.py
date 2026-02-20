#!/usr/bin/env python3
"""
Zendesk Daily Ticket Summary
Fetches all tickets received today and generates a markdown report.
"""

import os
import requests
from datetime import datetime, timezone
from collections import defaultdict
import sys


def get_credentials():
    """Get Zendesk credentials from environment variables or prompt."""
    subdomain = os.getenv('ZENDESK_SUBDOMAIN') or input("Enter Zendesk subdomain: ")
    email = os.getenv('ZENDESK_EMAIL') or input("Enter your Zendesk email: ")
    api_token = os.getenv('ZENDESK_API_TOKEN') or input("Enter your API token: ")

    return subdomain, email, api_token


def fetch_todays_tickets(subdomain, email, api_token):
    """Fetch all tickets created today from Zendesk."""
    base_url = f"https://{subdomain}.zendesk.com/api/v2"

    # Get today's date in ISO format (start of day UTC)
    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_iso = today_start.isoformat()

    # Search for tickets created today
    search_url = f"{base_url}/search.json"
    params = {
        'query': f'type:ticket created>={today_iso}',
        'sort_by': 'created_at',
        'sort_order': 'desc'
    }

    tickets = []

    while True:
        response = requests.get(
            search_url,
            auth=(f"{email}/token", api_token),
            params=params
        )

        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}", file=sys.stderr)
            sys.exit(1)

        data = response.json()
        tickets.extend(data.get('results', []))

        # Check if there are more pages
        next_page = data.get('next_page')
        if not next_page:
            break

        search_url = next_page
        params = {}  # Next page URL includes params

    return tickets


def generate_markdown_report(tickets, subdomain):
    """Generate a markdown report from tickets."""
    today = datetime.now(timezone.utc).date().strftime('%B %d, %Y')

    # Statistics
    total_tickets = len(tickets)

    # Group by priority
    by_priority = defaultdict(int)
    # Group by status
    by_status = defaultdict(int)
    # Group by type (if available)
    by_type = defaultdict(int)

    for ticket in tickets:
        priority = ticket.get('priority', 'none')
        status = ticket.get('status', 'unknown')
        ticket_type = ticket.get('type', 'unknown')

        by_priority[priority] += 1
        by_status[status] += 1
        by_type[ticket_type] += 1

    # Build markdown report
    report = f"""# Zendesk Daily Ticket Summary
**Date:** {today}
**Total Tickets Received:** {total_tickets}

---

## Overview

### By Priority
"""

    for priority in ['urgent', 'high', 'normal', 'low', 'none']:
        count = by_priority.get(priority, 0)
        if count > 0:
            report += f"- **{priority.title()}:** {count}\n"

    report += "\n### By Status\n"
    for status, count in sorted(by_status.items()):
        report += f"- **{status.title()}:** {count}\n"

    if by_type:
        report += "\n### By Type\n"
        for ticket_type, count in sorted(by_type.items()):
            report += f"- **{ticket_type.title()}:** {count}\n"

    report += "\n---\n\n## Ticket Details\n\n"

    if not tickets:
        report += "*No tickets received today.*\n"
    else:
        for ticket in tickets:
            ticket_id = ticket.get('id')
            subject = ticket.get('subject', 'No subject')
            status = ticket.get('status', 'unknown')
            priority = ticket.get('priority', 'none')
            created_at = ticket.get('created_at', '')
            requester_id = ticket.get('requester_id', 'N/A')

            # Format creation time
            if created_at:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_time = created_dt.strftime('%I:%M %p UTC')
            else:
                created_time = 'Unknown'

            ticket_url = f"https://{subdomain}.zendesk.com/agent/tickets/{ticket_id}"

            report += f"### [{ticket_id}]({ticket_url}) - {subject}\n"
            report += f"- **Status:** {status.title()}\n"
            report += f"- **Priority:** {priority.title()}\n"
            report += f"- **Created:** {created_time}\n"
            report += f"- **Requester ID:** {requester_id}\n"
            report += "\n"

    return report


def main():
    """Main function."""
    print("Zendesk Daily Ticket Summary")
    print("=" * 50)

    # Get credentials
    subdomain, email, api_token = get_credentials()

    print(f"\nFetching tickets from {subdomain}.zendesk.com...")

    # Fetch tickets
    tickets = fetch_todays_tickets(subdomain, email, api_token)

    print(f"Found {len(tickets)} ticket(s) created today.\n")

    # Generate report
    report = generate_markdown_report(tickets, subdomain)

    # Save to file
    filename = f"zendesk_summary_{datetime.now().strftime('%Y%m%d')}.md"
    with open(filename, 'w') as f:
        f.write(report)

    print(f"Report saved to: {filename}")
    print("\n" + "=" * 50)
    print(report)


if __name__ == "__main__":
    main()
