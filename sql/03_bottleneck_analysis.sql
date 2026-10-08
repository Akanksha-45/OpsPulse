-- OpsPulse - Process bottleneck analysis
-- Stage durations come from ticket_status_history (one clean interval per stage).
-- Bottleneck definition: stage with the largest share of end-to-end cycle time.

-- ============ 1. Stage duration profile ============
SELECT
    h.status AS process_stage,
    COUNT(*) AS samples,
    ROUND((PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY h.duration_hours))::numeric, 2) AS median_hours,
    ROUND((PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY h.duration_hours))::numeric, 2) AS p75_hours,
    ROUND((PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY h.duration_hours))::numeric, 2) AS p95_hours,
    ROUND(AVG(h.duration_hours), 2) AS mean_hours,
    ROUND(100.0 * SUM(h.duration_hours) / NULLIF(SUM(SUM(h.duration_hours)) OVER (), 0), 1) AS share_of_cycle_pct
FROM ticket_status_history h
JOIN tickets t ON t.ticket_id = h.ticket_id
                AND t.status = 'Closed' AND t.resolved_at IS NOT NULL
JOIN (
    SELECT ticket_id, SUM(duration_hours) AS total
    FROM ticket_status_history GROUP BY ticket_id
) t_total ON t_total.ticket_id = h.ticket_id
WHERE h.duration_hours >= 0
GROUP BY h.status
ORDER BY share_of_cycle_pct DESC;

-- ============ 2. Bottleneck stage by department ============
SELECT
    t.department,
    h.status AS stage,
    COUNT(*) AS samples,
    ROUND((PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY h.duration_hours))::numeric, 2) AS median_hours
FROM ticket_status_history h
JOIN tickets t ON t.ticket_id = h.ticket_id AND t.status = 'Closed'
WHERE h.duration_hours >= 0 AND h.status IN ('Investigation', 'Assigned', 'Resolution')
GROUP BY t.department, h.status
ORDER BY t.department, median_hours DESC;

-- ============ 3. Investigation latency drivers ============
SELECT
    t.category,
    COUNT(*) AS n,
    ROUND((PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY h.duration_hours))::numeric, 2) AS median_investigation_hours
FROM ticket_status_history h
JOIN tickets t ON t.ticket_id = h.ticket_id AND t.status = 'Closed'
WHERE h.status = 'Investigation' AND h.duration_hours >= 0
GROUP BY t.category
ORDER BY 3 DESC;

SELECT
    a.shift,
    ROUND((PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY h.duration_hours))::numeric, 2) AS median_investigation_hours
FROM ticket_status_history h
JOIN tickets t ON t.ticket_id = h.ticket_id AND t.status = 'Closed'
JOIN agents a ON a.agent_id = t.assigned_agent
WHERE h.status = 'Investigation' AND h.duration_hours >= 0
GROUP BY a.shift ORDER BY 2 DESC;