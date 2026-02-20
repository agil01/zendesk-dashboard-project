#!/bin/bash
# Zendesk Monitor Launcher

export ZENDESK_SUBDOMAIN="counterparthealth"
export ZENDESK_EMAIL="anthony.gil@counterparthealth.com"
export ZENDESK_API_TOKEN="24ICYAgncoLX19UJ6A3nmuIpZLXU3CrERIpav7kv"
export REFRESH_INTERVAL="${1:-30}"  # Default 30 seconds, or use first argument

echo "🚀 Starting Zendesk Real-Time Monitor"
echo "📡 Refresh interval: ${REFRESH_INTERVAL} seconds"
echo ""

python3 zendesk_monitor.py
