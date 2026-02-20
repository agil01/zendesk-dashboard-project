#!/bin/bash
# Quick launcher for Zendesk Web Dashboard

cd "$(dirname "$0")"

# Load configuration
if [ -f ../config/config.env ]; then
    export $(cat ../config/config.env | grep -v '^#' | xargs)
fi

echo "🚀 Starting Zendesk Dashboard Server..."
echo ""
echo "📊 Dashboard will open at: http://localhost:${SERVER_PORT:-8080}"
echo "⏱️  Auto-refresh: ${REFRESH_INTERVAL:-30} seconds"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 zendesk_server.py
