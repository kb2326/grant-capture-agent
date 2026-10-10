# ADR-0005: Embeddings

- Status: Accepted; re-tested 2026-10-10 by [ADR-0020](0020-embedding-choice.md) (still the choice)
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
We need an embedding model for hybrid retrieval over solicitation text. On 2026-10-07, `gemini-embedding-2` returned 404 for the project. `gemini-embedding-001` works at 768 dimensions in us-central1. Model IDs live in `app/config.py` and nowhere else.

## Decision
Use `gemini-embedding-001` at 768 dimensions.

## Alternatives considered
- 3072 dimensions: a much larger index and slower queries, and the quality gain is unproven for our data.
- `text-embedding-005`: older model, expected to be weaker.
- Waiting for `gemini-embedding-2`: blocks M1 on something we do not control.

## Consequences
The index stays small and cheap, which suits the budget. The embedding model and dimension are stored with each vector, so a later change means re-embedding rather than guessing which rows are stale. We will re-test `gemini-embedding-2` in M2 using the retrieval eval, and switch only if it measurably improves retrieval metrics.
