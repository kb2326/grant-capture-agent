# M4 Ship (free part): specification

| | |
|---|---|
| Status | In review |
| Date | 2026-10-10 |
| Parent design | [`system-design.md`](system-design.md) §10, §13–§16, §17 |
| Branch | `m4-ship` |
| Decisions | ADR-0012 (runtime choice, updated), ADR-0021 (new: deployment designed, not executed) |

## 1. Goal

Finish the project as a portfolio piece **without spending on cloud infrastructure**:

1. A **local product UI** (React + Vite + TypeScript) over a small FastAPI API that calls the real agents, live, with a visible cost for every action and a session spending cap.
2. A **deployment designed to production standard but not executed**: documents that teach how an AI product like this is taken to production, Terraform and CI that are validated and planned (never applied), and a production container that builds.
3. The **final README** with architecture diagrams and the measured results of M1–M3, plus **Medium and LinkedIn drafts**.
4. **Cloud spending stopped**: billable leftovers deleted after the user approves the exact list.

The October Gemini spend is already over the $10 target, so M4 is built to cost ≈ $0.05–0.20 (live UI testing only), capped in code.

### Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| A1 | UI runs locally | `npm run dev` (web) + `uv run uvicorn api.main:app` (API); search → analyze → draft works end to end on one real opportunity |
| A2 | Live only, cost visible | every action returns and displays `cost_usd`; a session counter; live calls blocked once `ui_session_budget_usd` (default $0.50) is reached |
| A3 | Results reused | the same analyze/draft request in one API process is served from an in-memory cache at $0 |
| A4 | Honest drafting UI | AI-use notice first; AI-use warnings shown; unsupported paragraphs highlighted; gaps panel; Markdown download |
| A5 | Tests | API routes with fake tools (pytest); React components (Vitest) for citations, gaps, notice and the cost counter; no LLM-text assertions |
| A6 | Deployment learning docs | `docs/deploy/` explains prototype → production, the target architecture, a step-by-step runbook, costs and teardown |
| A7 | Validated, not applied | `deployment/terraform/prod/` passes `terraform validate`; a `terraform plan` (no apply) output is saved as evidence; `.github/workflows/deploy.yml` is manual-only and disabled |
| A8 | Container builds | `docker build -f Dockerfile.api .` succeeds locally (API + built UI) |
| A9 | ADRs | ADR-0012 updated; ADR-0021 written |
| A10 | README + writing | final README (problem, screenshots, Mermaid diagrams, results, how it ships, cost honesty); `docs/writing/medium-article.md`, `docs/writing/linkedin-post.md`; no commercial product names |
| A11 | Spending stopped | inventory shown; the user approves deletions; billable leftovers deleted; no new Gemini usage after the session; how to disable billing documented |

### Out of scope
Any `terraform apply`, Agent Runtime or Cloud Run deployment, Memory Bank, Model Armor configuration, OAuth export, red teaming against a live endpoint, CI eval gate on a live deployment. These are documented in the runbook as the steps a future, funded M4b would take.

## 2. Facts measured before design (2026-10-10)
- Live in Google Cloud: 3 buckets (`grant-capture-agent-raw`, `grant-capture-agent-tfstate`, `grant-capture-agent_cloudbuild`), one Artifact Registry repository (`grant-capture`, ≈ 263 MB), 3 secrets, the budget. No Cloud SQL, Cloud Run services, schedulers or Agent Runtime engines.
- `app/fast_api_app.py` is the agents-cli scaffold (ADK's `get_fast_api_app`, A2A routes). It stays as the agent server; the product UI gets its own small API.
- Node 22 and npm 10 are installed locally.

## 3. Architecture

```
web/                         React + Vite + TypeScript
  src/api.ts                 typed client for /api/*
  src/pages/Search.tsx       request box, editable plan, opportunity cards (verdict pill, why)
  src/pages/Opportunity.tsx  analyze: verdict + deciding clauses, AI-use warnings, requirements/criteria/sections/deadlines with page citations
  src/pages/Draft.tsx        section picker, notice, paragraphs with sources, unsupported highlight, gaps panel, Markdown download
  src/components/CostMeter.tsx  per-action cost and session total
api/
  main.py                    FastAPI: /api/discover, /api/analyze/{id}, /api/brief/{id}, /api/draft, /api/session; serves web/dist
  budget.py                  SessionBudget: adds each action's cost, blocks live calls past ui_session_budget_usd
  cache.py                   in-memory result cache keyed by (action, args)
Dockerfile.api               multi-stage: build web/ with Node, run api with uv + uvicorn
deployment/terraform/prod/   Cloud Run (api+ui), Agent Runtime (root agent, Analyze A2A), Cloud SQL (off by default),
                             per-agent service accounts, Secret Manager access, budget alert — validate + plan only
.github/workflows/deploy.yml manual dispatch only, `if: false`, build → plan → (apply documented, not enabled)
docs/deploy/                 01-prototype-to-production.md, 02-architecture.md, 03-runbook.md, 04-costs.md, 05-teardown.md
docs/writing/                medium-article.md, linkedin-post.md
README.md                    final
```

### 3.1 API (`api/`)
- Routes call the existing tools: `find_opportunities` (B0), `analyze_opportunity` (B0), `load_brief`, `draft_section` (default variant).
- Every response includes `cost_usd` and `session_spent_usd`. `SessionBudget` keeps one total per API process; a request that would start a live call after the total reaches `ui_session_budget_usd` returns HTTP 402 with a plain message and no call is made.
- `ResultCache` keeps analyze/draft/brief results for the life of the process; a cache hit costs $0 and is marked `cached: true`.
- Errors return JSON `{error, hint}` with an actionable hint (database down → `docker compose up -d db`; no brief → analyze first).
- CORS allows only the local Vite dev origin; the API binds to 127.0.0.1.
- Settings in `app/config.py`: `ui_session_budget_usd = 0.50`.

### 3.2 UI (`web/`)
- Three pages, plain CSS, light and dark mode, no UI kit.
- Citations render as "p. 12" chips with the quote in a tooltip; unsupported paragraphs get an amber left border and an "unsupported: check before use" label; gaps list the requirement text.
- The AI-use notice is the first element of every draft view and of the Markdown download.
- Every action button shows the expected cost range before the click and the real cost after.
- All model text is rendered as text, never as HTML.

### 3.3 Deployment design (validated, not executed)
- **Target:** Cloud Run service for API+UI (min instances 0), Agent Runtime for the root agent and for Analyze as a separate A2A service, Cloud SQL Postgres 17 + pgvector (smallest shared-core tier, `enable_cloudsql=false` by default), Secret Manager, one service account per agent with least-privilege roles, Cloud Trace, budget alert at $10 with 50/90/100% thresholds.
- **Terraform:** `deployment/terraform/prod/` reuses the foundation's state bucket with a separate prefix. Proven with `terraform init` + `validate` + `plan -out` (plan output saved to `docs/deploy/evidence/terraform-plan.txt`, secrets redacted). `apply` is never run.
- **CI:** `deploy.yml` runs on `workflow_dispatch` only and its jobs have `if: false`; the file documents each step and how to enable it (Workload Identity Federation, already set up in M0).
- **Docs** teach: what changes between prototype and production (identity, secrets, data, scaling, observability, evals as a release gate, cost guardrails, rollback), the architecture with a diagram, a numbered runbook (command → what it does → how to check → how to undo), a monthly cost table (idle vs light use), and teardown.

### 3.4 Shutdown
1. Re-run the inventory (buckets, Artifact Registry, secrets, Cloud Run, Cloud SQL, schedulers, Agent Runtime, BigQuery).
2. Present deletions for approval: Artifact Registry images (`grant-capture`), Cloud Build bucket contents, and the raw-data bucket (re-downloadable).
3. Keep: Terraform state bucket, secrets, budget (≈ $0.20/month together) so the project can resume.
4. Confirm no new Gemini usage in Cloud Monitoring after the final session.
5. Document (not perform) how to disable billing for the project.

## 4. Testing
- `tests/unit/test_api.py`: each route with fake tools; budget block returns 402 without calling the tool; cache hit costs $0; error JSON has a hint.
- `web/src/**/*.test.tsx` (Vitest + Testing Library): notice renders first; unsupported paragraph gets the warning label; gaps render requirement text; cost meter adds costs; model text with `<script>` renders as text.
- Docker build and `terraform validate` are run once and their output saved as evidence.

## 5. Cost
| Item | Estimate |
|---|---|
| Building UI, API, Terraform, docs | $0 |
| Live UI checks (a few searches, 1–2 analyses, 1–2 drafts) | ≈ $0.05–0.20, capped at $0.50 per API session |
| `terraform plan`, `docker build` | $0 |
| After shutdown | ≈ $0.20/month (state bucket, secrets) |

## 6. Changes to existing decisions
- ADR-0012 (runtime choice): updated with the concrete target and the decision to design, validate and stop.
- ADR-0021: deployment designed to production standard, validated with `terraform plan`, not executed; reasons (cost, learning goal) and what a funded M4b would do.
- System design §10: the UI is live-only with a session cap; `api/` is separate from the agent server.
