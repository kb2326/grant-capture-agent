# ADR-0007: Offline index + live fallback

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
v0 called live APIs for every query. That is slow, depends on external availability and quotas (SAM.gov allows only about 10 API requests per day), and results change between runs. Changing results make evaluations unreproducible: a metric moving could mean the code changed or the data did.

## Decision
Ingest nightly into Postgres and search the local index. Use live API calls only for postings from the same day, when the index is older than 24 hours.

## Alternatives considered
- Live per-query calls (the v0 approach): slow, quota-limited and non-reproducible, so evals cannot be trusted.

## Consequences
Queries are fast and evals run against a frozen snapshot of the data. Retrieval can be tuned with SQL and indexes. The price is that data can be up to 24 hours stale, and ingestion becomes a job we must operate and monitor, with data-quality checks that fail the run on errors. Raw payloads are archived so a run can be replayed. The live fallback covers the freshness gap for new postings.
