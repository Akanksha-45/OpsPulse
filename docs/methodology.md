# Methodology — OpsPulse Bottleneck & SLA Intelligence Engine

## 1. Design philosophy
Observable ops data (ticket lifecycle, SLA outcomes, agent workloads) often hides the true
drivers of slow service. OpsPulse reverses that: we **engineer a known ground truth** into a
realistic dataset (with real data-quality defects), then build a full analytics/warehouse/ML
stack that must rediscover those facts — so every finding is verifiable, not anecdotal.

## 2. Data generation (00_generate_data.py)
- **Entity model**: 4,200 customers, 34 agents in 5 departments, 8 ticket categories,
  4 SLAs (L1/L2) priced in response + resolution hours.
- **Timeline simulation**: a continuous clock with Poisson inter-arrival (~4.6 min mean, 10%
  "skip" jumps to emulate bursts/unmonitored periods), ~12 months, ending at a fixed snapshot
  `2026-09-18T17:00:00`.
- **Engineered ground truth (deliberate, reproducible with seed 42)**:
  - *Investigation* is the primary bottleneck (largest stage duration share) and is driven hard
    by the Technical / Integration categories.
  - *Assigned → First Response* latency carries a secondary ~18% cycle share.
  - *Escalations / reopen attempts / strategic accounts / high concurrent load* inflate
    resolution; SLAs are tight for P1 and strategic clients, so those tickets breach most.
  - Calibration targets the realistic operating band: raw breach rate ≈ 23%, escalation ≈ 13%,
    reopen ≈ 8%.
- **Injected quality defects** so the ETL has real work: duplicate tickets, missing
  agent/channel, resolution before creation, negative stage durations, category typos.

## 3. Warehouse & ETL (00_build_database.py + sql/00_schema.sql)
- Raw CSVs loaded into `staging_*` tables (TEXT columns, no constraints).
- Staging → `public` mart: type coercion, FK constraints, `data_quality_audit` log table
  recording every rejected / repaired row per rule.
- All analytics reuse the mart, never the raw files.

## 4. Analysis modules
| Module | Purpose | Method |
|---|---|---|
| 01 | Data quality | rule checks → cleaned CSVs + audit JSON |
| 02 | EDA | KPIs + 5 diagnostic figures |
| 03 | Process analysis | stage-duration funnel, bottleneck decomposition, Mann–Whitney comparisons |
| 04 | Root cause | breach-rate lifts vs baseline per driver + 2-way combos + correlation heatmap |
| 05 | SLA prediction | Logistic Regression vs Random Forest, 80/20 split, ROC-AUC, feature importance |
| 06 | Priority engine | risk x value scoring for the open queue (`effective_risk` = 0.85·model + 0.15·urgency + value bonus), buckets OVER-BUDGET/CRITICAL/HIGH/MEDIUM/LOW |
| 07 | Workforce analytics | team performance, Gini workload-fairness index, shift/experience patterns |
| 08 | Business insights | what-if stage-reduction simulator + ranked recommendations |

## 5. What-if simulator (08)
For every resolved ticket we know per-stage hours (from the status history). A scenario applies a
multiplier to chosen stages, recomputes resolution time, and tallies tickets whose breach flag
flips from 1 → 0. This yields *analytical leverage estimates*: expected compliance gain,
percentage points, and recoverable ticket count. It is explicitly **not** a claim of achieved
improvements.

## 6. Model discipline
- Single 80/20 random split, seed fixed; evaluation on the held-out test set.
- Features: SLA-clock, priority, segment, category, agent-load (concurrent work at snapshot),
  first-response latency, escalation/reopen flags, derived ratios.
- **Honest framing**: reports use *association/driver* language, never causal claims; model
  scores are calibrated probabilities, not certainties.

## 7. Limitations
- Synthetic data: cross-checks are built-in but external validity is limited.
- Priority is a design input (P1 breach ≈ 91.7%) — treat as calibrated, not universal.
- What-if results scale linearly per ticket; queue-dynamics (agents serving 2 tickets
  simultaneously) are not modeled.
- Night-shift and experience-level deltas are small and should be treated as secondary.