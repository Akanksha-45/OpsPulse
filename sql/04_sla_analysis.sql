-- OpsPulse - SLA analysis
-- Snapshot: with live data replace '2026-09-18 17:00:00' with CURRENT_TIMESTAMP.
WITH snap AS (SELECT '2026-09-18 17:00:00'::timestamp AS ts)

-- ============ 1. Breach rate by priority and segment ============
SELECT
    t.priority,
    c.customer_segment,
    COUNT(*) FILTER (WHERE t.status='Closed') AS resolved,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.status='Closed' AND t.sla_breach)
          / NULLIF(COUNT(*) FILTER (WHERE t.status='Closed'), 0), 1) AS breach_pct
FROM tickets t
JOIN customers c ON c.customer_id = t.customer_id
GROUP BY 1, 2 ORDER BY t.priority, 4 DESC;

-- ============ 2. Factor association with breach on resolved tickets ============
SELECT
    t.category,
    COUNT(*) FILTER (WHERE t.status='Closed') AS resolved,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.status='Closed' AND t.sla_breach)
          / NULLIF(COUNT(*) FILTER (WHERE t.status='Closed'),0),1) AS breach_pct,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.resolution_time_hours)
          FILTER (WHERE t.status='Closed'))::numeric, 2) AS median_res_hours
FROM tickets t
GROUP BY t.category ORDER BY 3 DESC;

-- ============ 3. First-response SLA breach ============
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE status='Closed'
        AND EXTRACT(EPOCH FROM (first_response_at - created_at)) / 3600 > response_sla_hours)
        / NULLIF(COUNT(*) FILTER (WHERE status='Closed'),0),1) AS response_sla_breach_pct
FROM tickets;

-- ============ 4. High-risk OPEN tickets (elapsed >= 70% of SLA budget) ============
SELECT
    ticket_id, priority, category, department, customer_id,
    ROUND(EXTRACT(EPOCH FROM (s.ts - created_at)) / 3600, 1) AS elapsed_hours,
    sla_hours,
    ROUND(100.0 * (EXTRACT(EPOCH FROM (s.ts - created_at)) / 3600) / sla_hours, 0) AS elapsed_pct_of_sla
FROM tickets,
     (SELECT '2026-09-18 17:00:00'::timestamp AS ts) s
WHERE status = 'Open' AND (EXTRACT(EPOCH FROM (s.ts - created_at)) / 3600) >= 0.7 * sla_hours
ORDER BY elapsed_pct_of_sla DESC;

-- ============ 5. Breach profile: reopened / escalated / extreme ============
SELECT
    t.sla_breach,
    round(100.0 * AVG(t.reopened::int), 1)                                   AS reopen_pct,
    round(100.0 * AVG(t.escalation_required::int), 1)                        AS escalation_pct,
    round(100.0 * AVG((t.resolution_time_hours > 96)::int), 1)              AS extreme_rt_pct,
    round((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.resolution_time_hours))::numeric, 1) AS median_res_hours,
    COUNT(*) AS n
FROM tickets t
WHERE t.status = 'Closed'
GROUP BY t.sla_breach
ORDER BY t.sla_breach;