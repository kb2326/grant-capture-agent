# M3 Draft: specification

| | |
|---|---|
| Status | In review |
| Date | 2026-10-10 |
| Parent design | [`system-design.md`](system-design.md) §6, §7.6–7.7, §8.0, §8.4, §17 |
| Branch | `m3-draft` |
| Decisions | ADR-0018 (outcome recorded here) |

## 1. Goal

Given one proposal section (title, instructions, the requirements it must answer and the evaluation criteria), write a draft that:

1. cites the company's own documents for every claim (`[Cn]` labels mapped to chunks);
2. lists as **gaps** the requirements the company has no evidence for, instead of inventing evidence;
3. marks every sentence its citations do not support (`supported=false`).

Then measure it, and let the ablation decide between **B0** (long context: the whole company corpus in one call) and **B1** (corrective RAG: retrieve → grade → rewrite ≤ 2 → evidence or gap).

M3 runs **cost-minimal**: drafting and judging use Flash, grading uses Flash-Lite, the whole milestone is budgeted at **≤ $2.50**, and every paid run has a hard cap in code.

### Acceptance criteria

| # | Criterion | Target / evidence |
|---|---|---|
| A1 | Corpus expanded | ≥ 75 company docs: the 13 originals + ≈ 35 on-topic, ≈ 15 outdated, ≈ 15 off-topic; `data/company/manifest.json` lists each doc's kind, topics and facts; a test checks every manifest fact appears verbatim in its doc and the facts table is never contradicted by an on-topic doc |
| A2 | Corpus indexed | every company doc stored (`corpus='company'`), chunked by heading, chunks embedded with `gemini-embedding-001` |
| A3 | Draft task set | 12 controlled tasks (≈ 45 requirements, ≈ 15 deliberate gaps) in `evals/data/golden/draft_tasks.jsonl`, each supported requirement linked to manifest fact ids; reviewed by the user |
| A4 | Grader calibrated | the user labels 40 (requirement, chunk) pairs; Cohen's κ between the user and the Flash-Lite grader reported (target ≥ 0.6; one prompt revision allowed if below) |
| A5 | B0 and B1 drafting | both produce `DraftSection` with valid citations and requirement-id gaps on all 12 tasks |
| A6 | Metrics | gap recall/precision, evidence recall, citation validity, distractor-citation rate (code, from the manifest); faithfulness (Flash judge, silver) and B1 context precision; p50/p95 latency; $ per section; in `reports/m3/ablation.md` |
| A7 | Decision | ADR-0018 outcome written |
| A8 | Workflow | ADK 2 workflow: select sections → draft → `approve_draft` interrupt → Markdown export; `draft_section` agent tool |
| A9 | MCP server | FastMCP server exposing `search_opportunities`, `get_brief`, `check_eligibility`, `draft_section`; registered in the project's `.mcp.json` and called once from Claude Code |
| A10 | Demo | 2 real solicitations drafted end to end (not scored) |
| A11 | Spend | M3 Gemini spend ≤ $2.50, measured |

### Out of scope (moved to M4)
Sensitive Data Protection redaction of bios, Gen AI evaluation service autoraters, DOCX export, hybrid requirement extraction (ADR-0016 follow-up), Gemini Pro drafting.

## 2. Facts measured before design (2026-10-10)
- 13 company docs (≈ 6,250 words, ≈ 9k tokens) in `data/company/docs/`, written from the authoritative facts table in the M0 plan (Task 9). Deliberate gaps: no past work on **hydrogen, cybersecurity or offshore wind**. None is loaded into the database yet.
- 4 stored solicitation briefs. M2's `rag/` (embedders, RRF SQL pattern) is reusable.

## 3. Architecture

```
data/company/
  docs/                     13 originals + ≈ 67 generated (.md)
  corpus_plan.json          the topic plan the generator follows (checked in)
  manifest.json             doc -> {kind, topics, facts:[{id, text}]}
ingest/company_corpus.py    generate (Flash) | check | load (documents + heading chunks + embeddings)
rag/chunks.py               search_chunks(): hybrid search over chunks of one corpus (same RRF pattern as rag/search.py)
app/draft/
  contracts (app/contracts.py)  DraftTask, TaskRequirement, Paragraph, RetrievalAttempt, DraftSection
  corpus.py                 load company chunks, label them [C1..Cn]
  b0_long.py                long-context drafting with a Gemini context cache
  b1_crag.py                per requirement: queries -> search_chunks -> grade -> rewrite <= 2 -> evidence | gap
  grade.py                  Flash-Lite grader: (requirement, chunk) -> relevant | partly | not
  generate.py               Flash writes the section from labeled chunks; validates [Cn]
  faithfulness.py           Flash judge: sentence + cited chunks -> supported | unsupported
  service.py                draft(task, variant) -> DraftSection (+ cost, latency)
  workflow.py               ADK 2 graph with approve_draft interrupt; export Markdown
  tools.py                  draft_section(opportunity_id, section_title, variant="B0")
mcp_server/                 FastMCP server (stdio), .mcp.json at repo root
evals/
  draft_tasks.py            draft the task set (Flash) from the manifest; user reviews
  grader_label.py           local page: user labels 40 pairs -> evals/data/golden/grader_pairs.jsonl
  suites/draft.py           code metrics + judge metrics + decision rule
  draft.py                  CLI stages: tasks | run | judge | kappa | report
```

### 3.1 Corpus generation (`ingest/company_corpus.py generate`)
- `corpus_plan.json` (written by hand in the plan) lists ≈ 67 docs: file name, kind (`on_topic`, `outdated`, `off_topic`), topic, length, and the facts it must state.
  - **On-topic:** more past proposal sections, quarterly progress reports, test reports, white papers, two more bios, letters of support, an updated capability statement. All agree with the facts table.
  - **Outdated:** the same kinds of documents dated 2020–2022 with superseded numbers (for example 18 employees, an LGL-BMS2 with ±5 mV balancing, a 900 sq ft lab). Each states its date.
  - **Off-topic:** documents a real company keeps that do not help a proposal (office lease summary, travel policy, holiday schedule, a marketing flyer for a discontinued consumer charger, meeting minutes on parking).
  - The gap topics (hydrogen, cybersecurity, offshore wind) appear in no document.
- Flash writes one doc per call in the existing style (synthetic-data banner line, plain English, concrete numbers), given the facts table and that doc's plan entry.
- `check` (code, also a unit test over the checked-in files) verifies:
  - every manifest fact appears verbatim in its doc;
  - no on-topic doc contains an outdated value from a deny-list;
  - no doc mentions a gap topic.
- Generated docs are checked in. The generator never overwrites an existing file.

### 3.2 Loading and search
- `load` stores each doc as `documents(corpus='company', opportunity_id NULL)` via the blob store.
- It chunks by Markdown heading: sections over ≈ 800 tokens are split on paragraphs, and sections under ≈ 80 tokens are merged into the next. Each chunk's `section_path` is `doc title > heading`.
- `load` is idempotent by sha256 and embeds chunks with `GeminiEmbedder` (`chunks.embedding`).
- `rag/chunks.py search_chunks(session, *, query_text, query_vec, corpus, k=8)` uses the M2 RRF statement over `chunks` joined to `documents`, filtered by corpus.

### 3.3 Contracts (`app/contracts.py`)
```python
class TaskRequirement(BaseModel): id: str; text: str          # "R1".."Rn"
class DraftTask(BaseModel): id: str; section_title: str; instructions: str
    requirements: list[TaskRequirement]; criteria: list[str] = []; opportunity_id: UUID | None = None
class Paragraph(BaseModel): text: str; citations: list[UUID]; supported: bool | None = None
class RetrievalAttempt(BaseModel): requirement_id: str; query: str; chunk_ids: list[UUID]; grades: list[str]
class DraftSection(BaseModel): task_id: str; variant: Literal["B0","B1"]; paragraphs: list[Paragraph]
    gaps: list[str]                      # requirement ids with no evidence
    retrieval_trace: list[RetrievalAttempt] = []; tokens_in: int = 0; tokens_out: int = 0
    cost_usd: float = 0.0; latency_s: float = 0.0
```
The model-facing schema uses chunk labels (`"C12"`) and requirement ids. Code maps labels to chunk UUIDs, and an unknown label fails validation, which triggers one retry with the error.

### 3.4 B0: long context (`b0_long.py`)
- All company chunks, labeled `[C1]..[Cn]` with their `section_path`, go into a Gemini **context cache** (TTL 30 min, model `model_agent`) built once per run.
- Each section is one call: task + requirements + rules ("cite every claim; list unsupported requirement ids in `gaps`; never use a document dated before 2023 when a newer one exists").
- If the cache has expired, the call is retried uncached (same pattern as M1 Q&A).

### 3.5 B1: corrective RAG (`b1_crag.py`, `grade.py`)
- For each requirement:
  1. Flash writes 2 short queries (one call per section, for all its requirements).
  2. `search_chunks` returns the top 8.
  3. The Flash-Lite grader labels each (requirement, chunk) as `relevant`, `partly` or `not`, with a reason, one batched call per requirement.
  4. If fewer than 2 chunks are `relevant`, Flash rewrites the query from the grader's reasons, at most 2 times.
  5. The requirement ends as evidence (its relevant chunks) or a gap.
- Generation sees only the relevant chunks, labeled `[C1]..`, plus the list of gap requirement ids it must report.
- The retrieval trace is stored.

### 3.6 Faithfulness (`faithfulness.py`)
- Paragraphs are split into sentences.
- The Flash judge receives each paragraph's sentences with the text of their cited chunks (one call per section) and answers `supported`, `unsupported` or `no_claim` per sentence.
- A paragraph is `supported=false` if any sentence with a claim is unsupported.
- The faithfulness score is supported claims / all claims. A claim sentence without citations counts as unsupported.

### 3.7 Workflow and tools
- **ADK 2 graph:** `load_brief` (from `solicitation_briefs`, or analyze on demand) → `select_sections` (all required sections by default, or the requested ones) → `draft` (one node, sections in sequence) → `approve_draft` (interrupt: "ok", or edit text, or reject) → `export` (Markdown to `data/drafts/<opportunity>.md` + `drafts` rows with status).
- `draft_section(opportunity_id, section_title, variant="B0")` agent tool. For a real solicitation, requirements come from the brief's requirements whose page or section matches, and fall back to all requirements, at most 8.
- The default variant is set by the ablation result.

### 3.8 MCP server (`mcp_server/`)
- FastMCP over stdio, exposing `search_opportunities` (→ `find_opportunities`), `get_brief`, `check_eligibility` (→ verdict only) and `draft_section`.
- Each tool returns compact JSON.
- `.mcp.json` at the repo root registers it as `grant-capture` (`uv run python -m mcp_server`).
- Verified once by calling a tool from Claude Code.

## 4. Draft task set and labels

### 4.1 Tasks (`evals/draft_tasks.py`)
- Flash drafts 12 tasks from the manifest: section types such as technical approach, past performance, key personnel, facilities, commercialization and relevant experience.
- Each task has 3–5 requirements. ≈ 15 of the ≈ 45 are gaps, drawn from the gap topics or from capabilities the company lacks.
- Each supported requirement lists `support` fact ids. Code checks those ids exist and that gap requirements share no topic with any on-topic doc.
- The user reviews the tasks once. The file is then frozen.

### 4.2 Grader calibration (`evals/grader_label.py`)
- 40 pairs are sampled from B1's retrieval traces, stratified by the grader's own label (≈ 14 relevant, 13 partly, 13 not).
- A local page (FastAPI, same pattern as the M1 labeling page) shows the requirement and the chunk without the grader's label. The user clicks relevant / partly / not.
- κ is reported both 3-class and binary (relevant vs. not-relevant).

## 5. Evaluation (`evals/suites/draft.py`, `evals/draft.py`)

| Metric | How | Source |
|---|---|---|
| Gap recall / precision | gold gap ids vs. `DraftSection.gaps` | code |
| Evidence recall | supported requirement counts as covered if a cited chunk contains one of its support facts verbatim | code |
| Citation validity | share of citations that map to real chunks | code |
| Distractor-citation rate | share of citations pointing at outdated or off-topic docs | code + manifest |
| Faithfulness | supported claims / claims | Flash judge (silver) |
| Context precision (B1) | share of chunks passed to generation that the draft actually cites | code |
| Latency, cost | p50/p95 s, $ per section | measured |

**Decision rule (ADR-0018):**
- B1 is kept only if it improves gap recall, evidence recall or faithfulness by ≥ 0.05, without more than doubling $ per section or p95 latency.
- An increase under $0.005 or under 2 s is always acceptable.
- Ties go to B0, the simpler design.

## 6. Error handling
- **Unknown citation label:** one retry with the error, then the paragraph is dropped and the requirement is listed as a gap with the note "drafting failed".
- **Grader call fails:** those chunks count as not graded and are never used as evidence.
- **Context cache:** if it has expired or can't be created, the call runs uncached.
- **Budget:** every stage stops at `draft_eval_budget_usd` (default $1.00), counts failed calls, and can resume from saved results.
- **Corpus generation:** an existing file is never overwritten. A doc that fails `check` is regenerated once, then left out with a note.

## 7. Testing
- **Unit:**
  - heading chunker (split and merge);
  - manifest check;
  - label ↔ UUID mapping and validation;
  - gap and rewrite-cap logic in B1, using a fake grader;
  - faithfulness aggregation;
  - every metric on hand-computed examples;
  - κ (existing `cohen_kappa`);
  - approval parsing;
  - MCP tool registration.
- **DB:** company load is idempotent; `search_chunks` filters by corpus.
- **Never:** assertions on LLM text.
- **Smoke:** an offline `draft_smoke` suite scores saved fixture drafts.

## 8. Cost (estimate, enforced by caps)

| Item | Estimate |
|---|---|
| Generate ≈ 67 docs (Flash, ≈ 1.2k output tokens + thinking each) | ≈ $0.50 |
| Embed ≈ 600 chunks | ≈ $0.02 |
| Draft 12 tasks (Flash) | ≈ $0.02 |
| B0: 12 sections over a ≈ 75k-token cached corpus | ≈ $0.30 |
| B1: queries, grading, rewrites, generation | ≈ $0.20 |
| Faithfulness judge on both variants | ≈ $0.10 |
| Demo on 2 real solicitations (plus up to 2 Analyze runs) | ≈ $0.15 |
| **Total** | **≈ $1.30, cap $2.50** |

## 9. Changes to existing decisions
- ADR-0018: outcome recorded.
- System design §6 `DraftSection` gains `task_id`, `variant`, requirement-id gaps, tokens/cost/latency. §8.4 drafting uses Flash during the prototype; Pro is revisited in M4.
