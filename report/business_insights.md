# OpsPulse - Business Insights & Recommendations

## Baseline (62.5k tickets, 12 months)
- SLA compliance: 76.3% | median resolution 17.5h |
  avg first response 5.2h |
  escalation 13.0% | reopen 8.2%

## Bottleneck
- **Investigation** absorbs **45.9%** of cycle time
  (median 8.28h). Slowest category: **Technical Issue** at
  10.89h median.
- Secondary: **Assigned (time to first response)** (18.4%).

## Root causes (association evidence, not causal claims)
- Reopened tickets breach at **+173%** the base rate.
- Escalated tickets breach at **+37%** the base rate.
- P1 tickets breach in 91% of cases; P1+reopen and P1+strategic combos breach ~100%.
- Tight SLA accounts (Strategic 37.1%) drive disproportionate risk.

## What-if leverage
Bars below are simulated reductions in stage time applied to the 62k resolved tickets:

| Scenario | Compliance after (%) | Δ vs baseline (pp) | Recovered tickets |
|---|---|---|---|
| S1 investigation -20% | 79.3 | +3.0 | 1838 |
| S2 investigation -30% | 80.8 | +4.4 | 2763 |
| S3 first-response (Assigned) -30% | 78.5 | +2.2 | 1347 |
| S4 escalation stage -50% | 76.7 | +0.4 | 246 |
| S5 investigation -10% + Assigned -20% | 79.3 | +2.9 | 1823 |
| S6 combined -20% inv + -25% assigned | 81.1 | +4.8 | 2996 |

## Recommended actions (ranked by leverage)
1. **Investigation deep-dive (biggest lever):** Specialist routing + knowledge base for Technical Issue
   and Integration categories (median investigation 10.89h vs 5.5h Access Management).
2. **First-response automation:** mildly-tight SLA cases show FR latency 49.0%
   breach; auto-ack + triage bots cut Assigned-stage share.
3. **Reopen prevention:** closure checklists and regression checks (reopen adds breach risk).
4. **Workload rebalance:** Technical team at 3,540 tickets/agent vs 1,172 in Account Management;
   shift dispatch accordingly (night median +0.5h vs overall median).
5. **Strategic-account SLA alignment:** renegotiate or tool up for Strategic segment before defaults accumulate.

## Careful language note
All simulated gains are **analytical estimates**, not measured results. They estimate operational leverage
if process changes reduce stage time; they are not claims of implemented improvements.
