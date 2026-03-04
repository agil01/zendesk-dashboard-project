#!/usr/bin/env python3
"""
Zendesk Dashboard Server
Simple HTTP server with API proxy to handle CORS issues.
"""

import os
import json
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, time, timedelta
from zoneinfo import ZoneInfo


class ZendeskProxyHandler(SimpleHTTPRequestHandler):
    """HTTP handler with Zendesk API proxy."""

    def __init__(self, *args, **kwargs):
        # Get credentials from environment
        self.subdomain = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
        self.email = os.getenv('ZENDESK_EMAIL', 'anthony.gil@counterparthealth.com')
        self.api_token = os.getenv('ZENDESK_API_TOKEN', '24ICYAgncoLX19UJ6A3nmuIpZLXU3CrERIpav7kv')
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)

        # API proxy endpoint - all tickets
        if parsed_path.path == '/api/tickets':
            self.handle_api_request()
        # API endpoint - single ticket details
        elif parsed_path.path.startswith('/api/ticket/'):
            ticket_id = parsed_path.path.split('/')[-1]
            self.handle_ticket_detail_request(ticket_id)
        # API endpoint - agent statuses
        elif parsed_path.path == '/api/agents':
            self.handle_agents_request()
        # Serve dashboard HTML
        elif parsed_path.path == '/' or parsed_path.path == '/dashboard':
            self.serve_dashboard()
        else:
            # Serve static files
            super().do_GET()

    def get_ticket_sla_data(self, ticket_id):
        """Fetch SLA metric events for a specific ticket."""
        try:
            base_url = f"https://{self.subdomain}.zendesk.com/api/v2"
            metric_url = f"{base_url}/tickets/{ticket_id}/metric_events.json"

            response = requests.get(
                metric_url,
                auth=(f"{self.email}/token", self.api_token),
                timeout=5
            )

            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def parse_sla_metrics(self, metric_data, ticket_status):
        """Parse SLA metrics from metric events - prefers resolution_time, falls back to reply_time."""
        if not metric_data:
            return None

        # Try resolution_time first (preferred)
        for metric_type in ['resolution_time', 'reply_time']:
            if metric_type not in metric_data:
                continue

            events = metric_data.get(metric_type, [])
            sla_info = None

            # Find the apply_sla event which contains the target
            for event in events:
                if event.get('type') == 'apply_sla' and 'sla' in event:
                    sla_data = event['sla']
                    sla_info = {
                        'metric_type': metric_type,
                        'target_seconds': sla_data.get('target_in_seconds', sla_data.get('target', 0) * 60),
                        'business_hours': sla_data.get('business_hours', False),
                        'policy_title': sla_data.get('policy', {}).get('title', 'Unknown'),
                        'policy_id': sla_data.get('policy', {}).get('id')
                    }
                    break

            # If we found SLA info, check for breach and fulfillment
            if sla_info:
                fulfilled = False
                breach_time = None

                for event in events:
                    if event.get('type') == 'fulfill':
                        fulfilled = True
                    elif event.get('type') == 'breach':
                        breach_time = event.get('time')

                sla_info['fulfilled'] = fulfilled
                sla_info['breached'] = breach_time is not None
                sla_info['breach_time'] = breach_time

                # If we found resolution_time SLA, use it and stop
                if metric_type == 'resolution_time':
                    return sla_info

                # If reply_time and ticket is open, we can still use it
                if metric_type == 'reply_time':
                    return sla_info

        return None

    def handle_api_request(self):
        """Proxy API requests to Zendesk with SLA enrichment."""
        try:
            # Get today's tickets in CST timezone (12:01 AM CST to 11:59 PM CST)
            cst = ZoneInfo("America/Chicago")
            now_cst = datetime.now(cst)

            # Start at 12:01 AM CST today
            today_start = datetime.combine(now_cst.date(), time(0, 1), tzinfo=cst)

            # End at 11:59 PM CST today
            today_end = datetime.combine(now_cst.date(), time(23, 59, 59), tzinfo=cst)

            # Convert to UTC for Zendesk API
            today_start_utc = today_start.astimezone(timezone.utc)
            today_end_utc = today_end.astimezone(timezone.utc)

            today_start_iso = today_start_utc.isoformat()
            today_end_iso = today_end_utc.isoformat()

            base_url = f"https://{self.subdomain}.zendesk.com/api/v2"
            search_url = f"{base_url}/search.json"
            params = {
                'query': f'type:ticket created>={today_start_iso} created<={today_end_iso}',
                'sort_by': 'created_at',
                'sort_order': 'desc'
            }

            response = requests.get(
                search_url,
                auth=(f"{self.email}/token", self.api_token),
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                tickets = data.get('results', [])

                # Enrich first 50 tickets with SLA data (to avoid too many API calls)
                for ticket in tickets[:50]:
                    ticket_id = ticket.get('id')
                    if ticket_id:
                        sla_data = self.get_ticket_sla_data(ticket_id)
                        if sla_data:
                            sla_metrics = self.parse_sla_metrics(sla_data, ticket.get('status'))
                            ticket['sla_metrics'] = sla_metrics

                # Send JSON response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(tickets).encode())
            else:
                self.send_error(response.status_code, f"Zendesk API error: {response.text}")

        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    def handle_ticket_detail_request(self, ticket_id):
        """Get detailed ticket information including description and comments."""
        try:
            base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

            # Get ticket details
            ticket_url = f"{base_url}/tickets/{ticket_id}.json"
            ticket_response = requests.get(
                ticket_url,
                auth=(f"{self.email}/token", self.api_token),
                timeout=10
            )

            if ticket_response.status_code == 200:
                ticket_data = ticket_response.json()
                ticket = ticket_data.get('ticket', {})

                # Get ticket comments
                comments_url = f"{base_url}/tickets/{ticket_id}/comments.json"
                comments_response = requests.get(
                    comments_url,
                    auth=(f"{self.email}/token", self.api_token),
                    timeout=10
                )

                if comments_response.status_code == 200:
                    comments_data = comments_response.json()
                    ticket['comments'] = comments_data.get('comments', [])

                # Send JSON response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(ticket).encode())
            else:
                self.send_error(ticket_response.status_code, f"Zendesk API error: {ticket_response.text}")

        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    def handle_agents_request(self):
        """Fetch agent availability statuses from Zendesk Agent Availability API."""
        try:
            # Agent IDs to check
            agent_ids = ['39948397141915', '21761242009371', '21761363093147']

            agent_statuses = {}
            base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

            for agent_id in agent_ids:
                try:
                    # Fetch agent availability using Agent Availability API
                    availability_url = f"{base_url}/agent_availabilities/{agent_id}"
                    response = requests.get(
                        availability_url,
                        auth=(f"{self.email}/token", self.api_token),
                        timeout=10
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # Extract agent status from JSON:API format
                        agent_data = data.get('data', {})
                        attributes = agent_data.get('attributes', {})
                        agent_status_info = attributes.get('agent_status', {})

                        # Status name: online, away, transfers_only, offline
                        status = agent_status_info.get('name', 'offline')
                        updated_at = agent_status_info.get('updated_at')

                        agent_statuses[agent_id] = {
                            'status': status,
                            'updated_at': updated_at
                        }
                    else:
                        # Default to offline if we can't fetch status
                        agent_statuses[agent_id] = {
                            'status': 'offline',
                            'updated_at': None
                        }
                except Exception as e:
                    print(f"Error fetching status for agent {agent_id}: {e}")
                    agent_statuses[agent_id] = {
                        'status': 'offline',
                        'updated_at': None
                    }

            # Send JSON response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(agent_statuses).encode())

        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    def serve_dashboard(self):
        """Serve the dashboard HTML with embedded JavaScript."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zendesk Mission Control</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --color-bg-primary: #0a0e27;
            --color-bg-secondary: #0f1419;
            --color-bg-tertiary: #1a1f3a;
            --color-bg-card: #141824;
            --color-accent-cyan: #14f1d9;
            --color-accent-cyan-bright: #00fff7;
            --color-accent-purple: #8b5cf6;
            --color-accent-purple-bright: #a78bfa;
            --color-accent-blue: #6366f1;
            --color-text-primary: #e8edf5;
            --color-text-secondary: #9ca3af;
            --color-text-muted: #6b7280;
            --color-success: #10b981;
            --color-warning: #f59e0b;
            --color-error: #ef4444;
            --color-urgent: #dc2626;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }

        @keyframes pulse-glow {
            0%, 100% {
                opacity: 1;
                box-shadow: 0 0 20px currentColor, 0 0 40px currentColor;
            }
            50% {
                opacity: 0.7;
                box-shadow: 0 0 10px currentColor, 0 0 20px currentColor;
            }
        }

        @keyframes fade-in-up {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes hologram-flicker {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.97; }
        }

        @keyframes grid-pulse {
            0%, 100% { opacity: 0.03; }
            50% { opacity: 0.08; }
        }

        body {
            font-family: 'Rajdhani', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--color-bg-primary);
            color: var(--color-text-primary);
            padding: 20px;
            position: relative;
            overflow-x: hidden;
        }

        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background:
                linear-gradient(90deg, transparent 0%, rgba(20, 241, 217, 0.03) 50%, transparent 100%),
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 2px,
                    rgba(20, 241, 217, 0.03) 2px,
                    rgba(20, 241, 217, 0.03) 4px
                );
            pointer-events: none;
            z-index: 1;
            animation: grid-pulse 4s ease-in-out infinite;
        }

        body::after {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg,
                transparent,
                var(--color-accent-cyan),
                transparent
            );
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 2;
            opacity: 0.3;
        }

        .header {
            background: linear-gradient(135deg,
                rgba(99, 102, 241, 0.15) 0%,
                rgba(139, 92, 246, 0.15) 50%,
                rgba(20, 241, 217, 0.15) 100%
            );
            backdrop-filter: blur(10px);
            border: 1px solid rgba(20, 241, 217, 0.2);
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow:
                0 0 60px rgba(20, 241, 217, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.1),
                0 20px 40px rgba(0, 0, 0, 0.4);
            position: relative;
            z-index: 10;
            animation: fade-in-up 0.8s ease-out;
        }

        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: 16px;
            padding: 1px;
            background: linear-gradient(135deg,
                var(--color-accent-cyan),
                var(--color-accent-purple),
                var(--color-accent-blue)
            );
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            opacity: 0.3;
            animation: hologram-flicker 3s ease-in-out infinite;
        }

        .header h1 {
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 12px;
            background: linear-gradient(135deg,
                var(--color-accent-cyan-bright),
                var(--color-accent-purple-bright),
                var(--color-accent-cyan-bright)
            );
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        .header .meta {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            color: var(--color-text-secondary);
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
            position: relative;
        }

        .status-live {
            background: var(--color-accent-cyan);
            animation: pulse-glow 2s ease-in-out infinite;
            color: var(--color-accent-cyan);
        }

        .status-error {
            background: var(--color-error);
            animation: pulse-glow 2s ease-in-out infinite;
            color: var(--color-error);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 24px;
            margin-bottom: 30px;
            position: relative;
            z-index: 10;
        }

        .card {
            background: linear-gradient(135deg,
                rgba(20, 24, 36, 0.8) 0%,
                rgba(26, 31, 58, 0.6) 100%
            );
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 28px;
            border: 1px solid rgba(20, 241, 217, 0.15);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            position: relative;
            z-index: 10;
            overflow: hidden;
            animation: fade-in-up 0.6s ease-out backwards;
        }

        .grid .card:nth-child(1) { animation-delay: 0.1s; }
        .grid .card:nth-child(2) { animation-delay: 0.15s; }
        .grid .card:nth-child(3) { animation-delay: 0.2s; }
        .grid .card:nth-child(4) { animation-delay: 0.25s; }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg,
                transparent,
                var(--color-accent-cyan),
                transparent
            );
            opacity: 0;
            transition: opacity 0.4s;
        }

        .card::after {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: 12px;
            padding: 1px;
            background: linear-gradient(135deg,
                var(--color-accent-cyan),
                var(--color-accent-purple)
            );
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            opacity: 0;
            transition: opacity 0.4s;
        }

        .card:hover {
            transform: translateY(-6px) scale(1.02);
            box-shadow:
                0 0 40px rgba(20, 241, 217, 0.3),
                0 20px 40px rgba(0, 0, 0, 0.5);
            border-color: var(--color-accent-cyan);
            z-index: 20;
        }

        .card:hover::before,
        .card:hover::after {
            opacity: 1;
        }

        .card.clickable:hover::after {
            opacity: 1;
        }

        .card-header {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            color: var(--color-accent-cyan);
            font-weight: 600;
            margin-bottom: 16px;
            letter-spacing: 1.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .card-value {
            font-size: 56px;
            font-weight: 700;
            margin-bottom: 8px;
            line-height: 1;
            background: linear-gradient(135deg,
                var(--color-text-primary),
                var(--color-accent-cyan)
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .card-label {
            font-size: 14px;
            color: var(--color-text-secondary);
            font-weight: 400;
        }

        .urgent {
            color: var(--color-urgent);
            text-shadow: 0 0 10px rgba(220, 38, 38, 0.5);
        }
        .high {
            color: var(--color-warning);
            text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
        }
        .normal {
            color: var(--color-accent-blue);
            text-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
        }
        .low {
            color: var(--color-success);
            text-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
        }

        .section {
            background: linear-gradient(135deg,
                rgba(20, 24, 36, 0.6) 0%,
                rgba(26, 31, 58, 0.4) 100%
            );
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 30px;
            border: 1px solid rgba(20, 241, 217, 0.1);
            position: relative;
            z-index: 10;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }

        .section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg,
                transparent,
                var(--color-accent-purple),
                transparent
            );
        }

        .section-title {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--color-text-primary);
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        .badge {
            background: linear-gradient(135deg,
                var(--color-urgent),
                #b91c1c
            );
            color: white;
            padding: 4px 12px;
            border-radius: 16px;
            font-size: 12px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 20px rgba(220, 38, 38, 0.5);
            animation: pulse-glow 2s ease-in-out infinite;
        }

        .ticket-item {
            background: linear-gradient(135deg,
                rgba(10, 14, 39, 0.8) 0%,
                rgba(20, 24, 36, 0.6) 100%
            );
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 14px;
            border-left: 3px solid var(--color-accent-blue);
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            z-index: 10;
            border: 1px solid rgba(20, 241, 217, 0.08);
            border-left-width: 3px;
        }

        .ticket-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg,
                var(--color-accent-cyan),
                var(--color-accent-purple)
            );
            opacity: 0;
            transition: opacity 0.3s;
        }

        .ticket-item:hover {
            background: linear-gradient(135deg,
                rgba(20, 24, 36, 0.9) 0%,
                rgba(26, 31, 58, 0.7) 100%
            );
            transform: translateX(8px);
            box-shadow:
                0 0 30px rgba(20, 241, 217, 0.2),
                0 8px 24px rgba(0, 0, 0, 0.4);
            border-left-color: var(--color-accent-cyan);
        }

        .ticket-item:hover::before {
            opacity: 1;
        }

        .ticket-item.urgent {
            border-left-color: var(--color-urgent);
            background: linear-gradient(135deg,
                rgba(220, 38, 38, 0.08) 0%,
                rgba(20, 24, 36, 0.6) 100%
            );
        }

        .ticket-item.urgent::before {
            background: linear-gradient(180deg,
                var(--color-urgent),
                #b91c1c
            );
        }

        .ticket-item.urgent:hover {
            box-shadow:
                0 0 40px rgba(220, 38, 38, 0.3),
                0 8px 24px rgba(0, 0, 0, 0.4);
        }

        .ticket-item.status-resolved {
            border-left-color: var(--color-success);
            background: linear-gradient(135deg,
                rgba(16, 185, 129, 0.08) 0%,
                rgba(20, 24, 36, 0.6) 100%
            );
        }

        .ticket-item.status-resolved::before {
            background: linear-gradient(180deg,
                var(--color-success),
                #059669
            );
        }

        .ticket-item.status-resolved:hover {
            box-shadow:
                0 0 30px rgba(16, 185, 129, 0.25),
                0 8px 24px rgba(0, 0, 0, 0.4);
        }

        .ticket-item.status-active {
            border-left-color: var(--color-warning);
            background: linear-gradient(135deg,
                rgba(245, 158, 11, 0.08) 0%,
                rgba(20, 24, 36, 0.6) 100%
            );
        }

        .ticket-item.status-active::before {
            background: linear-gradient(180deg,
                var(--color-warning),
                #d97706
            );
        }

        .ticket-item.status-active:hover {
            box-shadow:
                0 0 30px rgba(245, 158, 11, 0.25),
                0 8px 24px rgba(0, 0, 0, 0.4);
        }

        .ticket-id {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 13px;
            color: var(--color-accent-cyan);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            text-shadow: 0 0 10px rgba(20, 241, 217, 0.4);
        }

        .ticket-subject {
            font-size: 16px;
            margin-bottom: 12px;
            font-weight: 500;
            color: var(--color-text-primary);
            line-height: 1.4;
        }

        .ticket-meta {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--color-text-secondary);
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }

        .ticket-meta span {
            padding: 4px 8px;
            background: rgba(20, 241, 217, 0.05);
            border-radius: 4px;
            border: 1px solid rgba(20, 241, 217, 0.1);
        }

        .ticket-actions {
            margin-top: 14px;
            display: flex;
            gap: 10px;
        }

        .ticket-actions a, .ticket-actions button {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 8px 14px;
            border-radius: 6px;
            text-decoration: none;
            transition: all 0.3s;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .view-zendesk {
            background: linear-gradient(135deg,
                var(--color-accent-blue),
                var(--color-accent-purple)
            );
            color: white;
            border: none;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .view-zendesk:hover {
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
            transform: translateY(-2px);
        }

        .view-details {
            background: rgba(20, 241, 217, 0.1);
            color: var(--color-accent-cyan);
            border: 1px solid var(--color-accent-cyan);
        }

        .view-details:hover {
            background: rgba(20, 241, 217, 0.2);
            box-shadow: 0 0 20px rgba(20, 241, 217, 0.3);
            transform: translateY(-2px);
        }

        /* Main Content Containers - Lower z-index */
        #content {
            position: relative;
            z-index: 10;
        }

        #alerts {
            position: relative;
            z-index: 10;
        }

        /* Modal Styles */
        .modal {
            display: none;
            position: fixed !important;
            z-index: 999999 !important;
            left: 0 !important;
            top: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background-color: rgba(10, 14, 39, 0.95) !important;
            backdrop-filter: blur(8px);
            animation: fadeIn 0.4s;
            overflow-y: auto;
            pointer-events: auto !important;
        }

        .modal.show {
            display: flex !important;
            align-items: center;
            justify-content: center;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                backdrop-filter: blur(0px);
            }
            to {
                opacity: 1;
                backdrop-filter: blur(8px);
            }
        }

        .modal-content {
            background: linear-gradient(135deg,
                rgba(20, 24, 36, 0.95) 0%,
                rgba(26, 31, 58, 0.9) 100%
            ) !important;
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 40px;
            max-width: 800px;
            width: 90%;
            max-height: 85vh;
            overflow-y: auto;
            position: relative !important;
            z-index: 1000000 !important;
            border: 1px solid rgba(20, 241, 217, 0.2);
            box-shadow:
                0 0 60px rgba(20, 241, 217, 0.2),
                0 30px 60px rgba(0, 0, 0, 0.6);
            animation: slideUp 0.3s;
            border: 1px solid #334155;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
            pointer-events: auto !important;
        }

        @keyframes slideUp {
            from {
                transform: translateY(50px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .modal-close {
            position: absolute !important;
            top: 20px !important;
            right: 20px !important;
            font-size: 32px;
            font-weight: bold;
            color: var(--color-text-secondary);
            cursor: pointer;
            background: rgba(20, 241, 217, 0.1);
            border: 1px solid rgba(20, 241, 217, 0.2);
            padding: 0;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            transition: all 0.3s;
            z-index: 1000001 !important;
        }

        .modal-close:hover {
            color: var(--color-accent-cyan);
            background: rgba(20, 241, 217, 0.2);
            transform: scale(1.1) rotate(90deg);
            box-shadow: 0 0 20px rgba(20, 241, 217, 0.4);
        }

        .modal-header {
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(20, 241, 217, 0.2);
        }

        .modal-header h2 {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 12px;
            background: linear-gradient(135deg,
                var(--color-accent-cyan),
                var(--color-accent-purple)
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .modal-body {
            color: var(--color-text-primary);
        }

        .detail-section {
            margin-bottom: 28px;
        }

        .detail-section h3 {
            font-family: 'JetBrains Mono', monospace;
            color: var(--color-accent-cyan);
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 12px;
            font-weight: 700;
            letter-spacing: 1.5px;
        }

        .detail-content {
            background: rgba(10, 14, 39, 0.6);
            padding: 20px;
            border-radius: 8px;
            white-space: pre-wrap;
            line-height: 1.7;
            border: 1px solid rgba(20, 241, 217, 0.1);
            font-size: 14px;
        }

        .comment-item {
            background: rgba(10, 14, 39, 0.5);
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 14px;
            border-left: 2px solid rgba(20, 241, 217, 0.3);
            border: 1px solid rgba(20, 241, 217, 0.1);
            border-left-width: 2px;
            transition: all 0.3s;
        }

        .comment-item:hover {
            background: rgba(20, 24, 36, 0.6);
            border-left-color: var(--color-accent-cyan);
            box-shadow: 0 0 20px rgba(20, 241, 217, 0.1);
        }

        .comment-author {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            color: var(--color-accent-cyan);
            margin-bottom: 6px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .comment-time {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            color: var(--color-text-muted);
            margin-bottom: 10px;
        }

        .comment-body {
            color: var(--color-text-primary);
            font-size: 13px;
            line-height: 1.6;
        }

        .loading-spinner {
            text-align: center;
            padding: 40px;
        }

        .loading-spinner::after {
            content: "Loading...";
            font-family: 'JetBrains Mono', monospace;
            color: var(--color-accent-cyan);
            font-size: 14px;
        }

        /* SLA Status Badges */
        .sla-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            border: 1px solid;
            box-shadow: 0 0 10px currentColor;
        }

        .sla-ok {
            background: rgba(16, 185, 129, 0.15);
            color: var(--color-success);
            border-color: var(--color-success);
        }

        .sla-warning {
            background: rgba(245, 158, 11, 0.15);
            color: var(--color-warning);
            border-color: var(--color-warning);
            animation: pulse-sla 2s ease-in-out infinite;
        }

        .sla-breach {
            background: rgba(220, 38, 38, 0.2);
            color: var(--color-urgent);
            border-color: var(--color-urgent);
            animation: pulse-sla 1.5s ease-in-out infinite;
            box-shadow: 0 0 20px rgba(220, 38, 38, 0.6);
        }

        .sla-none {
            background: rgba(107, 114, 128, 0.15);
            color: var(--color-text-muted);
            border-color: var(--color-text-muted);
        }

        @keyframes pulse-sla {
            0%, 100% {
                opacity: 1;
                box-shadow: 0 0 20px currentColor;
            }
            50% {
                opacity: 0.7;
                box-shadow: 0 0 10px currentColor;
            }
        }

        .alert-banner {
            background: linear-gradient(135deg,
                rgba(220, 38, 38, 0.2) 0%,
                rgba(185, 28, 28, 0.15) 100%
            );
            backdrop-filter: blur(10px);
            border: 1px solid var(--color-urgent);
            padding: 18px 24px;
            border-radius: 12px;
            margin-bottom: 24px;
            animation: slideIn 0.4s ease-out;
            position: relative;
            z-index: 10;
            box-shadow: 0 0 30px rgba(220, 38, 38, 0.3);
        }

        @keyframes slideIn {
            from {
                transform: translateY(-20px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .loading {
            text-align: center;
            padding: 60px;
            font-size: 16px;
            color: var(--color-text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }

        .spinner {
            border: 3px solid rgba(20, 241, 217, 0.2);
            border-top: 3px solid var(--color-accent-cyan);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 0.8s linear infinite;
            margin: 30px auto;
            box-shadow: 0 0 20px rgba(20, 241, 217, 0.3);
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .controls {
            display: flex;
            gap: 12px;
            margin-bottom: 30px;
            flex-wrap: wrap;
            position: relative;
            z-index: 10;
            animation: fade-in-up 0.6s ease-out;
        }

        button {
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg,
                var(--color-accent-cyan),
                var(--color-accent-blue)
            );
            color: var(--color-bg-primary);
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 4px 12px rgba(20, 241, 217, 0.3);
            position: relative;
            overflow: hidden;
        }

        button::before {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg,
                var(--color-accent-cyan-bright),
                var(--color-accent-purple-bright)
            );
            opacity: 0;
            transition: opacity 0.3s;
        }

        button:hover::before {
            opacity: 1;
        }

        button:hover {
            box-shadow: 0 6px 20px rgba(20, 241, 217, 0.5);
            transform: translateY(-2px);
        }

        button span {
            position: relative;
            z-index: 1;
        }

        button.secondary {
            background: rgba(20, 241, 217, 0.1);
            color: var(--color-accent-cyan);
            border: 1px solid rgba(20, 241, 217, 0.3);
            box-shadow: none;
        }

        button.secondary::before {
            background: rgba(20, 241, 217, 0.2);
        }

        button.secondary:hover {
            background: rgba(20, 241, 217, 0.15);
            box-shadow: 0 0 20px rgba(20, 241, 217, 0.3);
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 12px;
            height: 12px;
        }

        ::-webkit-scrollbar-track {
            background: rgba(10, 14, 39, 0.5);
            border-radius: 6px;
        }

        ::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg,
                var(--color-accent-cyan),
                var(--color-accent-purple)
            );
            border-radius: 6px;
            border: 2px solid rgba(10, 14, 39, 0.5);
        }

        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg,
                var(--color-accent-cyan-bright),
                var(--color-accent-purple-bright)
            );
            box-shadow: 0 0 10px rgba(20, 241, 217, 0.5);
        }

        /* Firefox scrollbar */
        * {
            scrollbar-width: thin;
            scrollbar-color: var(--color-accent-cyan) rgba(10, 14, 39, 0.5);
        }

        /* Agent Status Section */
        .agent-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .agent-card {
            background: linear-gradient(135deg,
                rgba(20, 24, 36, 0.8) 0%,
                rgba(26, 31, 58, 0.6) 100%
            );
            backdrop-filter: blur(10px);
            border-radius: 14px;
            padding: 24px;
            border: 1px solid rgba(20, 241, 217, 0.15);
            position: relative;
            overflow: hidden;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
        }

        .agent-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg,
                var(--color-accent-cyan),
                var(--color-accent-purple)
            );
            opacity: 0.7;
        }

        .agent-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 0 30px rgba(20, 241, 217, 0.25);
            border-color: var(--color-accent-cyan);
        }

        .agent-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 18px;
        }

        .agent-name {
            font-size: 18px;
            font-weight: 700;
            color: var(--color-text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .agent-avatar {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse-glow 2s ease-in-out infinite;
        }

        .agent-status-online {
            background: var(--color-success);
            color: var(--color-success);
            box-shadow: 0 0 12px currentColor;
        }

        .agent-status-busy {
            background: var(--color-warning);
            color: var(--color-warning);
            box-shadow: 0 0 12px currentColor;
        }

        .agent-status-critical {
            background: var(--color-urgent);
            color: var(--color-urgent);
            box-shadow: 0 0 12px currentColor;
        }

        .agent-status-away {
            background: var(--color-warning);
            color: var(--color-warning);
            box-shadow: 0 0 12px currentColor;
        }

        .agent-status-offline {
            background: var(--color-text-muted);
            color: var(--color-text-muted);
            box-shadow: 0 0 12px currentColor;
        }

        .agent-status-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid;
        }

        .agent-status-label.online {
            color: var(--color-success);
            border-color: var(--color-success);
            background: rgba(16, 185, 129, 0.1);
        }

        .agent-status-label.busy {
            color: var(--color-warning);
            border-color: var(--color-warning);
            background: rgba(245, 158, 11, 0.1);
        }

        .agent-status-label.critical {
            color: var(--color-urgent);
            border-color: var(--color-urgent);
            background: rgba(220, 38, 38, 0.1);
        }

        .agent-status-label.away {
            color: var(--color-warning);
            border-color: var(--color-warning);
            background: rgba(245, 158, 11, 0.1);
        }

        .agent-status-label.offline {
            color: var(--color-text-muted);
            border-color: var(--color-text-muted);
            background: rgba(107, 114, 128, 0.1);
        }

        .agent-metrics {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }

        .agent-metric {
            text-align: center;
        }

        .agent-metric-value {
            font-size: 28px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
            background: linear-gradient(135deg,
                var(--color-text-primary),
                var(--color-accent-cyan)
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .agent-metric-value.urgent {
            background: linear-gradient(135deg,
                var(--color-urgent),
                #f97316
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .agent-metric-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 9px;
            color: var(--color-text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .agent-workload {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid rgba(20, 241, 217, 0.1);
        }

        .agent-workload-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            color: var(--color-text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }

        .agent-workload-bar {
            height: 8px;
            background: rgba(20, 241, 217, 0.1);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }

        .agent-workload-fill {
            height: 100%;
            background: linear-gradient(90deg,
                var(--color-accent-cyan),
                var(--color-accent-purple)
            );
            border-radius: 4px;
            transition: width 0.6s ease-out;
            box-shadow: 0 0 10px rgba(20, 241, 217, 0.5);
        }

        .agent-workload-fill.high {
            background: linear-gradient(90deg,
                var(--color-warning),
                #f97316
            );
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
        }

        .agent-workload-fill.critical {
            background: linear-gradient(90deg,
                var(--color-urgent),
                #b91c1c
            );
            box-shadow: 0 0 10px rgba(220, 38, 38, 0.5);
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            .header h1 {
                font-size: 28px;
            }

            .card-value {
                font-size: 42px;
            }

            .grid {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            }

            .agent-status-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ ZENDESK MISSION CONTROL</h1>
        <div class="meta">
            <span class="status-indicator status-live"></span>
            <span id="status">LIVE</span>
            <span style="opacity: 0.5; margin: 0 8px;">|</span>
            <span>LAST UPDATE: <span id="lastUpdate">Loading...</span></span>
            <span style="opacity: 0.5; margin: 0 8px;">|</span>
            <span>AUTO-REFRESH: <span id="refreshInterval">30s</span></span>
            <span style="opacity: 0.5; margin: 0 8px;">|</span>
            <span>TIMEZONE: CST</span>
        </div>
    </div>

    <div class="controls">
        <button onclick="fetchData()">🔄 Refresh Now</button>
        <button class="secondary" onclick="toggleAutoRefresh()">
            <span id="autoRefreshBtn">⏸️ Pause Auto-Refresh</span>
        </button>
        <button class="secondary" onclick="changeInterval()">⏱️ Change Interval</button>
    </div>

    <div id="alerts"></div>

    <div id="content" class="loading">
        <div class="spinner"></div>
        Loading dashboard...
    </div>

    <!-- Ticket Details Modal -->
    <div id="ticketModal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeTicketModal()">&times;</button>
            <div id="modalBody" class="loading-spinner">
                Loading ticket details...
            </div>
        </div>
    </div>

    <!-- Filtered Tickets Modal -->
    <div id="filteredTicketsModal" class="modal">
        <div class="modal-content" style="max-width: 1000px;">
            <button class="modal-close" onclick="closeFilteredTicketsModal()">&times;</button>
            <div id="filteredTicketsBody">
                Loading tickets...
            </div>
        </div>
    </div>

    <script>
        // Store all tickets globally for filtering
        let allTickets = [];
        let agentStatuses = {};

        const CONFIG = {
            subdomain: 'counterparthealth',
            refreshInterval: 30000,
            autoRefresh: true
        };

        // Agent name mapping
        const AGENT_NAMES = {
            '39948397141915': 'Bola Kuye',
            '21761242009371': 'Candice Brown',
            '21761363093147': 'Ron Pineda'
        };

        function getAgentName(agentId) {
            return AGENT_NAMES[agentId] || `Agent ID: ${agentId}`;
        }

        // Get agent status from Zendesk unified status
        function getAgentStatus(agentId, agentData) {
            const zendeskStatus = agentStatuses[agentId];

            if (zendeskStatus && zendeskStatus.status) {
                const status = zendeskStatus.status.toLowerCase();

                if (status === 'online') {
                    return { status: 'online', label: 'Online' };
                } else if (status === 'away') {
                    return { status: 'away', label: 'Away' };
                } else if (status === 'transfers_only') {
                    return { status: 'away', label: 'Transfers Only' };
                } else if (status === 'offline') {
                    return { status: 'offline', label: 'Offline' };
                } else {
                    return { status: 'offline', label: 'Offline' };
                }
            }

            // Default to offline if status unknown
            return { status: 'offline', label: 'Offline' };
        }

        // Fetch agent statuses from Zendesk
        async function fetchAgentStatuses() {
            try {
                const response = await fetch('/api/agents');
                if (response.ok) {
                    agentStatuses = await response.json();
                }
            } catch (error) {
                console.error('Error fetching agent statuses:', error);
            }
        }

        // Get workload percentage based on total volume
        function getWorkloadPercentage(agentData, totalAssignedTickets) {
            if (totalAssignedTickets === 0) return 0;
            const agentTotal = agentData.total || 0;
            return Math.round((agentTotal / totalAssignedTickets) * 100);
        }

        // SLA calculation using Zendesk SLA metrics (resolution_time or reply_time)
        function getSLAStatus(ticket) {
            const now = new Date();
            const created = new Date(ticket.created_at);
            const ageMinutes = (now - created) / (1000 * 60);

            // Check if ticket has actual SLA data from Zendesk
            const slaMetrics = ticket.sla_metrics;

            // If ticket is already solved/closed
            if (['solved', 'closed'].includes(ticket.status)) {
                if (slaMetrics) {
                    // Check if SLA was breached before resolution
                    if (slaMetrics.breached) {
                        return {
                            status: 'breach',
                            label: 'Breached',
                            remaining: null,
                            fulfilled: slaMetrics.fulfilled,
                            metricType: slaMetrics.metric_type
                        };
                    } else {
                        return {
                            status: 'ok',
                            label: 'Met',
                            remaining: null,
                            fulfilled: slaMetrics.fulfilled,
                            metricType: slaMetrics.metric_type
                        };
                    }
                }
                return { status: 'ok', label: 'Resolved', remaining: null };
            }

            // For open tickets, use actual SLA target from Zendesk
            if (slaMetrics && slaMetrics.target_seconds) {
                const slaTargetMinutes = slaMetrics.target_seconds / 60;
                const remaining = slaTargetMinutes - ageMinutes;
                const percentRemaining = (remaining / slaTargetMinutes) * 100;

                const metricLabel = slaMetrics.metric_type === 'resolution_time' ? 'Resolution' : 'Reply';

                // Already breached
                if (slaMetrics.breached || remaining <= 0) {
                    return {
                        status: 'breach',
                        label: 'Breached',
                        remaining: Math.abs(remaining),
                        overdue: true,
                        policy: slaMetrics.policy_title,
                        metricType: metricLabel
                    };
                }
                // At risk (less than 25% time remaining)
                else if (percentRemaining <= 25) {
                    return {
                        status: 'warning',
                        label: 'At Risk',
                        remaining: remaining,
                        overdue: false,
                        policy: slaMetrics.policy_title,
                        metricType: metricLabel
                    };
                }
                // On track
                else {
                    return {
                        status: 'ok',
                        label: 'On Track',
                        remaining: remaining,
                        overdue: false,
                        policy: slaMetrics.policy_title,
                        metricType: metricLabel
                    };
                }
            }

            // Fallback: No SLA data available
            return {
                status: 'none',
                label: 'No SLA',
                remaining: null
            };
        }

        function formatSLATime(minutes) {
            if (minutes < 60) {
                return `${Math.round(minutes)}m`;
            } else if (minutes < 1440) {
                return `${Math.round(minutes / 60)}h`;
            } else {
                return `${Math.round(minutes / 1440)}d`;
            }
        }

        function renderSLABadge(ticket) {
            const sla = getSLAStatus(ticket);

            // Only show "breach" status for resolution_time SLA breaches
            // Hide breach badges for reply_time or other non-resolution SLA types
            if (sla.status === 'breach' && sla.metricType !== 'Resolution') {
                // Don't show breach badge for non-resolution SLAs (e.g., reply_time)
                return '';
            }

            const timeText = sla.remaining !== null
                ? (sla.overdue ? `+${formatSLATime(sla.remaining)}` : formatSLATime(sla.remaining))
                : '';

            let badgeText = sla.label;
            if (timeText) {
                badgeText += ` (${timeText})`;
            }

            // Add policy name and metric type as tooltip if available
            let tooltipParts = [];
            if (sla.policy) tooltipParts.push(`Policy: ${sla.policy}`);
            if (sla.metricType) tooltipParts.push(`Metric: ${sla.metricType}`);
            const titleAttr = tooltipParts.length > 0 ? `title="${tooltipParts.join(', ')}"` : '';

            return `<span class="sla-badge sla-${sla.status}" ${titleAttr}>${badgeText}</span>`;
        }

        let refreshTimer = null;
        let previousTickets = {};

        async function fetchTickets() {
            try {
                const response = await fetch('/api/tickets');

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const tickets = await response.json();
                return tickets;
            } catch (error) {
                console.error('Fetch error:', error);
                updateStatus('error', error.message);
                return null;
            }
        }

        function calculateStats(tickets) {
            const stats = {
                total: tickets.length,
                urgent: 0,
                high: 0,
                normal: 0,
                low: 0,
                new: 0,
                open: 0,
                pending: 0,
                solved: 0,
                closed: 0,
                byAssignee: {},
                unassigned: 0,
                sla: {
                    breached: 0,
                    atRisk: 0,
                    onTrack: 0
                }
            };

            tickets.forEach(ticket => {
                const priority = ticket.priority || 'none';
                const status = ticket.status || 'unknown';
                const assignee = ticket.assignee_id;

                stats[priority] = (stats[priority] || 0) + 1;
                stats[status] = (stats[status] || 0) + 1;

                // Calculate SLA status for open tickets
                // Only count resolution_time SLA breaches, not reply_time
                if (!['solved', 'closed'].includes(status)) {
                    const sla = getSLAStatus(ticket);
                    const slaMetrics = ticket.sla_metrics;
                    const isResolutionSLA = slaMetrics && slaMetrics.metric_type === 'resolution_time';

                    if (sla.status === 'breach' && isResolutionSLA) {
                        stats.sla.breached++;
                    } else if (sla.status === 'warning' && isResolutionSLA) {
                        stats.sla.atRisk++;
                    } else if (isResolutionSLA) {
                        stats.sla.onTrack++;
                    }
                }

                if (assignee) {
                    if (!stats.byAssignee[assignee]) {
                        stats.byAssignee[assignee] = { total: 0, urgent: 0, open: 0 };
                    }
                    stats.byAssignee[assignee].total++;
                    if (priority === 'urgent') stats.byAssignee[assignee].urgent++;
                    if (['new', 'open', 'pending'].includes(status)) stats.byAssignee[assignee].open++;
                } else {
                    stats.unassigned++;
                }
            });

            return stats;
        }

        function detectNewTickets(tickets) {
            const newTickets = [];
            const currentIds = {};

            tickets.forEach(ticket => {
                currentIds[ticket.id] = true;
                if (!previousTickets[ticket.id]) {
                    newTickets.push(ticket);
                }
            });

            previousTickets = currentIds;
            return newTickets;
        }

        function renderDashboard(tickets, stats) {
            const urgentTickets = tickets.filter(t =>
                t.priority === 'urgent' && !['solved', 'closed'].includes(t.status)
            );

            const resolutionRate = stats.total > 0 ? Math.round((stats.solved / stats.total) * 100) : 0;

            const html = `
                <div class="grid">
                    <div class="card clickable" onclick="showFilteredTickets(() => true, '📊 All Tickets Today')">
                        <div class="card-header">Total Tickets Today</div>
                        <div class="card-value">${stats.total}</div>
                        <div class="card-label">Today (CST)</div>
                    </div>
                    <div class="card clickable" onclick="showFilteredTickets(t => ['solved', 'closed'].includes(t.status), '✅ Resolved Tickets')">
                        <div class="card-header">Resolution Rate</div>
                        <div class="card-value">${resolutionRate}%</div>
                        <div class="card-label">${stats.solved} of ${stats.total} solved</div>
                    </div>
                    <div class="card clickable" onclick="showFilteredTickets(t => t.priority === 'urgent' && !['solved', 'closed'].includes(t.status), '🔴 Active Urgent Tickets')">
                        <div class="card-header urgent">Urgent Tickets</div>
                        <div class="card-value urgent">${stats.urgent || 0}</div>
                        <div class="card-label">${urgentTickets.length} active</div>
                    </div>
                    <div class="card clickable" onclick="showFilteredTickets(t => ['open', 'new', 'pending'].includes(t.status), '📂 Open Tickets')">
                        <div class="card-header">Open Tickets</div>
                        <div class="card-value normal">${(stats.open || 0) + (stats.new || 0) + (stats.pending || 0)}</div>
                        <div class="card-label">Requires attention</div>
                    </div>
                </div>

                <div class="grid" style="grid-template-columns: repeat(4, 1fr);">
                    <div class="card clickable" onclick="showFilteredTickets(t => t.priority === 'urgent', '🔴 Urgent Priority Tickets')">
                        <div class="card-header urgent">🔴 Urgent</div>
                        <div class="card-value urgent">${stats.urgent || 0}</div>
                    </div>
                    <div class="card clickable" onclick="showFilteredTickets(t => t.priority === 'high', '🟠 High Priority Tickets')">
                        <div class="card-header high">🟠 High</div>
                        <div class="card-value high">${stats.high || 0}</div>
                    </div>
                    <div class="card clickable" onclick="showFilteredTickets(t => t.priority === 'normal', '🟡 Normal Priority Tickets')">
                        <div class="card-header normal">🟡 Normal</div>
                        <div class="card-value normal">${stats.normal || 0}</div>
                    </div>
                    <div class="card clickable" onclick="showFilteredTickets(t => t.priority === 'low', '🟢 Low Priority Tickets')">
                        <div class="card-header low">🟢 Low</div>
                        <div class="card-value low">${stats.low || 0}</div>
                    </div>
                </div>

                ${Object.keys(stats.byAssignee).length > 0 ? `
                    <div class="section">
                        <div class="section-title">👥 AGENT STATUS MONITOR</div>
                        <div class="agent-status-grid">
                            ${(() => {
                                // Calculate total assigned tickets across all agents
                                const totalAssignedTickets = Object.values(stats.byAssignee).reduce((sum, agent) => sum + agent.total, 0);

                                return Object.entries(stats.byAssignee)
                                    .sort((a, b) => b[1].open - a[1].open)
                                    .map(([assigneeId, data]) => {
                                        const agentStatus = getAgentStatus(assigneeId, data);
                                        const workloadPercentage = getWorkloadPercentage(data, totalAssignedTickets);
                                        const workloadClass = workloadPercentage >= 40 ? 'critical' : workloadPercentage >= 25 ? 'high' : '';

                                    return `
                                        <div class="agent-card" onclick="showFilteredTickets(t => t.assignee_id == '${assigneeId}', '👤 ${getAgentName(assigneeId)} Tickets')">
                                            <div class="agent-header">
                                                <div class="agent-name">
                                                    <span class="agent-avatar agent-status-${agentStatus.status}"></span>
                                                    ${getAgentName(assigneeId)}
                                                </div>
                                                <span class="agent-status-label ${agentStatus.status}">${agentStatus.label}</span>
                                            </div>
                                            <div class="agent-metrics">
                                                <div class="agent-metric">
                                                    <div class="agent-metric-value">${data.total}</div>
                                                    <div class="agent-metric-label">Total</div>
                                                </div>
                                                <div class="agent-metric">
                                                    <div class="agent-metric-value">${data.open}</div>
                                                    <div class="agent-metric-label">Open</div>
                                                </div>
                                                <div class="agent-metric">
                                                    <div class="agent-metric-value urgent">${data.urgent || 0}</div>
                                                    <div class="agent-metric-label">Urgent</div>
                                                </div>
                                            </div>
                                            <div class="agent-workload">
                                                <div class="agent-workload-label">
                                                    <span>Volume Share</span>
                                                    <span>${Math.round(workloadPercentage)}%</span>
                                                </div>
                                                <div class="agent-workload-bar">
                                                    <div class="agent-workload-fill ${workloadClass}" style="width: ${workloadPercentage}%"></div>
                                                </div>
                                            </div>
                                        </div>
                                    `;
                                    }).join('');
                            })()}
                            ${stats.unassigned > 0 ? `
                                <div class="agent-card" onclick="showFilteredTickets(t => !t.assignee_id, '⚪ Unassigned Tickets')" style="border-color: rgba(239, 68, 68, 0.3);">
                                    <div class="agent-header">
                                        <div class="agent-name">
                                            <span class="agent-avatar agent-status-critical"></span>
                                            Unassigned
                                        </div>
                                        <span class="agent-status-label critical">Action Needed</span>
                                    </div>
                                    <div class="agent-metrics">
                                        <div class="agent-metric">
                                            <div class="agent-metric-value urgent">${stats.unassigned}</div>
                                            <div class="agent-metric-label">Tickets</div>
                                        </div>
                                        <div class="agent-metric">
                                            <div class="agent-metric-value">—</div>
                                            <div class="agent-metric-label">Open</div>
                                        </div>
                                        <div class="agent-metric">
                                            <div class="agent-metric-value">—</div>
                                            <div class="agent-metric-label">Urgent</div>
                                        </div>
                                    </div>
                                    <div class="agent-workload">
                                        <div class="agent-workload-label">
                                            <span>Requires Assignment</span>
                                        </div>
                                        <div class="agent-workload-bar">
                                            <div class="agent-workload-fill critical" style="width: 100%"></div>
                                        </div>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}

                <div class="section">
                    <div class="section-title">📈 Tickets by Hour of Day</div>
                    <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                        <canvas id="ticketsByHourChart" style="max-height: 300px;"></canvas>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">📨 Tickets by Channel <span style="font-size: 12px; color: #94a3b8; font-weight: 400;">(Click to drill-in)</span></div>
                    <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                        <canvas id="ticketsByChannelChart" style="max-height: 300px; cursor: pointer;"></canvas>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">⏱️ SLA Status (Resolution Time)</div>
                    <div class="grid" style="grid-template-columns: repeat(3, 1fr);">
                        <div class="card clickable" onclick="showFilteredTickets(t => !['solved', 'closed'].includes(t.status) && t.sla_metrics && t.sla_metrics.metric_type === 'resolution_time' && getSLAStatus(t).status === 'breach', '🚨 SLA Breached Tickets (Resolution Time)')">
                            <div class="card-header" style="color: #ef4444;">🚨 Breached</div>
                            <div class="card-value" style="color: #ef4444;">${stats.sla.breached}</div>
                            <div class="card-label">Past due</div>
                        </div>
                        <div class="card clickable" onclick="showFilteredTickets(t => !['solved', 'closed'].includes(t.status) && t.sla_metrics && t.sla_metrics.metric_type === 'resolution_time' && getSLAStatus(t).status === 'warning', '⚠️ SLA At Risk Tickets (Resolution Time)')">
                            <div class="card-header" style="color: #f59e0b;">⚠️ At Risk</div>
                            <div class="card-value" style="color: #f59e0b;">${stats.sla.atRisk}</div>
                            <div class="card-label">< 25% time left</div>
                        </div>
                        <div class="card clickable" onclick="showFilteredTickets(t => !['solved', 'closed'].includes(t.status) && t.sla_metrics && t.sla_metrics.metric_type === 'resolution_time' && getSLAStatus(t).status === 'ok', '✅ SLA On Track Tickets (Resolution Time)')">
                            <div class="card-header" style="color: #22c55e;">✅ On Track</div>
                            <div class="card-value" style="color: #22c55e;">${stats.sla.onTrack}</div>
                            <div class="card-label">Good standing</div>
                        </div>
                    </div>
                </div>

                ${urgentTickets.length > 0 ? `
                    <div class="section">
                        <div class="section-title">
                            🔴 Active Urgent Tickets
                            <span class="badge">${urgentTickets.length}</span>
                        </div>
                        ${urgentTickets.map(ticket => `
                            <div class="ticket-item urgent" data-ticket-id="${ticket.id}">
                                <div class="ticket-id">#${ticket.id} 🔗 ${renderSLABadge(ticket)}</div>
                                <div class="ticket-subject">${ticket.subject || 'No subject'}</div>
                                <div class="ticket-meta">
                                    <span>Status: ${(ticket.status || 'unknown').toUpperCase()}</span>
                                    <span>Created: ${formatTime(ticket.created_at)}</span>
                                    ${ticket.assignee_id ? `<span>Assigned: ${getAgentName(ticket.assignee_id)}</span>` : '<span>Unassigned</span>'}
                                </div>
                                <div class="ticket-actions">
                                    <a href="https://${CONFIG.subdomain}.zendesk.com/agent/tickets/${ticket.id}" target="_blank" class="view-zendesk" onclick="event.stopPropagation()">🔗 View in Zendesk</a>
                                    <button class="view-details" onclick="showTicketDetails(${ticket.id}); event.stopPropagation()">📋 View Details</button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <div class="section">
                    <div class="section-title">
                        📋 Recent Tickets
                        <span class="badge">${Math.min(tickets.length, 10)}</span>
                    </div>
                    ${tickets.slice(0, 10).map(ticket => {
                        const isResolved = ['solved', 'closed'].includes(ticket.status);
                        const isUrgent = ticket.priority === 'urgent' && !isResolved;
                        const statusClass = isResolved ? 'status-resolved' : 'status-active';
                        const urgentClass = isUrgent ? 'urgent' : '';

                        return `
                        <div class="ticket-item ${urgentClass} ${statusClass}" data-ticket-id="${ticket.id}">
                            <div class="ticket-id">#${ticket.id} 🔗 ${renderSLABadge(ticket)}</div>
                            <div class="ticket-subject">${ticket.subject || 'No subject'}</div>
                            <div class="ticket-meta">
                                <span>Priority: ${(ticket.priority || 'none').toUpperCase()}</span>
                                <span>Status: ${(ticket.status || 'unknown').toUpperCase()}</span>
                                <span>Created: ${formatTime(ticket.created_at)}</span>
                                ${ticket.assignee_id ? `<span>Assigned: ${getAgentName(ticket.assignee_id)}</span>` : '<span>Unassigned</span>'}
                            </div>
                            <div class="ticket-actions">
                                <a href="https://${CONFIG.subdomain}.zendesk.com/agent/tickets/${ticket.id}" target="_blank" class="view-zendesk" onclick="event.stopPropagation()">🔗 View in Zendesk</a>
                                <button class="view-details" onclick="showTicketDetails(${ticket.id}); event.stopPropagation()">📋 View Details</button>
                            </div>
                        </div>
                        `;
                    }).join('')}
                </div>
            `;

            document.getElementById('content').innerHTML = html;

            // Render the charts after DOM update
            setTimeout(() => {
                renderTicketsByHourChart(tickets);
                renderTicketsByChannelChart(tickets);
            }, 100);
        }

        let ticketsByHourChartInstance = null;
        let ticketsByChannelChartInstance = null;

        function renderTicketsByHourChart(tickets) {
            const ctx = document.getElementById('ticketsByHourChart');
            if (!ctx) return;

            // Process tickets by hour
            const hourCounts = new Array(24).fill(0);

            tickets.forEach(ticket => {
                const created = new Date(ticket.created_at);
                const hour = created.getHours();
                hourCounts[hour]++;
            });

            // Create hour labels (12-hour format with AM/PM)
            const hourLabels = Array.from({length: 24}, (_, i) => {
                const hour12 = i === 0 ? 12 : i > 12 ? i - 12 : i;
                const ampm = i < 12 ? 'AM' : 'PM';
                return `${hour12}${ampm}`;
            });

            // Destroy previous chart instance if it exists
            if (ticketsByHourChartInstance) {
                ticketsByHourChartInstance.destroy();
            }

            // Create new chart
            ticketsByHourChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: hourLabels,
                    datasets: [{
                        label: 'Tickets Created',
                        data: hourCounts,
                        borderColor: '#14f1d9',
                        backgroundColor: 'rgba(20, 241, 217, 0.15)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointBackgroundColor: '#14f1d9',
                        pointBorderColor: '#0a0e27',
                        pointBorderWidth: 2,
                        pointHoverBackgroundColor: '#00fff7',
                        pointHoverBorderColor: '#14f1d9',
                        pointHoverBorderWidth: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: true,
                            labels: {
                                color: '#14f1d9',
                                font: {
                                    family: 'JetBrains Mono',
                                    size: 12,
                                    weight: 700
                                },
                                padding: 15,
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(20, 24, 36, 0.95)',
                            titleColor: '#14f1d9',
                            bodyColor: '#e8edf5',
                            borderColor: '#14f1d9',
                            borderWidth: 1,
                            padding: 14,
                            displayColors: true,
                            titleFont: {
                                family: 'JetBrains Mono',
                                size: 13,
                                weight: 700
                            },
                            bodyFont: {
                                family: 'JetBrains Mono',
                                size: 12
                            },
                            callbacks: {
                                label: function(context) {
                                    const count = context.parsed.y;
                                    return count === 1 ? '1 ticket' : `${count} tickets`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                color: '#9ca3af',
                                stepSize: 1,
                                font: {
                                    family: 'JetBrains Mono',
                                    size: 11
                                },
                                callback: function(value) {
                                    return Number.isInteger(value) ? value : '';
                                }
                            },
                            grid: {
                                color: 'rgba(20, 241, 217, 0.05)',
                                drawBorder: false,
                                lineWidth: 1
                            },
                            title: {
                                display: true,
                                text: 'NUMBER OF TICKETS',
                                color: '#14f1d9',
                                font: {
                                    family: 'JetBrains Mono',
                                    size: 10,
                                    weight: 700
                                },
                                padding: { top: 10, bottom: 10 }
                            }
                        },
                        x: {
                            ticks: {
                                color: '#9ca3af',
                                maxRotation: 45,
                                minRotation: 45,
                                font: {
                                    family: 'JetBrains Mono',
                                    size: 10
                                }
                            },
                            grid: {
                                color: 'rgba(20, 241, 217, 0.03)',
                                drawBorder: false
                            },
                            title: {
                                display: true,
                                text: 'Hour of Day',
                                color: '#94a3b8',
                                font: {
                                    size: 12
                                }
                            }
                        }
                    }
                }
            });
        }

        function renderTicketsByChannelChart(tickets) {
            const ctx = document.getElementById('ticketsByChannelChart');
            if (!ctx) return;

            // Process tickets by channel
            const channelCounts = {};

            tickets.forEach(ticket => {
                // Get channel from via object
                const channel = ticket.via?.channel || 'unknown';
                // Special case for API to make it all caps
                const channelName = channel.toLowerCase() === 'api' ? 'API' : channel.charAt(0).toUpperCase() + channel.slice(1);
                channelCounts[channelName] = (channelCounts[channelName] || 0) + 1;
            });

            // Sort channels by count (descending)
            const sortedChannels = Object.entries(channelCounts)
                .sort((a, b) => b[1] - a[1]);

            const channelLabels = sortedChannels.map(([channel]) => channel);
            const channelData = sortedChannels.map(([, count]) => count);

            // Color palette for channels - Mission Control theme
            const channelColors = {
                'API': '#14f1d9',      // Electric Cyan
                'Email': '#8b5cf6',    // Purple
                'Web': '#6366f1',      // Blue
                'Mobile': '#a78bfa',   // Light Purple
                'Chat': '#00fff7',     // Bright Cyan
                'Unknown': '#6b7280'   // Gray
            };

            const backgroundColors = channelLabels.map(label => channelColors[label] || '#9ca3af');
            const borderColors = channelLabels.map(label => channelColors[label] || '#9ca3af');

            // Destroy previous chart instance if it exists
            if (ticketsByChannelChartInstance) {
                ticketsByChannelChartInstance.destroy();
            }

            // Create new chart
            ticketsByChannelChartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: channelLabels,
                    datasets: [{
                        label: 'Tickets by Channel',
                        data: channelData,
                        backgroundColor: backgroundColors,
                        borderColor: '#0a0e27',
                        borderWidth: 3,
                        hoverOffset: 15,
                        hoverBorderColor: '#14f1d9',
                        hoverBorderWidth: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    onClick: (event, activeElements) => {
                        if (activeElements.length > 0) {
                            const index = activeElements[0].index;
                            const channelName = channelLabels[index];

                            // Filter tickets by channel
                            const filterFn = (ticket) => {
                                const ticketChannel = ticket.via?.channel || 'unknown';
                                const normalizedChannel = ticketChannel.toLowerCase() === 'api' ? 'API' : ticketChannel.charAt(0).toUpperCase() + ticketChannel.slice(1);
                                return normalizedChannel === channelName;
                            };

                            // Show filtered tickets modal
                            showFilteredTickets(filterFn, `📡 ${channelName} Channel Tickets`);
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'right',
                            labels: {
                                color: '#e8edf5',
                                font: {
                                    family: 'JetBrains Mono',
                                    size: 11,
                                    weight: 700
                                },
                                padding: 18,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                generateLabels: function(chart) {
                                    const data = chart.data;
                                    if (data.labels.length && data.datasets.length) {
                                        return data.labels.map((label, i) => {
                                            const value = data.datasets[0].data[i];
                                            const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
                                            const percentage = ((value / total) * 100).toFixed(1);
                                            return {
                                                text: `${label}: ${value} (${percentage}%)`,
                                                fillStyle: data.datasets[0].backgroundColor[i],
                                                strokeStyle: data.datasets[0].backgroundColor[i],
                                                fontColor: '#e8edf5',
                                                hidden: false,
                                                index: i
                                            };
                                        });
                                    }
                                    return [];
                                }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(20, 24, 36, 0.95)',
                            titleColor: '#14f1d9',
                            bodyColor: '#e8edf5',
                            borderColor: '#14f1d9',
                            borderWidth: 1,
                            padding: 14,
                            titleFont: {
                                family: 'JetBrains Mono',
                                size: 13,
                                weight: 700
                            },
                            bodyFont: {
                                family: 'JetBrains Mono',
                                size: 12
                            },
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} tickets (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }

        function showAlert(message) {
            const alertsDiv = document.getElementById('alerts');
            const alert = document.createElement('div');
            alert.className = 'alert-banner';
            alert.textContent = message;
            alertsDiv.appendChild(alert);

            setTimeout(() => {
                alert.remove();
            }, 5000);
        }

        function formatTime(isoTime) {
            if (!isoTime) return 'Unknown';
            const date = new Date(isoTime);
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }

        function updateStatus(status, message) {
            const statusEl = document.getElementById('status');
            const indicator = document.querySelector('.status-indicator');

            if (status === 'live') {
                statusEl.textContent = 'LIVE';
                indicator.className = 'status-indicator status-live';
            } else {
                statusEl.textContent = `Error: ${message}`;
                indicator.className = 'status-indicator status-error';
            }
        }

        async function fetchData() {
            // Fetch both tickets and agent statuses in parallel
            const [tickets] = await Promise.all([
                fetchTickets(),
                fetchAgentStatuses()
            ]);

            if (tickets) {
                allTickets = tickets; // Store globally for filtering
                const stats = calculateStats(tickets);
                const newTickets = detectNewTickets(tickets);

                if (newTickets.length > 0) {
                    showAlert(`🚨 ${newTickets.length} new ticket(s) received!`);
                }

                renderDashboard(tickets, stats);
                updateStatus('live');
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            }
        }

        function toggleAutoRefresh() {
            CONFIG.autoRefresh = !CONFIG.autoRefresh;
            const btn = document.getElementById('autoRefreshBtn');

            if (CONFIG.autoRefresh) {
                btn.textContent = '⏸️ Pause Auto-Refresh';
                startAutoRefresh();
            } else {
                btn.textContent = '▶️ Resume Auto-Refresh';
                stopAutoRefresh();
            }
        }

        function changeInterval() {
            const seconds = prompt('Enter refresh interval in seconds (minimum 10):', CONFIG.refreshInterval / 1000);
            if (seconds && !isNaN(seconds) && seconds >= 10) {
                CONFIG.refreshInterval = seconds * 1000;
                document.getElementById('refreshInterval').textContent = `${seconds}s`;
                stopAutoRefresh();
                startAutoRefresh();
            }
        }

        async function showTicketDetails(ticketId) {
            const modal = document.getElementById('ticketModal');
            const modalBody = document.getElementById('modalBody');

            // Show modal with loading state
            modal.classList.add('show');
            modalBody.innerHTML = '<div class="loading-spinner">Loading ticket details...</div>';

            try {
                const response = await fetch(`/api/ticket/${ticketId}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const ticket = await response.json();

                // Render ticket details
                const html = `
                    <div class="modal-header">
                        <h2>#${ticket.id} - ${ticket.subject || 'No subject'}</h2>
                        <div class="ticket-meta">
                            <span>Priority: ${(ticket.priority || 'none').toUpperCase()}</span> |
                            <span>Status: ${(ticket.status || 'unknown').toUpperCase()}</span> |
                            <span>Created: ${formatTime(ticket.created_at)}</span>
                        </div>
                    </div>
                    <div class="modal-body">
                        <div class="detail-section">
                            <h3>Description</h3>
                            <div class="detail-content">${ticket.description || 'No description'}</div>
                        </div>

                        ${ticket.assignee_id ? `
                            <div class="detail-section">
                                <h3>Assigned To</h3>
                                <div class="detail-content">${getAgentName(ticket.assignee_id)}</div>
                            </div>
                        ` : ''}

                        ${ticket.comments && ticket.comments.length > 0 ? `
                            <div class="detail-section">
                                <h3>Comments (${ticket.comments.length})</h3>
                                ${ticket.comments.map(comment => `
                                    <div class="comment-item">
                                        <div class="comment-author">Comment by User ID: ${comment.author_id}</div>
                                        <div class="comment-time">${formatTime(comment.created_at)}</div>
                                        <div class="comment-body">${comment.body || comment.plain_body || 'No content'}</div>
                                    </div>
                                `).join('')}
                            </div>
                        ` : '<p style="color: #94a3b8; font-style: italic;">No comments yet</p>'}

                        <div class="detail-section">
                            <a href="https://${CONFIG.subdomain}.zendesk.com/agent/tickets/${ticket.id}" target="_blank" class="view-zendesk" style="display: inline-block; margin-top: 10px;">🔗 Open in Zendesk</a>
                        </div>
                    </div>
                `;

                modalBody.innerHTML = html;
            } catch (error) {
                modalBody.innerHTML = `<div style="color: #ef4444; padding: 20px;">Error loading ticket details: ${error.message}</div>`;
            }
        }

        function closeTicketModal() {
            const modal = document.getElementById('ticketModal');
            modal.classList.remove('show');
        }

        function closeFilteredTicketsModal() {
            const modal = document.getElementById('filteredTicketsModal');
            modal.classList.remove('show');
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const ticketModal = document.getElementById('ticketModal');
            const filteredModal = document.getElementById('filteredTicketsModal');
            if (event.target === ticketModal) {
                closeTicketModal();
            }
            if (event.target === filteredModal) {
                closeFilteredTicketsModal();
            }
        }

        function showFilteredTickets(filterFn, title) {
            const modal = document.getElementById('filteredTicketsModal');
            const modalBody = document.getElementById('filteredTicketsBody');

            const filteredTickets = allTickets.filter(filterFn);

            modal.classList.add('show');

            const html = `
                <div class="modal-header">
                    <h2>${title}</h2>
                    <div class="ticket-meta" style="font-size: 14px;">
                        Showing ${filteredTickets.length} ticket(s)
                    </div>
                </div>
                <div class="modal-body">
                    ${filteredTickets.length > 0 ? filteredTickets.map(ticket => `
                        <div class="ticket-item ${ticket.priority === 'urgent' ? 'urgent' : ''}" data-ticket-id="${ticket.id}">
                            <div class="ticket-id">#${ticket.id} 🔗 ${renderSLABadge(ticket)}</div>
                            <div class="ticket-subject">${ticket.subject || 'No subject'}</div>
                            <div class="ticket-meta">
                                <span>Priority: ${(ticket.priority || 'none').toUpperCase()}</span>
                                <span>Status: ${(ticket.status || 'unknown').toUpperCase()}</span>
                                <span>Created: ${formatTime(ticket.created_at)}</span>
                                ${ticket.assignee_id ? `<span>Assigned: ${getAgentName(ticket.assignee_id)}</span>` : '<span>Unassigned</span>'}
                            </div>
                            <div class="ticket-actions">
                                <a href="https://${CONFIG.subdomain}.zendesk.com/agent/tickets/${ticket.id}" target="_blank" class="view-zendesk" onclick="event.stopPropagation()">🔗 View in Zendesk</a>
                                <button class="view-details" onclick="showTicketDetails(${ticket.id}); event.stopPropagation()">📋 View Details</button>
                            </div>
                        </div>
                    `).join('') : '<p style="color: #94a3b8; text-align: center; padding: 40px;">No tickets found</p>'}
                </div>
            `;

            modalBody.innerHTML = html;
        }

        function startAutoRefresh() {
            stopAutoRefresh();
            if (CONFIG.autoRefresh) {
                refreshTimer = setInterval(fetchData, CONFIG.refreshInterval);
            }
        }

        function stopAutoRefresh() {
            if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
            }
        }

        // Initialize
        fetchData();
        startAutoRefresh();
    </script>
</body>
</html>"""

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    """Start the server."""
    port = 8080

    # Set credentials
    os.environ['ZENDESK_SUBDOMAIN'] = os.getenv('ZENDESK_SUBDOMAIN', 'counterparthealth')
    os.environ['ZENDESK_EMAIL'] = os.getenv('ZENDESK_EMAIL', 'anthony.gil@counterparthealth.com')
    os.environ['ZENDESK_API_TOKEN'] = os.getenv('ZENDESK_API_TOKEN', '24ICYAgncoLX19UJ6A3nmuIpZLXU3CrERIpav7kv')

    server = HTTPServer(('localhost', port), ZendeskProxyHandler)

    print("=" * 80)
    print("🚀 Zendesk Dashboard Server Started")
    print("=" * 80)
    print(f"\n✅ Server running at: http://localhost:{port}")
    print(f"📊 Dashboard URL: http://localhost:{port}/dashboard")
    print(f"\n🔗 Open in browser: http://localhost:{port}\n")
    print("Press Ctrl+C to stop the server")
    print("=" * 80 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user.")
        server.shutdown()


if __name__ == "__main__":
    main()
