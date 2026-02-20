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

    def serve_dashboard(self):
        """Serve the dashboard HTML with embedded JavaScript."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zendesk Real-Time Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }

        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }

        .header .meta {
            opacity: 0.9;
            font-size: 14px;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        .status-live {
            background: #22c55e;
            box-shadow: 0 0 10px #22c55e;
        }

        .status-error {
            background: #ef4444;
            box-shadow: 0 0 10px #ef4444;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 25px;
            border: 1px solid #334155;
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            border-color: #60a5fa;
        }

        .card.clickable:hover::after {
            content: "📋 Click to view tickets";
            position: absolute;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 10px;
            color: #60a5fa;
            white-space: nowrap;
        }

        .card-header {
            font-size: 12px;
            text-transform: uppercase;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 10px;
            letter-spacing: 0.5px;
        }

        .card-value {
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .card-label {
            font-size: 14px;
            color: #cbd5e1;
        }

        .urgent { color: #ef4444; }
        .high { color: #f59e0b; }
        .normal { color: #3b82f6; }
        .low { color: #22c55e; }

        .section {
            background: #1e293b;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid #334155;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .badge {
            background: #ef4444;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .ticket-item {
            background: #0f172a;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #3b82f6;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }

        .ticket-item:hover {
            background: #1e293b;
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        .ticket-item.urgent {
            border-left-color: #ef4444;
        }

        .ticket-id {
            font-weight: 600;
            color: #60a5fa;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .ticket-subject {
            font-size: 15px;
            margin-bottom: 8px;
        }

        .ticket-meta {
            font-size: 12px;
            color: #94a3b8;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }

        .ticket-actions {
            margin-top: 10px;
            display: flex;
            gap: 10px;
        }

        .ticket-actions a, .ticket-actions button {
            font-size: 12px;
            padding: 6px 12px;
            border-radius: 4px;
            text-decoration: none;
            transition: all 0.2s;
        }

        .view-zendesk {
            background: #3b82f6;
            color: white;
            border: none;
        }

        .view-zendesk:hover {
            background: #2563eb;
        }

        .view-details {
            background: #475569;
            color: white;
            border: none;
        }

        .view-details:hover {
            background: #334155;
        }

        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.8);
            animation: fadeIn 0.3s;
        }

        .modal.show {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .modal-content {
            background: #1e293b;
            border-radius: 12px;
            padding: 30px;
            max-width: 800px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
            animation: slideUp 0.3s;
            border: 1px solid #334155;
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
            position: absolute;
            top: 15px;
            right: 20px;
            font-size: 28px;
            font-weight: bold;
            color: #94a3b8;
            cursor: pointer;
            background: none;
            border: none;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-close:hover {
            color: #e2e8f0;
        }

        .modal-header {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #334155;
        }

        .modal-header h2 {
            color: #60a5fa;
            margin-bottom: 10px;
            font-size: 24px;
        }

        .modal-body {
            color: #cbd5e1;
        }

        .detail-section {
            margin-bottom: 25px;
        }

        .detail-section h3 {
            color: #94a3b8;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 10px;
            font-weight: 600;
        }

        .detail-content {
            background: #0f172a;
            padding: 15px;
            border-radius: 6px;
            white-space: pre-wrap;
            line-height: 1.6;
        }

        .comment-item {
            background: #0f172a;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 10px;
            border-left: 3px solid #475569;
        }

        .comment-author {
            font-weight: 600;
            color: #60a5fa;
            margin-bottom: 5px;
            font-size: 13px;
        }

        .comment-time {
            font-size: 11px;
            color: #64748b;
            margin-bottom: 8px;
        }

        .comment-body {
            color: #cbd5e1;
            font-size: 13px;
            line-height: 1.5;
        }

        .loading-spinner {
            text-align: center;
            padding: 40px;
        }

        .loading-spinner::after {
            content: "Loading...";
            color: #60a5fa;
        }

        /* SLA Status Badges */
        .sla-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .sla-ok {
            background: #22c55e;
            color: white;
        }

        .sla-warning {
            background: #f59e0b;
            color: white;
        }

        .sla-breach {
            background: #ef4444;
            color: white;
            animation: pulse-sla 2s infinite;
        }

        .sla-none {
            background: #475569;
            color: #cbd5e1;
        }

        @keyframes pulse-sla {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .alert-banner {
            background: #dc2626;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            animation: slideIn 0.3s ease-out;
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
            padding: 40px;
            font-size: 18px;
            color: #64748b;
        }

        .spinner {
            border: 3px solid #334155;
            border-top: 3px solid #60a5fa;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        button {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        button:hover {
            background: #2563eb;
        }

        button.secondary {
            background: #475569;
        }

        button.secondary:hover {
            background: #334155;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Zendesk Real-Time Dashboard</h1>
        <div class="meta">
            <span class="status-indicator status-live"></span>
            <span id="status">Live</span> |
            Last update: <span id="lastUpdate">Loading...</span> |
            Auto-refresh: <span id="refreshInterval">30s</span> |
            Timezone: CST
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

                <div class="section">
                    <div class="section-title">📈 Tickets by Hour of Day</div>
                    <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                        <canvas id="ticketsByHourChart" style="max-height: 300px;"></canvas>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">📨 Tickets by Channel</div>
                    <div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;">
                        <canvas id="ticketsByChannelChart" style="max-height: 300px;"></canvas>
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

                ${Object.keys(stats.byAssignee).length > 0 ? `
                    <div class="section">
                        <div class="section-title">👥 Tickets by Assignee</div>
                        <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                            ${Object.entries(stats.byAssignee)
                                .sort((a, b) => b[1].total - a[1].total)
                                .slice(0, 6)
                                .map(([assigneeId, data]) => `
                                    <div class="card clickable" onclick="showFilteredTickets(t => t.assignee_id == '${assigneeId}', '👤 ${getAgentName(assigneeId)} Tickets')">
                                        <div class="card-header">${getAgentName(assigneeId)}</div>
                                        <div class="card-value" style="font-size: 28px;">${data.total}</div>
                                        <div class="card-label">
                                            ${data.urgent > 0 ? `🔴 ${data.urgent} urgent` : ''}
                                            ${data.open > 0 ? `📂 ${data.open} open` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            ${stats.unassigned > 0 ? `
                                <div class="card clickable" onclick="showFilteredTickets(t => !t.assignee_id, '⚪ Unassigned Tickets')">
                                    <div class="card-header">⚪ Unassigned</div>
                                    <div class="card-value" style="font-size: 28px;">${stats.unassigned}</div>
                                    <div class="card-label">Need assignment</div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}

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
                    ${tickets.slice(0, 10).map(ticket => `
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
                    `).join('')}
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
                        borderColor: '#60a5fa',
                        backgroundColor: 'rgba(96, 165, 250, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#60a5fa',
                        pointBorderColor: '#1e293b',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: true,
                            labels: {
                                color: '#e2e8f0',
                                font: {
                                    size: 14,
                                    weight: 600
                                }
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1e293b',
                            titleColor: '#e2e8f0',
                            bodyColor: '#cbd5e1',
                            borderColor: '#334155',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: false,
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
                                color: '#94a3b8',
                                stepSize: 1,
                                callback: function(value) {
                                    return Number.isInteger(value) ? value : '';
                                }
                            },
                            grid: {
                                color: '#334155',
                                drawBorder: false
                            },
                            title: {
                                display: true,
                                text: 'Number of Tickets',
                                color: '#94a3b8',
                                font: {
                                    size: 12
                                }
                            }
                        },
                        x: {
                            ticks: {
                                color: '#94a3b8',
                                maxRotation: 45,
                                minRotation: 45
                            },
                            grid: {
                                color: '#334155',
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
                const channelName = channel.charAt(0).toUpperCase() + channel.slice(1);
                channelCounts[channelName] = (channelCounts[channelName] || 0) + 1;
            });

            // Sort channels by count (descending)
            const sortedChannels = Object.entries(channelCounts)
                .sort((a, b) => b[1] - a[1]);

            const channelLabels = sortedChannels.map(([channel]) => channel);
            const channelData = sortedChannels.map(([, count]) => count);

            // Color palette for channels
            const channelColors = {
                'Api': '#3b82f6',      // Blue
                'Email': '#ef4444',    // Red
                'Web': '#22c55e',      // Green
                'Mobile': '#f59e0b',   // Orange
                'Chat': '#8b5cf6',     // Purple
                'Unknown': '#64748b'   // Gray
            };

            const backgroundColors = channelLabels.map(label => channelColors[label] || '#94a3b8');
            const borderColors = backgroundColors.map(color => color);

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
                        borderColor: borderColors,
                        borderWidth: 2,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'right',
                            labels: {
                                color: '#ffffff',
                                font: {
                                    size: 14,
                                    weight: 600
                                },
                                padding: 15,
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
                                                strokeStyle: data.datasets[0].borderColor[i],
                                                fontColor: '#ffffff',
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
                            backgroundColor: '#1e293b',
                            titleColor: '#e2e8f0',
                            bodyColor: '#cbd5e1',
                            borderColor: '#334155',
                            borderWidth: 1,
                            padding: 12,
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
                statusEl.textContent = 'Live';
                indicator.className = 'status-indicator status-live';
            } else {
                statusEl.textContent = `Error: ${message}`;
                indicator.className = 'status-indicator status-error';
            }
        }

        async function fetchData() {
            const tickets = await fetchTickets();

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
