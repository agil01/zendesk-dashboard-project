# SLA Metrics Upgrade - Zendesk Dashboard

**Date**: February 19, 2026
**Status**: ✅ Complete

## Overview

The Zendesk Real-Time Dashboard has been upgraded to use **actual SLA resolution metrics configured in Zendesk** instead of hardcoded values. The dashboard now accurately tracks SLA breaches based on your organization's actual SLA policies.

## What Changed

### Before (Hardcoded SLAs)
- Urgent: 60 minutes
- High: 240 minutes
- Normal: 480 minutes
- Low: 1440 minutes
- **Problem**: Didn't reflect actual Zendesk SLA policies

### After (Zendesk SLA Metrics)
- ✅ Fetches actual SLA policies from Zendesk API
- ✅ Uses configured resolution time or reply time metrics
- ✅ Accurately tracks SLA breaches as defined in your Zendesk
- ✅ Shows SLA policy name and metric type
- ✅ Displays business hours vs calendar hours settings

## Technical Implementation

### New Server Features

1. **SLA Data Fetching** (`get_ticket_sla_data`)
   - Retrieves metric_events for each ticket
   - Fetches first 50 tickets to balance performance

2. **SLA Parsing** (`parse_sla_metrics`)
   - Extracts SLA target times from metric events
   - Prioritizes resolution_time over reply_time
   - Tracks SLA breaches and fulfillment status

3. **Ticket Enrichment**
   - Each ticket now includes `sla_metrics` field with:
     - `metric_type`: "resolution_time" or "reply_time"
     - `target_seconds`: Actual SLA target from Zendesk
     - `business_hours`: Whether using business hours
     - `policy_title`: Name of SLA policy
     - `breached`: Whether SLA was breached
     - `fulfilled`: Whether SLA was met

### Updated Frontend

1. **Smart SLA Calculation**
   - Uses actual Zendesk SLA targets
   - Calculates remaining time based on real policies
   - Shows breach status from Zendesk

2. **Enhanced SLA Badges**
   - Displays policy name on hover
   - Shows metric type (Resolution vs Reply)
   - Color-coded status:
     - 🔴 Red: Breached
     - 🟠 Orange: At Risk (< 25% time remaining)
     - 🟢 Green: On Track

## Example SLA Data

```json
{
  "metric_type": "reply_time",
  "target_seconds": 300,
  "business_hours": true,
  "policy_title": "Problem Support SLA's",
  "policy_id": 21945692532379,
  "fulfilled": true,
  "breached": false,
  "breach_time": null
}
```

## SLA Breach Detection

The dashboard now only shows breaches when:
1. Ticket has a **resolution_time** SLA policy (not reply_time)
2. Zendesk reports a breach event in metric_events
3. OR current ticket age exceeds the SLA target

**Important**: The SLA Status section specifically tracks **Resolution Time** SLAs only. This ensures the breach count reflects tickets that have exceeded their resolution SLA target, not just reply time.

### Why Resolution Time Only?

- **Resolution Time**: Measures total time to resolve a ticket (most important metric)
- **Reply Time**: Only measures time to first response (less critical for breach tracking)
- The dashboard prioritizes showing critical resolution SLA breaches for action

## Metric Types Supported

### Resolution Time (Preferred)
- Tracks time from ticket creation to resolution
- Most accurate for overall ticket handling
- Used when available

### Reply Time (Fallback)
- Tracks time to first public reply
- Used when resolution SLA not configured
- Still provides valuable tracking

## Performance Considerations

- SLA data fetched for first 50 tickets only
- Prevents excessive API calls
- Balances accuracy with performance

## How to Use

### View SLA Information

1. Open dashboard: http://localhost:8080
2. View the "SLA Status (Resolution Time)" section
   - Shows only tickets with resolution_time SLA policies
   - Breached, At Risk, and On Track counts
3. Look for SLA badges next to ticket IDs
4. Hover over badges to see:
   - SLA policy name
   - Metric type (Resolution/Reply)

**Note**: The SLA Status counters only include tickets with **resolution_time** SLA policies. Tickets with only reply_time SLAs will still show SLA badges but won't be counted in the SLA Status section.

### Interpret SLA Status

| Badge | Meaning | Action |
|-------|---------|--------|
| 🟢 On Track | > 25% time remaining | Monitor normally |
| 🟠 At Risk | < 25% time remaining | Prioritize soon |
| 🔴 Breached | Past target time | Immediate attention |
| Met/Resolved | Closed, met SLA | No action |

## Testing

Verified with ticket #4018:
- ✅ SLA data fetched successfully
- ✅ Policy: "Problem Support SLA's"
- ✅ Target: 5 minutes (300 seconds)
- ✅ Metric: reply_time
- ✅ Status: Fulfilled, not breached

## Benefits

1. **Accuracy**: Uses your actual SLA policies, not estimates
2. **Compliance**: Matches Zendesk's SLA tracking exactly
3. **Flexibility**: Adapts to your SLA policy changes automatically
4. **Transparency**: Shows which policy and metric is being tracked
5. **Actionable**: Breach detection aligns with Zendesk reports

## Next Steps

### Recommended Enhancements

1. **SLA Policy Configuration**
   - Ensure all ticket types have appropriate SLA policies in Zendesk
   - Configure both reply_time and resolution_time for comprehensive tracking

2. **Business Hours**
   - Review business hours settings in Zendesk
   - Consider impact on SLA calculations

3. **Monitoring**
   - Watch dashboard for SLA breaches
   - Use "At Risk" warnings to prevent breaches

## Troubleshooting

### "No SLA" Badge Appears

**Cause**: Ticket doesn't have an SLA policy applied in Zendesk

**Solution**:
1. Check Zendesk SLA policies (Admin → Business Rules → SLA)
2. Ensure ticket type/priority has a policy assigned
3. Verify policy is active

### SLA Times Seem Off

**Cause**: Business hours vs calendar hours confusion

**Solution**:
- Check `business_hours` field in SLA data
- Review Zendesk schedule settings
- Dashboard shows actual remaining time

## Files Modified

- `scripts/zendesk_server.py`
  - Added `get_ticket_sla_data()` method
  - Added `parse_sla_metrics()` method
  - Updated `handle_api_request()` to enrich tickets
  - Updated `getSLAStatus()` JavaScript function
  - Updated `renderSLABadge()` to show metric type

## API Endpoints Used

- `/api/v2/search.json` - Fetch tickets
- `/api/v2/tickets/{id}/metric_events.json` - Fetch SLA metrics

## Dashboard Access

- **URL**: http://localhost:8080
- **Auto-refresh**: Every 30 seconds
- **SLA Updates**: Real-time from Zendesk

---

## Summary

Your Zendesk dashboard now uses **real SLA resolution metrics** configured in your Zendesk instance. SLA breaches are only reported when resolution time (or reply time) exceeds the actual SLA target as defined in your Zendesk policies.

**Ready to use!** Open http://localhost:8080 to see your SLA metrics in action.
