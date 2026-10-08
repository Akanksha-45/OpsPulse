import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from utils.config import DATA_PROCESSED
from utils.viz import save

t = pd.read_csv(DATA_PROCESSED / "tickets.csv", parse_dates=["created_at", "resolved_at", "first_response_at"])
h = pd.read_csv(DATA_PROCESSED / "ticket_status_history.csv", parse_dates=["start_time", "end_time"])
c = pd.read_csv(DATA_PROCESSED / "customers.csv")
e = pd.read_csv(DATA_PROCESSED / "escalations.csv")

resolved = t[t.status == "Closed"].copy()
print(f"tickets {len(t):,} | resolved {len(resolved):,} | open {len(t)-len(resolved):,}")

kpis = dict(
    total_tickets=len(t),
    open_backlog=len(t) - len(resolved),
    sla_compliance_pct=round(100 * (1 - resolved.sla_breach.mean()), 1),
    avg_resolution_hours=round(resolved.resolution_time_hours.mean(), 2),
    median_resolution_hours=round(resolved.resolution_time_hours.median(), 2),
    avg_first_response_hours=round(((t.first_response_at - t.created_at).dt.total_seconds() / 3600).mean(), 2),
    escalation_rate_pct=round(100 * len(e) / len(t), 1),
    reopen_rate_pct=round(100 * t.reopened.sum() / len(resolved), 1),
)
print("KPIs:", kpis)

res_clean = resolved[resolved.resolution_time_hours < 150]
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].hist(res_clean.resolution_time_hours, bins=60, color="#1f6feb", alpha=0.85)
ax[0].axvline(res_clean.resolution_time_hours.median(), color="#f76707", ls="--", label="median")
ax[0].set_xlabel("Resolution time (hours)"); ax[0].set_title("Resolution time distribution")
ax[0].legend()
ax[1].hist(np.log1p(res_clean.resolution_time_hours), bins=60, color="#0ca678", alpha=0.85)
ax[1].set_xlabel("log1p(resolution hours)"); ax[1].set_title("log scale (right-skew)")
save(fig, "02_resolution_distribution.png")

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
for ax, col in zip(axes.ravel(), ["priority", "category", "channel", "department"]):
    rate = resolved.groupby(col).sla_breach.mean().sort_values(ascending=False) * 100
    rate.plot(kind="bar", ax=ax, color="#f76707", alpha=0.9)
    ax.set_title(f"SLA breach rate by {col}"); ax.set_ylabel("% breached"); ax.tick_params(axis="x", rotation=45)
save(fig, "02_breach_by_dimension.png")

seg = resolved.merge(c[["customer_id", "customer_segment"]], on="customer_id")
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
seg.groupby("customer_segment").sla_breach.mean().sort_values(ascending=False).plot(kind="bar", ax=ax[0], color="#7950f2")
ax[0].set_title("Breach rate by customer segment"); ax[0].set_ylabel("% breached")
seg.groupby("customer_segment").resolution_time_hours.median().sort_values(ascending=False).plot(kind="bar", ax=ax[1], color="#0ca678")
ax[1].set_title("Median resolution by segment"); ax[1].set_ylabel("hours")
save(fig, "02_segment_analysis.png")

t["month"] = t.created_at.dt.to_period("M").astype(str)
trend = t.groupby("month").agg(vol=("ticket_id", "count"), open_n=("status", lambda s: (s == "Open").sum())).reset_index()
revealed = t[t.status == "Closed"].groupby("month").agg(
    vol=("ticket_id", "count"), breach_rate=("sla_breach", "mean")).reset_index()
fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
revealed.plot(x="month", y="vol", ax=ax[0], color="#1f6feb")
ax[0].set_title("Resolved ticket volume by month")
(revealed.breach_rate * 100).plot(ax=ax[1], color="#e64980", marker="o")
ax[1].set_title("SLA breach rate trend"); ax[1].set_ylabel("% breached"); ax[1].set_ylim(0, 60)
for a in ax: a.tick_params(axis="x", rotation=90)
save(fig, "02_monthly_trend.png")

resolved["month"] = resolved.created_at.dt.to_period("M").astype(str)
pivot = resolved.pivot_table(index="month", columns="priority", values="sla_breach", aggfunc="mean") * 100
fig, ax = plt.subplots(figsize=(11, 4))
pivot.plot(ax=ax, marker="o")
ax.set_title("SLA breach trend by priority"); ax.set_ylabel("% breached")
save(fig, "02_breach_trend_priority.png")

print("EDA figures saved.")