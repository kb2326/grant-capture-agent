# grant-capture-agent

**AI grant capture for small R&D companies: find federal funding you can win, rule out what you can't, and draft the proposal from your own evidence.**

An open, measured rebuild of the grant-capture workflow pioneered by SweetSpot AI, built on Google ADK and Gemini Enterprise Agent Platform.

> **Status: v1 rebuild in progress (started Oct 2026).** The design phase is under way. The v0 prototype is preserved in [`legacy/`](legacy/) and under the git tag `v0-besi-prototype`.

## What it does

| Module | The question it answers | How |
|---|---|---|
| **Discover** | "Which open opportunities fit what we do?" | Plan-Execute-Verify agents on ADK over a hybrid-search index of Grants.gov, SBIR.gov and SAM.gov |
| **Analyze** | "Are we even eligible, and what does this solicitation require?" | Solicitation agent: the LLM extracts each clause, rules decide the knockouts, and every verdict quotes its source |
| **Draft** | "Write the technical section using only our real evidence." | Corrective RAG over company documents: grade the retrieved passages, re-query when evidence is weak, cite every claim, flag gaps |

A person approves the search plan and every draft. The system never submits anything.

## How it's being built

The project follows the same steps an AI product team would: PRD → system design → decision records → eval sets → plan → test-first build → deploy → eval report. Every metric is measured on labeled data before it is claimed.

**Planned stack:** Google ADK 2.x · agents-cli · Gemini 3.x · Gen AI SDK · Cloud SQL Postgres + pgvector · Docling · Vertex AI Ranking API · MCP (Toolbox for Databases + a custom server) · Agent Runtime · Model Armor · Cloud Run · Terraform · GitHub Actions · Cloud Trace

## Repository layout

```
docs/
  guide/          project field guide (plain-language overview of the whole build)
  reference/      public API specs (Simpler Grants, SBIR.gov)
legacy/
  v0-besi-prototype/   first prototype (Nov–Dec 2025), kept for comparison
```

The v1 source tree (`app/`, `rag/`, `evals/`, `deploy/`) will be added in milestone M0.

## Roadmap

- [ ] **M0 Foundation:** scaffold, ingestion job, Postgres schema, CI, eval harness
- [ ] **M1 Analyze:** parsing, Solicitation agent, knockout rules, 25+ hand-labeled solicitations
- [ ] **M2 Discover:** hybrid search, reranking, PEV workflow with an approval step, timing benchmark
- [ ] **M3 Draft:** corrective RAG, faithfulness check, MCP server
- [ ] **M4 Ship:** Agent Runtime deployment, web UI, tracing, CI eval gate, red-team set, eval report

## Author

Karthick Balaje · [LinkedIn](https://linkedin.com/in/karthickbalajege) · [Medium](https://medium.com/@karthickbalaje01)
