-- OpsPulse - Workforce analytics
WITH snap AS (SELECT '2026-09-18 17:00:00'::timestamp AS ts)

-- ============ 1. Team workload & performance ============
SELECT
    a.department,
    a.team,
    COUNT(DISTINCT a.agent_id)                                   AS agents,
    COUNT(t.ticket_id)                                          AS assigned_tickets,
    ROUND(COUNT(t.ticket_id)::numeric / NULLIF(COUNT(DISTINCT a.agent_id), 0), 0) AS tickets_per_agent,
    COUNT(t.ticket_id) FILTER (WHERE t.status = 'Open')          AS open_tickets,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.resolution_time_hours)
          FILTER (WHERE t.status = 'Closed'))::numeric, 1)                  AS median_res_hours,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.status='Closed' AND NOT t.sla_breach)
          / NULLIF(COUNT(*) FILTER (WHERE t.status='Closed'), 0), 1) AS sla_compliance_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.escalation_required)
          / NULLIF(COUNT(*), 0), 1)                               AS escalation_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.reopened)
          / NULLIF(COUNT(*) FILTER (WHERE t.status='Closed'), 0), 1) AS reopen_pct
FROM agents a
LEFT JOIN tickets t ON t.assigned_agent = a.agent_id
GROUP BY a.department, a.team
ORDER BY tickets_per_agent DESC;

-- ============ 2. Workload vs resolution time (agent-level) ============
WITH agent_agg AS (
    SELECT
        t.assigned_agent AS agent_id,
        COUNT(t.ticket_id) AS tickets,
        COUNT(t.ticket_id) FILTER (WHERE t.status='Open') AS open_now,
        ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.resolution_time_hours)
              FILTER (WHERE t.status='Closed'))::numeric, 2) AS median_res_hours
    FROM tickets t
    WHERE t.assigned_agent IS NOT NULL
    GROUP BY 1
)
SELECT
    a.agent_id, a.department, a.team, a.shift, a.experience_level,
    aa.tickets, aa.open_now,
    round(100.0 * aa.open_now / NULLIF(a.capacity_per_day, 0), 1) AS workload_load_pct,
    aa.median_res_hours
FROM agent_agg aa
JOIN agents a ON a.agent_id = aa.agent_id
ORDER BY workload_load_pct DESC;

-- ============ 3. Shift & experience-level performance ============
SELECT
    a.shift,
    COUNT(*) AS resolved,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.resolution_time_hours))::numeric, 2) AS median_res_hours,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.sla_breach) / NULLIF(COUNT(*),0), 1) AS breach_pct
FROM tickets t
JOIN agents a ON a.agent_id = t.assigned_agent
WHERE t.status = 'Closed'
GROUP BY a.shift ORDER BY 3;

SELECT
    a.experience_level,
    COUNT(*) AS resolved,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.resolution_time_hours))::numeric, 2) AS median_res_hours,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.sla_breach) / NULLIF(COUNT(*),0), 1) AS breach_pct
FROM tickets t
JOIN agents a ON a.agent_id = t.assigned_agent
WHERE t.status = 'Closed'
GROUP BY a.experience_level ORDER BY 3;