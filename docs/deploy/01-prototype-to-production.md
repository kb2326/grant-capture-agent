# 1. From prototype to production

Everything in this project so far runs on one laptop: Postgres in Docker, Python processes started by hand, Gemini called with your personal Google sign-in, and spending tracked by reading Cloud Monitoring after the fact. That is the right way to build and measure an idea. It is the wrong way to let other people depend on it. This page walks through what has to change, concern by concern, and why each change matters. The rest of this folder turns these answers into a concrete design ([architecture](02-architecture.md)), the exact steps ([runbook](03-runbook.md)), the bill ([costs](04-costs.md)) and the way back out ([teardown](05-teardown.md)).

## Identity: who is allowed to do what
**Laptop:** every call runs as you, with your full owner rights on the project.
**Production:** every running component gets its own **service account** with only the roles it needs. The API can read the database password and nothing else; the Analyze agent can call Gemini and read the database; the CI pipeline can push images but cannot read data. No component ever holds a key file: Cloud Run and Agent Runtime attach the identity to the running process, and GitHub Actions gets short-lived credentials through **Workload Identity Federation** (already set up in the foundation Terraform).
**Why it matters:** if one piece is compromised or buggy, the damage is limited to what that piece was allowed to do. This is also what auditors and security reviewers ask first.

## Secrets: where passwords and API keys live
**Laptop:** a git-ignored `.env` file.
**Production:** **Secret Manager**. Cloud Run injects a secret as an environment variable at start-up (`DB_PASSWORD` in our Terraform), and only identities that were granted `secretAccessor` on that one secret can read it. Rotating a key means adding a new secret version; nothing is rebuilt.
**Why it matters:** secrets never sit in images, logs or repositories, and access to each one is listed and auditable.

## Data: the database and its schema
**Laptop:** Postgres 16 + pgvector in Docker, migrated with Alembic by hand.
**Production:** **Cloud SQL** for Postgres with pgvector, the smallest shared-core tier, private by default and reached through the Cloud SQL connector. Migrations become a **deploy step** that runs before the new version takes traffic, and automated backups are on.
**Why it matters:** a managed database survives restarts, is backed up, and is patched for you. The catch is cost: Cloud SQL bills every hour it exists, even idle (see [costs](04-costs.md)), which is why our foundation Terraform keeps it switched off (`enable_cloudsql=false`) unless a demo needs it.

## Scaling: running only when used
**Laptop:** processes run while the terminal is open.
**Production:** the API and UI run on **Cloud Run** with `min_instance_count = 0`: when nobody uses the site, nothing runs and nothing is billed; the first request after a quiet period waits a few seconds for a **cold start**. The agents run on **Agent Runtime**, Google's managed hosting for ADK agents, which also keeps conversation sessions so a workflow can pause for human approval and resume later.
**Why it matters:** a demo used a few times a week costs cents instead of dollars, at the price of an occasional slow first request.

## Observability: seeing what happened
**Laptop:** print statements and our own cost counters.
**Production:** every request is **traced** (Cloud Trace shows each agent step, tool call and Gemini call with timings), logs are structured and searchable, and Gemini token counts per model are charted in Cloud Monitoring (the same metric we used to measure M1-M3 spend).
**Why it matters:** when a user says "it was slow" or "it gave a wrong answer", you can find that exact request and see which step was at fault.

## Evaluation as a release gate
**Laptop:** we ran ablations by hand and read the reports.
**Production:** the cheap offline suites (`analyze_smoke`, `discover_smoke`, `draft_smoke`) run in CI on every pull request, and a release is **blocked** if a key metric regresses (for example knockout recall below 0.95). Expensive live evaluations run on a schedule or before a release, with a hard budget.
**Why it matters:** an AI system can get worse without any code error: a prompt tweak or a model update can silently lower quality. Treating evals like tests is how teams catch that.

## Cost guardrails: budgets alert, code caps
**Laptop:** we estimated before runs and checked Cloud Monitoring afterwards. October still went over the target, mostly from Gemini "thinking" tokens.
**Production:** three layers. A **budget alert** emails at 50/90/100% of the monthly target, but an alert does **not** stop spending. **Caps in code** do: the local UI's `ui_session_budget_usd`, the eval budget caps, and the drafting `draft_thinking_budget`. As a last resort, **disabling billing** on the project stops everything (see [teardown](05-teardown.md)).
**Why it matters:** the only guardrail that reliably stops spend is one that refuses the next call.

## Safety and honesty
- **Prompt injection:** solicitation documents are untrusted text. In production they would be screened by **Model Armor** before reaching the model, in addition to what the code already does (quotes are verified verbatim, eligibility is decided by plain-Python rules, never by the model).
- **Honest output:** every draft starts with the AI-use notice, gaps are listed rather than invented, and unsupported sentences are flagged. Agency rules on AI use (NIH, NSF) are quoted from each solicitation.

## Rollback: undoing a bad release
**Laptop:** `git checkout`.
**Production:** every Cloud Run deploy is an immutable **revision**; rolling back is shifting traffic to the previous revision (one command, seconds). Infrastructure changes go through `terraform plan` → human review → `apply`, and the Terraform state (in the `grant-capture-agent-tfstate` bucket) records exactly what exists.
**Why it matters:** the fastest fix for a bad release is to undo it, then investigate.

## What we actually did in M4
We designed all of the above, wrote the Terraform and the container, and **proved** them without spending: `terraform validate` and `terraform plan` (14 resources to add, nothing created; see [`evidence/terraform-plan.txt`](evidence/terraform-plan.txt)), a local `docker build` and run of the production image ([`evidence/docker-build.txt`](evidence/docker-build.txt)), and a deploy workflow that exists but is disabled. ADR-0021 records why we stopped there.
