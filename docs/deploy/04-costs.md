# 4. What it would cost

Prices change; treat these as order-of-magnitude estimates and check the current Google Cloud price pages before a real deployment. Gemini costs per action are **measured** in this project (M1-M3 reports); infrastructure costs are list-price estimates for `us-central1`.

## Monthly cost if deployed

| Service | Idle (nobody uses it) | Light demo use (a few sessions a week) | Notes |
|---|---|---|---|
| Cloud Run (API + UI) | ≈ $0 | ≈ $0-1 | scale to zero; the free tier covers small traffic |
| Agent Runtime (root + Analyze) | **several $/month to tens of $/month** | same | billed per vCPU and memory hour while instances run; the biggest uncertainty, so deploy only for the demo window |
| Cloud SQL Postgres, smallest tier | **≈ $7-10** | ≈ $7-10 | bills every hour it exists, even idle; this is why it is off by default |
| Artifact Registry (images) | ≈ $0.10-0.30 | same | the production image is about 2 GB |
| Cloud Storage (raw files, state) | ≈ $0.05 | same | |
| Secret Manager (3 secrets) | ≈ $0.18 | same | |
| Cloud Logging / Trace | ≈ $0 | ≈ $0 | within free allotments at this volume |
| **Gemini** | $0 | see below | pay per call only |

## Gemini per action (measured)

| Action | Cost | Source |
|---|---|---|
| Discover search (plan + hybrid search) | ≈ $0.003 | M2 report |
| Analyze one solicitation (whole documents) | ≈ $0.04 | M1 report |
| Draft one section (long context, cached corpus) | ≈ $0.04-0.08 with thinking uncapped; lower with `draft_thinking_budget=1024` (not yet measured) | M3 report |
| Re-embed all opportunity cards | ≈ $0.22 | M2 |
| Embed the company corpus | ≈ $0.01 | M3 |

A typical demo session (5 searches, 2 analyses, 2 drafts) is about **$0.25** of Gemini. The local UI's session cap is $0.50.

## Reality check: what the prototype actually spent

| Milestone | Gemini spend (Cloud Monitoring token counts) | Biggest driver |
|---|---|---|
| M1 Analyze | ≈ $8.60 | AI labeling with the Pro model, page-window ablation |
| M2 Discover | ≈ $1.02 | Flash planning (thinking tokens), embeddings |
| M3 Draft | ≈ $1.6-2.0 | Flash thinking tokens in long-context drafting |
| M4 (free part) | ≈ $0.1 (one live UI check) | |

October's total went over the $10 monthly target. Two lessons are built into the code now: thinking tokens are billed as output (drafting caps them), and an alert does not stop spend (caps in code do).

## The cheapest way to show it working
1. Keep everything local (Docker database, local API and UI): infrastructure $0, Gemini only per action.
2. If a public URL is needed for a few days: Cloud Run + Cloud SQL for that window only (≈ $0.30/day for the database), Agent Runtime skipped (the API calls the agents in-process, which our code already supports), then tear down.
3. Full production layout (Agent Runtime + A2A + Cloud SQL around the clock): budget tens of dollars a month.
