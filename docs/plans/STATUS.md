# Project status and handoff

*Read this first in any new session (local or cloud).*

## Where we are
- *Updated 2026-10-10.* **M0 Foundation, M1 Analyze and M2 Discover complete** (M2 merged from branch `m2-discover`).
- M2 results (`reports/m2/ablation.md`, 15 golden queries, AI-labeled silver set of 719 judgments):
  - Embeddings (ADR-0020): `gemini-embedding-001` nDCG@10 0.514 vs EmbeddingGemma 2 0.472 (local was better on the 5 vague queries, 0.499 vs 0.441). Gemini chosen; the `emb_local` column stays for a later re-test. `gemini-embedding-2` works in location `global` (unmeasured).
  - Rerank: Vertex Ranking API gave no gain (0.512 vs 0.514); built but off (`discover_rerank=False`).
  - Workflow (ADR-0017): B0 single pass kept; B1 never refined (0 of 20) because the verifier only counts passing candidates. Next idea: an LLM-graded sufficiency check.
  - Discover P@10 0.50 (target 0.70, not met); one request ~$0.003, p50 11 s (the Flash planner dominates).
  - Analyze over local A2A works behind `discover_v4_transport` (direct by default); preferences persist in `preferences` and an ADK memory service.
- Spend: M2 ≈ $1.02 (Flash $0.58, Flash-Lite labels $0.13, embeddings $0.22, ranker ≈ $0.09; Cloud Monitoring token counts + our own counters). The project stays **cost-minimal**.
- EmbeddingGemma 2 on CPU would take ~9 h for 2,737 cards; it was run on Kaggle's free T4 (6 min) from a private dataset and notebook. Kaggle token lives in `.env` (`KAGGLE_API_TOKEN`).
- **Next: M3 Draft** (brainstorm → spec → plan).
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
