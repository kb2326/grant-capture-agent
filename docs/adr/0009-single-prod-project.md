# ADR-0009: Single prod project

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The whole project runs on a $10/month budget in one personal GCP project (`grant-capture-agent`). Typical practice is separate dev, staging and production projects, but each extra project brings its own fixed costs (databases, runtimes, networking) and more infrastructure to keep in sync.

## Decision
Use a single production project. CI deploys to a `-preview` Agent Runtime instance and promotes it only after the eval gate passes.

## Alternatives considered
- A separate staging project: better isolation, but it roughly doubles the fixed costs, which the budget cannot absorb.

## Consequences
Costs stay inside the budget and there is one environment to understand. Isolation is weaker than with separate projects: a mistake in preview shares IAM, quotas and the database with production. We mitigate this with the preview deployment, the eval gate before promotion, and the rule that Cloud SQL is stopped or deleted after use. If the project ever served real customers, this decision should be superseded by a multi-project layout.
