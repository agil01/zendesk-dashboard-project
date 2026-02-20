# Zendesk MCP Server

This directory contains the Model Context Protocol (MCP) server for Zendesk integration.

## What is MCP?

Model Context Protocol (MCP) allows Claude to interact with external systems and data sources. This server exposes Zendesk ticket data and operations to Claude Code.

## Features

### Resources (Read-only data)
- `zendesk://tickets/recent` - Tickets from the last 24 hours
- `zendesk://tickets/urgent` - All urgent priority tickets
- `zendesk://tickets/open` - All open status tickets
- `zendesk://stats/summary` - Ticket statistics summary

### Tools (Interactive operations)
- `get_urgent_tickets` - Get all urgent priority tickets with filters
- `get_ticket_details` - Get detailed info about a specific ticket
- `search_tickets` - Search tickets by subject or description
- `get_ticket_stats` - Get statistics (counts by status, priority)
- `create_ticket_summary` - Generate formatted summary reports
- `monitor_ticket_status` - Check status of specific tickets

## Installation

1. Install MCP dependencies:
```bash
cd ~/zendesk-dashboard-project/mcp_server
pip3 install -r requirements.txt
```

2. Make the server executable:
```bash
chmod +x zendesk_mcp_server.py
```

## Configuration

### Option 1: Claude Desktop App

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zendesk": {
      "command": "python3",
      "args": [
        "/Users/anthonygil/zendesk-dashboard-project/mcp_server/zendesk_mcp_server.py"
      ],
      "env": {
        "ZENDESK_SUBDOMAIN": "counterparthealth",
        "ZENDESK_EMAIL": "your.email@company.com",
        "ZENDESK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

### Option 2: Claude Code CLI

Add to `~/.config/claude-code/config.json`:

```json
{
  "mcpServers": {
    "zendesk": {
      "command": "python3",
      "args": [
        "/Users/anthonygil/zendesk-dashboard-project/mcp_server/zendesk_mcp_server.py"
      ],
      "env": {
        "ZENDESK_SUBDOMAIN": "counterparthealth",
        "ZENDESK_EMAIL": "your.email@company.com",
        "ZENDESK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

**Note**: The server will also automatically load credentials from `../config/config.env` if that file exists.

## Usage Examples

Once configured, you can use the MCP server in Claude Code:

### Get Urgent Tickets
```
Use the Zendesk MCP to get all urgent tickets from the last 24 hours
```

### Search Tickets
```
Search Zendesk tickets for "access request"
```

### Get Statistics
```
What are the current Zendesk ticket statistics?
```

### Create Summary Report
```
Generate a markdown summary of today's Zendesk tickets
```

### Monitor Specific Tickets
```
Check the status of Zendesk tickets 4010, 4009, and 4004
```

## Testing

Test the server manually:

```bash
# Run the server (it expects stdio communication)
python3 zendesk_mcp_server.py

# The server will wait for MCP protocol messages via stdin
# Press Ctrl+C to exit
```

For proper testing, use with Claude Desktop or Claude Code CLI.

## Troubleshooting

### Server Not Showing Up

1. Check config file location and format
2. Verify Python path is correct
3. Ensure dependencies are installed
4. Restart Claude Desktop/Code

### Authentication Errors

1. Verify credentials in config
2. Check API token is valid
3. Test credentials manually:
```bash
curl -u "your.email@company.com/token:your_token" \
  "https://counterparthealth.zendesk.com/api/v2/tickets.json"
```

### No Data Returned

1. Check if there are tickets in the time window
2. Verify API permissions
3. Check server logs for errors

## Development

To add new tools:

1. Add tool definition in `handle_list_tools()`
2. Add tool implementation in `handle_call_tool()`
3. Test with Claude Code
4. Update this README

## Security

- Never commit credentials to git
- Use environment variables or config files
- Rotate API tokens regularly
- Only share on secure networks

## Support

- Main project: See `../README.md`
- MCP Protocol: https://modelcontextprotocol.io
- Zendesk API: https://developer.zendesk.com/api-reference/

---

**Version**: 1.0.0
**Status**: ✅ Active
