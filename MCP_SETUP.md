# Zendesk MCP Server Setup Guide

This guide will help you set up the Zendesk MCP (Model Context Protocol) server so you can interact with Zendesk directly through Claude Code.

## What You'll Get

Once configured, you can use natural language commands like:
- "Show me all urgent Zendesk tickets"
- "Search Zendesk for access requests"
- "Generate a summary of today's tickets"
- "What's the status of ticket 4010?"

## Quick Setup (Recommended)

Run the automated setup script:

```bash
cd ~/zendesk-dashboard-project/mcp_server
./setup_mcp.sh
```

This will:
1. Install required dependencies
2. Check your credentials
3. Create the MCP configuration
4. Show you next steps

## Manual Setup

If you prefer to set it up manually:

### Step 1: Install Dependencies

```bash
cd ~/zendesk-dashboard-project/mcp_server
pip3 install -r requirements.txt
```

### Step 2: Make Server Executable

```bash
chmod +x ~/zendesk-dashboard-project/mcp_server/zendesk_mcp_server.py
```

### Step 3: Configure MCP

#### For Claude Desktop App

Create or edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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
        "ZENDESK_EMAIL": "anthony.gil@counterparthealth.com",
        "ZENDESK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

#### For Claude Code CLI

Create or edit `~/.config/claude-code/config.json`:

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
        "ZENDESK_EMAIL": "anthony.gil@counterparthealth.com",
        "ZENDESK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

**Note**: Replace credentials with your actual values from `config/config.env`

### Step 4: Restart Claude

- **Claude Desktop**: Close and reopen the app
- **Claude Code**: Restart your terminal or session

## Verify Installation

Test that the MCP server is working:

1. In Claude, try these commands:
   - "What Zendesk MCP tools are available?"
   - "Show me urgent Zendesk tickets"
   - "Get Zendesk ticket statistics"

2. You should see Claude using the MCP tools to fetch real data from Zendesk

## Available MCP Tools

### Resources (Read-only data streams)
- `zendesk://tickets/recent` - Recent tickets (24h)
- `zendesk://tickets/urgent` - All urgent tickets
- `zendesk://tickets/open` - All open tickets
- `zendesk://stats/summary` - Ticket statistics

### Tools (Interactive operations)

1. **get_urgent_tickets**
   - Get all urgent priority tickets
   - Parameters: `hours`, `include_solved`

2. **get_ticket_details**
   - Get detailed info about a specific ticket
   - Parameters: `ticket_id`

3. **search_tickets**
   - Search tickets by subject or description
   - Parameters: `query`, `hours`

4. **get_ticket_stats**
   - Get ticket statistics and counts
   - Parameters: `hours`

5. **create_ticket_summary**
   - Generate formatted summary reports
   - Parameters: `hours`, `format` (markdown/text/json)

6. **monitor_ticket_status**
   - Check status of specific tickets
   - Parameters: `ticket_ids` (array)

## Usage Examples

Once configured, you can use natural language:

### Get Urgent Tickets
```
Show me all urgent Zendesk tickets from the last 24 hours
```

### Search for Tickets
```
Search Zendesk tickets for "access request"
```

### Get Statistics
```
What are the current Zendesk ticket statistics?
```

### Generate Report
```
Create a markdown summary of today's Zendesk tickets
```

### Monitor Tickets
```
Check the status of Zendesk tickets 4010, 4009, and 4004
```

### Get Ticket Details
```
Show me details for Zendesk ticket 4010
```

## Troubleshooting

### MCP Server Not Available

**Issue**: Claude doesn't recognize Zendesk commands

**Solutions**:
1. Check config file exists and is valid JSON
2. Verify file path in config is correct
3. Restart Claude Desktop/Code
4. Check that dependencies are installed: `pip3 show mcp`

### Authentication Errors

**Issue**: "Authentication failed" or "401 Unauthorized"

**Solutions**:
1. Verify credentials in config match `config/config.env`
2. Check API token is valid in Zendesk
3. Test manually:
```bash
curl -u "your.email@company.com/token:your_token" \
  "https://counterparthealth.zendesk.com/api/v2/tickets.json"
```

### No Data Returned

**Issue**: Tools work but return empty results

**Solutions**:
1. Check if tickets exist in the time window
2. Expand time window: "show tickets from last 48 hours"
3. Verify API permissions in Zendesk

### Server Crashes

**Issue**: MCP server stops responding

**Solutions**:
1. Check logs in Claude
2. Verify Python dependencies: `pip3 install -r requirements.txt --upgrade`
3. Test server manually:
```bash
python3 ~/zendesk-dashboard-project/mcp_server/zendesk_mcp_server.py
# Press Ctrl+C to exit
```

## Advanced Configuration

### Custom Time Windows

Edit the default time window in queries:
```
Show me urgent tickets from the last 48 hours
```

### Multiple Output Formats

Request different formats:
```
Create a JSON summary of today's tickets
Create a text summary of today's tickets
```

### Combine with Other Tools

Use MCP alongside file operations:
```
Get urgent Zendesk tickets and save to a file
```

## Security Best Practices

1. **Protect Credentials**
   - Never commit config files with credentials
   - Use environment variables in shared configs
   - Rotate API tokens regularly

2. **Restrict Access**
   - Only install on trusted machines
   - Use read-only API tokens if possible
   - Monitor API usage in Zendesk

3. **Audit Logs**
   - Check Zendesk API logs regularly
   - Monitor for unusual access patterns

## Updating

To update the MCP server:

```bash
cd ~/zendesk-dashboard-project
git pull  # if using git
cd mcp_server
pip3 install -r requirements.txt --upgrade
```

Then restart Claude.

## Uninstalling

To remove the MCP server:

1. Remove from config file:
   - Delete the `"zendesk"` section from `claude_desktop_config.json` or `config.json`

2. Restart Claude

3. Optionally remove files:
```bash
rm -rf ~/zendesk-dashboard-project/mcp_server
```

## Support

- **MCP Server Issues**: See `mcp_server/README.md`
- **Zendesk Issues**: See main `README.md`
- **MCP Protocol**: https://modelcontextprotocol.io
- **Zendesk API**: https://developer.zendesk.com/api-reference/

## Next Steps

After setup:

1. Test basic commands to verify connection
2. Explore available tools and resources
3. Create custom workflows combining MCP with other Claude capabilities
4. Consider automating reports or monitoring

---

**Version**: 1.0.0
**Status**: ✅ Ready to use
**Last Updated**: 2026-02-20

Happy monitoring! 🎯
