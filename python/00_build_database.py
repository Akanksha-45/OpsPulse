import io
from pathlib import Path
from utils.config import DATA_RAW
import utils.db as db

LOADERS = {
    "staging_customers": ("customers", ["customer_id", "customer_segment", "region", "customer_value_kusd"]),
    "staging_agents": ("agents", ["agent_id", "department", "team", "experience_level", "shift", "location", "capacity_per_day"]),
    "staging_tickets": ("tickets", ["ticket_id", "customer_id", "created_at", "priority", "category", "channel",
                                     "department", "assigned_agent", "sla_hours", "response_sla_hours", "status",
                                     "resolved_at", "first_response_at", "escalation_required", "reopened",
                                     "resolution_time_hours", "sla_breach"]),
    "staging_ticket_status_history": ("ticket_status_history", ["ticket_id", "status", "start_time", "end_time", "duration_hours"]),
    "staging_escalations": ("escalations", ["escalation_id", "ticket_id", "escalation_type", "escalated_at", "reason"]),
    "staging_sla_rules": ("sla_rules", ["priority", "customer_segment", "sla_hours", "response_hours"]),
}


def load_csv(cur, table, columns):
    csv = (DATA_RAW / f"{table}.csv").read_text(encoding="utf-8")
    cur.copy_expert(f"COPY staging_{table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV, HEADER true, NULL '')", io.StringIO(csv))


TRANSFORM = """
-- 1) Reference tables (already clean)
INSERT INTO customers (customer_id, customer_segment, region, customer_value_kusd)
SELECT customer_id, customer_segment, region, customer_value_kusd::numeric FROM staging_customers;

INSERT INTO agents (agent_id, department, team, experience_level, shift, location, capacity_per_day)
SELECT agent_id, department, team, experience_level, shift, location, capacity_per_day::int FROM staging_agents;

INSERT INTO sla_rules (priority, customer_segment, sla_hours, response_hours)
SELECT priority, customer_segment, sla_hours::numeric, response_hours::numeric FROM staging_sla_rules;

-- 2) Tickets -> mart  (standardize category, drop logically impossible rows)
WITH src AS (
    SELECT
        ticket_id,
        customer_id,
        created_at::timestamp AS created_at,
        priority,
        initcap(replace(lower(TRIM(category)), '_', ' ')) AS category,
        NULLIF(TRIM(channel), '') AS channel,
        department,
        NULLIF(NULLIF(TRIM(assigned_agent), 'UNKNOWN'), '') AS assigned_agent,
        sla_hours::numeric, response_sla_hours::numeric, status,
        NULLIF(TRIM(resolved_at), '') AS resolved_at,
        NULLIF(TRIM(first_response_at), '') AS first_response_at,
        (escalation_required = 'True' OR escalation_required = 'true' OR escalation_required = 't') AS escalation_required,
        (reopened = 'True' OR reopened = 'true' OR reopened = 't') AS reopened,
        NULLIF(TRIM(resolution_time_hours), '') AS resolution_time_hours,
        (sla_breach = 'True' OR sla_breach = 'true' OR sla_breach = 't') AS sla_breach
    FROM staging_tickets
),
bad_ts AS (
    SELECT ticket_id FROM src
    WHERE resolved_at IS NOT NULL AND resolved_at::timestamp < created_at
),
inserted AS (
    INSERT INTO tickets
        (ticket_id, customer_id, created_at, priority, category, channel, department,
         assigned_agent, sla_hours, response_sla_hours, status, resolved_at, first_response_at,
         escalation_required, reopened, resolution_time_hours, sla_breach)
    SELECT ticket_id, customer_id, created_at, priority, category, channel, department,
           assigned_agent, sla_hours, response_sla_hours, status,
           resolved_at::timestamp, first_response_at::timestamp,
           escalation_required, reopened,
           CASE WHEN status = 'Closed' THEN resolution_time_hours::numeric ELSE NULL END,
           sla_breach
    FROM src
    WHERE ticket_id NOT IN (SELECT ticket_id FROM bad_ts)
    ON CONFLICT (ticket_id) DO NOTHING
    RETURNING ticket_id
)
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'tickets', ticket_id, 'resolved_at_before_created_at',
       'Logically impossible timestamp: resolved_at < created_at. Row excluded from mart.'
FROM bad_ts;
"""

TRANSFORM_HIST = """
INSERT INTO ticket_status_history (ticket_id, status, start_time, end_time, duration_hours)
SELECT h.ticket_id, h.status, h.start_time::timestamp, h.end_time::timestamp,
       CASE WHEN h.duration_hours::numeric >= 0 AND h.start_time::timestamp <= h.end_time::timestamp
            THEN h.duration_hours::numeric ELSE NULL END
FROM staging_ticket_status_history h
JOIN tickets t ON t.ticket_id = h.ticket_id
ON CONFLICT (ticket_id, status, start_time) DO NOTHING;
"""

TRANSFORM_ESC = """
INSERT INTO escalations (escalation_id, ticket_id, escalation_type, escalated_at, reason)
SELECT e.escalation_id, e.ticket_id, e.escalation_type, e.escalated_at::timestamp, e.reason
FROM staging_escalations e
JOIN tickets t ON t.ticket_id = e.ticket_id;
"""

AUDIT_HIST = """
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'ticket_status_history', ticket_id || '/' || status || '/' || start_time, 'non_monotonic_duration',
       'Negative or backward-timed stage: duration < 0 or end_time < start_time. Duration set to NULL in mart.'
FROM staging_ticket_status_history
WHERE duration_hours::numeric < 0 OR start_time::timestamp > end_time::timestamp;
"""

AUDIT_ORPHAN = """
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'ticket_status_history', ticket_id, 'orphan_stage_row',
       'History row references a ticket excluded from the mart (dropped by quality rules).'
FROM staging_ticket_status_history h
WHERE NOT EXISTS (SELECT 1 FROM tickets t WHERE t.ticket_id = h.ticket_id);
"""

AUDIT_CHANNEL = """
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'tickets', ticket_id, 'missing_channel',
       'Channel missing. Loaded into mart as NULL (available for analysis with null-handling).'
FROM staging_tickets WHERE NULLIF(TRIM(channel),'') IS NULL;
"""

AUDIT_AGENT = """
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'tickets', ticket_id, 'missing_assigned_agent',
       'Assigned agent missing/unknown. Loaded into mart as NULL.'
FROM staging_tickets WHERE NULLIF(TRIM(assigned_agent),'') IS NULL
   OR assigned_agent NOT IN (SELECT agent_id FROM agents);
"""

AUDIT_CATEGORY = """
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'tickets', ticket_id, 'category_standardized', category FROM staging_tickets
WHERE lower(replace(lower(category),'_',' ')) <> lower(category);
"""

AUDIT_DUPES = """
INSERT INTO data_quality_audit (source_table, row_key, issue, detail)
SELECT 'tickets', ticket_id, 'duplicate_ticket',
       'Duplicate ticket_id detected (count > 1). Only first occurrence kept in mart.'
FROM staging_tickets GROUP BY ticket_id HAVING COUNT(*) > 1;
"""

def run_audits(cur):
    cur.execute(AUDIT_CHANNEL)
    cur.execute(AUDIT_AGENT)
    cur.execute(AUDIT_CATEGORY)
    cur.execute(AUDIT_DUPES)
    cur.execute(AUDIT_HIST)
    cur.execute(AUDIT_ORPHAN)


def main():
    conn = db.connect()
    conn.autocommit = False
    with conn.cursor() as cur:
        schema = (Path(__file__).resolve().parents[1] / "sql" / "00_schema.sql").read_text(encoding="utf-8")
        cur.execute(schema)
        for table, (csv_name, cols) in LOADERS.items():
            load_csv(cur, csv_name, cols)
        cur.execute(TRANSFORM)
        cur.execute(TRANSFORM_HIST)
        cur.execute(TRANSFORM_ESC)
        run_audits(cur)
    conn.commit()
    with conn.cursor() as cur:
        for table in ["customers", "agents", "tickets", "ticket_status_history", "escalations", "sla_rules"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  mart {table}: {cur.fetchone()[0]:,} rows")
        cur.execute("SELECT issue, COUNT(*) FROM data_quality_audit GROUP BY issue ORDER BY 2 DESC")
        print("\n  audit log (top issues):")
        for issue, n in cur.fetchall():
            print(f"    {issue}: {n:,}")
    conn.close()


if __name__ == "__main__":
    main()