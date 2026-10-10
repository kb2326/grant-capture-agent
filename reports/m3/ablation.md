# M3 Draft ablation

Ground truth: gap, evidence, citation and distractor metrics are scored by code from the checked-in corpus plan (exact phrases). Faithfulness is a **silver** score from a Flash judge.
Grader calibration against the user's own labels: {'kappa_3': 0.5860771401693321, 'kappa_binary': 0.6335078534031413, 'n': 40}

| variant | gap_recall | gap_precision | evidence_recall | citation_validity | distractor_rate | faithfulness | context_precision | p50_s | p95_s | cost_usd | n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 1.000 | 1.000 | 0.944 | 1.000 | 0.014 | 0.833 | n/a | 40.781 | 80.078 | 0.078 | 12 |
| B1 | 1.000 | 1.000 | 0.944 | 1.000 | 0.035 | 0.776 | 0.709 | 84.094 | 122.407 | 0.043 | 12 |

## Decision

- ADR-0018: B0 (long context) - B1 is kept only with a >= 0.05 gain in gap recall, evidence recall or faithfulness without doubling cost or p95.
- Measured with Flash thinking uncapped; the shipped default draft_thinking_budget=1024 (added afterwards to cut cost) has not been measured, so quality, latency and cost at that setting are unknown until re-run.
