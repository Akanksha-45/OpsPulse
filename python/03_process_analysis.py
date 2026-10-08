import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu
from utils.config import DATA_PROCESSED, REPORT_DIR
from utils.viz import save

t, h, a, c, e = (
    pd.read_csv(DATA_PROCESSED / "tickets.csv", parse_dates=["created_at", "resolved_at"]),
    pd.read_csv(DATA_PROCESSED / "ticket_status_history.csv", parse_dates=["start_time", "end_time"]),
    pd.read_csv(DATA_PROCESSED / "agents.csv"),
    pd.read_csv(DATA_PROCESSED / "customers.csv"),
    pd.read_csv(DATA_PROCESSED / "escalations.csv"),
)

resolved_ids = set(t[t.status == "Closed"].ticket_id)
h = h[h.duration_hours >= 0]
hist = h[h.ticket_id.isin(resolved_ids)].copy()

cycle = hist.groupby("ticket_id").duration_hours.sum().rename("cycle_hours")
hist = hist.merge(cycle, on="ticket_id")

stage_profile = hist.groupby("status").agg(
    n=("duration_hours", "count"),
    median_hours=("duration_hours", "median"),
    mean_hours=("duration_hours", "mean"),
    p95_hours=("duration_hours", lambda s: s.quantile(0.95)),
    total_hours=("duration_hours", "sum"),
).sort_values("total_hours", ascending=False)
stage_profile["share_of_cycle_pct"] = 100 * stage_profile.total_hours / stage_profile.total_hours.sum()
print("== Stage duration profile (resolved tickets) ==")
print(stage_profile[["n", "median_hours", "mean_hours", "p95_hours", "share_of_cycle_pct"]].round(2).to_string())

fig, ax = plt.subplots(figsize=(10, 4.5))
stages = stage_profile[~stage_profile.index.isin(["Reopened"])].sort_values("share_of_cycle_pct")
colors = ["#f76707" if s == "Investigation" else "#1f6feb" for s in stages.index]
ax.barh(stages.index, stages.share_of_cycle_pct, color=colors, alpha=0.9)
ax.set_xlabel("Share of total cycle time (%)")
ax.set_title("Where does ticket cycle time go? (bottleneck = Investigation)")
for i, v in enumerate(stages.share_of_cycle_pct):
    ax.text(v + 0.4, i, f"{v:.1f}%", va="center")
ax.set_xlim(0, stages.share_of_cycle_pct.max() * 1.15)
save(fig, "03_bottleneck_funnel.png")

inv = hist[hist.status == "Investigation"].groupby("ticket_id").duration_hours.sum().rename("investigation_hours").reset_index()
inv = inv.merge(t[["ticket_id", "category", "department", "priority"]], on="ticket_id")
inv = inv.merge(t[["ticket_id", "assigned_agent"]].merge(a[["agent_id", "shift"]], left_on="assigned_agent", right_on="agent_id", how="left"), on="ticket_id")
inv = inv.merge(t[["ticket_id", "customer_id"]].merge(c[["customer_id", "customer_segment"]], on="customer_id"), on="ticket_id")
inv = inv.merge(e.groupby("ticket_id").size().rename("n_esc").reset_index(), on="ticket_id", how="left")
inv["n_esc"] = inv.n_esc.fillna(0)

print("\n== Investigation breakdown ==")
print("by category (median hrs):")
print(inv.groupby("category").investigation_hours.median().sort_values(ascending=False).round(2).to_string())
print("by department (median hrs):")
print(inv.groupby("department").investigation_hours.median().sort_values(ascending=False).round(2).to_string())
print("by priority (median hrs):")
print(inv.groupby("priority").investigation_hours.median().sort_values(ascending=False).round(2).to_string())
print("by segment (median hrs):")
print(inv.groupby("customer_segment").investigation_hours.median().sort_values(ascending=False).round(2).to_string())

df = pd.read_csv(DATA_PROCESSED / "analysis_features.csv", parse_dates=["created_at"])
df_r = df[df.status == "Closed"].dropna(subset=["resolution_time_hours"]).copy()

q = df_r.resolution_time_hours.quantile
load_high = df_r.agent_load > df_r.agent_load.quantile(0.66)
load_low = df_r.agent_load <= df_r.agent_load.quantile(0.33)
u1, p1 = mannwhitneyu(df_r.resolution_time_hours[load_high], df_r.resolution_time_hours[load_low])
u2, p2 = mannwhitneyu(df_r.resolution_time_hours[df_r.n_escalations > 0], df_r.resolution_time_hours[df_r.n_escalations == 0])
u3, p3 = mannwhitneyu(df_r.resolution_time_hours[df_r.category == "Technical Issue"],
                      df_r.resolution_time_hours[df_r.category != "Technical Issue"])

tests = dict(
    load_high_vs_low=dict(
        high_median=round(df_r.resolution_time_hours[load_high].median(), 2),
        low_median=round(df_r.resolution_time_hours[load_low].median(), 2),
        mannwhitney_u=round(float(u1), 1), p_value=round(float(p1), 30)),
    escalated_vs_not=dict(
        esc_median=round(df_r.resolution_time_hours[df_r.n_escalations > 0].median(), 2),
        no_esc_median=round(df_r.resolution_time_hours[df_r.n_escalations == 0].median(), 2),
        mannwhitney_u=round(float(u2), 1), p_value=round(float(p2), 30)),
    technical_vs_others=dict(
        tech_median=round(df_r.resolution_time_hours[df_r.category == "Technical Issue"].median(), 2),
        other_median=round(df_r.resolution_time_hours[df_r.category != "Technical Issue"].median(), 2),
        mannwhitney_u=round(float(u3), 1), p_value=round(float(p3), 30)),
)
print("\n== Statistical group comparisons (Mann-Whitney U) ==")
for name, r in tests.items():
    print(f"  {name}: {r}")

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
b1 = df_r.assign(group=np.where(load_high, "High load", "Low load"))
b1.boxplot(column="resolution_time_hours", by="group", ax=axes[0], grid=False)
axes[0].set_yscale("log"); axes[0].set_title("Resolution time by agent load")
b2 = df_r.assign(group=np.where(df_r.n_escalations > 0, "Escalated", "Not escalated"))
b2.boxplot(column="resolution_time_hours", by="group", ax=axes[1], grid=False)
axes[1].set_yscale("log"); axes[1].set_title("Resolution time by escalation")
for ax in axes: ax.set_ylabel("hours (log)"); ax.set_xlabel("")
fig.suptitle("")
save(fig, "03_group_comparisons.png")

report = {"stage_profile": stage_profile.round(2).to_dict("index"),
          "investigation_breakdown": {
              "by_category": inv.groupby("category").investigation_hours.median().sort_values(ascending=False).round(2).to_dict(),
              "by_department": inv.groupby("department").investigation_hours.median().sort_values(ascending=False).round(2).to_dict(),
              "by_priority": inv.groupby("priority").investigation_hours.median().sort_values(ascending=False).round(2).to_dict()},
          "tests": tests}
(REPORT_DIR / "bottleneck_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nSaved report/bottleneck_report.json")