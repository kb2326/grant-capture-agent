# Project status and handoff

*Updated 2026-10-07. Read this first in any new session (local or cloud).*

## Where we are
- *Updated 2026-10-08.* **M0 complete** (Parts A + B) on branch `m0-foundation` (PR #6), pending final review and merge.
- Local: 2,736 opportunities, 736 documents. Cloud: foundation live (buckets, secrets, Artifact Registry with `ingest:m0`, service accounts, WIF); the ingestion job ran once on Cloud SQL (487 opportunities, 226 documents, 0 failures); **Cloud SQL then deleted** (off by default).
- **Next: M1 Analyze** — brainstorm → spec update → plan. Starts with you hand-labeling 30+ solicitations (evals/LABELING.md).
- Deferred cleanups: ingestion job imports the agent package (harmless BigQuery warning); `uv run` rebuilds the project at container start.

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
