#!/bin/bash
# Setup script for Zendesk MCP Server

set -e

echo "🚀 Setting up Zendesk MCP Server..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Step 1: Find Python 3.10+
echo "🐍 Checking Python version..."
PYTHON_CMD=""

# Try python3.13, python3.12, python3.11, python3.10
for py_version in python3.13 python3.12 python3.11 python3.10; do
    if command -v $py_version &> /dev/null; then
        PYTHON_CMD=$py_version
        PY_VERSION=$($PYTHON_CMD --version)
        echo -e "${GREEN}✓ Found $PY_VERSION at $(which $PYTHON_CMD)${NC}"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}✗ Python 3.10+ required but not found${NC}"
    echo "  Please install Python 3.10+ using:"
    echo "  brew install python@3.13"
    exit 1
fi
echo ""

# Step 2: Install dependencies
echo "📦 Installing MCP dependencies..."
$PYTHON_CMD -m pip install -r "$SCRIPT_DIR/requirements.txt"
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 3: Make server executable
echo "🔧 Making server executable..."
chmod +x "$SCRIPT_DIR/zendesk_mcp_server.py"
echo -e "${GREEN}✓ Server is now executable${NC}"
echo ""

# Step 4: Check for credentials
echo "🔐 Checking credentials..."
CONFIG_FILE="$PROJECT_DIR/config/config.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}✗ Config file not found: $CONFIG_FILE${NC}"
    echo "  Please create it from config.example.env and add your credentials"
    exit 1
fi

# Load and check required variables
if grep -q "ZENDESK_SUBDOMAIN" "$CONFIG_FILE" && \
   grep -q "ZENDESK_EMAIL" "$CONFIG_FILE" && \
   grep -q "ZENDESK_API_TOKEN" "$CONFIG_FILE"; then
    echo -e "${GREEN}✓ Credentials found in config.env${NC}"
else
    echo -e "${RED}✗ Missing credentials in $CONFIG_FILE${NC}"
    echo "  Please ensure ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, and ZENDESK_API_TOKEN are set"
    exit 1
fi
echo ""

# Step 5: Detect config location and create MCP config
echo "📝 Setting up MCP configuration..."

# Try to find Claude config directory
if [ -d "$HOME/Library/Application Support/Claude" ]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
    CONFIG_TYPE="Claude Desktop"
elif [ -d "$HOME/.config/claude-code" ]; then
    CONFIG_DIR="$HOME/.config/claude-code"
    CONFIG_FILE="$CONFIG_DIR/config.json"
    CONFIG_TYPE="Claude Code CLI"
else
    # Create Claude Code config directory
    CONFIG_DIR="$HOME/.config/claude-code"
    CONFIG_FILE="$CONFIG_DIR/config.json"
    CONFIG_TYPE="Claude Code CLI"
    mkdir -p "$CONFIG_DIR"
    echo -e "${YELLOW}Created new config directory: $CONFIG_DIR${NC}"
fi

echo "Using $CONFIG_TYPE configuration"
echo "Config file: $CONFIG_FILE"
echo ""

# Load credentials from config.env
source "$PROJECT_DIR/config/config.env"

# Create or update MCP config
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}Config file already exists. You may need to manually add the zendesk server.${NC}"
    echo ""
    echo "Add this to your $CONFIG_FILE:"
else
    # Create new config
    cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "zendesk": {
      "command": "$PYTHON_PATH",
      "args": [
        "$SCRIPT_DIR/zendesk_mcp_server.py"
      ],
      "env": {
        "ZENDESK_SUBDOMAIN": "$ZENDESK_SUBDOMAIN",
        "ZENDESK_EMAIL": "$ZENDESK_EMAIL",
        "ZENDESK_API_TOKEN": "$ZENDESK_API_TOKEN"
      }
    }
  }
}
EOF
    echo -e "${GREEN}✓ Created MCP configuration${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Configuration for $CONFIG_FILE:"
echo ""
PYTHON_PATH=$(which $PYTHON_CMD)
cat << EOF
{
  "mcpServers": {
    "zendesk": {
      "command": "$PYTHON_PATH",
      "args": [
        "$SCRIPT_DIR/zendesk_mcp_server.py"
      ],
      "env": {
        "ZENDESK_SUBDOMAIN": "$ZENDESK_SUBDOMAIN",
        "ZENDESK_EMAIL": "$ZENDESK_EMAIL",
        "ZENDESK_API_TOKEN": "***hidden***"
      }
    }
  }
}
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 6: Next steps
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. If using Claude Desktop App:"
echo "   - Restart Claude Desktop"
echo "   - The Zendesk MCP server will be available"
echo ""
echo "2. If using Claude Code CLI:"
echo "   - Restart your terminal or reload config"
echo "   - Use commands like: 'Get urgent Zendesk tickets'"
echo ""
echo "3. Test the connection:"
echo "   - Ask Claude: 'What Zendesk MCP tools are available?'"
echo "   - Or: 'Show me today's urgent Zendesk tickets'"
echo ""
echo "For more info, see: $SCRIPT_DIR/README.md"
echo ""
