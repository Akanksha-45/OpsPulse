import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from utils.config import DATA_PROCESSED, REPORT_DIR
from utils.viz import save

t = pd.read_csv(DATA_PROCESSED / "tickets.csv", parse_dates=["created_at", "resolved_at"])
h = pd.read_csv(DATA_PROCESSED / "ticket_status_history.csv")
a = pd.read_csv(DATA_PROCESSED / "agents.csv")

a_map = a[["agent_id", "department", "team", "shift", "experience_level"]].rename(
    columns={"department": "dept", "team": "team_nm", "shift": "agent_shift",
             "experience_level": "agent_exp"})
team = t.merge(a_map, left_on="assigned_agent", right_on="agent_id", how="left")
team = team[team.assigned_agent.notna()]
team["department"] = team.dept.fillna(team.department)

perf = team.groupby(["department", "team_nm"]).agg(
    agents=("agent_id", "nunique"),
    tickets=("ticket_id", "count"),
    open_now=("ticket_id", lambda s: (team.loc[s.index, "status"] == "Open").sum()),
    median_res=("resolution_time_hours", lambda v: v.median()),
    sla_ok=("sla_breach", lambda s: (team.loc[s.index, "status"] == "Closed").sum() - s.sum()),
    escalated=("escalation_required", "sum"),
    reopened=("reopened", "sum"),
).reset_index()
perf["tickets_per_agent"] = perf.tickets / perf.agents
perf["compl_pct"] = 100 * perf.sla_ok / perf.tickets
perf["escalation_pct"] = 100 * perf.escalated / perf.tickets
perf["reopen_pct"] = 100 * perf.reopened / perf.tickets
perf = perf.rename(columns={"team_nm": "team"})
print("== Team performance ==")
print(perf[["department", "team", "agents", "tickets", "tickets_per_agent", "open_now",
            "median_res", "compl_pct", "escalation_pct", "reopen_pct"]].round(1).to_string(index=False))

agent_level = team.groupby("assigned_agent").agg(
    department=("department", "first"), shift=("agent_shift", "first"), exp=("agent_exp", "first"),
    tickets=("ticket_id", "count"),
    open_now=("ticket_id", lambda s: (team.loc[s.index, "status"] == "Open").sum()),
    median_res=("resolution_time_hours", "median"),
).reset_index()
agent_level = agent_level.merge(a[["agent_id", "capacity_per_day"]], left_on="assigned_agent", right_on="agent_id")
agent_level["load_pct"] = 100 * agent_level.open_now / agent_level.capacity_per_day

def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1) @ x) / (n * x.sum())

g = gini(agent_level.tickets)
print(f"\n== Fairness (Gini on tickets per agent) ==")
print(f"  Gini coefficient: {g:.3f}  (0 = perfectly even, 1 = fully concentrated)")
print(f"  Open-load Gini:  {gini(agent_level.open_now):.3f}")
print(f"  Median load%: {agent_level.load_pct.median():.1f}% | p90: {agent_level.load_pct.quantile(0.9):.1f}%")

print("\n== By shift ==")
shift = team[team.status == "Closed"].groupby("agent_shift").agg(
    n=("ticket_id", "count"),
    median_res=("resolution_time_hours", "median"),
    breach_pct=("sla_breach", "mean"),
).round(2)
shift["breach_pct"] = 100 * shift.breach_pct
print(shift.to_string())
print("\n== By experience ==")
exp = team[team.status == "Closed"].groupby("agent_exp").agg(
    n=("ticket_id", "count"),
    median_res=("resolution_time_hours", "median"),
    breach_pct=("sla_breach", "mean"),
).round(2)
exp["breach_pct"] = 100 * exp.breach_pct
print(exp.to_string())

fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
sc = axes[0].scatter(agent_level.median_res, agent_level.load_pct, s=agent_level.tickets * 1.6,
                     c=agent_level.tickets, cmap="viridis", alpha=0.85, edgecolors="white")
axes[0].set_xlabel("Median resolution time (h)"); axes[0].set_ylabel("Load (%)")
axes[0].set_title("Agent load vs resolution speed (bubble = tickets)")
fig.colorbar(sc, ax=axes[0], label="tickets")
r = np.corrcoef(agent_level.median_res, agent_level.load_pct)[0, 1]
axes[0].text(0.05, 0.9, f"r = {r:.2f}", transform=axes[0].transAxes)

shifted = team[team.status == "Closed"].copy()
s_med = shifted.groupby("agent_shift").resolution_time_hours.median().sort_values()
axes[1].bar(s_med.index, s_med.values, color="#7950f2")
axes[1].set_title("Median resolution by shift"); axes[1].set_ylabel("hours")

imp = shifted.groupby("agent_exp").resolution_time_hours.median().sort_values()
axes[2].bar(imp.index, imp.values, color="#0ca678")
axes[2].set_title("Median resolution by experience"); axes[2].set_ylabel("hours")
save(fig, "07_workforce_analytics.png")

report = {"team_performance": perf.to_dict("records"),
          "gini_tickets_per_agent": g, "gini_open": gini(agent_level.open_now),
          "agent_load": agent_level.round(2).to_dict("records"),
          "by_shift": shift.to_dict(), "by_experience": exp.to_dict(),
          "corr_load_resolution": round(float(r), 3)}
(REPORT_DIR / "workforce_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nSaved report/workforce_report.json")