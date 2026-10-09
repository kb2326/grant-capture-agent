# ADR-0003: Postgres + pgvector

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
Retrieval needs metadata filters (status, close date, agency), full-text search and vector similarity together. The scale is small: about 20,000 pages of solicitation text. The monthly budget is $10, and we want to see and tune every retrieval stage, because the retrieval design is part of what the project demonstrates.

## Decision
Use Cloud SQL Postgres 16 with the pgvector extension. Run hybrid search (full text plus vectors plus filters) in a single SQL query.

## Alternatives considered
- AlloyDB: has ScaNN indexes, but the minimum size costs far more than the whole budget.
- Vertex AI Vector Search: a separate system that must be kept in sync with the metadata database.
- Vertex AI RAG Engine: hides the retrieval stages, which makes them hard to evaluate and tune.

All three are compared against this choice in M5, so the decision can be revisited with data.

## Consequences
One database holds relational data, text search and embeddings, so filters and ranking compose naturally and costs stay low. We tune HNSW parameters ourselves and are responsible for index maintenance. Cloud SQL must be stopped or deleted after use to stay in budget. If scale grew by orders of magnitude, we would need to revisit this choice.
