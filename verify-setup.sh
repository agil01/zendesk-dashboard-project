#!/bin/bash
# Verification script to check if everything is set up correctly

echo "======================================================================"
echo "🔍 Zendesk Dashboard Project - Setup Verification"
echo "======================================================================"
echo ""

# Check Python
echo "1. Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "   ✅ $PYTHON_VERSION installed"
else
    echo "   ❌ Python 3 not found"
    exit 1
fi

# Check pip
echo ""
echo "2. Checking pip..."
if command -v pip3 &> /dev/null; then
    echo "   ✅ pip3 installed"
else
    echo "   ❌ pip3 not found"
    exit 1
fi

# Check dependencies
echo ""
echo "3. Checking Python dependencies..."
if python3 -c "import requests" 2>/dev/null; then
    echo "   ✅ requests library installed"
else
    echo "   ⚠️  requests library not installed"
    echo "   Run: pip3 install -r requirements.txt"
fi

# Check configuration
echo ""
echo "4. Checking configuration..."
if [ -f "config/config.env" ]; then
    echo "   ✅ config/config.env exists"

    source config/config.env

    if [ -n "$ZENDESK_SUBDOMAIN" ]; then
        echo "   ✅ ZENDESK_SUBDOMAIN: $ZENDESK_SUBDOMAIN"
    else
        echo "   ❌ ZENDESK_SUBDOMAIN not set"
    fi

    if [ -n "$ZENDESK_EMAIL" ]; then
        echo "   ✅ ZENDESK_EMAIL: ${ZENDESK_EMAIL:0:20}..."
    else
        echo "   ❌ ZENDESK_EMAIL not set"
    fi

    if [ -n "$ZENDESK_API_TOKEN" ]; then
        echo "   ✅ ZENDESK_API_TOKEN: ${ZENDESK_API_TOKEN:0:10}..."
    else
        echo "   ❌ ZENDESK_API_TOKEN not set"
    fi
else
    echo "   ❌ config/config.env not found"
    echo "   Run: cp config/config.example.env config/config.env"
    exit 1
fi

# Check scripts
echo ""
echo "5. Checking scripts..."
SCRIPTS=(
    "scripts/zendesk_server.py"
    "scripts/zendesk_monitor.py"
    "scripts/zendesk_daily_summary.py"
    "scripts/start_monitor.sh"
    "scripts/start-dashboard.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo "   ✅ $script"
    else
        echo "   ❌ $script not found"
    fi
done

# Check port availability
echo ""
echo "6. Checking port availability..."
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "   ⚠️  Port 8080 is in use"
    echo "   Kill process: kill \$(lsof -ti:8080)"
else
    echo "   ✅ Port 8080 is available"
fi

# Test API connection
echo ""
echo "7. Testing Zendesk API connection..."
source config/config.env

TEST_URL="https://${ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -u "${ZENDESK_EMAIL}/token:${ZENDESK_API_TOKEN}" "$TEST_URL")

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ API connection successful (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "401" ]; then
    echo "   ❌ Authentication failed (HTTP $HTTP_CODE)"
    echo "   Check your email and API token in config/config.env"
else
    echo "   ⚠️  API returned HTTP $HTTP_CODE"
fi

echo ""
echo "======================================================================"
echo "📋 Setup Summary"
echo "======================================================================"
echo ""
echo "Project Location: $(pwd)"
echo "Configuration: config/config.env"
echo "Main Scripts:"
echo "  - Web Dashboard: scripts/start-dashboard.sh"
echo "  - Terminal Monitor: scripts/start_monitor.sh"
echo "  - Daily Report: scripts/zendesk_daily_summary.py"
echo ""
echo "To start the web dashboard, run:"
echo "  ./scripts/start-dashboard.sh"
echo ""
echo "For full documentation, see README.md"
echo "======================================================================"
