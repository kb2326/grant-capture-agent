# ADR-0019: Docker locally, Terraform-managed Google Cloud for anything shared or deployed

- Status: Accepted
- Date: 2026-10-08
- Deciders: Karthick Balaje

## Context
The system needs a Postgres database with vector search for development, for the automated tests, for CI on GitHub, and in production. It also needs file storage, secret storage, container images, scheduled jobs and per-component identities in production. The budget is $10 a month, and a Cloud SQL instance costs about $0.25 a day while it exists. Even stopped, it costs about $7 a month for its IP address. The project also aims to show production-grade Google Cloud practice.

## Decision
**Two environments, each used for what it does best.**

- **Local (Docker):** Postgres 16 + pgvector runs in a Docker container (`docker compose up -d db`). It's used for day-to-day development, the 53 unit and database tests, and CI, where GitHub Actions starts the same container image as a service. It's free, starts in seconds, and gives every developer and every CI run an identical database.
- **Cloud (Google Cloud, managed with Terraform):** everything that is shared, scheduled or user-facing: Cloud Storage for raw files, Secret Manager for API keys, Artifact Registry for container images, Cloud SQL for the deployed database, a Cloud Run Job for ingestion, one service account per component, and keyless GitHub sign-in through Workload Identity Federation. All of it is declared in `deployment/terraform/`, so it can be reviewed, recreated or deleted with one command.
- **Cost control:** Cloud SQL is deleted when a milestone's cloud work is done (`terraform apply -var enable_cloudsql=false`) and recreated when needed. The data is rebuilt by re-running ingestion or replaying the raw zone.

## Alternatives considered
- **Cloud only (Cloud SQL for development and tests):** costs money for every test run, makes CI depend on cloud credentials, and is slow to start.
- **Local only:** free, but it never exercises the real deployment: IAM, secrets, managed services, scheduled jobs. Those are what production and the certification are about.
- **Clicking resources together in the Cloud Console:** quick once, but not reviewable, not repeatable, and easy to leave running and forget.
- **A SQLite or in-memory test database:** no pgvector, no full-text search, so the tests wouldn't test the real behaviour.

## Consequences
Tests and CI are fast, free and deterministic. The cloud setup is code that goes through review like any other change. The two environments must stay in step: the same Alembic migrations run against both, and the same Postgres major version (16) is used. Deleting Cloud SQL between milestones means the first cloud run of each milestone starts with a fresh database.
