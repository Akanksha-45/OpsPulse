import json
import numpy as np
import pandas as pd
from difflib import SequenceMatcher
from utils.config import DATA_RAW, DATA_PROCESSED, REPORT_DIR, SEED

CANONICAL_CATEGORIES = ["Technical Issue", "Integration", "Data Correction", "Feature Request",
                        "Security Concern", "Account Setup", "Billing Dispute", "Access Management"]


def best_match(value):
    value = value.strip().lower().replace("_", " ")
    if not value:
        return None
    scores = [(SequenceMatcher(None, value, c.lower()).ratio(), c) for c in CANONICAL_CATEGORIES]
    score, match = max(scores)
    return match if score >= 0.6 else None


def load_tables():
    cards = ["tickets", "ticket_status_history", "agents", "customers", "escalations", "sla_rules"]
    return {c: pd.read_csv(DATA_RAW / f"{c}.csv") for c in cards}


def check_tickets(t):
    issues = {}
    issues["duplicate_ticket_ids"] = int(t.ticket_id.duplicated().sum())
    issues["exact_duplicate_rows"] = int(t.duplicated().sum())

    t["created_at"] = pd.to_datetime(t.created_at, errors="coerce")
    t["resolved_at"] = pd.to_datetime(t.resolved_at, errors="coerce", format="mixed")
    t["first_response_at"] = pd.to_datetime(t.first_response_at, errors="coerce", format="mixed")

    issues["missing_assigned_agent"] = int((t.assigned_agent.isna() | t.assigned_agent.isin(["", "UNKNOWN", "N/A"])).sum())
    issues["missing_channel"] = int(t.channel.isna().sum())
    issues["missing_customer"] = int(t.customer_id.isna().sum())

    invalid_ts = t.resolved_at.notna() & (t.resolved_at < t.created_at)
    issues["resolved_before_created"] = int(invalid_ts.sum())

    unknown_agent = t.assigned_agent.isin(["", "UNKNOWN", "N/A"]).sum()
    issues["unknown_agent_values"] = int(unknown_agent)

    return t, issues


def normalize_category(t):
    uniq = t.category.astype(str).str.strip().unique()
    mapping = {u: best_match(u) for u in uniq}
    t["category_raw"] = t.category
    t["category"] = t.category.astype(str).str.strip().map(mapping)
    t["category"] = t.category.where(t.category.notna(), "Uncategorized")
    return t


def check_history(h, tickets):
    h["start_time"] = pd.to_datetime(h.start_time, errors="coerce", format="mixed")
    h["end_time"] = pd.to_datetime(h.end_time, errors="coerce", format="mixed")
    issues = {}
    issues["negative_duration"] = int((h.duration_hours < 0).sum())
    issues["end_before_start"] = int((h.end_time < h.start_time).sum())
    bad_seq = 0
    sample = h.merge(tickets[["ticket_id", "created_at"]], on="ticket_id", how="left")
    swapped = h[h.status.isin(["Resolution", "Closed"])].copy()
    return h, issues


def outliers(df, col):
    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    iqr = q3 - q1
    upper = q3 + 3.0 * iqr
    return df[df[col] > upper], float(upper)


def main():
    tables = load_tables()
    t, t_issues = check_tickets(tables["tickets"].copy())
    h, h_issues = check_history(tables["ticket_status_history"].copy(), t)

    t["assigned_agent"] = t.assigned_agent.replace({"": pd.NA, "UNKNOWN": pd.NA, "N/A": pd.NA})
    t = normalize_category(t)
    t["channel"] = t.channel.fillna("Unknown")

    t_clean = t[(t.resolved_at.isna()) | (t.resolved_at >= t.created_at)].drop_duplicates("ticket_id")
    resolved = t_clean[t_clean.status == "Closed"]
    res_out, res_upper = outliers(resolved, "resolution_time_hours")
    t_issues["extreme_resolution_outliers"] = int(len(res_out))
    t_issues["resolution_upper_iqr_bound"] = round(float(res_upper), 1)

    h_clean = h[h.start_time.notna() & h.end_time.notna() & (h.end_time >= h.start_time)]
    h_clean = h_clean[h_clean.ticket_id.isin(t_clean.ticket_id)]

    staged, stage_upper = outliers(h_clean[h_clean.duration_hours > 0], "duration_hours")
    h_issues["extreme_stage_outliers"] = int(len(staged))

    cleaned = {
        "tickets": t_clean,
        "ticket_status_history": h_clean,
        "agents": tables["agents"],
        "customers": tables["customers"],
        "escalations": tables["escalations"],
        "sla_rules": tables["sla_rules"],
    }
    for name, df in cleaned.items():
        df.to_csv(DATA_PROCESSED / f"{name}.csv", index=False)

    report = {
        "summary": {
            "raw_tickets": int(len(t)),
            "cleaned_tickets": int(len(t_clean)),
            "raw_history_rows": int(len(h)),
            "cleaned_history_rows": int(len(h_clean)),
            "rows_rejected": int(len(t) - len(t_clean)),
        },
        "ticket_checks": t_issues,
        "history_checks": h_issues,
    }
    (REPORT_DIR / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("== Data Quality Report ==")
    for k, v in report["summary"].items():
        print(f"  {k}: {v:,}")
    print("  ticket checks:")
    for k, v in t_issues.items():
        print(f"    {k}: {v:,}")
    print("  history checks:")
    for k, v in h_issues.items():
        print(f"    {k}: {v:,}")


if __name__ == "__main__":
    main()