import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from utils.config import DATA_PROCESSED, REPORT_DIR
from utils.viz import save

df = pd.read_csv(DATA_PROCESSED / "analysis_features.csv",
                 parse_dates=["created_at", "resolved_at", "first_response_at"])
res = df[df.status == "Closed"].copy()

thresholds = res.resolution_time_hours.quantile([0.33, 0.66])
load_hi = float(res.agent_load.quantile(0.66))
res["load_group"] = np.where(res.agent_load > load_hi, "high",
                             np.where(res.agent_load <= res.agent_load.quantile(0.33), "low", "mid"))

drivers = pd.DataFrame({
    "escalated": res.n_escalations > 0,
    "reopened": res.reopened,
    "high_agent_load": res.agent_load > load_hi,
    "technical_category": res.category == "Technical Issue",
    "integration_category": res.category == "Integration",
    "p1_priority": res.priority == "P1",
    "p2_priority": res.priority == "P2",
    "strategic_account": res.customer_segment == "Strategic",
    "night_created": res.is_night,
    "weekend_created": res.is_weekend,
    "first_response_slow": ((res.first_response_at - res.created_at).dt.total_seconds() / 3600 > res.response_sla_hours),
}, index=res.index)

base_rate = res.sla_breach.mean()
rows = []
for col in drivers.columns:
    present = res.sla_breach[drivers[col]]
    absent = res.sla_breach[~drivers[col]]
    rows.append(dict(driver=col,
                     share_pct=round(100 * drivers[col].mean(), 1),
                     breach_when_present=round(100 * present.mean(), 1),
                     breach_when_absent=round(100 * absent.mean(), 1),
                     lift=round(100 * present.mean() / (100 * base_rate), 2)))
lift = pd.DataFrame(rows).sort_values("breach_when_present", ascending=False)
print("== Driver lift (resolved tickets) ==")
print(lift.to_string(index=False))

combo_rows = []
for c in combinations(drivers.columns, 2):
    mask = drivers[c[0]] & drivers[c[1]]
    if mask.sum() < 200:
        continue
    rate = res.sla_breach[mask].mean()
    combo_rows.append(dict(driver=f"{c[0]} & {c[1]}", n=int(mask.sum()),
                           breach_rate=round(100 * rate, 1), lift=round(100 * rate / (100 * base_rate), 2)))
combos = pd.DataFrame(combo_rows).sort_values("breach_rate", ascending=False).head(12)
print("\n== Top 2-way driver combos (lift) ==")
print(combos.to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
top = lift.head(10).sort_values("breach_when_present")
axes[0].barh(top.driver, top.breach_when_present, color="#e64980", alpha=0.9)
axes[0].axvline(100 * base_rate, color="#364fc7", ls="--", label=f"baseline {100*base_rate:.0f}%")
axes[0].set_xlabel("SLA breach rate when driver present (%)"); axes[0].set_title("Single-driver breach lift"); axes[0].legend()
axes[1].barh(combos.driver, combos.breach_rate, color="#f76707", alpha=0.9)
axes[1].axvline(100 * base_rate, color="#364fc7", ls="--", label=f"baseline {100*base_rate:.0f}%")
axes[1].set_xlabel("SLA breach rate when both drivers present (%)"); axes[1].set_title("Two-driver combinations")
axes[1].legend()
save(fig, "04_driver_lift.png")

num_cols = ["resolution_time_hours", "agent_load", "n_escalations", "sla_hours", "investigation_hours"]
fig, ax = plt.subplots(figsize=(7, 6))
corr = res[num_cols].corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="vlag", center=0, ax=ax, cbar_kws={"label": "Pearson r"})
ax.set_title("Correlation with resolution time")
save(fig, "04_correlation_heatmap.png")

report = {"baseline_breach_rate_pct": round(100 * base_rate, 1),
          "driver_lift": lift.to_dict("records"),
          "top_combos": combos.to_dict("records"),
          "correlation": res[num_cols].corr().round(3).to_dict()}
(REPORT_DIR / "root_cause_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nSaved report/root_cause_report.json")