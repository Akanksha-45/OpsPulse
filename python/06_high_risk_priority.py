import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from utils.config import DATA_PROCESSED, DATA_POWERBI, REPORT_DIR
from utils.features import SNAPSHOT
from utils.viz import save

df = pd.read_csv(DATA_PROCESSED / "analysis_features.csv", parse_dates=["created_at"])
open_t = df[df.status == "Open"].copy()
open_t["elapsed_hours"] = (SNAPSHOT - open_t.created_at).dt.total_seconds() / 3600
open_t["wait_ratio"] = open_t.elapsed_hours / open_t.sla_hours

model = joblib.load(DATA_PROCESSED / "model_rf.joblib")
meta = joblib.load(DATA_PROCESSED / "model_meta.joblib")
cols = pd.read_csv(DATA_PROCESSED / "model_columns.csv").columns.tolist()

X_open = open_t[meta["cat_cols"] + meta["num_cols"]]
y_pred = model.predict_proba(X_open)[:, 1]

urgency = open_t.wait_ratio.clip(0, 1)
value_bonus = np.select(
    [open_t.customer_value_kusd >= open_t.customer_value_kusd.quantile(0.90),
     open_t.customer_value_kusd >= open_t.customer_value_kusd.quantile(0.75)],
    [0.05, 0.025], default=0.0)

open_t["model_risk"] = y_pred
open_t["urgency"] = np.round(urgency, 3)
open_t["value_bonus"] = value_bonus
open_t["effective_risk"] = np.clip(0.85 * y_pred + 0.15 * urgency + value_bonus, 0, 1)
open_t["over_budget"] = open_t.wait_ratio >= 1.0

def bucket(r, over_budget, prio):
    if over_budget:
        return "OVER-BUDGET"
    if r >= 0.70:
        return "CRITICAL"
    if r >= 0.55:
        return "HIGH"
    if prio == "P1":
        return "HIGH"
    if r >= 0.35:
        return "MEDIUM"
    return "LOW"

open_t["op_priority"] = [bucket(r, ob, p) for r, ob, p
                         in zip(open_t.effective_risk, open_t.over_budget, open_t.priority)]

def recommend(row):
    if row.op_priority == "OVER-BUDGET":
        return "Already past SLA budget: escalate + root-cause; treat as CRITICAL action"
    if row.op_priority == "CRITICAL":
        return "Immediate escalation / assign senior agent, pause SLA clock where possible"
    if row.op_priority == "HIGH":
        return "Reassign to available senior capacity within next shift"
    if row.op_priority == "MEDIUM":
        return "Monitor; add to next-dispatch queue with updated ETA"
    return "Normal queue; revisit before 70% of SLA budget"

open_t["recommended_action"] = open_t.apply(recommend, axis=1)
open_t["remaining_hours"] = (open_t.sla_hours - open_t.elapsed_hours).round(1)

out_cols = ["ticket_id", "customer_id", "customer_segment", "customer_value_kusd",
            "priority", "category", "department", "assigned_agent",
            "created_at", "elapsed_hours", "sla_hours", "remaining_hours",
            "model_risk", "urgency", "effective_risk", "op_priority", "recommended_action"]
risk_table = open_t[out_cols].sort_values("effective_risk", ascending=False)

risk_table.to_csv(DATA_PROCESSED / "open_risk_table.csv", index=False)
risk_table.to_csv(DATA_POWERBI / "open_risk_table.csv", index=False)

print(f"Open tickets: {len(open_t):,}")
print("Priority distribution:")
order = ["OVER-BUDGET", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
print(open_t.op_priority.value_counts().reindex(order).to_string())
print("\nTop 15 recommended actions:")
print(risk_table.head(15).to_string(index=False))

by_dept = open_t.groupby("department").agg(
    open=("ticket_id", "count"),
    over_budget=("op_priority", lambda s: (s == "OVER-BUDGET").sum()),
    critical=("op_priority", lambda s: (s == "CRITICAL").sum()),
    high=("op_priority", lambda s: (s == "HIGH").sum()),
).round(0)
at_risk_value = open_t[open_t.op_priority.isin(["OVER-BUDGET", "CRITICAL", "HIGH"])].groupby("department").customer_value_kusd.sum()
by_dept["at_risk_value_kusd"] = at_risk_value.reindex(by_dept.index).fillna(0).round(0)
print("\nRisk concentration by department:")
print(by_dept.to_string())

cat_agg = open_t.groupby("category").apply(
    lambda d: pd.Series({"open": len(d), "over_budget": (d.op_priority == "OVER-BUDGET").sum(),
                         "critical": (d.op_priority == "CRITICAL").sum(),
                         "risk": d.effective_risk.mean()}), include_groups=False).round(3).sort_values("risk", ascending=False)
print("\nRisk by category:")
print(cat_agg.to_string())

fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
axes[0].hist(open_t.effective_risk, bins=30, color="#1f6feb")
axes[0].set_title("Effective risk score (open)"); axes[0].set_xlabel("risk")
axes[0].axvline(0.70, color="#e03131", ls="--", label="critical")
axes[0].legend()
order = ["OVER-BUDGET", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
vc = open_t.op_priority.value_counts().reindex(order)
axes[1].bar(order, vc.values, color=["#c92a2a", "#e03131", "#f76707", "#f5f065", "#adb5bd"])
axes[1].set_title("Open cases by priority"); axes[1].set_ylabel("count")
risk_table.head(200).plot(x="ticket_id", y="effective_risk", ax=axes[2], kind="line",
                          color="#0ca678", linewidth=1, legend=False)
axes[2].set_title("Top 200 open cases (desc)"); axes[2].set_xlabel("ticket (ranked)")
axes[2].tick_params(axis="x", labelbottom=False)
save(fig, "06_high_risk_priority.png")

report = {"open_tickets": len(open_t),
          "priority_counts": open_t.op_priority.value_counts().to_dict(),
          "risk_by_department": by_dept.round(2).to_dict(),
          "risk_by_category": cat_agg.to_dict()}
(REPORT_DIR / "priority_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nSaved open_risk_table + report/priority_report.json")