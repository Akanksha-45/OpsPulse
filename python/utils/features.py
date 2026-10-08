import numpy as np
import pandas as pd
from utils.config import DATA_PROCESSED

SNAPSHOT = pd.Timestamp("2026-09-18 17:00:00")


def load_clean():
    t = pd.read_csv(DATA_PROCESSED / "tickets.csv",
                    parse_dates=["created_at", "resolved_at", "first_response_at"])
    h = pd.read_csv(DATA_PROCESSED / "ticket_status_history.csv",
                    parse_dates=["start_time", "end_time"])
    a = pd.read_csv(DATA_PROCESSED / "agents.csv")
    c = pd.read_csv(DATA_PROCESSED / "customers.csv")
    e = pd.read_csv(DATA_PROCESSED / "escalations.csv")
    return t, h, a, c, e


def agent_concurrent_load(t):
    """Concurrent workload metric: how many tickets the assigned agent had open
    at the moment this ticket was created."""
    load = np.zeros(len(t), dtype=int)
    for agent_id, grp in t[t.assigned_agent.notna()].groupby("assigned_agent"):
        srt = grp.sort_values("created_at")
        created = srt.created_at.to_numpy()
        resolved = srt.resolved_at.fillna(SNAPSHOT).to_numpy()
        query = srt.created_at.to_numpy()
        c_idx = np.searchsorted(created, query, side="right")
        r_idx = np.searchsorted(resolved, query, side="left")
        load[srt.index] = c_idx - r_idx
    return pd.Series(load, index=t.index, name="agent_load")


def build_analysis_frame():
    t, h, a, c, e = load_clean()
    t = t.copy()
    t["agent_load"] = agent_concurrent_load(t)
    t["time_of_day"] = t.created_at.dt.hour
    t["day_of_week"] = t.created_at.dt.dayofweek
    t["is_weekend"] = t.day_of_week >= 5
    t["is_night"] = (t.time_of_day < 6) | (t.time_of_day >= 22)
    t["current_wait_hours"] = (SNAPSHOT - t.created_at).dt.total_seconds() / 3600
    t["n_escalations"] = t.ticket_id.map(e.groupby("ticket_id").escalation_id.count()).fillna(0)

    h = h[h.duration_hours >= 0]
    inv = h[h.status == "Investigation"].groupby("ticket_id").duration_hours.sum()
    handoff_spans = h[h.status == "First Response"].groupby("ticket_id").duration_hours.sum()
    t["investigation_hours"] = t.ticket_id.map(inv)
    t["handoff_hours"] = t.ticket_id.map(handoff_spans)

    t = t.merge(c, on="customer_id", how="left")
    a = a.rename(columns={"department": "department_x", "team": "agent_team",
                          "experience_level": "agent_experience", "shift": "agent_shift",
                          "location": "agent_location"})
    t = t.merge(a, left_on="assigned_agent", right_on="agent_id", how="left")

    onehot_cols = ["priority", "category", "department", "channel", "customer_segment", "agent_shift"]
    for col in onehot_cols:
        dummies = pd.get_dummies(t[col], prefix=col, dtype=int)
        t = pd.concat([t, dummies], axis=1)

    t["wait_ratio"] = t.current_wait_hours / t.sla_hours
    t["cat_load"] = t.groupby("category").agent_load.transform("mean")
    return t


def save_analysis(df):
    out = DATA_PROCESSED / "analysis_features.csv"
    df.to_csv(out, index=False)
    return out