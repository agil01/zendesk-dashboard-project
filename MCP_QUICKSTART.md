# Zendesk MCP Server - Quick Start

## ✅ Setup Complete!

Your Zendesk MCP server is now configured and ready to use.

## What You Can Do Now

Use natural language commands in Claude Code to interact with Zendesk:

### Get Urgent Tickets
```
Show me all urgent Zendesk tickets
```

### Search Tickets
```
Search Zendesk for "access request"
```

### Get Statistics
```
What are my Zendesk ticket statistics for today?
```

### Generate Reports
```
Create a markdown summary of today's Zendesk tickets
```

### Monitor Tickets
```
Check the status of Zendesk tickets 4010, 4009, and 4004
```

### Get Ticket Details
```
Get details for Zendesk ticket 4010
```

## Available Tools

The MCP server provides these tools:

1. **get_urgent_tickets** - Get all urgent priority tickets
2. **get_ticket_details** - Get detailed info about a specific ticket
3. **search_tickets** - Search tickets by subject or description
4. **get_ticket_stats** - Get statistics (counts by status, priority)
5. **create_ticket_summary** - Generate formatted summary reports
6. **monitor_ticket_status** - Check status of specific tickets

## Configuration

Your MCP server is configured at:
```
~/.config/claude-code/config.json
```

The server uses:
- Python: `/Users/anthonygil/zendesk-dashboard-project/mcp_server/venv/bin/python`
- Server: `/Users/anthonygil/zendesk-dashboard-project/mcp_server/zendesk_mcp_server.py`
- Credentials: Loaded from `~/zendesk-dashboard-project/config/config.env`

## Testing

To verify the setup:

```bash
cd ~/zendesk-dashboard-project/mcp_server
./test_mcp.sh
```

## Usage Tips

1. **Be specific**: "Show urgent tickets from last 48 hours" works better than "show tickets"
2. **Use IDs**: Reference ticket IDs directly like "ticket 4010"
3. **Request formats**: Ask for "markdown summary" or "JSON format" for different outputs
4. **Combine tools**: "Search for access requests and create a summary"

## Troubleshooting

### Server Not Responding

1. Check configuration:
```bash
cat ~/.config/claude-code/config.json
```

2. Test the server:
```bash
cd ~/zendesk-dashboard-project/mcp_server
./test_mcp.sh
```

3. Verify credentials:
```bash
cat ~/zendesk-dashboard-project/config/config.env
```

### Authentication Errors

Update your API token in:
```bash
nano ~/zendesk-dashboard-project/config/config.env
```

Then restart Claude Code.

## Next Steps

1. Try the example commands above
2. Explore creating custom queries
3. Combine MCP with file operations (e.g., "Get urgent tickets and save to a file")
4. Set up automated reporting workflows

## Documentation

- Full setup guide: `MCP_SETUP.md`
- Server docs: `mcp_server/README.md`
- Main project: `README.md`

---

**Status**: ✅ Ready to use
**Version**: 1.0.0
**Last Updated**: 2026-02-20
