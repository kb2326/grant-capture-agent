# ADR-0018: Draft architecture chosen by ablation

- Status: Accepted (decision method); outcome measured in M3
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
