# ADR-0020: Embedding model chosen by measurement

- Status: Accepted
- Date: 2026-10-10
- Deciders: Karthick Balaje

## Context
ADR-0005 picked `gemini-embedding-001` (768-d) without measuring an alternative. M2 builds one searchable card per opportunity (title, agency, kind, status, close date, listings, NAICS and summary; ~600 tokens each, 2,737 cards) and needed to know whether a free local model is good enough.

Both models embedded the same cards with the same text:
- `gemini-embedding-001`, 768-d, `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`: $0.22 for all 2,737 cards.
- EmbeddingGemma 2 (`google/embeddinggemma-2`, Apache-2.0, 768-d, `Document` / `SearchQuery` prompts): $0. On this machine's CPU it would have taken ~8–9 hours, so it ran on Kaggle's free T4 GPU in 6 minutes (spot check: CPU and GPU vectors agree, cosine 0.998).

Measured on 15 golden queries with silver labels (Flash-Lite judge, 719 labels pooled from all six arms), hybrid search, no LLM and no rerank (`reports/m2/ablation.md`):

| | nDCG@10 | P@10 | Recall@20 | nDCG@10, vague slice | p50 latency |
|---|---|---|---|---|---|
| gemini-embedding-001 | **0.514** | **0.447** | **0.760** | 0.441 | 1.22 s |
| EmbeddingGemma 2 | 0.472 | 0.433 | 0.664 | **0.499** | 0.50 s |

`gemini-embedding-2` returned 404 in `us-central1` (as recorded in ADR-0005) but works in the `global` location. It was not added as a third arm, to keep spend minimal.

## Decision
Use `gemini-embedding-001` for Discover (`discover_embedding="gemini"`). Keep the `emb_local` column and the code path so the choice can be revisited with one setting.

## Alternatives considered
- EmbeddingGemma 2: free per query and better on vague requests, but 0.042 lower nDCG@10 overall (above the 0.03 decision threshold) and it needs a GPU to re-embed the corpus in reasonable time.
- `gemini-embedding-2` (global): available but unmeasured; the next candidate if retrieval quality becomes the bottleneck.
- Keeping both and fusing them: more moving parts for a gain not shown here.

## Consequences
Re-embedding all cards costs about $0.22, and only changed cards are re-embedded. Query embeddings add a network call (~0.7 s at p50). The labels are a silver set from an AI judge and the vague slice has only 5 queries, so the vague-slice advantage of the local model is a signal to re-test, not a finding. Revisit if vague requests dominate real use, or when `gemini-embedding-2` is measured. ADR-0005 is now "Accepted, re-tested by ADR-0020".
