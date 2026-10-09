# Project status and handoff

*Read this first in any new session (local or cloud).*

## Where we are
- *Updated 2026-10-09.* **M0 Foundation and M1 Analyze complete** (M1 merged from branch `m1-analyze`).
- M1 results (`reports/m1/ablation.md`, AI-labeled silver set of 40): knockout recall 1.00 (10/10), strict precision 0.91 (0.45 before the bullet-list rules fix), requirement recall 0.15 whole-document vs 0.69 page windows (n=7), quote fidelity 0.93, $0.04 per solicitation. ADR-0016: B0 for eligibility; hybrid (windows for requirements) planned for M3.
- Spend: M1 ~$8.60 of the $10/month budget (measured from Cloud Monitoring token counts). **From M2 on: cost-minimal** — small samples, Flash/Flash-Lite, local EmbeddingGemma 2, hard `eval_budget_usd` caps, estimate shown before any run > $0.50.
- **Next: M2 Discover** (brainstorm → spec → plan).
- Open data items: SAM.gov attachments for the 12 sampled notices were never fetched (quota spent on a failed run, since fixed); retry one notice first: `uv run python -m ingest sam-attachments --notice <id>`. NIH announcements sit behind a bot challenge and are not fetched.

## Deferred minors from the M1 review
- Quote normalization misses curly quotes and bullets; `MIN_QUOTE_CHARS` rejects "Phase II".
- Prompt-injection: injected text can make the model omit a clause; escape delimiter look-alikes inside documents.
- `analyze_opportunity` tool: validate `variant` and the UUID, return error dicts instead of raising.
- ADK workflow (not wired to the agent): stop on no documents, write a RunRow, guard a missing company profile.
- Labeling page "open file" downloads instead of showing the PDF inline.
- Scanned PDFs estimate 0 tokens and are not sent in B1.
- `app/agent.py` hard-codes the model ID (pre-existing).
- `sam_attachments` file-name fallback picks the wrong URL segment for links not ending in `/download`.
- The silver labeler shares input format and model family with the system (correlated errors).

## Deferred minors from the M0 review (fix when the area is next touched)
- The nightly job runs `--limit 500`, so cloud runs skip quality checks. Separate a safety cap from the partial-run flag.
- SAM bulk archiving loads the 210 MB extract into memory. Stream it to GCS before the M2 cloud SAM job.
- A fresh-but-yesterday SAM cache gets archived under today's date. Key the raw zone by extract date.
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
