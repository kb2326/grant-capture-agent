# 3. Runbook: how we would deploy

**Not executed in M4** (ADR-0021). This is the exact order a funded deployment would follow. Each step lists the command, what it does, how to check it worked, how to undo it, and whether it costs money. 💲 marks a step that starts billing. Run everything from the repository root as the personal account (`gcloud config get-value account` → `karthickbalaje01@gmail.com`), project `grant-capture-agent`.

Before starting: read [costs](04-costs.md), confirm the month's budget has room, and decide the end date of the demo (then follow [teardown](05-teardown.md)).

## 0. Pre-flight (free)
- **Command:** `uv run pytest tests/unit tests/db -q && uv run python -m evals.run --suite smoke --out reports/local && (cd web && npm test && npm run build)`
- **Does:** proves the code and the offline quality gates pass.
- **Check:** all green. **Undo:** nothing to undo.

## 1. Turn on the database 💲 (~$0.30/day while it exists)
- **Command:** `cd deployment/terraform/foundation && terraform plan -var enable_cloudsql=true` → read the plan → `terraform apply -var enable_cloudsql=true`
- **Does:** creates the Cloud SQL Postgres instance, database and app user; stores the generated password in Secret Manager.
- **Check:** `gcloud sql instances list` shows the instance `RUNNABLE`.
- **Undo:** `terraform apply` (back to `enable_cloudsql=false`) deletes the instance. Data is lost unless exported first.

## 2. Migrate and load data (free apart from step 1)
- **Command:** `bash scripts/cloudsql.sh proxy` (in a second terminal), then with `DATABASE_URL` pointing at `localhost:5434`: `uv run alembic upgrade head`, `uv run python -m ingest grants-gov --limit 500`, `uv run python -m rag build-cards`, `uv run python -m ingest.company_corpus load`.
- **Does:** creates the schema and loads opportunities, cards and the company corpus. Embedding the cards and chunks costs about $0.25 of Gemini (💲 small).
- **Check:** row counts match the local database (`select count(*) from opportunity_cards`).
- **Undo:** drop the database (or the whole instance in step 1's undo).

## 3. Build and push the image (≈ free; storage cents/month)
- **Command:** `gcloud builds submit --tag us-central1-docker.pkg.dev/grant-capture-agent/grant-capture/app:$(git rev-parse --short HEAD) --file Dockerfile.api .`
- **Does:** builds the API + UI image in Cloud Build and stores it in Artifact Registry.
- **Check:** `gcloud artifacts docker images list us-central1-docker.pkg.dev/grant-capture-agent/grant-capture` lists the tag.
- **Undo:** `gcloud artifacts docker images delete <image>@<digest> --delete-tags`.

## 4. Plan, review, then apply the runtime layer 💲 (Cloud Run: cents unless used heavily)
- **Command:** `cd deployment/terraform/prod && terraform init && terraform plan -var image=<tag from step 3> -out tfplan` → **a human reads the plan** → `terraform apply tfplan`
- **Does:** creates the per-agent service accounts and their roles, the API's roles (Gemini, Cloud SQL client, trace, the DB password, read access to the raw bucket), and the Cloud Run service `grant-capture-app` (scale to zero) with the Cloud SQL connector. The M4 plan output shows exactly this: 14 resources ([evidence](evidence/terraform-plan.txt)).
- **Check:** `gcloud run services describe grant-capture-app --region us-central1 --format='value(status.url)'` returns a URL; `curl <url>/api/session` returns `{"spent_usd":0.0,...}`.
- **Undo:** `terraform destroy` in `prod/` (removes the service and identities), or roll back to the previous revision: `gcloud run services update-traffic grant-capture-app --to-revisions <previous>=100`.

## 5. Deploy the agents to Agent Runtime 💲 (billed per vCPU and memory hour while running)
- **Command:** `agents-cli deploy` (root agent, identity `root-agent`), then the Analyze A2A service with identity `analyze-agent` (set `discover_v4_transport=a2a` and `analyze_a2a_url` to its endpoint).
- **Does:** packages the ADK agents and hosts them with managed sessions; Analyze runs as its own service that the root agent calls over A2A.
- **Check:** the agents-cli output lists the engine; a test query through the API returns a draft or a verdict; Cloud Trace shows the A2A hop.
- **Undo:** delete the reasoning engine (`agents-cli` or `gcloud ai reasoning-engines delete`).

## 6. Smoke test in production (Gemini cents)
- **Command:** open the Cloud Run URL; run one search, one analysis, one draft; watch the cost meter.
- **Check:** each action shows its cost, the session total stays under `ui_session_budget_usd`, repeats show "cached (free)", traces appear in Cloud Trace.
- **Undo:** nothing.

## 7. Guardrails on (free)
- **Command:** in `prod/terraform.tfvars` set `create_budget = true` and `billing_account = "<id>"` (from `gcloud billing projects describe grant-capture-agent`), then plan and apply; keep the scheduler paused unless nightly refresh is wanted.
- **Check:** the budget appears in Billing → Budgets & alerts with 50/90/100% thresholds.
- **Undo:** set `create_budget = false` and apply.

## 8. Enable CI deploys (optional, free)
- **Command:** edit `.github/workflows/deploy.yml`: remove `if: false`, set repository variables `WIF_PROVIDER` and `CI_SA_EMAIL` from the foundation outputs, and add a protected environment with a required reviewer before any `apply` job.
- **Check:** a manual run builds and plans; nothing applies without approval.
- **Undo:** restore `if: false`.

## When the demo is over
Follow [teardown](05-teardown.md) the same day. The two things that keep billing while idle are **Cloud SQL** and **Agent Runtime**; remove those first.
