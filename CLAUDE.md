# Coding Agent Guide

## Prerequisites

Install the CLI (one-time):
```bash
uv tool install google-agents-cli
```

---

## Development Phases

### Phase 1: Understand Requirements
Before writing any code, understand the project's requirements, constraints, and success criteria.

### Phase 2: Build and Implement
Implement agent logic in `app/`. Use `agents-cli playground` for interactive testing. Iterate based on user feedback.

### Phase 3: The Evaluation Loop (Main Iteration Phase)
Start with 1-2 eval cases, run `agents-cli eval run`, iterate by making changes and rerunning it until satisfied. Expect 5-10+ iterations. Once you have a baseline, reach for `agents-cli eval compare` (regression diffs), `agents-cli eval analyze` (cluster failure modes), and `agents-cli eval optimize` (auto-tune prompts). See the **Evaluation Guide** for metrics, dataset schema, LLM-as-judge config, and common gotchas.

### Phase 4: Pre-Deployment Tests
Run `uv run pytest tests/unit tests/integration`. Fix issues until all tests pass.

### Phase 5: Deploy to Dev
**Requires explicit human approval.** Run `agents-cli deploy` only after user confirms. See the **Deployment Guide** for details.

### Phase 6: Production Deployment
Ask the user: Option A (simple single-project) or Option B (full CI/CD pipeline with `agents-cli infra cicd`).

## Development Commands

| Command | Purpose |
|---------|---------|
| `agents-cli playground` | Interactive local testing |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |
| `agents-cli eval dataset synthesize` | Synthesize multi-turn eval scenarios for your agent |
| `agents-cli eval run` | Run the agent over the eval dataset and grade the traces |
| `agents-cli eval generate` / `agents-cli eval grade` | Decoupled form: produce traces, then grade them |
| `agents-cli eval compare` | Compare two grade-results files (regression check) |
| `agents-cli eval analyze` | Cluster failure modes from grade results |
| `agents-cli eval metric list` | List built-in metrics available in the SDK |
| `agents-cli eval optimize` | Auto-tune agent prompts using eval data |
| `agents-cli lint` | Check code quality |
| `agents-cli infra single-project` | Set up project infrastructure (Terraform) |
| `agents-cli deploy` | Deploy to dev |
| `agents-cli scaffold enhance` | Add deployment target or CI/CD to project |
| `agents-cli scaffold upgrade` | Upgrade project to latest version |

---

## Operational Guidelines for Coding Agents

- **Code preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values (e.g., `model`), comments, and formatting.
- **NEVER change the model** unless explicitly asked.
- **Model 404 errors**: Fix `GOOGLE_CLOUD_LOCATION` (e.g., `global` instead of `us-central1`), not the model name.
- **ADK tool imports**: Import the tool instance, not the module: `from google.adk.tools.load_web_page import load_web_page`
- **Run Python with `uv`**: `uv run python script.py`. Run `agents-cli install` first.
- **Stop on repeated errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
- **Terraform conflicts** (Error 409): Use `terraform import` instead of retrying creation.

## Project conventions (grant-capture-agent)

- Read `docs/plans/STATUS.md` first, then `docs/design/system-design.md` before changing behaviour; plans live in `docs/plans/`.
- Packages: `app/` (ADK agents), `ingest/` (data sources + pipeline), `rag/` (retrieval library, M1+), `db/` (models + migrations), `evals/` (metric harness).
- Tests: `tests/unit` (no network, no DB), `tests/db` (needs `docker compose up -d db`), `tests/integration` + `tests/eval` (call Gemini; run manually).
- Never assert on LLM output text in pytest; use `agents-cli eval run`.
- Eligibility and verification decisions are plain Python in `app/rules/`, never model judgements.
- Architecture is chosen by ablation (baseline vs. variant, decided by evals) — see system design §8.0.
- Models and thresholds come from `app/config.py`; don't hard-code model IDs elsewhere.
- GCP: project `grant-capture-agent`, personal account only. Stop or delete Cloud SQL after use.
- Never commit `.env`; never mention commercial products used as inspiration anywhere in the repo.
- Commits: conventional prefix (`feat`, `fix`, `docs`, `test`, `chore`, `infra`) and the Co-Authored-By trailer.

## Coding-agent workspace
- Hook: Python is auto-formatted after edits (`.claude/settings.json`).
- Skills: `ingest-status` (data health), `eval-report` (run and explain evals).
- Subagent: `data-quality-reviewer`. Run it after changing `ingest/` or `db/`, before opening a PR.
- Each milestone PR also gets a code review and, before cloud/infra changes merge, a security review.

## Cloud commands (M0 Part B)
- Infra is Terraform in `deployment/terraform/foundation/` (state in `gs://grant-capture-agent-tfstate`). Always `terraform plan` and read it before `apply`.
- Cloud SQL is OFF by default (`enable_cloudsql = false` in `terraform.tfvars`, ADR-0019). To use it: `terraform apply -var enable_cloudsql=true`; when done: `terraform apply` (back to false).
- Tunnel to Cloud SQL: `bash scripts/cloudsql.sh proxy` (localhost:5434); password: `gcloud secrets versions access latest --secret db-app-password`.
- Keys to Secret Manager: `bash scripts/secrets_put.sh` (never prints values).
- Ingestion image: `gcloud builds submit --config cloudbuild.ingest.yaml --substitutions _IMAGE=<artifact_repo>/ingest:<tag> .`; run: `gcloud run jobs execute grant-capture-ingest --region us-central1 --wait`.

## Discover commands (M2)
- Index: `uv run python -m rag build-cards`, then `uv run python -m rag embed --model gemini --max-usd 0.50` (local EmbeddingGemma 2: `uv sync --group local-embed --inexact`, `--model local`; CPU takes hours, see STATUS for the Kaggle GPU route).
- Evals: `uv run python -m evals.discover {queries|retrieval|label|workflow|report}`; `workflow` needs `--yes` above $0.50.
- Analyze over A2A: `uv run uvicorn app.analyze.a2a_app:a2a_app --host 127.0.0.1 --port 8001`, then set `DISCOVER_V4_TRANSPORT=a2a`.
