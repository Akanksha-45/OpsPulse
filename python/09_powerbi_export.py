import json
import numpy as np
import pandas as pd
from utils.config import DATA_PROCESSED, DATA_POWERBI, REPORT_DIR
from utils.db import export_powerbi

t = pd.read_csv(DATA_PROCESSED / "analysis_features.csv",
                parse_dates=["created_at", "resolved_at", "first_response_at"])
h = pd.read_csv(DATA_PROCESSED / "ticket_status_history.csv", parse_dates=["start_time", "end_time"])
cust = pd.read_csv(DATA_PROCESSED / "customers.csv")
agents = pd.read_csv(DATA_PROCESSED / "agents.csv")
a = t.merge(cust[["customer_id", "customer_value_kusd"]], on="customer_id", how="left")
a = a.merge(agents[["agent_id", "department", "team", "shift", "experience_level"]]
            .rename(columns={"department": "agent_dept"}), left_on="assigned_agent",
            right_on="agent_id", how="left")
a["agent_dept"] = a.agent_dept.fillna(a.department)

ticket_keys = ["ticket_id", "customer_id", "customer_segment", "region", "priority", "category",
               "status", "sla_hours", "response_sla_hours",
               "created_at", "resolved_at", "first_response_at",
               "resolution_time_hours", "wait_ratio",
               "sla_breach", "escalation_required", "reopened",
               "n_escalations", "assigned_agent", "agent_department", "team", "shift",
               "experience_level"]
a["agent_department"] = a.agent_dept
closed = a[a.status == "Closed"].copy()
closed["compliance"] = (closed.sla_breach == 0).astype(int)
export_powerbi(closed[ticket_keys + ["compliance"]], "tickets_resolved")

open_t = pd.read_csv(DATA_PROCESSED / "open_risk_table.csv")
export_powerbi(open_t, "tickets_open")

stage = h[h.duration_hours >= 0].groupby(["ticket_id", "status"]).agg(
    hours=("duration_hours", "sum"), n_entries=("duration_hours", "count")
).reset_index()
export_powerbi(stage, "stage_time_detail")

stage_pivot = stage.pivot_table(index="ticket_id", columns="status", values="hours",
                                aggfunc="sum", fill_value=0).reset_index()
export_powerbi(stage_pivot, "stage_time_ticket")

resolved = t[t.status == "Closed"]
daily = (resolved.groupby(resolved.created_at.dt.date).agg(
    created=("ticket_id", "count"),
    resolved=("ticket_id", lambda s: resolved.loc[s.index, "resolved_at"].notna().sum()),
    breached=("sla_breach", "sum"),
    median_res_h=("resolution_time_hours", "median"))
    .reset_index().rename(columns={"created_at": "date"}))
daily["compliance_pct"] = 100 * (1 - daily.breached / daily.resolved)
export_powerbi(daily, "daily_kpi")

monthly_kpi = resolved.groupby(resolved.created_at.dt.to_period("M")).agg(
    created=("ticket_id", "count"),
    complied=("sla_breach", lambda s: (s == 0).sum()),
    median_res_h=("resolution_time_hours", "median"),
    eso=("escalation_required", "mean"),
    rp=("reopened", "mean"),
).reset_index()
monthly_kpi["month"] = monthly_kpi.created_at.astype(str)
monthly_kpi["compliance_pct"] = 100 * monthly_kpi.complied / monthly_kpi.created
export_powerbi(monthly_kpi.drop(columns=["created_at"]), "monthly_kpi")

segment = resolved.groupby("customer_segment").agg(
    n=("ticket_id", "count"),
    median_res_h=("resolution_time_hours", "median"),
    compliance=("sla_breach", lambda s: 1 - s.mean()),
    value_kusd=("customer_value_kusd", "sum"),
).reset_index()
segment["compliance_pct"] = 100 * segment.compliance
export_powerbi(segment, "segment_kpi")

category = resolved.groupby(["category", "priority"]).agg(
    n=("ticket_id", "count"),
    median_res_h=("resolution_time_hours", "median"),
    compliance=("sla_breach", lambda s: 1 - s.mean()),
).reset_index()
category["compliance_pct"] = 100 * category.compliance
export_powerbi(category, "category_kpi")

team_kpi = (resolved.merge(agents[["agent_id", "team", "department"]]
                           .rename(columns={"department": "agent_dept"}),
                           left_on="assigned_agent", right_on="agent_id", how="left")
            .groupby(["team", "agent_dept"]).agg(
    n=("ticket_id", "count"),
    median_res_h=("resolution_time_hours", "median"),
    compliance=("sla_breach", lambda s: 1 - s.mean()),
).reset_index().rename(columns={"agent_dept": "department"}))
team_kpi["compliance_pct"] = 100 * team_kpi.compliance
export_powerbi(team_kpi, "team_kpi")

rc = json.loads((REPORT_DIR / "root_cause_report.json").read_text(encoding="utf-8"))
drivers = pd.DataFrame(rc["driver_lift"])[["driver", "lift"]].copy()
drivers["lift"] = drivers.lift.round(2)
export_powerbi(drivers, "driver_lifts")

ins = json.loads((REPORT_DIR / "business_insights.json").read_text(encoding="utf-8"))
scen = pd.DataFrame(ins["scenarios"])
export_powerbi(scen, "whatif_scenarios")

kpi = pd.DataFrame([{
    "kpi": "compliance_pct", "value": ins["compliance"]["overall_pct"],
    "open_tickets": ins["backlog"]["open_tickets"],
    "over_budget": ins["backlog"]["over_budget"],
    "bottleneck_share_pct": ins["bottleneck"]["share_of_cycle_pct"],
}])
export_powerbi(kpi, "kpi_summary")

print("Exported", len(list((DATA_POWERBI).glob("*.csv"))), "Power BI tables ->", DATA_POWERBI)