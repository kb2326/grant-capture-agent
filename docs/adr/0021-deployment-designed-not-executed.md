# ADR-0021: Deployment designed to production standard, not executed

- Status: Accepted
- Date: 2026-10-10
- Deciders: Karthick Balaje

## Context
M4 was planned as "ship": Terraform-provisioned production, agents on Agent Runtime, the UI on Cloud Run, tracing, per-agent identity, an eval gate in CI. By the end of M3 the October Gemini spend was about $11.2-11.6, over the project's $10/month target, and the project's stated purpose is learning, not running a public service. A real deployment also bills by the hour for some components even when idle (Cloud SQL ≈ $7-10/month; Agent Runtime while instances run).

## Decision
Design the production deployment to the standard a team would review, prove it without spending, and stop there:
- the runtime layer is written in Terraform (`deployment/terraform/prod/`) and proven with `terraform validate` and `terraform plan` (14 resources to add; nothing created; output saved in `docs/deploy/evidence/`);
- the production image (`Dockerfile.api`) is built and run locally;
- the deploy workflow exists but every job is disabled (`if: false`) and there is no apply step;
- the "how this ships" documents (`docs/deploy/`) teach the prototype-to-production changes, the architecture, a runbook with costs per step, and teardown;
- billable leftovers from M0-M3 are emptied after the user approves the list.

## Alternatives considered
- **Deploy for a day, then tear down:** the most realistic learning, and a live URL for the write-ups; rejected for now because October is already over budget. The runbook makes this a short, costed exercise for a later month.
- **Documents only, no code:** cheaper still, but nothing would be checked; Terraform that has never been planned often fails on the first real run.
- **Keep a permanent small deployment:** Cloud SQL alone would exceed a meaningful share of the monthly target.

## Consequences
There is no public URL; the README and write-ups use screenshots of the local UI, which runs the same code against the same models. Anyone (including a future funded "M4b") can deploy by following `docs/deploy/03-runbook.md`, starting from a reviewed plan. The deploy path is unproven at runtime: IAM propagation, cold starts and Agent Runtime packaging may still surface issues that `plan` cannot catch, and those would be the first things to watch in a real deployment.
