#!/usr/bin/env python3
"""
Unified Zendesk Data Client
Provides a single interface for accessing Zendesk data via MCP or direct API
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

import requests
from requests.auth import HTTPBasicAuth


class DataSource(Enum):
    """Data source type"""
    MCP = "mcp"
    API = "api"


class ZendeskClient:
    """
    Unified Zendesk client that can use MCP server or direct API access.

    Priority:
    1. Try MCP server if available
    2. Fall back to direct API access
    """

    def __init__(self, force_api: bool = False):
        """
        Initialize Zendesk client.

        Args:
            force_api: If True, skip MCP and use API directly
        """
        self.subdomain = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
        self.email = os.getenv('ZENDESK_EMAIL')
        self.api_token = os.getenv('ZENDESK_API_TOKEN')
        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

        # Determine data source
        self.data_source = DataSource.API
        self.mcp_client = None

        if not force_api:
            try:
                # Try to import MCP client
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
                self.mcp_available = True
                self.data_source = DataSource.MCP
            except ImportError:
                self.mcp_available = False
        else:
            self.mcp_available = False

    async def _ensure_mcp_connection(self):
        """Ensure MCP connection is established."""
        if not self.mcp_available or self.mcp_client:
            return

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            # Find MCP server
            mcp_server_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'mcp_server',
                'zendesk_mcp_server.py'
            )

            venv_python = os.path.join(
                os.path.dirname(__file__),
                '..',
                'mcp_server',
                'venv',
                'bin',
                'python'
            )

            if not os.path.exists(venv_python):
                # Fall back to API
                self.data_source = DataSource.API
                return

            server_params = StdioServerParameters(
                command=venv_python,
                args=[mcp_server_path],
                env={
                    'ZENDESK_SUBDOMAIN': self.subdomain,
                    'ZENDESK_EMAIL': self.email,
                    'ZENDESK_API_TOKEN': self.api_token
                }
            )

            # Create MCP client
            stdio_transport = await stdio_client(server_params)
            self.mcp_client = ClientSession(*stdio_transport)
            await self.mcp_client.__aenter__()

        except Exception as e:
            print(f"Failed to connect to MCP server: {e}", file=sys.stderr)
            self.data_source = DataSource.API
            self.mcp_client = None

    async def _call_mcp_tool(self, tool_name: str, arguments: dict) -> Any:
        """Call an MCP tool."""
        await self._ensure_mcp_connection()

        if not self.mcp_client:
            raise RuntimeError("MCP client not available")

        result = await self.mcp_client.call_tool(tool_name, arguments)

        # Parse result
        if result.content and len(result.content) > 0:
            content = result.content[0]
            if hasattr(content, 'text'):
                return json.loads(content.text)

        return None

    def _fetch_tickets_api(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch tickets using direct API access."""
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
            print(f"Error fetching tickets from API: {e}", file=sys.stderr)
            return []

    def _fetch_ticket_api(self, ticket_id: int) -> Dict[str, Any]:
        """Fetch a specific ticket using direct API access."""
        url = f"{self.base_url}/tickets/{ticket_id}.json"
        auth = HTTPBasicAuth(f"{self.email}/token", self.api_token)

        try:
            response = requests.get(url, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('ticket', {})
        except Exception as e:
            raise ValueError(f"Error fetching ticket {ticket_id} from API: {e}")

    # Public API methods

    def get_tickets(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent tickets.

        Args:
            hours: Number of hours to look back

        Returns:
            List of ticket dictionaries
        """
        if self.data_source == DataSource.MCP and self.mcp_available:
            try:
                # Use MCP
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._call_mcp_tool('get_ticket_stats', {'hours': hours})
                )
                loop.close()

                # MCP stats don't include full tickets, so fetch via API
                # In future, could add MCP tool for this
                return self._fetch_tickets_api(hours)
            except Exception as e:
                print(f"MCP failed, falling back to API: {e}", file=sys.stderr)
                return self._fetch_tickets_api(hours)
        else:
            return self._fetch_tickets_api(hours)

    def get_urgent_tickets(self, hours: int = 24, include_solved: bool = False) -> List[Dict[str, Any]]:
        """
        Get urgent priority tickets.

        Args:
            hours: Number of hours to look back
            include_solved: Include solved tickets

        Returns:
            List of urgent ticket dictionaries
        """
        if self.data_source == DataSource.MCP and self.mcp_available:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._call_mcp_tool('get_urgent_tickets', {
                        'hours': hours,
                        'include_solved': include_solved
                    })
                )
                loop.close()
                return result.get('tickets', [])
            except Exception as e:
                print(f"MCP failed, falling back to API: {e}", file=sys.stderr)
                tickets = self._fetch_tickets_api(hours)
                urgent = [t for t in tickets if t.get('priority') == 'urgent']
                if not include_solved:
                    urgent = [t for t in urgent if t.get('status') != 'solved']
                return urgent
        else:
            tickets = self._fetch_tickets_api(hours)
            urgent = [t for t in tickets if t.get('priority') == 'urgent']
            if not include_solved:
                urgent = [t for t in urgent if t.get('status') != 'solved']
            return urgent

    def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Get a specific ticket by ID.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket dictionary
        """
        if self.data_source == DataSource.MCP and self.mcp_available:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._call_mcp_tool('get_ticket_details', {'ticket_id': ticket_id})
                )
                loop.close()
                return result
            except Exception as e:
                print(f"MCP failed, falling back to API: {e}", file=sys.stderr)
                return self._fetch_ticket_api(ticket_id)
        else:
            return self._fetch_ticket_api(ticket_id)

    def search_tickets(self, query: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Search tickets by subject or description.

        Args:
            query: Search query
            hours: Number of hours to look back

        Returns:
            List of matching ticket dictionaries
        """
        if self.data_source == DataSource.MCP and self.mcp_available:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._call_mcp_tool('search_tickets', {
                        'query': query,
                        'hours': hours
                    })
                )
                loop.close()
                return result.get('tickets', [])
            except Exception as e:
                print(f"MCP failed, falling back to API: {e}", file=sys.stderr)
                tickets = self._fetch_tickets_api(hours)
                query_lower = query.lower()
                return [
                    t for t in tickets
                    if query_lower in t.get('subject', '').lower()
                    or query_lower in t.get('description', '').lower()
                ]
        else:
            tickets = self._fetch_tickets_api(hours)
            query_lower = query.lower()
            return [
                t for t in tickets
                if query_lower in t.get('subject', '').lower()
                or query_lower in t.get('description', '').lower()
            ]

    def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get ticket statistics.

        Args:
            hours: Number of hours to look back

        Returns:
            Statistics dictionary
        """
        if self.data_source == DataSource.MCP and self.mcp_available:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._call_mcp_tool('get_ticket_stats', {'hours': hours})
                )
                loop.close()
                return result
            except Exception as e:
                print(f"MCP failed, falling back to API: {e}", file=sys.stderr)
                tickets = self._fetch_tickets_api(hours)
                return self._calculate_stats(tickets)
        else:
            tickets = self._fetch_tickets_api(hours)
            return self._calculate_stats(tickets)

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

    def create_summary(self, hours: int = 24, format: str = 'markdown') -> str:
        """
        Create a ticket summary report.

        Args:
            hours: Number of hours to look back
            format: Output format (markdown, text, json)

        Returns:
            Formatted summary string
        """
        if self.data_source == DataSource.MCP and self.mcp_available:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._call_mcp_tool('create_ticket_summary', {
                        'hours': hours,
                        'format': format
                    })
                )
                loop.close()
                return result
            except Exception as e:
                print(f"MCP failed, falling back to API: {e}", file=sys.stderr)
                tickets = self._fetch_tickets_api(hours)
                stats = self._calculate_stats(tickets)
                return self._format_summary(tickets, stats, format)
        else:
            tickets = self._fetch_tickets_api(hours)
            stats = self._calculate_stats(tickets)
            return self._format_summary(tickets, stats, format)

    def _format_summary(self, tickets: List[Dict[str, Any]], stats: Dict[str, Any], format: str) -> str:
        """Format tickets as summary."""
        if format == 'json':
            return json.dumps({"stats": stats, "tickets": tickets}, indent=2)
        elif format == 'markdown':
            return self._format_markdown_summary(tickets, stats)
        else:
            return self._format_text_summary(tickets, stats)

    def _format_markdown_summary(self, tickets: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
        """Format tickets as markdown summary."""
        lines = [
            f"# Zendesk Ticket Summary",
            f"",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Data Source**: {self.data_source.value.upper()}",
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
            f"Data Source: {self.data_source.value.upper()}",
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

    def get_data_source(self) -> str:
        """Get current data source (mcp or api)."""
        return self.data_source.value

    async def close(self):
        """Close MCP connection if open."""
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
            self.mcp_client = None


# Convenience functions for backward compatibility

def fetch_recent_tickets(hours: int = 24) -> List[Dict[str, Any]]:
    """Fetch recent tickets (backward compatible)."""
    client = ZendeskClient()
    return client.get_tickets(hours)


def calculate_stats(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics (backward compatible)."""
    client = ZendeskClient()
    return client._calculate_stats(tickets)
