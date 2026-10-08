# ADR-0017: Discover architecture chosen by ablation

- Status: Accepted (decision method); outcome measured in M2
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
