# ADR-0012: Runtime choice

- Status: Accepted. Target: Cloud Run for the API and UI, Agent Runtime for the agents (Analyze as its own A2A service). Designed and validated with `terraform plan` in M4, not deployed (ADR-0021)
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The agents need managed sessions, so that workflows can pause for human approval and resume, and ideally managed memory for user preferences. The other components are different in kind: the API, the UI and the ingestion job are ordinary containers with no need for agent-specific hosting. Cost matters, with a $10/month ceiling, so idle resources should scale to zero where possible.

## Decision
Run the agents on Agent Runtime. Run the API, UI and the nightly ingestion job on Cloud Run.

## Alternatives considered
- Cloud Run for everything: simplest to reason about, but we would lose managed sessions and memory and would have to build them ourselves.
- GKE: maximum flexibility, but the operational overhead and baseline cost are not justified for a single-user demo.

## Consequences
Each component uses the platform that fits it, and sessions and memory come managed. The cost is two deployment paths to maintain, with separate configuration, CI steps and permissions. The `-preview` Agent Runtime instance in ADR-0009 covers the agent path, while Cloud Run revisions cover the rest. We will watch whether the two paths cause drift in environment configuration.
