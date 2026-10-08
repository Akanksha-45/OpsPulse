# Data Dictionary — OpsPulse

All cleaned data is published to `data/processed/`; raw simulations to `data/raw/`.
The mart lives in PostgreSQL (`opspulse` database).

## Core columns (tickets / analysis_features)

| Column | Type | Description |
|---|---|---|
| `ticket_id` | string | Unique ticket id (T######). |
| `customer_id` | string | Customer reference (C#####). |
| `customer_segment`, `region` | categorical | SMB / Mid-Market / Enterprise / Strategic; region of the account. |
| `customer_value_kusd` | float | Contract value in kUSD (risk x value prioritisation). |
| `priority` | P1..P4 | Severity; P1 breaches ~92% of the time (by design). |
| `category` | categorical | 8 categories (Technical Issue, Access Management, Integration, etc.). |
| `department` | categorical | Owning department. |
| `assigned_agent` | string | Agent id (A###). |
| `status` | Open / Closed / Cancelled | Lifecycle state at snapshot. |
| `created_at`, `resolved_at`, `first_response_at` | datetime | Key lifecycle timestamps. |
| `sla_hours` | float | Total resolution SLA budget (hours). |
| `response_sla_hours` | float | Time-to-first-response budget (hours). |
| `resolution_time_hours` | float | Actual end-to-end resolution (hours). |
| `sla_breach` | 0/1 | SLA compliance outcome for closed tickets. |
| `escalation_required`, `n_escalations` | bool/int | Escalation flags. |
| `reopened` | bool | Ticket was reopened after closure. |
| `wait_ratio` | float | Elapsed / SLA budget (1 = at budget), used by the priority engine. |
| `elapsed_hours`, `remaining_hours` | float | Snapshot-relative for open tickets. |
| `agent_concurrent_load` | int | Tickets this agent held concurrently at the ticket's created time. |
| `breach_risk` / `effective_risk` | float 0..1 | Model probability / blended risk x value score (06). |
| `op_priority` | OVER-BUDGET / CRITICAL / HIGH / MEDIUM / LOW | Triage bucket for open queue. |

## Stage history (`ticket_status_history`)
Rows are `(ticket_id, status, start_time, end_time, duration_hours)`. Stage names:
`Created` (queue), `Assigned`, `Investigation`, `Resolution`, `Escalated` (on escalated
tickets), `Reopened` (on reopen attempts), `Closed`.

## Reference tables
`agents.csv` — agent_id, department, team, experience_level, shift, location, capacity_per_day.
`customers.csv` — customer_id, customer_segment, region, customer_value_kusd.
`sla_rules.csv`, `escalations.csv` — support tables used by the simulator / mart.

## Warehouse (PostgreSQL)
- `staging_*` — raw, unconstrained.
- `public.tickets / agents / customers / sla_rules / ticket_status_history / escalations` — mart
  with FK constraints and cleaned types.
- `data_quality_audit` — every detected defect (rule → count), e.g.
  duplicate_ticket (251), resolved_at_before_created_at (252), missing_channel (631),
  category_standardized (530), orphan_stage_row (1,637).

## Power BI exports (`data/powerbi/`)
`tickets_resolved`, `tickets_open`, `stage_time_detail`, `stage_time_ticket`, `daily_kpi`,
`monthly_kpi`, `segment_kpi`, `category_kpi`, `team_kpi`, `driver_lifts`, `whatif_scenarios`,
`kpi_summary` — flat, relationship-ready tables (see `docs/powerbi_guide.md`).