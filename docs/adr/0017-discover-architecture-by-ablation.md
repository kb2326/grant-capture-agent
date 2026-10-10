# ADR-0017: Discover architecture chosen by ablation

- Status: Accepted. Outcome measured in M2 (2026-10-10): B0 (single pass) is the default; B1 never fired
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
v0 used a Plan, Execute, Verify style, but nobody measured whether it beat something simpler. Current agent-engineering guidance says to add multi-step behaviour only when it demonstrably improves outcomes. A refinement loop should help when the first plan misses, typically on vague or broad requests, and it costs extra model calls, latency and money.

## Decision
Build two variants over the same `SearchPlan` contract and approval step. B0 is a single pass: understand the query, hybrid search, rerank, rule filters. B1 is Plan, Execute, Verify with up to three refinement iterations. M2 runs both on the golden query set, including a labeled vague-query slice, and keeps B1 only if it wins on quality without an unacceptable cost or latency penalty.

## Alternatives considered
- Assume PEV is better because v0 used it: carries an untested assumption forward.

## Consequences
Because both variants share the plan contract, the comparison is fair and the approval step is identical. We build more up front, since two workflows must exist, and we report P@10, p50 and p95 latency and cost per run overall and on the vague slice. The result may well be that the simple baseline is enough; that is an acceptable and useful outcome.

## Outcome (measured 2026-10-10)
Full numbers: `reports/m2/ablation.md`. 15 golden queries (10 specific, 5 vague), silver labels from `gemini-3.5-flash-lite`, Gemini embeddings, no rerank (both chosen by the earlier ablations, ADR-0020).

| | B0 single pass | B1 Plan-Execute-Verify |
|---|---|---|
| nDCG@10 (all / vague) | 0.464 / 0.599 | 0.425 / 0.544 |
| P@10 (all) | 0.500 | 0.467 |
| Cost per request | $0.0033 | $0.0034 |
| p50 / p95 latency | 11.4 s / 35.8 s | 11.9 s / 15.9 s |
| Plans refined | – | 0 of 20 queries |

**Decision: B0.** B1 never refined: its trigger is "fewer than K=5 candidates pass the rules", and with 2,700 opportunities almost every first plan passes 5. The B0/B1 gap is therefore planner run-to-run variation, not the loop. The lesson is that an evaluator-optimizer loop needs an evaluator that judges *relevance*, not just a count; the next candidate is an LLM-graded sufficiency check (the same Flash-Lite grader used for labels, calibrated against hand labels first). Latency is dominated by the Flash planning call (~10 s); raw hybrid search alone takes ~1 s.
