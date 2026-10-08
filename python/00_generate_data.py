import random
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from utils.config import DATA_RAW, SEED

rng = np.random.default_rng(SEED)

NOW = pd.Timestamp("2026-09-18 17:00:00")
N_TICKETS = 100_000
N_CUSTOMERS = 4_200
N_AGENTS = 34
BUSINESS_START = pd.Timestamp("2025-09-01 08:00:00")
STAGE_ORDER = ["Created", "Awaiting Assignment", "Assigned", "First Response",
               "Investigation", "Escalated", "Resolution", "Closed", "Reopened"]

CATEGORIES = {
    "Technical Issue": 1.45,
    "Integration": 1.28,
    "Data Correction": 1.12,
    "Feature Request": 1.08,
    "Security Concern": 1.20,
    "Account Setup": 0.98,
    "Billing Dispute": 0.78,
    "Access Management": 0.72,
}
PRIORITIES = {"P1": 0.50, "P2": 0.75, "P3": 1.00, "P4": 1.10}
PRIORITY_MIX = {"P1": 0.10, "P2": 0.20, "P3": 0.45, "P4": 0.25}
CHANNELS = {"Email": 0.40, "Portal": 0.30, "Phone": 0.18, "Chat": 0.12}
DEPARTMENTS = ["Support", "Technical", "Billing", "Account Management", "Product Ops"]
DEPARTMENT_WEIGHTS = [0.38, 0.26, 0.16, 0.12, 0.08]
CHANNEL_DEPT = {
    "Email": ["Support", "Technical", "Billing", "Account Management", "Product Ops"],
    "Portal": ["Support", "Technical", "Billing", "Account Management", "Product Ops"],
    "Phone": ["Support", "Technical", "Billing"],
    "Chat": ["Support", "Technical"],
}
SEGMENTS = {"Strategic": 0.08, "Enterprise": 0.22, "Mid-Market": 0.34, "SMB": 0.36}
REGIONS = ["North America", "EMEA", "LATAM", "APAC"]
SEGMENT_REGION_PREF = {
    "Strategic": [0.5, 0.3, 0.05, 0.15],
    "Enterprise": [0.45, 0.3, 0.08, 0.17],
    "Mid-Market": [0.4, 0.3, 0.12, 0.18],
    "SMB": [0.35, 0.3, 0.15, 0.2],
}
EXPERIENCE = ["Senior", "Mid", "Junior", "Lead"]
EXP_WEIGHTS = [0.30, 0.40, 0.20, 0.10]
SHIFTS = ["Morning", "Evening", "Night"]
SHIFT_WEIGHTS = [0.55, 0.30, 0.15]
LOCATIONS = ["US East", "US West", "EU West", "EU East", "APAC South", "APAC North"]
CAT_TO_DEPT = {
    "Technical Issue": "Technical", "Integration": "Technical",
    "Data Correction": "Support", "Feature Request": "Product Ops",
    "Security Concern": "Technical", "Account Setup": "Account Management",
    "Billing Dispute": "Billing", "Access Management": "Support",
}
SLA_BASE_HOURS = {"P1": 8, "P2": 16, "P3": 40, "P4": 96}
RESPONSE_SLA_HOURS = {"P1": 2, "P2": 3, "P3": 6, "P4": 12}
SEGMENT_SLA_FACTOR = {"Strategic": 0.68, "Enterprise": 0.82, "Mid-Market": 1.00, "SMB": 1.15}
ESCALATION_RATE = 0.13
ESCALATION_TYPES = ["Level 1", "Level 2", "Management", "VIP"]
ESCALATION_REASONS = ["Customer dissatisfaction", "Technical complexity", "SLA risk",
                      "VIP account priority", "Incomplete information", "Cross-functional impact"]
REOPEN_RATE = 0.08
REOPEN_REASONS = ["Issue not fully resolved", "Customer follow-up", "Regression detected",
                  "Partial fix applied"]
QUALITY_INJECTION = dict(
    duplicate_rows=0.004,
    missing_agent=0.012,
    missing_channel=0.010,
    invalid_timestamps=0.004,
    bad_sequence=0.010,
    category_typos=0.010,
    nonsense_outliers=0.002,
)


def lognormal(median, sigma, size):
    return rng.lognormal(np.log(median), sigma, size=size)


def poisson_pick(pairs, k=1):
    keys = [p[0] for p in pairs]
    weights = np.asarray([p[1] for p in pairs], dtype=float)
    weights = weights / weights.sum()
    out = rng.choice(keys, size=k, p=weights)
    return out[0] if k == 1 else out


def random_dt(start, end, rng_i):
    span = (end - start).total_seconds()
    return start + pd.to_timedelta(rng_i.integers(0, int(span)), unit="s")


DEPT_COUNTS = {"Support": 9, "Technical": 8, "Billing": 6, "Account Management": 6, "Product Ops": 5}


def make_agents():
    rows = []
    dept_i = 0
    for dept, count in DEPT_COUNTS.items():
        for _ in range(count):
            dept_i += 1
            if dept == "Product Ops":
                team = f"PO Squad {1 + (dept_i-1) % 3}"
            else:
                team = f"{dept} L1"
            rows.append(dict(
                agent_id=f"A{dept_i:03d}", department=dept, team=team,
                experience_level=poisson_pick(list(zip(EXPERIENCE, EXP_WEIGHTS))),
                shift=poisson_pick(list(zip(SHIFTS, SHIFT_WEIGHTS))),
                location=rng.choice(LOCATIONS),
                capacity_per_day=int(rng.integers(10, 26)),
            ))
    return pd.DataFrame(rows)


def make_customers():
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        seg = poisson_pick(list(zip(SEGMENTS.keys(), SEGMENTS.values())))
        region = rng.choice(REGIONS, p=SEGMENT_REGION_PREF[seg])
        base_value = {"Strategic": 400, "Enterprise": 160, "Mid-Market": 60, "SMB": 12}[seg]
        value = max(4.0, round(base_value * rng.lognormal(0, 0.45), 1))
        rows.append(dict(customer_id=f"C{i:05d}", customer_segment=seg,
                         region=region, customer_value_kusd=value))
    return pd.DataFrame(rows)


def make_sla_rules():
    rows = []
    for prio in PRIORITIES:
        for seg in SEGMENTS:
            rows.append(dict(priority=prio, customer_segment=seg,
                             sla_hours=round(SLA_BASE_HOURS[prio] * SEGMENT_SLA_FACTOR[seg], 2),
                             response_hours=round(RESPONSE_SLA_HOURS[prio] * SEGMENT_SLA_FACTOR[seg], 2)))
    return pd.DataFrame(rows)


def alloc_stage(dt):
    created_h = dt.hour + dt.minute / 60
    is_night = created_h < 6 or created_h >= 22
    is_weekend = dt.weekday() >= 5
    queue_wait = lognormal(0.80, 0.55, 1)[0] * (1.7 if is_weekend else 1.0) * (1.4 if is_night else 1.0)
    assign_ts = dt + timedelta(hours=queue_wait)
    reply = lognormal(2.50, 0.62, 1)[0]
    if is_night:
        reply *= 1.6
    if is_weekend:
        reply *= 1.3
    handoff = lognormal(0.40, 0.50, 1)[0]
    return dt, assign_ts, assign_ts + timedelta(hours=reply), handoff


def build_agents_index(agents):
    return {d: np.where(agents.department.values == d)[0].tolist()
            for d in agents.department.unique()}


def assign_agent(cat, by_dept, agent_dept0):
    dept = CAT_TO_DEPT[cat]
    pool = by_dept[dept] if len(by_dept[dept]) > 0 else by_dept[agent_dept0]
    return int(rng.choice(pool))


def generate():
    print("[1/6] Generating reference tables ...")
    agents = make_agents()
    customers = make_customers()
    sla_rules = make_sla_rules()
    agents.to_csv(DATA_RAW / "agents.csv", index=False)
    customers.to_csv(DATA_RAW / "customers.csv", index=False)
    sla_rules.to_csv(DATA_RAW / "sla_rules.csv", index=False)

    cust_seg = customers.customer_segment.tolist()
    cust_id = customers.customer_id.tolist()
    n_cust = len(cust_id)
    sla_lookup = {(r.priority, r.customer_segment): (r.sla_hours, r.response_hours)
                  for r in sla_rules.itertuples()}
    by_dept = build_agents_index(agents)
    agent_dept0 = agents.department.iloc[0]
    a_id = list(agents.agent_id)
    a_cap = list(agents.capacity_per_day)

    day = BUSINESS_START.to_pydatetime()
    now_ts = NOW.to_pydatetime()
    cap_ts = now_ts - timedelta(hours=12)
    idx = 0
    ticket_rows, history_rows, escalation_rows = [], [], []
    open_cnt = [0] * len(agents)

    print("[2/6] Simulating ticket lifecycle over ~380 days ...")
    day_ts = BUSINESS_START.to_pydatetime()
    while idx < N_TICKETS and day_ts < cap_ts:
        if rng.random() < 0.10:
            day_ts += timedelta(minutes=38)
            continue
        cat = poisson_pick(list(CATEGORIES.items()))
        prio = poisson_pick(list(PRIORITY_MIX.items()))
        ch = poisson_pick(list(CHANNELS.items()))
        dept = rng.choice(CHANNEL_DEPT[ch])
        ci = int(rng.integers(0, n_cust))
        seg = cust_seg[ci]
        ai = assign_agent(cat, by_dept, agent_dept0)
        sla_hours, resp_sla = sla_lookup[(prio, seg)]

        workload = open_cnt[ai] / max(a_cap[ai], 1)
        workload_mult = 1 + 0.55 * min(workload, 2.2)

        created, assign_ts, first_resp, handoff = alloc_stage(day_ts)

        prio_mult = PRIORITIES[prio]
        cat_mult = CATEGORIES[cat]
        inv1 = lognormal(8.0, 0.52, 1)[0] * cat_mult * prio_mult * workload_mult

        escalated = rng.random() < ESCALATION_RATE
        esc_type = esc_reason = esc_ts = None
        inv2 = None
        if escalated:
            esc_stage = lognormal(3.2, 0.45, 1)[0]
            esc_type = rng.choice(ESCALATION_TYPES)
            esc_reason = rng.choice(ESCALATION_REASONS)
            inv2 = inv1 * 0.62
        else:
            esc_stage = 0.0

        res_time = lognormal(1.55, 0.60, 1)[0] * cat_mult * 0.6
        close_time = lognormal(0.85, 0.60, 1)[0]

        stages = [
            ("Created", created, assign_ts),
            ("Assigned", assign_ts, first_resp),
            ("First Response", first_resp, first_resp + timedelta(hours=handoff)),
        ]
        inv_start = first_resp + timedelta(hours=handoff)
        if escalated:
            esc_ts = inv_start + timedelta(hours=inv1 * 0.35)
            esc_end = esc_ts + timedelta(hours=esc_stage)
            inv_end = esc_end + timedelta(hours=inv1 * 0.28 + inv2)
            stages += [
                ("Investigation", inv_start, esc_ts),
                ("Escalated", esc_ts, esc_end),
                ("Investigation", esc_end, inv_end),
            ]
        else:
            inv_end = inv_start + timedelta(hours=inv1)
            stages.append(("Investigation", inv_start, inv_end))

        res_end = inv_end + timedelta(minutes=1) + timedelta(hours=res_time)
        close_end = res_end + timedelta(hours=close_time)
        stages += [
            ("Resolution", res_end - timedelta(hours=res_time), res_end),
            ("Closed", res_end, close_end),
        ]

        reopen_gap = None
        if rng.random() < REOPEN_RATE:
            reopen_gap = lognormal(30.0, 0.7, 1)[0]
            reopen_ts = close_end + timedelta(hours=max(reopen_gap * 0.35, 0.5))
            re_res = close_end + timedelta(hours=max(reopen_gap, 1.0))
            stages += [
                ("Reopened", close_end, reopen_ts),
                ("Resolution", reopen_ts, re_res),
                ("Closed", re_res, re_res + timedelta(hours=close_time)),
            ]

        total_hours = sum((b - a).total_seconds() / 3600 for _, a, b in stages)
        age_hours = max(0.0, (now_ts - created).total_seconds() / 3600)
        if total_hours > age_hours - 1:
            resolved = False
        else:
            p_open = 0.50 * np.exp(-age_hours / 48.0) + 0.003
            resolved = rng.random() > p_open

        if resolved and reopen_gap is not None:
            resolved_at = stages[-1][2]
        elif resolved:
            resolved_at = close_end
        else:
            resolved_at = None

        if resolved:
            open_cnt[ai] = max(0, open_cnt[ai] - 1)
        else:
            open_cnt[ai] += 1

        status = "Closed" if resolved else "Open"

        if not resolved:
            stages = [(s, a, min(b, now_ts))
                      for s, a, b in stages if a < now_ts]
            if stages:
                s0, a0, b0 = stages[-1]
                stages[-1] = (s0, a0, now_ts)

        ticket_no = idx
        tid = f"T{ticket_no+1001:06d}"
        idx += 1

        res_h = (resolved_at - created).total_seconds() / 3600 if resolved else None
        ticket_rows.append([
            tid, cust_id[ci], created, prio, cat, ch, dept,
            a_id[ai], sla_hours, resp_sla,
            status, resolved_at, first_resp, bool(escalated), bool(reopen_gap is not None and resolved),
            res_h,
            bool(resolved and res_h > sla_hours),
        ])

        for s, a, b in stages:
            history_rows.append([tid, s, a, b,
                                 max(0.0, (b - a).total_seconds() / 3600)])

        if escalated:
            escalation_rows.append([f"E{idx:06d}", tid, esc_type, esc_ts, esc_reason])

        day_ts += timedelta(minutes=4.6)

    ticket_cols = ["ticket_id", "customer_id", "created_at", "priority", "category",
                   "channel", "department", "assigned_agent", "sla_hours",
                   "response_sla_hours", "status", "resolved_at", "first_response_at",
                   "escalation_required", "reopened", "resolution_time_hours", "sla_breach"]
    tickets = pd.DataFrame(ticket_rows, columns=ticket_cols)
    hist_cols = ["ticket_id", "status", "start_time", "end_time", "duration_hours"]
    history = pd.DataFrame(history_rows, columns=hist_cols)
    esc_cols = ["escalation_id", "ticket_id", "escalation_type", "escalated_at", "reason"]
    escalations = pd.DataFrame(escalation_rows, columns=esc_cols)
    return agents, customers, sla_rules, tickets, history, escalations


def inject_quality(agents, customers, sla_rules, tickets, history, escalations):
    r = rng
    tickets = tickets.copy()
    history = history.copy()

    n_drop_agent = int(len(tickets) * QUALITY_INJECTION["missing_agent"])
    agent_mask = r.choice(tickets.index, size=n_drop_agent, replace=False)
    tickets.loc[agent_mask, "assigned_agent"] = rng.choice(
        ["", "UNKNOWN", "A001"], size=n_drop_agent)

    n_miss_ch = int(len(tickets) * QUALITY_INJECTION["missing_channel"])
    ch_mask = r.choice(tickets.index, size=n_miss_ch, replace=False)
    tickets.loc[ch_mask, "channel"] = np.nan

    n_bad_ts = int(len(tickets) * QUALITY_INJECTION["invalid_timestamps"])
    for mid in r.choice(tickets.index, size=n_bad_ts, replace=False):
        if pd.notna(tickets.loc[mid, "resolved_at"]):
            tmp = tickets.loc[mid, "created_at"]
            tickets.loc[mid, "created_at"] = tickets.loc[mid, "resolved_at"] + pd.Timedelta(hours=r.integers(1, 40))
            tickets.loc[mid, "resolved_at"] = tmp

    n_bad_seq = int(len(tickets) * QUALITY_INJECTION["bad_sequence"])
    seq_rows = history[history.status.isin(["Resolution", "Closed"])]
    for hid in r.choice(seq_rows.index, size=n_bad_seq, replace=False):
        history.loc[hid, "duration_hours"] = -abs(history.loc[hid, "duration_hours"]) - r.integers(1, 10)

    n_typo = int(len(tickets) * QUALITY_INJECTION["category_typos"])
    for mid in r.choice(tickets.index, size=n_typo, replace=False):
        cat = tickets.loc[mid, "category"]
        tickets.loc[mid, "category"] = cat.lower().replace(" ", "_")

    n_dup = int(len(tickets) * QUALITY_INJECTION["duplicate_rows"])
    dup_idx = r.choice(tickets.index, size=n_dup, replace=False)
    dups = tickets.loc[dup_idx]
    tickets = pd.concat([tickets, dups], ignore_index=True)

    return tickets, history


def main():
    from utils.config import DATA_RAW
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    agents, customers, sla_rules, tickets, history, escalations = generate()
    rate = tickets.sla_breach.mean()
    print(f"  raw SLA breach rate = {rate:.3f} (target 0.18-0.24)")
    tickets, history = inject_quality(agents, customers, sla_rules, tickets, history, escalations)
    cards = ["tickets", "ticket_status_history", "agents", "customers", "escalations", "sla_rules"]
    data = [tickets, history, agents, customers, escalations, sla_rules]
    for name, df in zip(cards, data):
        df.to_csv(DATA_RAW / f"{name}.csv", index=False)
        print(f"  wrote data/raw/{name}.csv  ({len(df):,} rows)")
    print("Done.")


if __name__ == "__main__":
    main()