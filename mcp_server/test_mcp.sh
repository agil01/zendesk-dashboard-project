#!/bin/bash
# Quick test script for Zendesk MCP Server

echo "🧪 Testing Zendesk MCP Server..."
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"

# Load config
source "$SCRIPT_DIR/../config/config.env"

# Export credentials
export ZENDESK_SUBDOMAIN
export ZENDESK_EMAIL
export ZENDESK_API_TOKEN

echo "Configuration loaded:"
echo "  Subdomain: $ZENDESK_SUBDOMAIN"
echo "  Email: $ZENDESK_EMAIL"
echo "  Token: ${ZENDESK_API_TOKEN:0:10}..."
echo ""

echo "Python: $PYTHON_CMD"
$PYTHON_CMD --version
echo ""

echo "MCP package installed:"
$PYTHON_CMD -c "import mcp; print(f'  mcp version: {mcp.__version__}')" 2>/dev/null || echo "  ERROR: mcp not installed"
echo ""

echo "Testing imports..."
$PYTHON_CMD -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/../scripts')
from mcp.server import Server
from mcp.server.stdio import stdio_server
import requests
print('  ✓ All imports successful')
" 2>/dev/null || echo "  ERROR: Import failed"
echo ""

echo "Testing Zendesk API connection..."
$PYTHON_CMD -c "
import os
import requests
from requests.auth import HTTPBasicAuth

subdomain = os.getenv('ZENDESK_SUBDOMAIN')
email = os.getenv('ZENDESK_EMAIL')
token = os.getenv('ZENDESK_API_TOKEN')
url = f'https://{subdomain}.zendesk.com/api/v2/users/me.json'
auth = HTTPBasicAuth(f'{email}/token', token)

try:
    response = requests.get(url, auth=auth, timeout=10)
    response.raise_for_status()
    print('  ✓ Zendesk API connection successful')
except Exception as e:
    print(f'  ✗ Zendesk API connection failed: {e}')
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To start the MCP server manually:"
echo "  $PYTHON_CMD $SCRIPT_DIR/zendesk_mcp_server.py"
echo ""
echo "The server is configured in:"
echo "  ~/.config/claude-code/config.json"
echo ""
echo "Restart Claude Code to use the MCP server."
echo ""
