-- OpsPulse - KPI & trend analysis
-- Snapshot time: the dataset's "as-of" moment. Replace with CURRENT_TIMESTAMP for live data.
WITH snap AS (SELECT '2026-09-18 17:00:00'::timestamp AS ts)

-- ============ 1. Control tower KPIs ============
SELECT
    COUNT(*)                                                        AS total_tickets,
    COUNT(*) FILTER (WHERE status = 'Open')                         AS open_backlog,
    COUNT(*) FILTER (WHERE status = 'Closed')                       AS resolved_tickets,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Closed' AND NOT sla_breach)
          / NULLIF(COUNT(*) FILTER (WHERE status = 'Closed'), 0), 1) AS sla_compliance_pct,
    ROUND(AVG(resolution_time_hours) FILTER (WHERE status = 'Closed'), 2)  AS avg_res_time_hours,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY resolution_time_hours)
           FILTER (WHERE status = 'Closed'))::numeric, 2)                    AS median_res_time_hours,
    ROUND(AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 3600)
          FILTER (WHERE first_response_at IS NOT NULL), 2)                AS avg_first_response_hours,
    ROUND(100.0 * (SELECT COUNT(*) FROM escalations) / NULLIF(COUNT(*), 0), 1) AS escalation_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE reopened) / NULLIF(COUNT(*) FILTER (WHERE status='Closed'), 0), 1) AS reopen_rate_pct,
    COUNT(*) FILTER (WHERE status = 'Open'
        AND (EXTRACT(EPOCH FROM (s.ts - created_at)) / 3600) >= 0.7 * sla_hours) AS high_risk_open
FROM tickets, snap s;

-- ============ 2. Monthly trend ============
SELECT
    to_char(date_trunc('month', created_at), 'YYYY-MM') AS month,
    COUNT(*)                                           AS volume,
    ROUND(AVG(resolution_time_hours) FILTER (WHERE status='Closed'), 2)  AS avg_res_hours,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status='Closed' AND NOT sla_breach)
          / NULLIF(COUNT(*) FILTER (WHERE status='Closed'), 0), 1)         AS sla_compliance_pct,
    COUNT(*) FILTER (WHERE status='Open')               AS open_at_snapshot
FROM tickets
GROUP BY 1
ORDER BY 1;

-- ============ 3. Volume by category, channel, priority ============
SELECT category, COUNT(*) AS n,
       ROUND(AVG(resolution_time_hours) FILTER (WHERE status='Closed'),2) AS avg_res,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status='Closed' AND sla_breach)
             / NULLIF(COUNT(*) FILTER (WHERE status='Closed'),0),1) AS breach_pct
FROM tickets
GROUP BY category ORDER BY n DESC;

SELECT channel, COUNT(*) AS n, ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),1) AS share_pct
FROM tickets GROUP BY channel ORDER BY n DESC;

SELECT priority, COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status='Closed' AND sla_breach)
             / NULLIF(COUNT(*) FILTER (WHERE status='Closed'),0),1) AS breach_pct
FROM tickets GROUP BY priority ORDER BY priority;