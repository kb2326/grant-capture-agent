# ADR-0018: Draft architecture chosen by ablation

- Status: Accepted. Outcome measured in M3 (2026-10-10): B0 (long context) is the default drafter
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
Corrective RAG (retrieve, grade, re-query, report a gap) matters when the evidence base is large. A real company accumulates hundreds of proposals, reports and CVs, far more than fits usefully in one prompt. The synthetic company corpus today has only 13 documents, small enough to put entirely in context, so testing corrective RAG on it would prove little.

## Decision
Expand the synthetic corpus in M3 to about 80 documents, including off-topic and outdated distractors. Then compare B0, long-context drafting with the whole page-tagged corpus in one call, against B1, corrective RAG with per-section retrieval, grading and at most two rewrites. Keep B1 only if it wins on measured quality at acceptable cost.

## Alternatives considered
- Assume corrective RAG is needed on a 13-document corpus: it would add complexity the data cannot justify.

## Consequences
Both variants use the same citation rules and faithfulness check, so the comparison isolates the retrieval strategy. M3 reports faithfulness, context relevance, gap detection, drafting time and cost per run. The grader is calibrated first, with agreement (kappa) reported. We must build and label the larger corpus, which is real effort, but it makes the result credible.

## Outcome (measured 2026-10-10)
Full numbers: `reports/m3/ablation.md`. 12 controlled draft tasks (46 requirements, 10 deliberate gaps) over a 75-document synthetic corpus (13 originals, 35 current, 15 outdated, 12 off-topic; 345 passages, about 54k tokens). Gap, evidence, citation and distractor metrics are scored by code from the checked-in corpus plan; faithfulness is a silver score from a Flash judge.

| | B0 long context (cached corpus) | B1 corrective RAG |
|---|---|---|
| Gap recall / precision | 1.00 / 1.00 | 1.00 / 1.00 |
| Evidence recall | 0.944 | 0.944 |
| Citations to outdated or off-topic docs | 1.4% | 3.5% |
| Faithfulness (silver) | 0.83 | 0.78 |
| p50 / p95 latency | 41 s / 80 s | 84 s / 122 s |
| $ per section (our counter) | $0.078 (overstated: cached tokens counted at full price) | $0.043 |

**Grader calibration:** Cohen's κ between the user's 40 hand labels and the Flash-Lite grader is 0.63 (relevant vs. not; target 0.6) and 0.59 across three classes. When they disagreed, the grader was stricter (5 of 40 pairs: grader "partly", user "relevant"), which errs toward flagging gaps rather than accepting weak evidence.

**Decision: B0.** Corrective RAG brought no quality gain on a corpus that fits in one cached context. Long context was slightly more faithful, cited outdated documents less often and ran twice as fast. Both caught every true gap and invented none. B1 stays in the code as the path for a corpus too large for the context window; the decision should be re-run when the company corpus grows by roughly 10x or when cost per section matters more than latency.

**Cost note:** Flash's thinking tokens (billed as output, up to 17k per section) dominated spend; drafting now caps them (`draft_thinking_budget=1024`). These measurements were taken with thinking **uncapped**: the shipped default has not been measured, so faithfulness, latency and cost at 1,024 thinking tokens are unknown until B0 is re-run (about $0.50, planned for M4).
