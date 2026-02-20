#!/usr/bin/env python3
"""
Zendesk MCP Server
Exposes Zendesk ticket data and operations via Model Context Protocol
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Add parent directory to path to import existing scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions, Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Resource,
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource,
    )
except ImportError:
    print("ERROR: mcp package not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

import requests
from requests.auth import HTTPBasicAuth


class ZendeskMCPServer:
    def __init__(self):
        self.server = Server("zendesk-server")
        self.subdomain = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
        self.email = os.getenv('ZENDESK_EMAIL')
        self.api_token = os.getenv('ZENDESK_API_TOKEN')
        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

        # Verify credentials
        if not self.email or not self.api_token:
            print("WARNING: ZENDESK_EMAIL or ZENDESK_API_TOKEN not set", file=sys.stderr)

        # Setup handlers
        self._setup_handlers()

    def _setup_handlers(self):
        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List available Zendesk resources."""
            return [
                Resource(
                    uri="zendesk://tickets/recent",
                    name="Recent Tickets",
                    description="Tickets from the last 24 hours",
                    mimeType="application/json",
                ),
                Resource(
                    uri="zendesk://tickets/urgent",
                    name="Urgent Tickets",
                    description="All urgent priority tickets",
                    mimeType="application/json",
                ),
                Resource(
                    uri="zendesk://tickets/open",
                    name="Open Tickets",
                    description="All open status tickets",
                    mimeType="application/json",
                ),
                Resource(
                    uri="zendesk://stats/summary",
                    name="Ticket Statistics",
                    description="Summary statistics for tickets",
                    mimeType="application/json",
                ),
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a Zendesk resource."""
            if uri == "zendesk://tickets/recent":
                tickets = await self._fetch_recent_tickets(hours=24)
                return json.dumps(tickets, indent=2)

            elif uri == "zendesk://tickets/urgent":
                tickets = await self._fetch_recent_tickets(hours=24)
                urgent = [t for t in tickets if t.get('priority') == 'urgent']
                return json.dumps(urgent, indent=2)

            elif uri == "zendesk://tickets/open":
                tickets = await self._fetch_recent_tickets(hours=24)
                open_tickets = [t for t in tickets if t.get('status') in ['new', 'open']]
                return json.dumps(open_tickets, indent=2)

            elif uri == "zendesk://stats/summary":
                tickets = await self._fetch_recent_tickets(hours=24)
                stats = self._calculate_stats(tickets)
                return json.dumps(stats, indent=2)

            else:
                raise ValueError(f"Unknown resource: {uri}")

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available Zendesk tools."""
            return [
                Tool(
                    name="get_urgent_tickets",
                    description="Get all urgent priority tickets with details",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hours": {
                                "type": "number",
                                "description": "Number of hours to look back (default: 24)",
                                "default": 24
                            },
                            "include_solved": {
                                "type": "boolean",
                                "description": "Include solved tickets (default: false)",
                                "default": False
                            }
                        }
                    }
                ),
                Tool(
                    name="get_ticket_details",
                    description="Get detailed information about a specific ticket",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ticket_id": {
                                "type": "number",
                                "description": "The Zendesk ticket ID"
                            }
                        },
                        "required": ["ticket_id"]
                    }
                ),
                Tool(
                    name="search_tickets",
                    description="Search tickets by subject or description",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query string"
                            },
                            "hours": {
                                "type": "number",
                                "description": "Number of hours to look back (default: 24)",
                                "default": 24
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_ticket_stats",
                    description="Get statistics about tickets (counts by status, priority, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hours": {
                                "type": "number",
                                "description": "Number of hours to look back (default: 24)",
                                "default": 24
                            }
                        }
                    }
                ),
                Tool(
                    name="create_ticket_summary",
                    description="Generate a formatted summary report of tickets",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hours": {
                                "type": "number",
                                "description": "Number of hours to look back (default: 24)",
                                "default": 24
                            },
                            "format": {
                                "type": "string",
                                "enum": ["markdown", "text", "json"],
                                "description": "Output format (default: markdown)",
                                "default": "markdown"
                            }
                        }
                    }
                ),
                Tool(
                    name="monitor_ticket_status",
                    description="Check status of specific tickets and detect changes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ticket_ids": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "List of ticket IDs to monitor"
                            }
                        },
                        "required": ["ticket_ids"]
                    }
                ),
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""

            if name == "get_urgent_tickets":
                hours = arguments.get('hours', 24)
                include_solved = arguments.get('include_solved', False)

                tickets = await self._fetch_recent_tickets(hours)
                urgent = [t for t in tickets if t.get('priority') == 'urgent']

                if not include_solved:
                    urgent = [t for t in urgent if t.get('status') != 'solved']

                result = {
                    "count": len(urgent),
                    "tickets": urgent
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            elif name == "get_ticket_details":
                ticket_id = arguments['ticket_id']
                ticket = await self._fetch_ticket(ticket_id)

                return [TextContent(
                    type="text",
                    text=json.dumps(ticket, indent=2)
                )]

            elif name == "search_tickets":
                query = arguments['query']
                hours = arguments.get('hours', 24)

                tickets = await self._fetch_recent_tickets(hours)
                query_lower = query.lower()

                matching = [
                    t for t in tickets
                    if query_lower in t.get('subject', '').lower()
                    or query_lower in t.get('description', '').lower()
                ]

                result = {
                    "query": query,
                    "count": len(matching),
                    "tickets": matching
                }

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            elif name == "get_ticket_stats":
                hours = arguments.get('hours', 24)
                tickets = await self._fetch_recent_tickets(hours)
                stats = self._calculate_stats(tickets)

                return [TextContent(
                    type="text",
                    text=json.dumps(stats, indent=2)
                )]

            elif name == "create_ticket_summary":
                hours = arguments.get('hours', 24)
                format_type = arguments.get('format', 'markdown')

                tickets = await self._fetch_recent_tickets(hours)
                stats = self._calculate_stats(tickets)

                if format_type == 'markdown':
                    summary = self._format_markdown_summary(tickets, stats)
                elif format_type == 'json':
                    summary = json.dumps({"stats": stats, "tickets": tickets}, indent=2)
                else:  # text
                    summary = self._format_text_summary(tickets, stats)

                return [TextContent(
                    type="text",
                    text=summary
                )]

            elif name == "monitor_ticket_status":
                ticket_ids = arguments['ticket_ids']
                results = []

                for ticket_id in ticket_ids:
                    try:
                        ticket = await self._fetch_ticket(ticket_id)
                        results.append({
                            "id": ticket_id,
                            "status": ticket.get('status'),
                            "priority": ticket.get('priority'),
                            "subject": ticket.get('subject'),
                            "updated_at": ticket.get('updated_at')
                        })
                    except Exception as e:
                        results.append({
                            "id": ticket_id,
                            "error": str(e)
                        })

                return [TextContent(
                    type="text",
                    text=json.dumps(results, indent=2)
                )]

            else:
                raise ValueError(f"Unknown tool: {name}")

    async def _fetch_recent_tickets(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch tickets from the last N hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        cutoff_str = cutoff_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        url = f"{self.base_url}/search.json"
        params = {
            'query': f'type:ticket created>{cutoff_str}',
            'sort_by': 'created_at',
            'sort_order': 'desc'
        }

        auth = HTTPBasicAuth(f"{self.email}/token", self.api_token)

        try:
            response = requests.get(url, params=params, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            print(f"Error fetching tickets: {e}", file=sys.stderr)
            return []

    async def _fetch_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Fetch a specific ticket by ID."""
        url = f"{self.base_url}/tickets/{ticket_id}.json"
        auth = HTTPBasicAuth(f"{self.email}/token", self.api_token)

        try:
            response = requests.get(url, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('ticket', {})
        except Exception as e:
            raise ValueError(f"Error fetching ticket {ticket_id}: {e}")

    def _calculate_stats(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from tickets."""
        total = len(tickets)

        by_status = {}
        by_priority = {}

        for ticket in tickets:
            status = ticket.get('status', 'unknown')
            priority = ticket.get('priority', 'unknown')

            by_status[status] = by_status.get(status, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "urgent_count": by_priority.get('urgent', 0),
            "open_count": by_status.get('new', 0) + by_status.get('open', 0),
            "solved_count": by_status.get('solved', 0)
        }

    def _format_markdown_summary(self, tickets: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
        """Format tickets as markdown summary."""
        lines = [
            f"# Zendesk Ticket Summary",
            f"",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## Statistics",
            f"",
            f"- **Total Tickets**: {stats['total']}",
            f"- **Open**: {stats['open_count']}",
            f"- **Solved**: {stats['solved_count']}",
            f"- **Urgent**: {stats['urgent_count']}",
            f"",
            f"### By Priority",
            f""
        ]

        for priority, count in stats['by_priority'].items():
            lines.append(f"- {priority.title()}: {count}")

        lines.extend([
            f"",
            f"### By Status",
            f""
        ])

        for status, count in stats['by_status'].items():
            lines.append(f"- {status.title()}: {count}")

        # Add urgent tickets section
        urgent = [t for t in tickets if t.get('priority') == 'urgent' and t.get('status') != 'solved']

        if urgent:
            lines.extend([
                f"",
                f"## Active Urgent Tickets",
                f""
            ])

            for ticket in urgent:
                ticket_id = ticket.get('id')
                subject = ticket.get('subject', 'No subject')
                status = ticket.get('status', 'unknown')
                url = f"https://{self.subdomain}.zendesk.com/agent/tickets/{ticket_id}"
                lines.append(f"- [#{ticket_id}]({url}) - {subject} ({status})")

        return "\n".join(lines)

    def _format_text_summary(self, tickets: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
        """Format tickets as plain text summary."""
        lines = [
            "=" * 60,
            "ZENDESK TICKET SUMMARY",
            "=" * 60,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "STATISTICS",
            "-" * 60,
            f"Total Tickets: {stats['total']}",
            f"Open: {stats['open_count']}",
            f"Solved: {stats['solved_count']}",
            f"Urgent: {stats['urgent_count']}",
            "",
            "BY PRIORITY",
            "-" * 60
        ]

        for priority, count in stats['by_priority'].items():
            lines.append(f"{priority.title()}: {count}")

        lines.extend(["", "BY STATUS", "-" * 60])

        for status, count in stats['by_status'].items():
            lines.append(f"{status.title()}: {count}")

        return "\n".join(lines)

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="zendesk",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


async def main():
    """Main entry point."""
    # Load environment from config file
    config_path = os.path.join(
        os.path.dirname(__file__), '..', 'config', 'config.env'
    )

    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    server = ZendeskMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
