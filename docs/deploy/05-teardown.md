# 5. Teardown: stopping all spend

Use this after any demo, and as the reference for what was done at the end of M4. Order matters: remove what bills by the hour first.

## If a deployment exists
1. **Agent Runtime engines** (billed while running): `gcloud ai reasoning-engines list --region us-central1` then delete each (`gcloud ai reasoning-engines delete <id> --region us-central1`).
2. **Runtime layer**: `cd deployment/terraform/prod && terraform plan -destroy` → read → `terraform destroy`. Removes the Cloud Run service and the per-agent identities.
3. **Cloud SQL** (≈ $7-10/month even idle): `cd deployment/terraform/foundation && terraform apply` with `enable_cloudsql = false` (the default). Export data first if it matters: `gcloud sql export sql <instance> gs://<bucket>/backup.sql --database=grant_capture`.
4. **Scheduler**: keep the nightly ingestion job paused (`gcloud scheduler jobs pause …`).

## Leftovers that bill a little (what M4 did)
These are managed by the foundation Terraform, so they are **emptied, not deleted**, to keep the Terraform state true:
- **Images**: `gcloud artifacts docker images list us-central1-docker.pkg.dev/grant-capture-agent/grant-capture`, then `gcloud artifacts docker images delete <image> --delete-tags --quiet` for each. An empty repository costs nothing.
- **Build artifacts**: `gcloud storage rm "gs://grant-capture-agent_cloudbuild/**"`.
- **Raw downloads**: `gcloud storage rm "gs://grant-capture-agent-raw/**"` (the source files can be downloaded again by the ingestion commands).

Kept on purpose, because they make resuming easy and cost about $0.20/month together: the Terraform state bucket (`grant-capture-agent-tfstate`), the three secrets, and the budget alert. The exact before/after inventory from M4 is in [`evidence/shutdown-inventory.txt`](evidence/shutdown-inventory.txt).

## Stop Gemini spend
Gemini bills only when called. Nothing in this project calls it unless you run a command or the local UI. To be sure: stop the local API (`Ctrl+C`), and check Cloud Monitoring → Metrics → `aiplatform.googleapis.com/publisher/online_serving/token_count` shows no new points.

## The strongest stop: disable billing
Disabling billing on the project stops **every** paid service immediately and prevents any new charge. Paid resources are shut down (and may be deleted after a grace period), so do it only when nothing in the project should keep running.
- Console: Billing → Account management → find `grant-capture-agent` → Actions → Disable billing.
- Command line: `gcloud billing projects unlink grant-capture-agent`.
- To resume later: `gcloud billing projects link grant-capture-agent --billing-account=<id>`, then follow the [runbook](03-runbook.md).

Free resources (buckets' metadata, Terraform state, secrets) are kept while billing is off, but buckets and secrets also have small storage costs, so they are only fully free when the project is unlinked or the resources are deleted.
