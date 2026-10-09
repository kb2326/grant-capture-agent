# Project status and handoff

*Read this first in any new session (local or cloud).*

## Where we are
- *Updated 2026-10-09.* **M0 Foundation complete and merged to `main`** (PR #6). 65 tests (unit + db), CI green. An independent whole-branch review found 2 Critical + 4 Important issues; all fixed test-first.
- Local: 2,736 opportunities, 736 documents. Cloud: foundation live; Cloud SQL deleted (off by default, `enable_cloudsql=false`). The `ingest:m0` image predates the review fixes, so rebuild it before the next cloud run.
- **Next: M1 Analyze.** Brainstorm, then spec update, then plan. Starts with hand-labeling 30+ solicitations (`evals/LABELING.md`).

## Deferred minors from the M0 review (fix when the area is next touched)
- The nightly job runs `--limit 500`, so cloud runs skip quality checks. Separate a safety cap from the partial-run flag.
- SAM bulk archiving loads the 210 MB extract into memory. Stream it to GCS before the M2 cloud SAM job.
- A fresh-but-yesterday SAM cache gets archived under today's date. Key the raw zone by extract date.
- Generic mime (`application/octet-stream`) on a `.pdf` is skipped. Fall back to the suffix or check the response Content-Type.
- SAM `resourceLinks` names have no suffix. Use Content-Disposition when M1 fetches SAM attachments.
- A blank `SIMPLER_GRANTS_API_KEY=` skips the Secret Manager fallback. Treat empty as unset.
- `estimated_award_count` accepts `bool`.
- WIF trusts the repo name and every ref. Use repository_id/owner_id plus a ref condition before M4 grants deploy rights.
- `scripts/secrets_put.sh` exits 1 when `SAM_API_KEY` is empty.
- `variables.tf` defaults `enable_cloudsql=true` (tfvars overrides it to false).
- The ingestion job imports the agent package (BigQuery warning), and `uv run` rebuilds at container start.

## Decisions that aren't obvious from the code
- Architecture is chosen by **ablation**: simple baseline vs. richer variant, decided by evals (system design §8.0, ADRs 0016–0018). Don't assume PEV or CRAG wins.
- Data sources: Grants.gov via Simpler Grants API (60 requests/min); SAM.gov via its **daily public CSV** (API only for on-demand attachments, about 10 requests/day). SBIR.gov API and DoD DSIP are blocked; don't use them.
- Records are validated against the official CommonGrants SDK (`common-grants-sdk`).
- Models (verified 2026-10-07): `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview` (location `global`); embeddings `gemini-embedding-001`, 768-d, `us-central1` (`gemini-embedding-2` returned 404).
- The repo never mentions any commercial product used as inspiration.

## Environment (local machine)
- GCP project `grant-capture-agent` (personal account only; $10/month budget). Cloud SQL is deleted between uses (a stopped instance still bills about $7/month for its IP address).
- API keys live only in the local, git-ignored `.env` (`SIMPLER_GRANTS_API_KEY`, `SAM_API_KEY`). Never commit them.
- Tools installed locally: agents-cli 1.9, gcloud (ADC signed in), Terraform 1.16.5, uv, Docker.

## Cloud sessions (claude.ai/code)
Good for Part A code and unit tests (Tasks 1–12, except live API checks and DB tests if Docker is unavailable). Not for Part B (needs local Google Cloud sign-in) or the live ingestion run (needs the keys). Commit to `m0-foundation`; local sessions pull and run the live steps.
