# M2 Discover ablation

Labels: **silver set** from `ai:gemini-3.5-flash-lite` (an AI reviewer, not a person). Read every number as agreement with that reviewer.
Pooling: only results that some arm ranked in its top 10 were labeled; unlabeled results count as not relevant, which can understate an arm that finds things the others miss.

## Embeddings (no LLM, no rerank)

| arm | slice | p@10 | ndcg@10 | recall@20 | p50_s | p95_s | cost_usd | n |
|---|---|---|---|---|---|---|---|---|
| gemini | all | 0.447 | 0.514 | 0.760 | 1.218 | 1.813 | 0.0000 | 15 |
| gemini | specific | 0.400 | 0.550 | 0.911 | 1.704 | 1.813 | 0.0000 | 10 |
| gemini | vague | 0.540 | 0.441 | 0.580 | 0.516 | 1.750 | 0.0000 | 5 |
| local | all | 0.433 | 0.472 | 0.664 | 0.500 | 0.610 | 0.000 | 15 |
| local | specific | 0.380 | 0.459 | 0.767 | 0.516 | 0.610 | 0.000 | 10 |
| local | vague | 0.540 | 0.499 | 0.540 | 0.484 | 0.500 | 0.000 | 5 |

## Rerank (no LLM)

| arm | slice | p@10 | ndcg@10 | recall@20 | p50_s | p95_s | cost_usd | n |
|---|---|---|---|---|---|---|---|---|
| gemini | all | 0.447 | 0.514 | 0.760 | 1.218 | 1.813 | 0.0000 | 15 |
| gemini | specific | 0.400 | 0.550 | 0.911 | 1.704 | 1.813 | 0.0000 | 10 |
| gemini | vague | 0.540 | 0.441 | 0.580 | 0.516 | 1.750 | 0.0000 | 5 |
| gemini+rerank | all | 0.487 | 0.512 | 0.791 | 1.313 | 2.312 | 0.0010 | 15 |
| gemini+rerank | specific | 0.430 | 0.538 | 0.911 | 1.047 | 2.312 | 0.0010 | 10 |
| gemini+rerank | vague | 0.600 | 0.461 | 0.646 | 1.313 | 2.219 | 0.0010 | 5 |

## Workflow: single pass (B0) vs Plan-Execute-Verify (B1)

| arm | slice | p@10 | ndcg@10 | recall@20 | p50_s | p95_s | cost_usd | n |
|---|---|---|---|---|---|---|---|---|
| B0 | all | 0.500 | 0.464 | 0.523 | 11.407 | 35.782 | 0.0033 | 15 |
| B0 | specific | 0.430 | 0.397 | 0.467 | 12.078 | 35.782 | 0.0038 | 10 |
| B0 | vague | 0.640 | 0.599 | 0.590 | 7.407 | 13.000 | 0.0025 | 5 |
| B1 | all | 0.467 | 0.425 | 0.533 | 11.875 | 15.875 | 0.0034 | 15 |
| B1 | specific | 0.400 | 0.365 | 0.467 | 11.875 | 13.719 | 0.0036 | 10 |
| B1 | vague | 0.600 | 0.544 | 0.612 | 10.297 | 15.875 | 0.0031 | 5 |

## Decisions

- Embeddings: gemini (nDCG@10 gemini 0.514 vs local 0.472).
- Rerank: off (nDCG@10 0.514 without vs 0.512 with).
- Workflow (ADR-0017): inconclusive. B1 refined its plan on 0 of 15 golden queries (it refines only when fewer than K candidates pass the rules), so B0 and B1 ran the same code and the gap (nDCG@10 B0 0.464 vs B1 0.425; vague 0.599 vs 0.544) is planner run-to-run variation. B0 stays the default as the simpler design.
- Workflow rows are not comparable with retrieval rows: the workflow applies the plan's filters (14 days to close, minimum award) that the labeler ignores, searches the planner's queries, and presents 10 results, so its Recall@20 is effectively Recall@10.
- Run-to-run planner variation is about 0.04 nDCG@10 (B0 and B1 ran identical code), larger than the 0.03 decision threshold; read the embedding gap (0.042, deterministic arms) as directional.
