# OpsPulse — Operational Bottleneck & SLA Intelligence Engine

End-to-end Operations Analytics project: from a simulated service-desk dataset (with
deliberately engineered bottlenecks and real data-quality defects) through a PostgreSQL
warehouse, statistical bottleneck/root-cause analysis, SLA-breach prediction, a live
risk×value priority engine, workforce fairness analytics, and a what-if scenario simulator —
finished with Power BI-ready exports and a documented methodology.

**TL;DR findings:** Investigation consumes ~46% of cycle time (the bottleneck);
reopened (2.7x), P1 (3.9x) and slow-first-response (2.1x) drive breaches; a Random Forest
predicts SLA breach at ROC-AUC ≈ 0.92; simulated stage reductions could lift compliance from
76.3% to ~81% and recover ~3k closed tickets.

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 00_generate_data.py   synthetic service-desk simulation (ground truth)      │
│        │ raw CSVs (tickets, status history, agents, customers, SLAs)        │
│        ▼                                                                    │
│ 00_build_database.py  staging_* → public mart + data_quality_audit (SQL)    │
│        │ sql/00_schema.sql                                                  │
│        ▼                                                                    │
│ 01_data_quality.py    cleaned CSVs ⇒ analysis_features.csv                  │
│        │                                                                    │
│        ├─▶ 02 EDA (figures)        05 SLA prediction (LR/RF, ROC 0.92)     │
│        ├─▶ 03 bottleneck/funnel    06 priority triage (risk×value)         │
│        ├─▶ 04 root-cause + drivers 07 workforce analytics (Gini)           │
│        └─▶ 08 what-if scenarios + recommendations                          │
│        └─▶ 09 Power BI export (13 tables)                                  │
└────────────────────────────────────────────────────────────────────────────┘
```

## Repo layout
```
OpsPulse/
├─ data/            raw/        raw simulations
│                   processed/  cleaned CSVs, analysis features, models
│                   powerbi/    Power BI-facing tables
├─ python/          00_…09_*.py analysis modules + utils/ (config, db, viz, features)
├─ sql/             warehouse schema + KPI/bottleneck/SLA/workforce queries
├─ report/          JSON snapshots per module + figures/*.png
└─ docs/            methodology · data dictionary · findings · Power BI guide
```

## How to run
Requires Python 3.10+ (pandas, numpy, scikit-learn, scipy, matplotlib, seaborn,
psycopg2-binary) and a local PostgreSQL with a database `opspulse` (connect params in
`python/utils/config.py`; `db.py` auto-creates the database if missing).

```bash
cd OpsPulse/python
python 00_generate_data.py      # step 1  (simulate)
python 00_build_database.py     # step 2  (staging → mart, audit log)
python 01_data_quality.py       # step 3  (cleaned CSVs)
python 02_eda.py                # step 4
python 03_process_analysis.py   # step 5  bottleneck
python 04_root_cause_analysis.py# step 6
python 05_sla_prediction.py     # step 7  models + artefacts
python 06_high_risk_priority.py # step 8  open-queue triage
python 07_workforce_analytics.py# step 9
python 08_business_insights.py  # step 10 what-if + recommendations
python 09_powerbi_export.py     # step 11 Power BI tables
```

Every step is deterministic (seed 42) and writes JSON + PNG artefacts into `report/` so the
whole pipeline is reproducible end-to-end (~30s/core step on a laptop).

## Notebook mapping (.ipynb)
`nbconvert` is not installed in this environment, so equivalent deliverable logic ships as
`.py` modules. Mapping to the originally planned notebooks:

| Planned notebook | Delivered as |
|---|---|
| 00_Data_Generation | `00_generate_data.py`, `00_build_database.py` |
| 01_Data_Quality | `01_data_quality.py` |
| 02_EDA | `02_eda.py` |
| 03_Process_Analysis | `03_process_analysis.py` |
| 04_Root_Cause | `04_root_cause_analysis.py` |
| 05_SLA_Prediction | `05_sla_prediction.py` |
| 06_Priority | `06_high_risk_priority.py` |
| 07_Workforce | `07_workforce_analytics.py` |
| 08_Business_Insights | `08_business_insights.py` |

## SQL layer
In addition to the Python ETL, `sql/` contains the mart build (`00_schema.sql`) and analysis
queries (`02_kpi_analysis.sql` … `05_workforce_analysis.sql`) that mirror the Python analysis —
demonstrating both direct SQL analytics and a Python ML path on the same warehouse.

## Power BI
`data/powerbi/` holds 13 flat, relationship-ready tables; `docs/powerbi_guide.md` gives the
DAX measures and a four-page blueprint (Executive SLA & Bottleneck, Open Risk & Priority
Queue, Stage Time/Funnel, Scenarios & Workforce).

## Docs
- `docs/methodology.md` — generation design, warehouse, ML and what-if methodology, limitations.
- `docs/data_dictionary.md` — schema and column reference.
- `docs/business_findings.md` — headlined findings, driver lifts, scenario table, actions.
- `docs/powerbi_guide.md` — import, measures, page blueprint.

## Tech stack
Python 3.10 (pandas, scikit-learn, scipy, matplotlib, seaborn, psycopg2), PostgreSQL 17,
Power BI Desktop. No cloud services required.