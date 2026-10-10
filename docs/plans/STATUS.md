# Project status and handoff

*Read this first in any new session (local or cloud).*

## Where we are
- *Updated 2026-10-10.* **M0-M3 complete** (M3 merged from branch `m3-draft`).
- M3 results (`reports/m3/ablation.md`, 12 controlled draft tasks, 46 requirements, 10 true gaps, 75-doc corpus):
  - B0 long context (cached corpus) vs. B1 corrective RAG: both flagged 10/10 gaps and invented none; evidence recall 0.944 each; B0 more faithful (0.83 vs 0.78, silver), fewer outdated/off-topic citations (1.4% vs 3.5%), twice as fast (p50 41 s vs 84 s). ADR-0018: B0 is the default.
  - Grader calibration: κ 0.63 (binary) / 0.59 (3-class) vs. the user's 40 hand labels; the grader is stricter than the user.
  - Analyze now extracts quoted `ai_policy` clauses (`brief_v2`); every draft starts with the AI-use notice.
  - MCP server `grant-capture` (`.mcp.json`) verified from a real MCP client over stdio.
- Spend: M3 ≈ $1.6-2.0 (corpus $0.57, drafting runs ≈ $1.0-1.4, mostly Flash thinking tokens). **October total ≈ $11.2-11.6, over the $10/month target**; drafting now caps thinking (`draft_thinking_budget=1024`). The real-solicitation demo was skipped for budget and moves to M4.
- **Next: M4 Ship** (brainstorm -> spec -> plan); keep it cost-minimal and mostly free-tier.

## Open items from M3
- Real-solicitation demo (draft one section for an analyzed opportunity) moved to M4 with the UI.
- `draft_thinking_budget` was added after the measured runs; re-measure B0 cost with it in M4.

## Deferred minors from the M2 review
- A2A client: the thread pool's shutdown waits past the result timeout; the `httpx.AsyncClient` is never closed.
- A negation-only query (`-solar`) gives every card an arbitrary sparse rank (`ts_rank_cd` = 0); skip sparse search when the query has no positive terms.
- `verify` adds rejected candidates' `source_id` to `seen`, so a later copy is labelled V5 instead of its real reason.
- A plan edit that is not JSON ("drop defense") silently runs the original plan; say it was ignored or re-prompt.
- A stored `min_award_usd` floor can never be lowered (max of all stored values).
- `embed_cards`: a batch returning fewer vectors raises outside the try and aborts the run.
- `run_arm` loses the spend of a query that raises without `cost_usd`, and always runs the first query.
- `open_session` builds a new engine per tool call and never disposes of it; cache the engine.
- `build_cards` loads every row at once; use `yield_per` as the index grows.
- An empty `why` (the explainer skipped a weak match) shows as blank; label it "weak match".
- Coverage gaps: AGENCY_ALIASES covers DoD/HHS/DOE/USDA/DHS/NASA/NSF only; an exclusion that matches no agency is not reported.

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
