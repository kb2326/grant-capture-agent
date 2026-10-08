# Project status and handoff

*Updated 2026-10-07. Read this first in any new session (local or cloud).*

## Where we are
- *Updated 2026-10-08.* M0 **Part A (local) complete**: Tasks 1–13 incl. 2b/7b/8b/8c on branch `m0-foundation` (draft PR #6, CI green, 53 tests). Progress ledger: `.superpowers/sdd/2026-10-07-m0-foundation/progress.md` (local, git-ignored).
- Local data: 2,736 opportunities (Grants.gov 1,199; SAM.gov 1,537), 736 documents, raw zone in `data/blobs/` (git-ignored).
- **Next: M0 Part B (Tasks 14–17, cloud)** — waits for the user's explicit "go cloud" (creates billable resources). Terraform files for Task 14 are drafted (untracked) in `deployment/terraform/foundation/` and `scripts/`.
- After M0: final whole-branch review, merge PR #6, then M1 (Analyze).

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
