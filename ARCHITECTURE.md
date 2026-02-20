# Zendesk Dashboard Project - Architecture

## Overview

The Zendesk Dashboard Project provides multiple interfaces for accessing and monitoring Zendesk ticket data, with a unified architecture that supports both direct API access and MCP (Model Context Protocol) integration.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      ZENDESK API                             │
│              (Single Source of Truth)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐       ┌────────▼────────┐
│   MCP Server   │       │  Direct API     │
│   (Optional)   │       │  (Always Works) │
└───────┬────────┘       └────────┬────────┘
        │                         │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │  Unified Client Layer   │
        │  (zendesk_client.py)    │
        │  - Auto-detects MCP     │
        │  - Falls back to API    │
        └────────────┬────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐       ┌────────▼────────┐
│   Dashboard    │       │  Legacy Tools   │
│   Tools (New)  │       │  (Compatible)   │
│                │       │                 │
│ - Web Server   │       │ - Monitor       │
│ - Terminal     │       │ - Summary       │
│ - Reports      │       │ - Scripts       │
└────────────────┘       └─────────────────┘
```

## Components

### 1. Data Source Layer

#### Zendesk API
- **Primary data source** for all ticket information
- REST API v2
- Authentication: Email + API Token
- Rate limits: ~200 requests/minute

#### MCP Server (Optional Enhancement)
- **Location**: `mcp_server/zendesk_mcp_server.py`
- **Purpose**: AI-powered interface for Claude Code
- **Features**:
  - Natural language queries
  - Structured tool calls
  - Resource streaming
  - Automatic caching
- **When Active**: Provides enhanced capabilities for AI interactions
- **When Inactive**: System falls back to direct API

### 2. Client Layer

#### Unified Zendesk Client
- **File**: `scripts/zendesk_client.py`
- **Purpose**: Single interface for all data access
- **Features**:
  - Auto-detects MCP availability
  - Graceful fallback to API
  - Consistent interface for all tools
  - Connection pooling
  - Error handling

**Data Source Selection Logic**:
```python
if MCP_available and not force_api:
    use MCP Server
else:
    use Direct API
```

#### API Wrapper (Backward Compatible)
- **File**: `scripts/zendesk_api_wrapper.py`
- **Purpose**: Lightweight API access for simple scripts
- **Use Case**: When MCP overhead isn't needed

### 3. Application Layer

#### Web Dashboard (`zendesk_server.py`)
- Real-time browser interface
- SLA tracking and metrics
- Auto-refresh capabilities
- **Data Source**: Direct API (optimized for web)
- **Port**: 8080
- **Access**: http://localhost:8080

#### Terminal Monitor (`zendesk_monitor.py`)
- CLI real-time dashboard
- Live updates and alerts
- Sound notifications
- **Data Source**: Direct API (low latency)
- **Usage**: `./start_monitor.sh`

#### Daily Summary (`zendesk_daily_summary.py`)
- Report generation
- Markdown/HTML output
- Statistical analysis
- **Data Source**: Direct API or MCP
- **Output**: `zendesk_summary_YYYYMMDD.md`

#### MCP Server Tools
- Natural language interface
- AI-powered queries
- Advanced filtering
- **Data Source**: Direct API (via MCP protocol)
- **Access**: Through Claude Code

## Data Flow

### Example: Fetching Urgent Tickets

**Via MCP (Claude Code)**:
```
User → Claude Code → MCP Client → MCP Server → Zendesk API → Response
```

**Via Web Dashboard**:
```
User → Browser → Web Server → Zendesk API → Response
```

**Via Unified Client (New Scripts)**:
```
Script → ZendeskClient → [MCP Server OR Direct API] → Zendesk API → Response
```

## Design Decisions

### Why Keep Direct API Access?

1. **Reliability**: Always works, even if MCP server is down
2. **Performance**: Lower latency for simple queries
3. **Simplicity**: No additional dependencies for basic tools
4. **Compatibility**: Existing scripts continue to work

### Why Add MCP Integration?

1. **AI Enhancement**: Natural language queries via Claude
2. **Advanced Features**: Complex filtering and analysis
3. **User Experience**: Easier for non-technical users
4. **Future-Proof**: Leverages modern AI capabilities

### Hybrid Approach Benefits

1. **Best of Both Worlds**: Speed of API + Power of MCP
2. **Graceful Degradation**: Falls back if MCP unavailable
3. **Flexibility**: Users choose their preferred interface
4. **Maintainability**: Single source of truth (Zendesk API)

## Configuration

### Environment Variables

```bash
# Required for all tools
ZENDESK_SUBDOMAIN=counterparthealth
ZENDESK_EMAIL=your.email@company.com
ZENDESK_API_TOKEN=your_api_token

# Optional for web dashboard
SERVER_PORT=8080
REFRESH_INTERVAL=30
```

### MCP Configuration

**File**: `~/.config/claude-code/config.json`

```json
{
  "mcpServers": {
    "zendesk": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/zendesk_mcp_server.py"]
    }
  }
}
```

## Data Source Indicators

All tools now show which data source they're using:

- **MCP**: ` Data Source: MCP` (when MCP server is active)
- **API**: ` Data Source: API` (direct Zendesk API)

## Performance Characteristics

| Tool | Data Source | Latency | Best For |
|------|-------------|---------|----------|
| Web Dashboard | Direct API | ~500ms | Real-time monitoring |
| Terminal Monitor | Direct API | ~500ms | Quick checks |
| Daily Summary | Direct API | ~1s | Reports |
| MCP Tools | MCP → API | ~800ms | AI queries |
| Claude Code | MCP → API | ~800ms | Natural language |

## Error Handling

### Cascading Fallback

```
MCP Server → Direct API → Cached Data → Error Message
```

1. **Try MCP**: If configured and available
2. **Fall back to API**: Always available
3. **Use Cache**: If network issues
4. **Show Error**: Only as last resort

## Security

### Credential Management

- **Storage**: `config/config.env` (git-ignored)
- **Access**: Environment variables only
- **Transmission**: HTTPS only
- **MCP**: Credentials passed via environment, never in code

### API Token Security

- **Rotation**: Regular token rotation recommended
- **Permissions**: Read-only where possible
- **Monitoring**: Track API usage in Zendesk
- **Storage**: Never committed to git

## Scalability

### Current Limits

- **API Rate Limit**: ~200 req/min
- **Concurrent Connections**: Unlimited (HTTP)
- **Data Volume**: Tickets from last 24-48 hours
- **MCP Connections**: 1 per user

### Optimization Strategies

1. **Caching**: MCP server caches responses
2. **Pagination**: Large result sets paginated
3. **Filtering**: Server-side filtering where possible
4. **Connection Pooling**: Reuse HTTP connections

## Future Enhancements

### Planned Features

1. **Webhook Integration**: Real-time ticket updates
2. **Database Layer**: Local caching for offline access
3. **Multi-Tenant**: Support multiple Zendesk accounts
4. **Analytics**: Historical trend analysis
5. **Alerts**: Configurable notification system

### MCP Enhancements

1. **Read/Write**: Support ticket creation via MCP
2. **Attachments**: Handle file uploads
3. **Advanced Search**: Complex query building
4. **Batch Operations**: Bulk ticket updates

## Monitoring

### Health Checks

- **API**: `/api/tickets` endpoint
- **MCP**: Tool availability check
- **Web Dashboard**: Browser console logs
- **Terminal**: Real-time status display

### Metrics

- Response times
- Error rates
- Data source usage (MCP vs API)
- Ticket volume trends

## Development

### Adding New Tools

1. Import `ZendeskClient` or `zendesk_api_wrapper`
2. Call methods (e.g., `get_tickets()`)
3. Handle responses
4. Display data source indicator

### Testing

```bash
# Test API connection
python scripts/zendesk_api_wrapper.py

# Test MCP server
cd mcp_server && ./test_mcp.sh

# Test unified client
python scripts/zendesk_client.py
```

## Troubleshooting

### Common Issues

1. **"MCP Not Available"**
   - Normal - system falls back to API
   - Install MCP: `pip install mcp`

2. **"API Authentication Failed"**
   - Check `config/config.env`
   - Verify API token in Zendesk

3. **"No Tickets Found"**
   - Check time window (default 24h)
   - Verify tickets exist in Zendesk

## References

- **Zendesk API**: https://developer.zendesk.com/api-reference/
- **MCP Protocol**: https://modelcontextprotocol.io
- **Project Docs**: See README.md, MCP_SETUP.md

---

**Version**: 2.0.0 (With MCP Integration)
**Last Updated**: 2026-02-20
**Status**: ✅ Production Ready
