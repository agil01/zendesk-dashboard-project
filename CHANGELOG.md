# Changelog

All notable changes to this project will be documented in this file.

## [2.2.0] - 2026-02-20

### Added

#### Interactive Drill-Down
- **Channel Chart Drill-Down**: Click-to-explore functionality on Tickets by Channel chart
  - Click any channel slice (API, Email, Web, Mobile, Chat) to view tickets
  - Modal displays filtered tickets with full details
  - Visual indicator: "(Click to drill-in)" hint in section title
  - Pointer cursor on hover for better UX
  - Channel-specific filtering with proper ticket counts

### Changed

#### Visual Improvements
- **API Label**: Changed "Api" to "API" (all caps) in legend and labels
- **Updated Colors**:
  - API: Changed from blue to turquoise (#14b8a6)
  - Email: Changed from red to yellow (#eab308)
  - Other channels remain: Web (green), Mobile (orange), Chat (purple)
- Enhanced chart interactivity and user engagement

---

## [2.1.0] - 2026-02-20

### Added

#### Dashboard Enhancements
- **Tickets by Channel Chart**: New doughnut chart visualizing ticket distribution by source channel
  - Channel breakdown: API, Email, Web, Mobile, Chat
  - Color-coded visualization (API: blue, Email: red, Web: green, Mobile: orange, Chat: purple)
  - Interactive legend with ticket counts and percentages
  - Auto-refresh with dashboard updates
  - Integrated seamlessly into existing dashboard layout

### Changed
- Enhanced chart rendering with dual chart support (Hour + Channel)
- Updated dashboard layout to include channel analytics section

---

## [2.0.0] - 2026-02-20

### Added - MCP Integration 🚀

#### New Features
- **MCP Server**: Full Model Context Protocol integration for AI-powered Zendesk queries
- **Natural Language Interface**: Ask Claude about tickets using plain English
- **Unified Client**: Smart data access layer with automatic MCP/API fallback
- **6 MCP Tools**: 
  - `get_urgent_tickets` - Get urgent priority tickets with filters
  - `get_ticket_details` - Detailed ticket information
  - `search_tickets` - Search by subject/description
  - `get_ticket_stats` - Statistics and counts
  - `create_ticket_summary` - Formatted reports (markdown/text/json)
  - `monitor_ticket_status` - Track specific tickets
- **4 MCP Resources**:
  - `zendesk://tickets/recent` - Recent tickets stream
  - `zendesk://tickets/urgent` - Urgent tickets stream
  - `zendesk://tickets/open` - Open tickets stream
  - `zendesk://stats/summary` - Statistics stream

#### New Files
- `mcp_server/zendesk_mcp_server.py` - MCP server implementation
- `mcp_server/requirements.txt` - MCP dependencies
- `mcp_server/README.md` - Server documentation
- `mcp_server/setup_mcp.sh` - Automated setup script
- `mcp_server/test_mcp.sh` - Verification script
- `scripts/zendesk_client.py` - Unified client with MCP/API support
- `scripts/zendesk_api_wrapper.py` - Lightweight API wrapper
- `ARCHITECTURE.md` - System architecture documentation
- `INTEGRATION_SUMMARY.md` - Integration overview
- `MCP_SETUP.md` - Detailed setup guide
- `MCP_QUICKSTART.md` - Quick reference
- `MCP_INSTALLATION_COMPLETE.md` - Setup confirmation
- `CHANGELOG.md` - This file

#### Documentation Updates
- Updated `README.md` with MCP integration information
- Added MCP section to Quick Start
- Updated Tools Included section
- Enhanced Features list

### Changed

#### Architecture
- Introduced hybrid MCP + API architecture
- All tools now support transparent data source selection
- Automatic fallback from MCP to API
- Data source indicators in all outputs

#### Backward Compatibility
- ✅ All existing tools work unchanged
- ✅ Same configuration requirements
- ✅ Same performance characteristics
- ✅ No breaking changes

### Technical Details

#### Data Flow
```
Before: User → Tools → Zendesk API
After:  User → Tools → [MCP or API] → Zendesk API
        User → Claude → MCP Server → Zendesk API
```

#### Performance
- Web Dashboard: ~500ms (unchanged - uses API)
- Terminal Monitor: ~500ms (unchanged - uses API)
- Daily Summary: ~1s (unchanged - uses API)
- MCP Queries: ~800ms (new capability)

#### Requirements
- Python 3.10+ for MCP server (uses virtual environment)
- Python 3.9+ for existing tools (unchanged)
- MCP package (auto-installed in venv)
- Existing dependencies unchanged

### Migration Guide

#### For Users
1. Existing workflows continue to work as-is
2. Optionally enable MCP for AI-powered queries
3. No configuration changes required
4. MCP is an enhancement, not a requirement

#### For Developers
1. Import `zendesk_client.py` for unified access
2. Client auto-detects MCP availability
3. Graceful fallback to API
4. Same interface for both sources

### Security
- MCP uses same credentials as API
- Environment-based credential management
- No credentials in code or config files
- Virtual environment isolation for MCP

### Known Issues
- None - all tests passing

### Upgrade Notes
- No upgrade required for existing users
- MCP is opt-in enhancement
- See `MCP_SETUP.md` for MCP installation
- Fallback to API ensures continuous operation

---

## [1.0.0] - 2026-02-19

### Initial Release

#### Features
- Web Dashboard with real-time monitoring
- Terminal Monitor with live updates
- Daily Summary report generator
- Executive report templates
- SLA tracking and metrics
- Multi-interface support
- Auto-refresh capabilities
- Priority tracking
- Status analytics

#### Tools
- `zendesk_server.py` - Web dashboard server
- `zendesk_monitor.py` - Terminal monitor
- `zendesk_daily_summary.py` - Report generator
- `start-dashboard.sh` - Web launcher
- `start_monitor.sh` - Terminal launcher

#### Documentation
- Comprehensive README.md
- Quick start guide (QUICKSTART.md)
- Skill integration guide (SKILL.md)
- Index and navigation (INDEX.md)
- Setup verification script

#### Configuration
- Environment-based configuration
- Example configuration template
- Security best practices
- Credential protection (.gitignore)

---

## Version History

- **2.2.0** (2026-02-20) - Interactive Drill-Down & Visual Updates
- **2.1.0** (2026-02-20) - Tickets by Channel Chart
- **2.0.0** (2026-02-20) - MCP Integration
- **1.0.0** (2026-02-19) - Initial Release

## Upgrade Path

### From 2.1.0 to 2.2.0
```bash
cd ~/zendesk-dashboard-project
git pull
# Restart dashboard to see drill-down and color updates
./scripts/start-dashboard.sh
```

**Impact**: Zero - all existing functionality preserved, enhanced with click-to-drill interactivity

### From 2.0.0 to 2.1.0
```bash
cd ~/zendesk-dashboard-project
git pull
# Restart dashboard to see new channel chart
./scripts/start-dashboard.sh
```

**Impact**: Zero - all existing functionality preserved, new chart added automatically

### From 1.0.0 to 2.0.0
```bash
cd ~/zendesk-dashboard-project
git pull

# Optional: Set up MCP
cd mcp_server
./setup_mcp.sh
```

**Impact**: Zero - all existing functionality preserved

## Support

For issues, questions, or feature requests:
1. Check documentation in `docs/` directory
2. Review `ARCHITECTURE.md` for design details
3. See `INTEGRATION_SUMMARY.md` for MCP info
4. Create issue on GitHub

---

**Current Version**: 2.2.0
**Last Updated**: 2026-02-20
**Status**: Production Ready
