#!/usr/bin/env python3
"""
Zendesk Real-Time Ticket Monitor
Continuous monitoring dashboard with auto-refresh and alerts.
"""

import os
import requests
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json
import sys


class ZendeskMonitor:
    def __init__(self, subdomain, email, api_token):
        self.subdomain = subdomain
        self.email = email
        self.api_token = api_token
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.previous_tickets = {}
        self.alert_sound = '\a'  # System bell

    def fetch_recent_tickets(self, hours=24):
        """Fetch tickets from the last N hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff_time.isoformat()

        search_url = f"{self.base_url}/search.json"
        params = {
            'query': f'type:ticket created>={cutoff_iso}',
            'sort_by': 'created_at',
            'sort_order': 'desc'
        }

        tickets = []
        while True:
            try:
                response = requests.get(
                    search_url,
                    auth=(f"{self.email}/token", self.api_token),
                    params=params,
                    timeout=10
                )

                if response.status_code != 200:
                    return None, f"Error: {response.status_code}"

                data = response.json()
                tickets.extend(data.get('results', []))

                next_page = data.get('next_page')
                if not next_page:
                    break

                search_url = next_page
                params = {}

            except Exception as e:
                return None, f"Connection error: {str(e)}"

        return tickets, None

    def get_stats(self, tickets):
        """Calculate statistics from tickets."""
        stats = {
            'total': len(tickets),
            'urgent': 0,
            'high': 0,
            'normal': 0,
            'low': 0,
            'new': 0,
            'open': 0,
            'pending': 0,
            'solved': 0,
            'closed': 0,
            'by_requester': defaultdict(int),
            'by_type': defaultdict(int),
        }

        for ticket in tickets:
            priority = ticket.get('priority', 'none')
            status = ticket.get('status', 'unknown')
            requester_id = ticket.get('requester_id')
            ticket_type = ticket.get('type', 'unknown')

            stats[priority] += 1
            stats[status] += 1
            stats['by_requester'][requester_id] += 1
            stats['by_type'][ticket_type] += 1

        return stats

    def detect_changes(self, current_tickets):
        """Detect new tickets and status changes."""
        changes = {
            'new_tickets': [],
            'status_changes': [],
            'priority_changes': []
        }

        current_ids = {t['id']: t for t in current_tickets}

        # Detect new tickets
        for ticket_id, ticket in current_ids.items():
            if ticket_id not in self.previous_tickets:
                changes['new_tickets'].append(ticket)
            else:
                prev = self.previous_tickets[ticket_id]
                # Detect status changes
                if prev.get('status') != ticket.get('status'):
                    changes['status_changes'].append({
                        'ticket': ticket,
                        'old_status': prev.get('status'),
                        'new_status': ticket.get('status')
                    })
                # Detect priority changes
                if prev.get('priority') != ticket.get('priority'):
                    changes['priority_changes'].append({
                        'ticket': ticket,
                        'old_priority': prev.get('priority'),
                        'new_priority': ticket.get('priority')
                    })

        self.previous_tickets = current_ids
        return changes

    def clear_screen(self):
        """Clear terminal screen."""
        os.system('clear' if os.name != 'nt' else 'cls')

    def format_time(self, iso_time):
        """Format ISO timestamp to readable time."""
        if not iso_time:
            return "Unknown"
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        return dt.strftime('%I:%M %p')

    def display_dashboard(self, tickets, stats, changes, error=None):
        """Display the monitoring dashboard."""
        self.clear_screen()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("=" * 80)
        print(f"🎯 ZENDESK REAL-TIME MONITOR - {self.subdomain}.zendesk.com")
        print(f"⏰ Last Update: {now}")
        print("=" * 80)

        if error:
            print(f"\n❌ ERROR: {error}\n")
            return

        # Overall stats
        print(f"\n📊 OVERVIEW (Last 24 Hours)")
        print(f"├─ Total Tickets: {stats['total']}")
        print(f"├─ New: {stats['new']} | Open: {stats['open']} | Pending: {stats['pending']}")
        print(f"└─ Solved: {stats['solved']} | Closed: {stats['closed']}")

        # Priority breakdown
        print(f"\n🔥 PRIORITY DISTRIBUTION")
        urgent_icon = "🔴" if stats['urgent'] > 0 else "⚪"
        high_icon = "🟠" if stats['high'] > 0 else "⚪"
        print(f"├─ {urgent_icon} Urgent: {stats['urgent']}")
        print(f"├─ {high_icon} High: {stats['high']}")
        print(f"├─ 🟡 Normal: {stats['normal']}")
        print(f"└─ 🟢 Low: {stats['low']}")

        # Alerts for new tickets
        if changes['new_tickets']:
            print(f"\n🚨 NEW TICKETS DETECTED ({len(changes['new_tickets'])})")
            print(self.alert_sound, end='')  # System bell
            for ticket in changes['new_tickets'][:5]:  # Show max 5
                ticket_id = ticket['id']
                subject = ticket.get('subject', 'No subject')[:50]
                priority = ticket.get('priority', 'none').upper()
                created = self.format_time(ticket.get('created_at'))
                print(f"├─ [{ticket_id}] {subject}")
                print(f"│  Priority: {priority} | Created: {created}")

        # Alerts for status changes
        if changes['status_changes']:
            print(f"\n📝 STATUS CHANGES ({len(changes['status_changes'])})")
            for change in changes['status_changes'][:5]:
                ticket = change['ticket']
                ticket_id = ticket['id']
                subject = ticket.get('subject', 'No subject')[:50]
                print(f"├─ [{ticket_id}] {subject}")
                print(f"│  {change['old_status'].upper()} → {change['new_status'].upper()}")

        # Priority changes
        if changes['priority_changes']:
            print(f"\n⚡ PRIORITY CHANGES ({len(changes['priority_changes'])})")
            for change in changes['priority_changes'][:5]:
                ticket = change['ticket']
                ticket_id = ticket['id']
                subject = ticket.get('subject', 'No subject')[:50]
                print(f"├─ [{ticket_id}] {subject}")
                print(f"│  {change['old_priority'].upper()} → {change['new_priority'].upper()}")

        # Top requesters
        if stats['by_requester']:
            print(f"\n👥 TOP REQUESTERS")
            top_requesters = sorted(stats['by_requester'].items(), key=lambda x: x[1], reverse=True)[:3]
            for requester_id, count in top_requesters:
                print(f"├─ Requester {requester_id}: {count} ticket(s)")

        # Urgent tickets list
        urgent_tickets = [t for t in tickets if t.get('priority') == 'urgent' and t.get('status') not in ['solved', 'closed']]
        if urgent_tickets:
            print(f"\n🔴 ACTIVE URGENT TICKETS ({len(urgent_tickets)})")
            for ticket in urgent_tickets[:10]:
                ticket_id = ticket['id']
                subject = ticket.get('subject', 'No subject')[:50]
                status = ticket.get('status', 'unknown').upper()
                created = self.format_time(ticket.get('created_at'))
                url = f"https://{self.subdomain}.zendesk.com/agent/tickets/{ticket_id}"
                print(f"├─ [{ticket_id}] {subject}")
                print(f"│  Status: {status} | Created: {created}")
                print(f"│  URL: {url}")

        print("\n" + "=" * 80)
        print("Press Ctrl+C to stop monitoring | Auto-refresh every 30 seconds")
        print("=" * 80)

    def run(self, refresh_interval=30):
        """Run the monitoring loop."""
        print("Starting Zendesk Monitor...")
        print("Fetching initial data...\n")

        try:
            while True:
                tickets, error = self.fetch_recent_tickets(hours=24)

                if tickets is not None:
                    stats = self.get_stats(tickets)
                    changes = self.detect_changes(tickets)
                    self.display_dashboard(tickets, stats, changes)
                else:
                    self.display_dashboard([], {}, {}, error=error)

                time.sleep(refresh_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user.")
            print("Final stats saved to zendesk_monitor_log.json")

            # Save final state
            with open('zendesk_monitor_log.json', 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'tickets': list(self.previous_tickets.values())
                }, f, indent=2)

            sys.exit(0)


def main():
    """Main function."""
    # Get credentials
    subdomain = os.getenv('ZENDESK_SUBDOMAIN') or input("Enter Zendesk subdomain: ")
    email = os.getenv('ZENDESK_EMAIL') or input("Enter your Zendesk email: ")
    api_token = os.getenv('ZENDESK_API_TOKEN') or input("Enter your API token: ")

    # Get refresh interval
    try:
        interval = int(os.getenv('REFRESH_INTERVAL', '30'))
    except:
        interval = 30

    monitor = ZendeskMonitor(subdomain, email, api_token)
    monitor.run(refresh_interval=interval)


if __name__ == "__main__":
    main()
