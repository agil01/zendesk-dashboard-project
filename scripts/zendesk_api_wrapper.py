#!/usr/bin/env python3
"""
Simple API wrapper for backward compatibility
Uses direct API access - lightweight and fast
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from typing import List, Dict, Any


def fetch_recent_tickets(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Fetch tickets from the last N hours using direct API.

    Args:
        hours: Number of hours to look back

    Returns:
        List of ticket dictionaries
    """
    subdomain = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
    email = os.getenv('ZENDESK_EMAIL')
    api_token = os.getenv('ZENDESK_API_TOKEN')

    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    base_url = f"https://{subdomain}.zendesk.com/api/v2"
    url = f"{base_url}/search.json"
    params = {
        'query': f'type:ticket created>{cutoff_str}',
        'sort_by': 'created_at',
        'sort_order': 'desc'
    }

    auth = HTTPBasicAuth(f"{email}/token", api_token)

    try:
        response = requests.get(url, params=params, auth=auth, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except Exception as e:
        print(f"Error fetching tickets from API: {e}")
        return []


def calculate_stats(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate statistics from tickets.

    Args:
        tickets: List of ticket dictionaries

    Returns:
        Statistics dictionary
    """
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
