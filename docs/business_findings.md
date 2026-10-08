# Business Findings — OpsPulse

Numbers below come from the cleaned 62.5k-ticket dataset (12 months simulated into a snapshot),
computed by modules 02–08. They are associations and simulation estimates — no causal claims.

## Headline
- SLA compliance **76.3%**; median resolution **17.4h**, average **21.5h**; average first response
  **5.2h**; escalation **13.1%**; reopen **8.2%**.
- **The bottleneck is Investigation**: it consumes **~46%** of end-to-end cycle time
  (median 7.3h). The next-biggest stage is time-to-first-response (Assigned) at **~18%**.
- Investigation is slowest on **Technical Issue** and **Integration** tickets
  (median ~10.9h vs 5.5h for Access Management).

## Root causes / high-risk drivers (lift vs baseline breach rate)
| Driver | Lift |
|---|---|
| Priority P1 | 3.9x (breach ≈ 92%) |
| Reopened ticket | 2.7x |
| Priority P2 | 2.2x |
| Slow first response | 2.1x |
| Strategic account | 1.5x |
| Escalated | 1.3x |
| Technical category | 1.2x |
| High agent concurrent load | 1.1x |

Two-way combos compound: P1 × reopen and P1 × strategic breach ~100% of the time.

## ML / prediction
- Logistic Regression and Random Forest both reach **ROC-AUC ≈ 0.92** on held-out data
  (RF F1 0.74). Top features: remaining SLA budget, SLA clock pressure, and priority.
- The models run in **06** to triage the live open queue rather than only explain history.

## Open queue & prioritisation
- 357 open tickets; **~76% are already past their SLA budget** (chronic backlog, incl. a long tail
  up to 381 days). Only 86 remain inside budget; of those, 15 are at critical/high risk.
- Risk x value engine flags Strategic accounts holding the largest at-risk contract value
  (Support dept ~9.3M kUSD, Technical ~7.8M kUSD at risk).

## Workforce
- Technical team runs the hottest load (~3.5k tickets/agent, 73% compliance); Account Management
  is comparatively light (~1.2k/agent, 78%). Workload inequality (Gini) is moderate at 0.27.
- Night shift is slightly slower than evening (18.0h vs 15.8h median).

## What-if leverage (simulated stage reductions on the 62k resolved tickets)
| Scenario | Compliance after | Δ vs baseline | Recovered tickets |
|---|---|---|---|
| Investigation −20% | 79.3% | +3.0pp | 1,838 |
| Investigation −30% | 80.8% | +4.4pp | 2,763 |
| First response −30% | 78.5% | +2.2pp | 1,347 |
| Escalation stage −50% | 76.7% | +0.4pp | 246 |
| Investigation −10% + Assigned −20% | 79.3% | +2.9pp | 1,823 |
| Combined −20% inv + −25% assd | 81.1% | +4.8pp | 2,996 |

## Recommended actions (by leverage)
1. **Investigation deep-dive** — specialist routing + knowledge base for Technical/Integration.
2. **First-response automation** — auto-acknowledgement and triage for tight-SLA tickets.
3. **Reopen prevention** — closure checklists / regression checks (reopen adds ~2.7x risk).
4. **Workload rebalance** — shift dispatch from Technical/Billing to underutilised teams.
5. **Strategic-account SLA alignment** — review SLAs their contracts can actually meet.

Verification notes: breach-rate test set ROC-AUC 0.92, all numeric production steps are
deterministic (seed 42); see `report/*.json` for exact per-module outputs.