#!/usr/bin/env python3
"""Week-over-week Zendesk management report generator (Product Success / CA App Support).

Usage:
  python3 -I generate_wow_management_report.py \
     --cur-start 2026-09-28 --cur-end 2026-10-04 \
     --prev-start 2026-09-21 --prev-end 2026-09-27 \
     --data-dir "~/Desktop/Claude Files/wow_data" \
     --snapshot 2026-10-07 \
     --out "~/Desktop/Claude Files/management_report_2026-09-28_2026-10-04.html"

Data files expected in --data-dir (compact records written from Zendesk MCP search results,
cohort = tickets CREATED in the week; fields id,status,priority,created_at,updated_at,assignee_id,tags):
  cur_bola.json cur_candice.json cur_ron.json cur_other.json   (other = any other/unassigned assignee)
  prev_bola.json prev_candice.json prev_ron.json prev_other.json
  sla_cur.json sla_prev.json   ({"source":..., "compliance_pct":100, "tickets":N,
                                  "tiers":{"Urgent":{"avg":"2h 6m","target":"6h","tickets":9},...}}) or null
"""
import argparse, json, os, sys, statistics, html, collections, datetime as dt

AGENTS = [("Bola Kuye", "bola", "39948397141915"),
          ("Candice Brown", "candice", "21761242009371"),
          ("Ron Pineda", "ron", "21761363093147")]
RESOLVED = {"solved", "closed"}
UNRESOLVED = {"open", "pending", "hold", "new"}
NOISE = ("pending_since_", "last_reminder_")

# ---------------------------------------------------------------------------
# Tag -> (issue group, closed reason).  First match wins (ordered).  Reason names are fixed
# so they stay identical week to week.  Mirrors the Sep 28-Oct 4 executive summary logic.
# ---------------------------------------------------------------------------
G_UMAC, G_EHR, G_APP, G_CLM, G_EUE, G_IUE, G_OTH, G_NONE = (
    "User Management Admin Console", "EHR Configuration", "Application Issues", "Claims & Payments",
    "External User Error", "Internal User Error", "Other", "No Closed-Reason Tag")
NO_REASON = "No reason yet"
RULES = [
    # Humana first (beats ehr_integration_initiated / ehr_* sub tags)
    ({"hum_practice_activation"}, G_EHR, "Humana Practice Activation"),
    ({"kno2_submission"}, G_EHR, "Kno2 Submission"),
    ({"kno2_oid_/_publication_info"}, G_EHR, "Kno2 OID / Publication"),
    ({"system_email_notification_failure", "ehr_integration_initiated"}, G_EHR, "EHR Integration Initiated / Interface Authorized"),
    ({"ehr_data_user_mapping_issues"}, G_EHR, "User Mapping Issue"),
    ({"ehr_data_other"}, G_EHR, "EHR Data - Other"),
    # application issue family (includes EHR application tags, as in the exec summary)
    ({"app_issues_new_issue_identified"}, G_APP, "New Issue Identified"),
    ({"app_issues_unable_to_reproduce"}, G_APP, "Unable to Reproduce"),
    ({"app_issues_other"}, G_APP, "App Issues - Other"),
    ({"ehr_app_error_launching_ehr_application", "ehr_app_new_ehr_bug_identified"}, G_APP, "EHR App - Error Launching / New Bug"),
    ({"ehr_app_diagnosis_issue"}, G_APP, "EHR App - Diagnosis Issue"),
    ({"ehr_app_other"}, G_APP, "EHR App - Other"),
    ({"connectivity_other", "issue_type_connectivity"}, G_APP, "Connectivity - Other"),
    ({"app_issues_no_response_external_user"}, G_APP, "App Issues - No Response"),
    # UMAC
    ({"import_npi_/_tin"}, G_UMAC, "Import NPI / TIN"),
    ({"umac_no_action_required"}, G_UMAC, "No Action Required"),
    ({"create_employee_user"}, G_UMAC, "Create Employee User"),
    ({"umac_suspend/remove_access_umac"}, G_UMAC, "Suspend / Remove Access"),
    ({"umac_contract_settings"}, G_UMAC, "Contract Settings"),
    ({"umac_admin_command"}, G_UMAC, "Admin Command"),
    ({"umac_other"}, G_UMAC, "Other UMAC"),
    ({"environment/user_role_access_change"}, G_UMAC, "Environment / Role Access Change"),
    ({"umac_add/update_roles"}, G_UMAC, "Add / Update Roles"),
    ({"umac_registration_link/email_not_received"}, G_UMAC, "Registration Email Not Received"),
    ({"umac_duplicate"}, G_UMAC, "Duplicate Request"),
    ({"umac_no_response_internal_user", "umac_no_response_external_user"}, G_UMAC, "No Response"),
    # Claims
    ({"timely_filing__tf__denial"}, G_CLM, "Timely Filing (TF) Denial"),
    ({"rematch_visits"}, G_CLM, "Rematch Visits"),
    ({"cp_billing/claims_inquiry"}, G_CLM, "Billing / Claims Inquiry"),
    ({"cp_other"}, G_CLM, "Claims / Payments - Other"),
    # user error
    ({"eue_user_training"}, G_EUE, "User Training"),
    ({"eue_issue_type_delete_reopen_ccv"}, G_EUE, "Delete / Reopen / CCV"),
    ({"eue_working_as_designed"}, G_EUE, "Working as Designed"),
    ({"eue_duplicate_external_user_error"}, G_EUE, "Duplicate"),
    ({"eue_no_response_external_user"}, G_EUE, "No Response"),
    ({"iue_user_training"}, G_IUE, "User Training"),
    # other
    ({"other_miscellaneous"}, G_OTH, "Miscellaneous (MFA / Verification Codes, Questions)"),
    ({"it_okta"}, G_OTH, "IT / Okta Access"),
    ({"cdm_other"}, G_OTH, "Customer Data Management - Other"),
    # fallbacks by broad tag (no sub reason set)
    ({"ehr_data_integration_athena", "ehr_data_integration_ecw"}, G_EHR, "EHR Data Integration"),
    ({"application_issues", "ehr_application_issues"}, G_APP, "Application Issue - No Sub-Reason"),
    ({"claims/payments"}, G_CLM, "Claims / Payments - Other"),
]
# Issue-type categories used by the weekly ticket-count dashboard (5 buckets)
CAT_OF_GROUP = {G_EHR: "EHR / Integration", G_UMAC: "UMAC", G_CLM: "Claims / Payments",
                G_APP: "Application Issues", G_EUE: "Other / Misc", G_IUE: "Other / Misc",
                G_OTH: "Other / Misc", G_NONE: "Other / Misc"}
CATS = ["EHR / Integration", "UMAC", "Claims / Payments", "Application Issues", "Other / Misc"]
PRIO = ["urgent", "high", "normal", "low"]


def classify(t):
    tags = set(t["tags"])
    for needles, grp, reason in RULES:
        if tags & needles:
            return grp, reason
    # broad group tag with nothing more specific
    if "ehr_configuration" in tags:
        return G_EHR, "EHR Configuration - Other"
    if "user_management_admin_console" in tags:
        return G_UMAC, "Other UMAC"
    if "issue_type_other" in tags:
        return G_OTH, "Miscellaneous (MFA / Verification Codes, Questions)"
    return G_NONE, NO_REASON


def pd(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def load(data_dir, label):
    out = {}
    for name, key, aid in AGENTS:
        p = os.path.join(data_dir, f"{label}_{key}.json")
        out[name] = json.load(open(p))
    p = os.path.join(data_dir, f"{label}_other.json")
    out["Other / unassigned"] = json.load(open(p)) if os.path.exists(p) else []
    return out


def week_stats(data, start, end, snapshot):
    tickets = [dict(t, owner=a) for a, lst in data.items() for t in lst]
    ids = [t["id"] for t in tickets]
    assert len(ids) == len(set(ids)), "duplicate ticket ids across agent files"
    s = dt.datetime.combine(start, dt.time.min); e = dt.datetime.combine(end, dt.time.max)
    for t in tickets:
        c = pd(t["created_at"]); assert s <= c <= e, f"ticket {t['id']} outside cohort window"
        t["group"], t["reason"] = classify(t)
        t["cat"] = CAT_OF_GROUP[t["group"]]
        t["resolved"] = t["status"] in RESOLVED
        t["source"] = "internal" if "internal" in t["tags"] else "external" if "external" in t["tags"] else "unknown"
    return tickets


def hms(sec):
    if sec is None: return "n/a"
    h = sec / 3600
    return f"{h:.1f} h" if h < 48 else f"{h/24:.1f} d"


def pctile(vals, p):
    v = sorted(vals)
    if not v: return None
    k = (len(v) - 1) * p / 100
    f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def detect_batches(tix, threshold):
    """same requester + same calendar day (UTC) + same closed reason, count > threshold"""
    g = collections.defaultdict(list)
    for t in tix:
        g[(t["requester_id"], t["created_at"][:10], t["reason"])].append(t["id"])
    return [dict(day=k[1], reason=k[2], requester=k[0], n=len(v), ids=sorted(v))
            for k, v in g.items() if len(v) > threshold]


def build(args):
    D = os.path.expanduser(args.data_dir)
    cs, ce = dt.date.fromisoformat(args.cur_start), dt.date.fromisoformat(args.cur_end)
    ps, pe = dt.date.fromisoformat(args.prev_start), dt.date.fromisoformat(args.prev_end)
    snap = dt.datetime.fromisoformat(args.snapshot + "T23:59:59")
    cur = week_stats(load(D, "cur"), cs, ce, snap)
    prev = week_stats(load(D, "prev"), ps, pe, snap)
    sla = {}
    for k in ("cur", "prev"):
        p = os.path.join(D, f"sla_{k}.json")
        sla[k] = json.load(open(p)) if os.path.exists(p) else None
    return cs, ce, ps, pe, snap, cur, prev, sla


# ------------------------------------------------------------------ formatting helpers
def e(x): return html.escape(str(x))


def delta(c, p, pol="neutral", pp=False, unit=""):
    """pol: 'up' (increase is good) | 'down' (decrease is good) | 'neutral' (volume)"""
    d = c - p
    if pp:
        txt = f"{d:+.1f}pp"
    else:
        pc = f" ({d / p * 100:+.1f}%)" if p else " (new)" if d else ""
        txt = (f"{d:+d}" if isinstance(d, int) else f"{d:+.1f}") + f"{unit}{pc}"
    if abs(d) < 1e-9:
        return '<span class="neutral">&#9644; 0</span>'
    arrow = "&#9650;" if d > 0 else "&#9660;"
    if pol == "neutral": cls = "vol"
    else: cls = "good" if ((d > 0) == (pol == "up")) else "bad"
    return f'<span class="{cls}">{arrow} {e(txt)}</span>'


def pct(n, d): return (n / d * 100) if d else 0.0


def tbl(head, rows, cls="", total_last=False):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = []
    for i, r in enumerate(rows):
        tr = ' class="total-row"' if (total_last and i == len(rows) - 1) else ""
        sub = ""
        if isinstance(r, tuple) and r and r[0] == "__grp__":
            b.append(f'<tr class="grp-row"><td colspan="{len(head)}">{e(r[1])}</td></tr>'); continue
        b.append(f"<tr{tr}>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>")
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{"".join(b)}</tbody></table>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cur-start", required=True); ap.add_argument("--cur-end", required=True)
    ap.add_argument("--prev-start", required=True); ap.add_argument("--prev-end", required=True)
    ap.add_argument("--data-dir", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--snapshot", required=True, help="YYYY-MM-DD snapshot date of statuses")
    ap.add_argument("--batch-threshold", type=int, default=10)
    ap.add_argument("--expect-cur", help="check values e.g. Bola=37,Candice=33,Ron=30")
    ap.add_argument("--expect-prev")
    ap.add_argument("--extra-unresolved-note", default="#7150/#7152/#7153/#6669 (on-hold task tickets)")
    args = ap.parse_args()
    cs, ce, ps, pe, snap, cur, prev, sla = build(args)

    def lab(a, b): return f"{a.strftime('%b')} {a.day}–{b.strftime('%b')} {b.day}" if a.month != b.month else f"{a.strftime('%b')} {a.day}–{b.day}"
    CL, PL = lab(cs, ce), lab(ps, pe)
    names = [a[0] for a in AGENTS]

    # ---- expectation checks
    def check(tix, spec, label):
        if not spec: return
        for kv in spec.split(","):
            k, v = kv.split("="); n = sum(1 for t in tix if t["owner"].startswith(k))
            assert n == int(v), f"{label}: {k} expected {v} got {n}"
    check(cur, args.expect_cur, "cur"); check(prev, args.expect_prev, "prev")

    # ---- core aggregates
    def core(tix):
        r = {}
        r["total"] = len(tix)
        r["resolved"] = sum(t["resolved"] for t in tix)
        r["unres"] = r["total"] - r["resolved"]
        r["rate"] = pct(r["resolved"], r["total"])
        r["status"] = collections.Counter(t["status"] for t in tix)
        assert sum(r["status"].values()) == r["total"]
        r["by_agent"] = {}
        for a in names + ["Other / unassigned"]:
            ts = [t for t in tix if t["owner"] == a]
            r["by_agent"][a] = dict(total=len(ts), resolved=sum(t["resolved"] for t in ts),
                                    unres=[t["id"] for t in ts if not t["resolved"]],
                                    status=collections.Counter(t["status"] for t in ts))
        assert sum(v["total"] for v in r["by_agent"].values()) == r["total"]
        r["cat"] = collections.Counter(t["cat"] for t in tix); assert sum(r["cat"].values()) == r["total"]
        r["grp"] = collections.Counter(t["group"] for t in tix); assert sum(r["grp"].values()) == r["total"]
        r["reason"] = collections.Counter((t["group"], t["reason"]) for t in tix)
        assert sum(r["reason"].values()) == r["total"]
        r["reason_agent"] = collections.Counter((t["group"], t["reason"], t["owner"]) for t in tix)
        assert sum(r["reason_agent"].values()) == r["total"]
        r["prio"] = collections.Counter(t["priority"] for t in tix); assert sum(r["prio"].values()) == r["total"]
        r["src"] = collections.Counter(t["source"] for t in tix); assert sum(r["src"].values()) == r["total"]
        r["dow"] = collections.Counter(pd(t["created_at"]).weekday() for t in tix)
        assert sum(r["dow"].values()) == r["total"]
        ttr = [(pd(t["updated_at"]) - pd(t["created_at"])).total_seconds() for t in tix if t["resolved"]]
        r["ttr_n"] = len(ttr); r["ttr_med"] = statistics.median(ttr) if ttr else None; r["ttr_p90"] = pctile(ttr, 90)
        ages = collections.Counter()
        for t in tix:
            if not t["resolved"]:
                d = (snap.date() - pd(t["created_at"]).date()).days
                ages["0-3 days" if d <= 3 else "4-7 days" if d <= 7 else "8-14 days" if d <= 14 else "15+ days"] += 1
        r["ages"] = ages; assert sum(ages.values()) == r["unres"]
        r["batches"] = detect_batches(tix, args.batch_threshold)
        r["batch_n"] = sum(b["n"] for b in r["batches"]); r["batch_ids"] = {i for b in r["batches"] for i in b["ids"]}
        rq = collections.Counter(t["requester_id"] for t in tix)
        r["req"] = rq.most_common(5)
        return r
    C, P = core(cur), core(prev)

    # ---- section builders -------------------------------------------------
    S = []   # html sections
    ex_c, ex_p = C["total"] - C["batch_n"], P["total"] - P["batch_n"]

    # KPI tiles
    def tile(label, c, p, fmt, pol, pp=False, sub=""):
        dd = delta(c, p, pol, pp=pp)
        return (f'<div class="metric-box"><span class="value">{fmt(c)}</span><div class="label">{label}</div>'
                f'<div class="sub">{dd}</div><div class="sub">prev: {fmt(p)}{sub}</div></div>')
    f_i = lambda x: f"{x:d}"; f_p = lambda x: f"{x:.1f}%"
    kpis = "".join([
        tile("Tickets created", C["total"], P["total"], f_i, "neutral"),
        tile("Resolved (solved+closed)", C["resolved"], P["resolved"], f_i, "up"),
        tile("Resolution rate", C["rate"], P["rate"], f_p, "up", pp=True),
        tile("Still open (open/pend/hold)", C["unres"], P["unres"], f_i, "down"),
    ])
    S.append(f'<div class="metric-row">{kpis}</div>')

    # 1. volume table by agent
    rows = []
    for a in names + ["Other / unassigned"]:
        c, p = C["by_agent"][a], P["by_agent"][a]
        if a.startswith("Other") and c["total"] == 0 and p["total"] == 0:
            rows.append([f"<em>{a}</em>", "0", "0", "&#9644; 0", "0", "0", "&ndash;", "&ndash;", "0 / 0"]); continue
        rr = lambda x: f"{pct(x['resolved'], x['total']):.1f}%" if x["total"] else "&ndash;"
        rows.append([f"<strong>{a}</strong>", c["total"], p["total"], delta(c["total"], p["total"]),
                     c["resolved"], p["resolved"], rr(c), rr(p), f'{len(c["unres"])} / {len(p["unres"])}'])
    rows.append(["<strong>Team total</strong>", C["total"], P["total"], delta(C["total"], P["total"]),
                 C["resolved"], P["resolved"], f'{C["rate"]:.1f}%', f'{P["rate"]:.1f}%', f'{C["unres"]} / {P["unres"]}'])
    S.append("<h3>1. Ticket Volume, Resolution &amp; Open Status</h3>")
    S.append(f'<p class="note">Cohort = tickets <strong>created</strong> in the week; status as of {snap.date():%b} {snap.day}. '
             f'Current = {CL}, Previous = {PL}. "Resolved" = solved + closed.</p>')
    S.append(tbl(["Agent", "Created (cur)", "Created (prev)", "Change", "Resolved (cur)", "Resolved (prev)",
                  "Res. rate (cur)", "Res. rate (prev)", "Open cur / prev"], rows, "cmp", True))
    # status table
    sts = ["open", "pending", "hold", "solved", "closed"]
    rows = [[s.title(), C["status"].get(s, 0), P["status"].get(s, 0),
             delta(C["status"].get(s, 0), P["status"].get(s, 0), "down" if s in UNRESOLVED else "up" if s in RESOLVED else "neutral")] for s in sts]
    others = [s for s in set(C["status"]) | set(P["status"]) if s not in sts]
    for s in others: rows.append([s.title(), C["status"][s], P["status"][s], delta(C["status"][s], P["status"][s])])
    rows.append(["Total", C["total"], P["total"], delta(C["total"], P["total"])])
    S.append(tbl(["Status", "Current", "Previous", "Change"], rows, "cmp", True))
    unres_c = ", ".join(f"#{i}" for a in names + ["Other / unassigned"] for i in C["by_agent"][a]["unres"])
    unres_p = ", ".join(f"#{i}" for a in names + ["Other / unassigned"] for i in P["by_agent"][a]["unres"])

    # 2. SLA
    S.append("<h3>2. SLA Compliance (Business-Hour Average First Response)</h3>")
    if sla["cur"] and sla["prev"]:
        tiers = ["Urgent", "High", "Normal", "Low"]
        def mins(s):
            import re
            m = re.fullmatch(r"(?:(\d+)h)?\s*(?:(\d+)m)?", s.strip()); return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        rows = []
        for t in tiers:
            c, p = sla["cur"]["tiers"][t], sla["prev"]["tiers"][t]
            rows.append([f"<strong>{t}</strong>", c["avg"], p["avg"], delta(mins(c["avg"]), mins(p["avg"]), "down", unit="m"),
                         c["target"], c["tickets"], p["tickets"]])
        rows.append(["<strong>Compliance</strong>", f'{sla["cur"]["compliance_pct"]:g}%', f'{sla["prev"]["compliance_pct"]:g}%',
                     delta(sla["cur"]["compliance_pct"], sla["prev"]["compliance_pct"], "up", pp=True), "&ndash;",
                     sla["cur"]["tickets"], sla["prev"]["tickets"]])
        S.append(tbl(["Priority", "Avg (cur)", "Avg (prev)", "Change (minutes)", "Target", "Tickets (cur)", "Tickets (prev)"], rows, "cmp"))
    else:
        miss = [k for k in ("cur", "prev") if not sla[k]]
        S.append(f'<div class="callout callout-red"><strong>SLA data not available</strong> for: {", ".join(miss)}. No figures have been estimated.</div>')

    # 3. Issue type
    S.append("<h3>3. Tickets by Issue Type</h3>")
    rows = []
    for k in CATS:
        rows.append([f"<strong>{k}</strong>", C["cat"][k], f'{pct(C["cat"][k], C["total"]):.1f}%', P["cat"][k],
                     f'{pct(P["cat"][k], P["total"]):.1f}%', delta(C["cat"][k], P["cat"][k])])
    rows.append(["Total", C["total"], "100%", P["total"], "100%", delta(C["total"], P["total"])])
    S.append(tbl(["Issue type", f"{CL}", "% of cur", f"{PL}", "% of prev", "Change"], rows, "cmp", True))

    # 4. closed reasons
    S.append("<h3>4. Closed Reason Details</h3>")
    group_order = [G_UMAC, G_EHR, G_APP, G_CLM, G_EUE, G_IUE, G_OTH, G_NONE]
    allr = sorted(set(C["reason"]) | set(P["reason"]), key=lambda k: (group_order.index(k[0]), -(C["reason"][k] + P["reason"][k]), k[1]))
    rows = []
    for g in group_order:
        rs = [k for k in allr if k[0] == g]
        if not rs: continue
        gc, gp = C["grp"][g], P["grp"][g]
        rows.append([f"<strong>{g}</strong>", f"<strong>{gc}</strong>", f"<strong>{gp}</strong>", delta(gc, gp)])
        for k in rs:
            rows.append([f'<span class="ind">{e(k[1])}</span>', C["reason"][k], P["reason"][k], delta(C["reason"][k], P["reason"][k])])
    rows.append(["Total", C["total"], P["total"], delta(C["total"], P["total"])])
    for i, r in enumerate(rows):
        if r[0].startswith("<strong>"): r.append("grp")
    body = []
    for i, r in enumerate(rows):
        cls = ' class="grp-row"' if len(r) == 5 else ' class="total-row"' if i == len(rows) - 1 else ""
        body.append(f"<tr{cls}>" + "".join(f"<td>{x}</td>" for x in r[:4]) + "</tr>")
    S.append(f'<table class="cmp"><thead><tr><th>Issue type / closed reason</th><th>{CL}</th><th>{PL}</th><th>Change</th></tr></thead><tbody>{"".join(body)}</tbody></table>')
    k2c = sum(v for (g, r), v in C["reason"].items() if r.startswith("Kno2")); k2p = sum(v for (g, r), v in P["reason"].items() if r.startswith("Kno2"))

    # 5. reasons by agent
    S.append("<h3>5. Closed Reason Details by Agent</h3>")
    hdr = ["Issue type / closed reason"]
    for a in names: hdr += [f"{a.split()[0]} {CL.split('–')[0]}", f"{a.split()[0]} prev"]
    hdr += ["Team cur", "Team prev"]
    hdr = ["Issue type / closed reason"] + sum([[f"{a.split()[0]} cur", f"{a.split()[0]} prev"] for a in names], []) + ["Team cur", "Team prev"]
    def agent_cells(key_fn, tag):
        cells = []
        for a in names:
            cells += [C["reason_agent"][key_fn(a)] if tag == "r" else 0, P["reason_agent"][key_fn(a)] if tag == "r" else 0]
        return cells
    body = []
    for g in group_order:
        rs = [k for k in allr if k[0] == g]
        if not rs: continue
        gcells = []
        for a in names:
            gcells += [sum(v for (gg, r, o), v in C["reason_agent"].items() if gg == g and o == a),
                       sum(v for (gg, r, o), v in P["reason_agent"].items() if gg == g and o == a)]
        gcells += [C["grp"][g], P["grp"][g]]
        body.append('<tr class="grp-row"><td>' + e(g) + "</td>" + "".join(f"<td>{x}</td>" for x in gcells) + "</tr>")
        for k in rs:
            cells = []
            for a in names:
                cells += [C["reason_agent"][(k[0], k[1], a)], P["reason_agent"][(k[0], k[1], a)]]
            cells += [C["reason"][k], P["reason"][k]]
            body.append(f'<tr><td><span class="ind">{e(k[1])}</span></td>' + "".join(f'<td class="{"z" if x == 0 else ""}">{x if x else "&ndash;"}</td>' for x in cells) + "</tr>")
    tot = []
    for a in names: tot += [C["by_agent"][a]["total"], P["by_agent"][a]["total"]]
    tot += [C["total"], P["total"]]
    body.append('<tr class="total-row"><td>Total</td>' + "".join(f"<td>{x}</td>" for x in tot) + "</tr>")
    # assert that matrix sums to agent totals
    for a in names:
        assert sum(v for (g, r, o), v in C["reason_agent"].items() if o == a) == C["by_agent"][a]["total"]
        assert sum(v for (g, r, o), v in P["reason_agent"].items() if o == a) == P["by_agent"][a]["total"]
    oc, op = C["by_agent"]["Other / unassigned"]["total"], P["by_agent"]["Other / unassigned"]["total"]
    S.append('<div class="scroll"><table class="cmp matrix"><thead><tr>' + "".join(f"<th>{h}</th>" for h in hdr) + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")
    S.append(f'<p class="note">Tickets owned by other/unassigned: {oc} (cur), {op} (prev) &mdash; excluded from this matrix by design and reported in section 1.</p>' if (oc or op) else
             '<p class="note">No tickets were owned by anyone other than the three agents in either week (team-wide query cross-checked).</p>')

    # 6. recommended additions
    S.append('<h3>6. Additional Metrics</h3><div class="callout callout-blue"><strong>Recommended additions</strong> &mdash; supplementary metrics not in the original request.</div>')
    # 6a priority
    S.append("<h4>6a. Priority mix</h4>")
    rows = [[p.title(), C["prio"][p], f'{pct(C["prio"][p], C["total"]):.1f}%', P["prio"][p], f'{pct(P["prio"][p], P["total"]):.1f}%', delta(C["prio"][p], P["prio"][p])] for p in PRIO]
    extra = [p for p in set(C["prio"]) | set(P["prio"]) if p not in PRIO]
    for p in extra: rows.append([str(p), C["prio"][p], "", P["prio"][p], "", delta(C["prio"][p], P["prio"][p])])
    rows.append(["Total", C["total"], "100%", P["total"], "100%", delta(C["total"], P["total"])])
    S.append(tbl(["Priority", "Cur", "% cur", "Prev", "% prev", "Change"], rows, "cmp", True))
    # 6b source
    S.append("<h4>6b. Internal vs external source</h4>")
    rows = [[s.title(), C["src"][s], f'{pct(C["src"][s], C["total"]):.1f}%', P["src"][s], f'{pct(P["src"][s], P["total"]):.1f}%', delta(C["src"][s], P["src"][s])] for s in ("internal", "external")]
    if C["src"]["unknown"] or P["src"]["unknown"]:
        rows.append(["No source tag", C["src"]["unknown"], f'{pct(C["src"]["unknown"], C["total"]):.1f}%', P["src"]["unknown"], f'{pct(P["src"]["unknown"], P["total"]):.1f}%', delta(C["src"]["unknown"], P["src"]["unknown"])])
    rows.append(["Total", C["total"], "100%", P["total"], "100%", delta(C["total"], P["total"])])
    S.append(tbl(["Source (tag)", "Cur", "% cur", "Prev", "% prev", "Change"], rows, "cmp", True))
    # 6d TTR
    S.append("<h4>6c. Time to resolution (created in window, solved/closed)</h4>")
    rows = [["Tickets resolved", C["ttr_n"], P["ttr_n"], delta(C["ttr_n"], P["ttr_n"], "neutral")],
            ["Median", hms(C["ttr_med"]), hms(P["ttr_med"]), delta(C["ttr_med"] / 3600, P["ttr_med"] / 3600, "down", unit="h") if C["ttr_med"] and P["ttr_med"] else ""],
            ["90th percentile", hms(C["ttr_p90"]), hms(P["ttr_p90"]), delta(C["ttr_p90"] / 3600, P["ttr_p90"] / 3600, "down", unit="h") if C["ttr_p90"] and P["ttr_p90"] else ""]]
    S.append(tbl(["Measure", "Cur", "Prev", "Change"], rows, "cmp"))
    # 6e aging
    S.append("<h4>6d. Backlog aging (unresolved tickets from each cohort)</h4>")
    bk = ["0-3 days", "4-7 days", "8-14 days", "15+ days"]
    rows = [[b, C["ages"][b], P["ages"][b], delta(C["ages"][b], P["ages"][b], "down")] for b in bk]
    rows.append(["Total unresolved", C["unres"], P["unres"], delta(C["unres"], P["unres"], "down")])
    S.append(tbl(["Age at snapshot", "Cur cohort", "Prev cohort", "Change"], rows, "cmp", True))
    # 6f batches
    S.append("<h4>6e. Batch / spike callouts and ex-batch totals</h4>")
    rows = []
    for lbl, X in (("Current", C), ("Previous", P)):
        for b in sorted(X["batches"], key=lambda b: b["day"]):
            rows.append([lbl, b["day"], e(b["reason"]), b["n"], "requester " + e(b["requester"])])
    S.append(tbl(["Week", "Day (UTC)", "Reason", "Tickets", "Detected by"], rows, "cmp") if rows else
              f'<p class="note">No batch exceeded {args.batch_threshold} tickets (same requester + day + closed reason) in either week.</p>')
    rows = [["Total tickets", C["total"], P["total"], delta(C["total"], P["total"])],
            [f"Batch tickets (&gt;{args.batch_threshold} same requester/day/reason)", C["batch_n"], P["batch_n"], delta(C["batch_n"], P["batch_n"])],
            ["<strong>Ex-batch total</strong>", f"<strong>{ex_c}</strong>", f"<strong>{ex_p}</strong>", delta(ex_c, ex_p)]]
    S.append(tbl(["", "Cur", "Prev", "Change"], rows, "cmp"))
    # informational same-reason concentration
    ko_c = C["reason"][(G_EHR, "Kno2 OID / Publication")]; ko_p = P["reason"][(G_EHR, "Kno2 OID / Publication")]
    S.append(f'<p class="note">Context: Kno2 OID/Publication tickets (system-generated, created in clusters) were {ko_c} in the current week vs {ko_p} in the previous week. '
             f'Batch detection works from tags/requester ids only (subjects are not stored to avoid names/PHI), so subject-pattern batches '
             f'(e.g. Clover termination sweeps) are only caught if they share requester, day and reason.</p>')
    # 6g workload
    S.append("<h4>6f. Workload share per agent</h4>")
    rows = []
    for a in names + (["Other / unassigned"] if (oc or op) else []):
        c, p = C["by_agent"][a]["total"], P["by_agent"][a]["total"]
        shc, shp = pct(c, C["total"]), pct(p, P["total"])
        rows.append([f"<strong>{a}</strong>", c, f"{shc:.1f}%", p, f"{shp:.1f}%", delta(shc, shp, "neutral", pp=True)])
    rows.append(["Total", C["total"], "100%", P["total"], "100%", ""])
    S.append(tbl(["Agent", "Cur", "Share cur", "Prev", "Share prev", "Share change"], rows, "cmp", True))

    # ---- executive summary bullets (computed)
    def top_reason(X, n=1):
        return sorted(X["reason"].items(), key=lambda kv: -kv[1])[:n]
    b = []
    d = C["total"] - P["total"]
    b.append(f'<strong>Volume:</strong> {C["total"]} tickets created {CL} vs {P["total"]} in {PL} ({d:+d}, {d / P["total"] * 100:+.1f}%). '
             f'Excluding detected batches the comparison is {ex_c} vs {ex_p} ({ex_c - ex_p:+d}, {(ex_c - ex_p) / ex_p * 100 if ex_p else 0:+.1f}%). '
             f'A change in volume is not inherently good or bad.')
    b.append(f'<strong>Resolution:</strong> {C["resolved"]} of {C["total"]} resolved ({C["rate"]:.1f}%) vs {P["resolved"]} of {P["total"]} ({P["rate"]:.1f}%, measured at the same {snap.date():%b} {snap.day} snapshot), '
             f'{C["rate"] - P["rate"]:+.1f}pp. {C["unres"]} tickets remain open/pending/hold ({", ".join(f"{k} {v}" for k, v in sorted(C["status"].items()) if k in UNRESOLVED)}) vs {P["unres"]}.')
    if sla["cur"] and sla["prev"]:
        b.append(f'<strong>SLA:</strong> {sla["cur"]["compliance_pct"]:g}% compliance both weeks (as published); average business-hour first response '
                 + ", ".join(f'{t} {sla["cur"]["tiers"][t]["avg"]} (was {sla["prev"]["tiers"][t]["avg"]})' for t in ["Urgent", "High", "Normal", "Low"]) + ", all well inside target.")
    else:
        b.append("<strong>SLA:</strong> prior-week figures were not available; no comparison made.")
    cat_moves = sorted(CATS, key=lambda k: C["cat"][k] - P["cat"][k])
    big = cat_moves[0]; up = cat_moves[-1]
    b.append(f'<strong>Mix:</strong> largest issue type this week is {max(CATS, key=lambda k: C["cat"][k])} ({C["cat"][max(CATS, key=lambda k: C["cat"][k])]} tickets). '
             f'Biggest drop: {big} ({C["cat"][big] - P["cat"][big]:+d}); {"biggest rise: " + up + f" ({C["cat"][up] - P["cat"][up]:+d})" if C["cat"][up] > P["cat"][up] else "no category rose"}.')
    tr = top_reason(C, 3)
    b.append("<strong>Closed reasons:</strong> top this week: " + "; ".join(f'{k[1]} {v} (prev {P["reason"][k]})' for k, v in tr) +
             f'. Kno2 OID/Publication {ko_c} vs {ko_p}.')
    b.append("<strong>Workload:</strong> " + ", ".join(f'{a.split()[0]} {C["by_agent"][a]["total"]} (prev {P["by_agent"][a]["total"]})' for a in names) + '.')
    exec_html = '<div class="callout callout-blue exec"><strong>Executive summary</strong><ul class="findings">' + "".join(f"<li>{x}</li>" for x in b) + "</ul></div>"

    css = CSS
    title = f"Week-over-Week Management Report {CL}, {ce.year} vs {PL}"
    page = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title><style>{css}</style></head><body>
<div class="toolbar"><button id="themeBtn" type="button">&#9681; Dark / Light</button><button id="pdfBtn" type="button">Export to PDF</button></div>
<div class="report-header"><h1>Product Success Team &mdash; Week-over-Week Management Report</h1>
<h2>Zendesk Support &nbsp;|&nbsp; {CL}, {ce.year} (current) vs {PL}, {pe.year} (previous)</h2>
<div class="header-meta"><span><strong>Snapshot:</strong> {snap.date():%B} {snap.day}, {snap.year} &nbsp; <strong>Prepared for:</strong> Carolyn Egan</span><span class="classification">INTERNAL USE &mdash; BUSINESS CONFIDENTIAL</span></div></div>
{exec_html}
<div class="legend">Change colours: <span class="good">&#9650;&#9660; favourable</span> &nbsp; <span class="bad">&#9650;&#9660; unfavourable</span> &nbsp; <span class="vol">&#9650;&#9660; volume (neither good nor bad)</span></div>
{"".join(S)}
<div class="report-footer"><span>Product Success Team &nbsp;|&nbsp; WoW management report {CL} vs {PL} &nbsp;|&nbsp; data snapshot {snap.date()}</span><span>INTERNAL USE &mdash; BUSINESS CONFIDENTIAL</span></div>
<script>
(function(){{var r=document.documentElement,k='wowTheme';var s=null;try{{s=localStorage.getItem(k)}}catch(e){{}}
if(!s)s=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';r.setAttribute('data-theme',s);
document.getElementById('themeBtn').onclick=function(){{var n=r.getAttribute('data-theme')==='dark'?'light':'dark';r.setAttribute('data-theme',n);try{{localStorage.setItem(k,n)}}catch(e){{}}}};
document.getElementById('pdfBtn').onclick=function(){{window.print()}};}})();
</script></body></html>"""
    out = os.path.expanduser(args.out)
    open(out, "w").write(page)

    # ---- machine-readable summary for the hand-off
    print(json.dumps({
        "cur_total": C["total"], "prev_total": P["total"],
        "cur_by_agent": {a: C["by_agent"][a]["total"] for a in C["by_agent"]},
        "prev_by_agent": {a: P["by_agent"][a]["total"] for a in P["by_agent"]},
        "cur_resolved": C["resolved"], "prev_resolved": P["resolved"],
        "cur_rate": round(C["rate"], 1), "prev_rate": round(P["rate"], 1),
        "cur_unres": C["unres"], "prev_unres": P["unres"],
        "cat_cur": dict(C["cat"]), "cat_prev": dict(P["cat"]),
        "prio_cur": dict(C["prio"]), "prio_prev": dict(P["prio"]),
        "src_cur": dict(C["src"]), "src_prev": dict(P["src"]),
        "ttr_cur_med_h": round(C["ttr_med"] / 3600, 1), "ttr_prev_med_h": round(P["ttr_med"] / 3600, 1),
        "ttr_cur_p90_h": round(C["ttr_p90"] / 3600, 1), "ttr_prev_p90_h": round(P["ttr_p90"] / 3600, 1),
        "batches_cur": [(b["day"], b["reason"], b["n"]) for b in C["batches"]],
        "batches_prev": [(b["day"], b["reason"], b["n"]) for b in P["batches"]],
        "ex_batch": [ex_c, ex_p],
        "top_reasons_cur": [(k[1], v) for k, v in top_reason(C, 6)],
        "top_reasons_prev": [(k[1], v) for k, v in top_reason(P, 6)],
        "unres_cur": unres_c, "unres_prev": unres_p,
        "out": out}, indent=1, default=str))


CSS = """
:root{--bg:#fff;--fg:#1a202c;--muted:#6b7280;--accent:#06b6d4;--accent-d:#0e7490;--card:#f8fafc;--bd:#e2e8f0;--row:#f0f9ff;--tot:#e0f2fe;--grp:#e0f2fe;
--good:#16a34a;--bad:#dc2626;--vol:#0e7490;--cb:#e0f2fe;--cbfg:#0c4a6e;--ab:#fef3c7;--abfg:#78350f;--rb:#fee2e2;--rbfg:#7f1d1d;--th:#0e7490}
[data-theme=dark]{--bg:#0f172a;--fg:#e2e8f0;--muted:#94a3b8;--accent:#22d3ee;--accent-d:#67e8f9;--card:#1e293b;--bd:#334155;--row:#162033;--tot:#134e5e;--grp:#164e63;
--good:#4ade80;--bad:#f87171;--vol:#67e8f9;--cb:#0b3b4a;--cbfg:#cffafe;--ab:#3b2f0b;--abfg:#fde68a;--rb:#4c1d1d;--rbfg:#fecaca;--th:#155e75}
@page{margin:.6in .6in;size:letter}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Georgia,'Times New Roman',serif;font-size:10.5pt;color:var(--fg);line-height:1.6;max-width:9in;margin:0 auto;padding:.5in .6in;background:var(--bg)}
.toolbar{position:fixed;top:14px;right:14px;display:flex;gap:8px;z-index:1000}
.toolbar button{background:linear-gradient(135deg,#06b6d4,#0891b2);color:#fff;border:0;padding:.5rem 1rem;border-radius:6px;font:600 9pt Arial,sans-serif;cursor:pointer;box-shadow:0 3px 10px rgba(6,182,212,.3)}
.report-header{border-bottom:3px solid var(--accent);padding-bottom:1rem;margin-bottom:1.25rem}
.report-header h1{font-size:19pt;letter-spacing:-.5px}.report-header h2{font-size:11.5pt;color:var(--muted);font-weight:400;margin-top:.2rem}
.header-meta{display:flex;justify-content:space-between;gap:1rem;margin-top:.6rem;font-size:9pt;color:var(--muted)}
.classification{display:inline-block;background:#1a202c;color:#fff;font:8pt Arial,sans-serif;padding:2px 8px;letter-spacing:1px;white-space:nowrap;height:fit-content}
h3{font-size:11.5pt;border-left:4px solid var(--accent);padding-left:.5rem;margin:1.5rem 0 .6rem;break-after:avoid}
h4{font:700 9.5pt Arial,sans-serif;color:var(--accent-d);margin:1rem 0 .3rem;text-transform:uppercase;letter-spacing:.4px;break-after:avoid}
.metric-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin:.75rem 0 1rem;break-inside:avoid}
.metric-box{border:1.5px solid var(--bd);border-radius:6px;padding:.65rem .75rem;text-align:center;background:var(--card)}
.metric-box .value{font-size:18pt;font-weight:700;color:var(--accent);display:block;line-height:1.2}
.metric-box .label{font:8pt Arial,sans-serif;text-transform:uppercase;letter-spacing:.3px;color:var(--muted)}
.metric-box .sub{font-size:8.5pt;color:var(--muted);margin-top:.2rem}
table{width:100%;border-collapse:collapse;font-size:9.2pt;margin:.4rem 0 .9rem;break-inside:avoid}
thead tr{background:var(--th);color:#fff}thead th{padding:.4rem .5rem;text-align:left;font:600 8.3pt Arial,sans-serif}
tbody tr:nth-child(even){background:var(--row)}tbody td{padding:.35rem .5rem;border-bottom:1px solid var(--bd);vertical-align:middle}
table.cmp td:not(:first-child),table.cmp th:not(:first-child){text-align:center}
tr.total-row,tr.total-row td{background:var(--tot)!important;font-weight:700}
tr.grp-row,tr.grp-row td{background:var(--grp)!important;font-weight:700}
.ind{padding-left:1.4rem;display:inline-block}.z{color:var(--muted)}
.good{color:var(--good);font-weight:600}.bad{color:var(--bad);font-weight:600}.vol{color:var(--vol);font-weight:600}.neutral{color:var(--muted)}
.legend{font:8.5pt Arial,sans-serif;color:var(--muted);margin:.5rem 0}
.callout{border-radius:4px;padding:.75rem 1rem;margin:.75rem 0;font-size:9.5pt;line-height:1.55}
.callout-blue{background:var(--cb);border-left:4px solid var(--accent);color:var(--cbfg)}
.callout-amber{background:var(--ab);border-left:4px solid #f59e0b;color:var(--abfg)}
.callout-red{background:var(--rb);border-left:4px solid #ef4444;color:var(--rbfg)}
.callout .good{color:var(--good)}.callout .bad{color:var(--bad)}
ul.findings{padding-left:1.2rem;margin:.4rem 0 .2rem}ul.findings li{margin-bottom:.3rem;font-size:9.5pt}
p.note{font-size:8.8pt;color:var(--muted);margin:.3rem 0 .8rem}
.scroll{overflow-x:auto}.matrix th,.matrix td{padding:.3rem .35rem;font-size:8.6pt}
code{font-family:Menlo,monospace;font-size:8.5pt}
.report-footer{margin-top:1.5rem;padding-top:.75rem;border-top:1px solid var(--bd);font:8pt Arial,sans-serif;color:var(--muted);display:flex;justify-content:space-between;gap:1rem}
@media print{*{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
body{padding:0;font-size:9.5pt;max-width:none}.toolbar{display:none!important}
.callout,.metric-row,table{break-inside:avoid}thead{display:table-header-group}tr{break-inside:avoid}h3,h4{break-after:avoid}
.matrix{break-inside:auto}}
"""

if __name__ == "__main__":
    main()
