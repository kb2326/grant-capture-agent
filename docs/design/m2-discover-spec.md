# M2 Discover: specification

| | |
|---|---|
| Status | In review |
| Date | 2026-10-09 |
| Parent design | [`system-design.md`](system-design.md) §7.3–7.5, §8.0, §8.1, §11 |
| Branch | `m2-discover` |
| Decisions | ADR-0005 (re-tested here), ADR-0017 (outcome recorded here), ADR-0020 (new: embedding choice) |

## 1. Goal

Given a request in plain English ("SBIR work on grid-forming inverters"), return a short, ranked list of **open opportunities the company can actually go after**, each with a one-sentence reason that quotes the opportunity text. Measure how good the list is, and let the measurements pick the architecture:

1. **Embeddings:** `gemini-embedding-001` (cloud) vs. EmbeddingGemma (local, free).
2. **Rerank:** Vertex AI Ranking API vs. no rerank.
3. **Workflow (ADR-0017):** single pass (B0) vs. Plan → Execute → Verify with refinement (B1).

M2 runs **cost-minimal**: it is a learning prototype, the whole milestone is budgeted at **≤ $2**, and every paid run has a hard cap in code.

### Acceptance criteria

| # | Criterion | Target / evidence |
|---|---|---|
| A1 | Every opportunity has a card | `opportunity_cards` row for 100% of `opportunities`; text hash stored |
| A2 | Cards embedded by both models | `emb_gemini` and `emb_local` non-null for 100% of cards |
| A3 | Hybrid search | dense + sparse fused with RRF in one SQL statement; DB test on seeded cards |
| A4 | Query set | 20 queries (15 golden, 5 dev), ≥ 5 golden labeled `vague` |
| A5 | Relevance labels | pooled top results per golden query labeled 0/1/2 (silver, AI labeler); stored in `evals/data/golden/discover_qrels.jsonl` |
| A6 | Retrieval metrics | P@10, nDCG@10, Recall@20 reported overall and on the vague slice, per arm |
| A7 | Three ablations | embeddings, rerank, B0 vs. B1: quality, p50/p95 latency, $ per request in `reports/m2/ablation.md` |
| A8 | Decisions recorded | ADR-0017 outcome; ADR-0020 (embedding) written |
| A9 | Approval step | ADK 2 workflow pauses at `approve_plan`; resumes with the approved or edited plan |
| A10 | Analyze over A2A (local) | Analyze exposed with ADK `to_a2a`; Discover's V4 check calls it; test with the service down |
| A11 | Preferences | plan edits and rejected candidates become stored preferences that the next plan reads |
| A12 | Spend | M2 Gemini spend ≤ $2, measured from Cloud Monitoring token counts |

### Out of scope (and where it goes)
- Deployed A2A service on Agent Runtime and Vertex Memory Bank → M4 (deploy). M2 uses the same ADK interfaces locally.
- Chunk-level search over attachments → only if the eval shows misses that the cards cannot fix (would be M3).
- Live API fallback when the index is stale → M4 (nightly job keeps the index fresh).
- Hand-labeled golden queries → the silver set is accepted for the prototype (same caveat as M1).

## 2. Facts measured before design (2026-10-09)

- Local DB: 2,737 opportunities (1,537 SAM.gov, 1,200 Grants.gov; 36 SBIR/STTR). Average summary ≈ 3,000 characters.
- 545 parsed documents → 12,782 chunks, none embedded. Only ~20% of opportunities have parsed documents, so attachments are not a usable search surface yet.
- One synthetic company, Lumen Grid Labs (for-profit, 32 employees, CO, 2 SBIR Phase I awards; capabilities in battery management, SiC/GaN converters, grid-forming inverters). Its `preferences` hold `min_award_usd: 50000` and `exclude_agencies`.
- M1 spent ≈ $8.60 of the $10/month budget.

## 3. Architecture

```
rag/                       pure Python, no ADK imports
  card.py                  build_card(opportunity) -> CardText (text, hash)
  embed.py                 Embedder protocol; GeminiEmbedder, LocalEmbedder
  search.py                hybrid_search(session, query_vec, query_text, filters, column, k) -> list[Hit]
  rerank.py                Reranker protocol; VertexRanker, NoRerank
  __main__.py              build-cards, embed --model gemini|local
db/                        opportunity_cards table + Alembic migration; preferences table
app/discover/
  plan.py                  Flash → SearchPlan
  execute.py               SearchPlan → list[Candidate]
  refine.py                (B1) SearchPlan + VerificationReport.feedback → SearchPlan
  service.py               discover(request, variant, ...) -> DiscoverResult   (B0 / B1 loop)
  workflow.py              ADK 2 graph with approve_plan interrupt
  a2a_client.py            ask the Analyze A2A service for a verdict
app/rules/verify.py        V1–V5, plain Python → VerificationReport
app/analyze/a2a_app.py     Analyze agent exposed with to_a2a (local port 8001)
app/memory.py              preferences: read/write table + ADK in-memory memory service
app/agent.py               new tool find_opportunities
```

### 3.1 Opportunity cards (`rag/card.py`)
Card text = `title | agency | kind | status | close date | assistance listings | NAICS` + the summary with HTML stripped, truncated to 2,000 tokens (estimated as characters / 4). `hash = sha256(text)`. Re-running `build-cards` updates only rows whose hash changed, and clears their embeddings so they are re-embedded.

### 3.2 Embeddings (`rag/embed.py`)
- `GeminiEmbedder`: `gemini-embedding-001`, 768-d, `us-central1`, task types `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`, batches of 100, retries on 429/5xx, records tokens and cost.
- `LocalEmbedder`: EmbeddingGemma via `sentence-transformers` on CPU, 768-d, using the model's document/query prompts. The model ID lives in `app/config.py` (`model_embedding_local`); the first task of the plan verifies which EmbeddingGemma release is downloadable and pins it.
- One quick check that `gemini-embedding-2` still returns 404; if it now works it is noted in ADR-0020 but not added as an arm (cost).
- Both vectors live in `opportunity_cards` (`emb_gemini vector(768)`, `emb_local vector(768)`), each with an HNSW cosine index. The model and dimension are recorded per column in a migration comment and in config.

### 3.3 Hybrid search (`rag/search.py`)
One SQL statement, two CTEs over `opportunity_cards` joined to `opportunities`:
- dense: top 50 by cosine distance on the chosen embedding column;
- sparse: top 50 by `ts_rank_cd(tsv, websearch_to_tsquery('english', :q))`;
- fused with RRF, `score = Σ 1/(60 + rank)`, top `k` returned.
Filters (applied in both CTEs): `kind IN`, `status IN` (default open, forecasted), `close_at >= today + min_days_to_close` (null close dates pass), `agency NOT IN exclude`.

### 3.4 Rerank (`rag/rerank.py`)
`VertexRanker` uses the Vertex AI Ranking API (`semantic-ranker-default-004`) on the top 30 fused hits, using card text. On any error it returns the fused order with `reranked=False`; a request never fails because of reranking. `NoRerank` returns the fused order.

### 3.5 Contracts (`app/contracts.py`)
`SearchQuery`, `SearchPlan`, `Candidate`, `Rejection`, `VerificationReport` exactly as in system design §6, plus:
- `Candidate.reranked: bool`, `Candidate.eligibility: Literal["ELIGIBLE","INELIGIBLE","NEEDS_REVIEW","unchecked"]`.
- `DiscoverResult(plan, candidates, rejected, iterations, usage)`.
`Candidate.why` cites a passage of the card (opportunity text); `matched_chunks` stays empty in M2.

### 3.6 Verify rules (`app/rules/verify.py`)
V1 status open/forecasted · V2 days to close ≥ `min_days_to_close` · V3 rerank score ≥ τ (τ tuned on the 5 dev queries; skipped when not reranked) · V4 no `INELIGIBLE` verdict for the company (cached verdict first; otherwise ask Analyze over A2A for at most 5 top candidates per request; if the service is down the candidate is marked `unchecked` and kept) · V5 no duplicate `source_id`. `K = 5`; every rejection records its `rule_id`.

**V4 cost guard:** Analyze costs ≈ $0.04 per solicitation, so V4 is **off in evals** (it would measure Analyze, not Discover) and on in the workflow, capped at 5 calls per request.

### 3.7 Workflows (`app/discover/service.py`, `workflow.py`)
- **B0:** plan → execute → verify → present (top 10 that pass).
- **B1:** plan → execute → verify → if fewer than K pass and iteration < 3: refine → execute → verify; stops early if the refined plan's queries equal an earlier plan's.
- ADK 2 graph: `plan → approve_plan (interrupt; user may edit) → execute → verify → [refine | present]`. Evals call `service.discover()` directly with auto-approval.
- Models: planning and refinement use `model_agent` (Flash). The `why` sentences for the top 10 come from one extra Flash call per request (in evals they are produced but not scored).

### 3.8 Preferences (`app/memory.py`)
- Stored in a `preferences(company_id, kind, value, source, created_at)` table: `exclude_agency`, `min_award_usd`, `avoid_topic`, `prefer_topic`.
- Written when the user edits a plan (removed agency → `exclude_agency`) or rejects a candidate with a reason; also loaded into ADK's `InMemoryMemoryService` so the agent can `load_memory` them in chat.
- The planner prompt receives the current preferences; `exclude_agency` and `min_award_usd` are also applied as hard search filters.

### 3.9 Analyze over A2A (local)
`app/analyze/a2a_app.py` wraps the existing Analyze agent with `google.adk.a2a.utils.agent_to_a2a.to_a2a` and serves it with uvicorn on port 8001. `a2a_client.py` sends "analyze opportunity <id> for company <id>" and parses the returned verdict JSON. Timeout 120 s.

## 4. Query set and labels

### 4.1 Queries (`evals/data/golden/discover_queries.jsonl`, dev in `evals/data/dev/`)
20 queries drafted once by Flash from the company profile, then reviewed by the user: 10 specific, 5 vague ("funding for our power electronics work"), 5 dev. Fields: `id, text, slice (specific|vague), split (golden|dev)`. Committed after review; never edited after labeling.

### 4.2 Relevance labels (`evals/discover_label.py`)
- Pool: union of the top 10 from every arm (2 embeddings × rerank on/off × B0/B1, B1 only for its final plan) per golden query, capped at 30 candidates per query.
- Labeler: `model_grader` (`gemini-3.5-flash-lite`), different from the system's planner, with its own prompt; judges each (query, company capabilities, card) as 2 relevant / 1 partly / 0 not relevant, with a short reason.
- Unpooled results count as not relevant (standard pooling assumption, stated in the report).
- File header `_meta: {labeler, silver: true}`.
- Spot check: the user reviews 20 random labels on the existing labeling page; agreement is reported.

## 5. Evaluation (`evals/suites/discover.py`, `evals/discover_ablation.py`)

- Metrics: **P@10** (label ≥ 1 counts as relevant), **nDCG@10** (graded gains 0/1/2), **Recall@20** (of all pooled label-2 items), p50/p95 latency, $ per request; overall and on the vague slice.
- Arms (each run once on the 15 golden queries):

| Ablation | Arms | Fixed |
|---|---|---|
| Embeddings | gemini vs. local | no LLM: query text searched directly, no rerank |
| Rerank | on vs. off | winning embedding, no LLM |
| Workflow | B0 vs. B1 | winning embedding + rerank setting |

- Decision rule: a richer arm is kept only if it improves nDCG@10 by ≥ 0.03 overall or on the vague slice without more than doubling $ per request or p95 latency. Ties go to the simpler or cheaper arm.
- Report: `reports/m2/ablation.md` with the three tables, the silver-set and pooling caveats, and the decision.

## 6. Error handling
- Embedding failure while indexing: the batch is retried; persistent failures leave the row null and are counted; the run continues.
- Query-time embedder unavailable (local model not loaded): fall back to the other column and log it.
- Ranking API failure: fused order, `reranked=False`.
- Empty search result: B0 returns an empty list with the plan; B1 refines.
- A2A unreachable or slow: `eligibility="unchecked"`.
- Planner returns invalid JSON: one retry, then a plan of one query equal to the request text.
- Budget: `run_cases` stops at `eval_budget_usd` (counting failed calls), resumable.

## 7. Testing
- Unit: card text and hash; RRF fusion math; verify rules V1–V5; refine stop conditions (cap and repeated plan); metric math (P@10, nDCG@10, Recall@20) on hand-computed examples; preference extraction from a plan edit; reranker fallback; A2A client timeout → `unchecked`.
- DB (`tests/db`): migration; hybrid search over 10 seeded cards with known vectors finds the expected top hit for a dense-only query, a keyword-only query and a filter.
- No assertions on LLM text. A 3-query smoke evalset for `agents-cli eval run`.

## 8. Cost (estimate, enforced by caps)

| Item | Estimate |
|---|---|
| Embed 2,737 cards with gemini-embedding-001 (≈ 2M tokens) | ≈ $0.30 |
| Local embeddings | $0 |
| Draft 20 queries (Flash) | < $0.01 |
| Relevance labels, ≈ 15 × 30 judgments (Flash-Lite) | ≈ $0.10 |
| Ranking API, ≈ 200 calls | ≈ $0.20 |
| B0 + B1 runs, 15 queries (Flash planner, ≤ 4 calls each) | ≈ $0.20 |
| **Total** | **≈ $0.80, cap $2** |

## 9. Changes to existing decisions
- ADR-0005: re-tested; superseded by ADR-0020 only if EmbeddingGemma wins.
- ADR-0017: outcome recorded.
- System design §6 contracts gain the fields in §3.5; §8.1 V4 gains the cost guard.
