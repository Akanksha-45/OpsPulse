# Power BI Setup & Page Blueprint

Pre-baked flat tables are exported to `data/powerbi/*.csv` by
`python/09_powerbi_export.py` (see repo README for the full run order).

## 1. Import into Power BI Desktop

1. **Get data > Text/CSV** for the tables in `data/powerbi/`.
2. For each CSV click **Transform Data > Detect data type**:
   - `tickets_resolved.csv` — set `created_at`, `resolved_at`, `first_response_at` to `Date/DateTime`;
     set `sla_breach`, `compliance` to `Whole Number`; `sla_hours`, `resolution_time_hours`,
     `wait_ratio`, `customer_value_kusd` to `Decimal`.
   - `tickets_open.csv` — set `created_at`, `remaining_hours` etc. numerically; `effective_risk`,
     `model_risk`, `urgency` to Decimal.
   - `daily_kpi.csv` / `monthly_kpi.csv` — set date/month to Date; ratios to Decimal.
   - `whatif_scenarios.csv` — set `compliance_after`, `gain_pct_points` to Decimal.
3. Load all; build "New table" for a `Date` dimension:

```DAX
DimDate = CALENDAR(MIN('tickets_resolved'[created_at]), MAX('tickets_resolved'[created_at]))
```

4. **Model view** relations (many-to-one, both directions optional):
   - `tickets_resolved[customer_segment]` → dimensions are columns, so just build visuals
     directly; add these simple **measures** before building pages.

## 2. Measures (DAX)

Basic measures on the imported tables:

```DAX
Total Tickets      = COUNTROWS('tickets_resolved')
Compliance %       = DIVIDE(SUM('tickets_resolved'[compliance]), COUNTROWS('tickets_resolved'))
Breach %           = 1 - [Compliance %]
Median Res (h)     = MEDIAN('tickets_resolved'[resolution_time_hours])
Avg Res (h)        = AVERAGE('tickets_resolved'[resolution_time_hours])
Open Tickets       = COUNTROWS('tickets_open')
Over Budget Open   = CALCULATE(COUNTROWS('tickets_open'), 'tickets_open'[op_priority] = "OVER-BUDGET")
At-Risk Open       = CALCULATE(COUNTROWS('tickets_open'),
                     'tickets_open'[op_priority] IN {"OVER-BUDGET","CRITICAL","HIGH"})
Investigation hrs  = DIVIDE(SUM('stage_time_ticket'[Investigation]), COUNTROWS('tickets_resolved'))
Recoverable (S6)   = SUM('whatif_scenarios'[tickets_recovered])
```

If you prefer the star model, build `DimTicket` from unique `ticket_id` fields, `FactStage`
from `stage_time_detail`, and `FactResolved` from `tickets_resolved`.

## 3. Four-page blueprint

### Page 1 — Executive SLA & Bottleneck Overview
- Cards: `Total Tickets`, `Compliance %`, `Median Res (h)`, `Open Tickets`, `Over Budget Open`.
- Line chart `daily_kpi`: `date` x, `compliance_pct` y.
- Bar chart `monthly_kpi`: `created` count by month; line for `compliance_pct`.
- Donut `tickets_resolved[customer_segment]` by `Total Tickets`.
- Bar `tickets_resolved[category]` by `Average resolution (h)` with color by `sla_breach`.

### Page 2 — Open Risk & Priority Queue
- Table of `tickets_open`: Ticket, Customer, Priority, Category, SLA hours, `effective_risk`,
  `op_priority`, `recommended_action`. Sort by `effective_risk` desc.
- Slicer on `op_priority` (OVER-BUDGET / CRITICAL / HIGH / MEDIUM / LOW).
- Matrix `tickets_open` by `department` == rows, `op_priority` = columns, value `count`.
- Summarize: 76% of open queue already past SLA budget → chronic backlog vs fresh risk.
- Replace static `recommended_action` text with its own RAG column via a `SWITCH` measure if needed.

### Page 3 — Stage Time & Bottleneck
- Clustered bar `stage_time_ticket` median `Investigation` / `Assigned` / `Escalated` / `Resolution`
  by `category`.
- "Share of cycle time" stacked chart from `stage_time_ticket` totals → Investigation ≈ 46%.
- Scatter `stage_time_ticket`: average `Investigation` vs `resolution_time_hours` per category.

### Page 4 — Scenario & Workforce
- Cards: `Recoverable (S6)` recovered tickets; `Compliance After S6`.
- Bar `whatif_scenarios`: `scenario` x, `compliance_after` y; compare against baseline card.
- Table `driver_lifts` sorted by `lift` desc (P1 3.9x, Reopened 2.7x, ...).
- Line or histogram from `monthly_kpi` by `team_kpi` `compliance_pct` by `team`;
  scatter `team_kpi` `median_res_h` vs `n`.

## 4. Notes & story hooks
- All KPIs derive from the same cleaned dataset (62.5k tickets, compliance ~76.3%).
- Keep slicers few so the "executive" page stays one-glance.
- The recommended actions column is generated in Python (06) but reading it directly here is fine.