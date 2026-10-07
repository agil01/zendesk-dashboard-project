#!/usr/bin/env python3
"""Convert pipe-delimited rows into JSON records. usage: ingest.py out.json < rows
row: id|status|priority|created|updated|requester|assignee_id|tags(comma-sep)
Noise tags (routing/reminder/macro) are dropped at ingest."""
import sys,json
DROP=('auto-routing-tag','counterparthealth','created_from_slack','claude_trigger_macro','claude_practice_activation','claude_termination','task_reminder_sent','reminder_active')
recs=[]
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    i,s,p,c,u,r,a,t=line.split('|')
    tags=[x for x in t.split(',') if x and x not in DROP and not x.startswith(('pending_since_','last_reminder_'))]
    recs.append(dict(id=int(i),status=s,priority=p,created_at=c,updated_at=u,requester_id=r,assignee_id=a,tags=tags))
json.dump(recs,open(sys.argv[1],'w'),indent=0)
print(len(recs),'records ->',sys.argv[1])
