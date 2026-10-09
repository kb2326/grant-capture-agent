# M1 Analyze: specification

| | |
|---|---|
| Status | In review |
| Date | 2026-10-09 |
| Parent design | [`system-design.md`](system-design.md) §8.0, §8.2, §8.3, §11, §17 |
| Branch | `m1-analyze` |
| Decisions | ADR-0004 (updated by this spec), ADR-0006, ADR-0016 |

## 1. Goal

Given one opportunity, produce:

1. A **solicitation brief**: eligibility clauses, "shall" requirements, evaluation criteria, required sections, page limits and deadlines. Every item carries a verbatim quote, its document and its page.
2. An **eligibility verdict** for the company (`ELIGIBLE`, `INELIGIBLE`, `NEEDS_REVIEW`), decided by deterministic rules, citing the clause that decided it.
3. **Measured quality** on hand-labeled golden sets, including the B0 (whole-document long context) vs. B1 (page-window chunked) comparison.

### Acceptance criteria

| # | Criterion | Target / evidence |
|---|---|---|
| A1 | Text layer stored for every stored document | `documents.parse_status` is `parsed` or `no_text_layer` for 100% of rows; chunks exist per page |
| A2 | Golden knockout set | ≥ 30 solicitations labeled by the user, ≥ 10 labeled `INELIGIBLE` |
| A3 | Golden requirements set | 10 solicitations with every proposer "shall/must/will" statement listed |
| A4 | Knockout flagged recall (INELIGIBLE caught as INELIGIBLE or NEEDS_REVIEW) | ≥ 0.95 reported |
| A5 | Knockout strict precision (predicted INELIGIBLE that are labeled INELIGIBLE) | ≥ 0.85 reported |
| A6 | Requirement recall | ≥ 0.85 reported |
| A7 | Quote fidelity | 100% of stored quotes verbatim on their cited page (enforced) |
| A8 | B0 vs. B1 ablation | Quality, p50/p95 latency, tokens and cost reported; winner recorded in ADR-0016 |
| A9 | Analyze workflow runs end to end in ADK | `agents-cli run "Analyze <opportunity id>"` returns a brief and a verdict; follow-up Q&A answers with page citations |
| A10 | Tests | Unit tests for every rule, the quote checker, the parsers and the metric matchers; CI green |

Targets are reported as measured. A miss is reported honestly together with its failure analysis; numbers are never tuned on the golden set.

### Out of scope (and where it goes)

- Embeddings and search: **M2**. M1 needs none; EmbeddingGemma 2 is compared with `gemini-embedding-001` in M2.
- OKF packaging of company knowledge: revisit at the start of **M3**, when the Draft agent consumes company evidence.
- A2A deployment of Analyze: **M2** (ADR-0013).
- Docling and Document AI Layout Parser for PDFs: **M5** comparison on a ~300-page sample.

## 2. Facts measured before design (2026-10-09)

| Fact | Value |
|---|---|
| Stored documents | 736 across 513 opportunities: 357 PDF, 320 HTML, 58 DOCX, 1 DOC |
| Documents per opportunity | median 1, p90 2, max 8 |
| PDF length | median 26 pages, p90 68, p99 112, max 166; 10,691 pages total |
| Text density | about 590 tokens per page; about 3% of sampled PDFs have no text layer |
| Docling PDF pipeline (CPU, warm) | 2.46 s/page, so about 7.3 h for the corpus |
| pypdf text layer | 0.066 s/page, so about 12 min for the corpus |
| Largest package | about 100k tokens, inside Gemini's context window |
| Document AI Layout Parser | $10 per 1,000 pages, so about $107 for the corpus (over budget) |

Every package fits in one long-context request. B0 is viable for all documents. B1 exists as the measured alternative and as a guard for future oversized packages (`ANALYZE_CONTEXT_BUDGET`, default 300k tokens).

## 3. Architecture

```
documents (M0) ──► text layer (ingest/textlayer.py) ──► chunks: one per page, page-tagged
                                                         │
opportunity ──► ADK 2 workflow "analyze" ────────────────┤
   load ─► extract (B0 whole doc | B1 page windows) ─► verify quotes ─► knockout rules ─► persist
                         │                                                  │
                    Gemini 3.8 Flash                                app/rules/eligibility.py
                    (structured output)                             (plain Python, unit-tested)
follow-up Q&A agent ─► same documents via context cache ─► answers with page citations
```

### 3.1 Text layer (`ingest/textlayer.py`)

- **PDF:** pypdf, page by page. Text is normalized (NFKC, whitespace collapsed, line-break hyphens joined: `require-\nments` becomes `requirements`). A page with fewer than 30 non-whitespace characters is a *no-text page*. A document whose pages are all no-text gets `parse_status = no_text_layer`.
- **HTML:** Docling's HTML converter (no ML models), producing Markdown. Treated as one logical "page" per heading-level-2 section, so citations name a section.
- **DOCX:** Docling's DOCX converter, same treatment as HTML.
- **DOC (legacy Word):** `parse_status = unsupported`; counted, not processed.
- **Storage:** one `chunks` row per page or section: `ord`, `page_start = page_end`, `section_path` (the heading, if known), `text`, `n_tokens` (characters / 4). `embedding` stays null until M2. `documents.page_count` and `parse_status` are set.
- **Command:** `python -m ingest parse [--limit N] [--opportunity ID]`. It is idempotent and skips documents already `parsed`.

### 3.2 Contracts (`app/contracts.py`)

```python
Category = Literal["entity_type", "size", "ownership", "location", "registration",
                   "program_phase", "cost_share", "other"]

class Citation(BaseModel):
    document_id: UUID
    page: int                      # page number (PDF) or section index (HTML/DOCX), 1-based
    quote: str                     # verbatim from that page

class Clause(BaseModel):
    category: Category
    citation: Citation
    constraint: dict | None        # proposed by the model; validated per category (§5)

class Requirement(BaseModel):
    text: str                      # the requirement in the solicitation's own words
    citation: Citation

class Criterion(BaseModel):
    name: str
    weight: str | None             # as stated ("30%", "30 points") or None
    citation: Citation

class SectionSpec(BaseModel):
    id: str                        # short slug, e.g. "technical-approach"
    title: str
    page_limit: int | None
    citation: Citation

class Deadline(BaseModel):
    label: str                     # "Full application", "Letter of intent", "Questions"
    when: str                      # as written; parsed date if unambiguous
    citation: Citation

class SolicitationBrief(BaseModel):
    opportunity_id: UUID
    variant: Literal["B0", "B1"]
    eligibility: list[Clause]
    requirements: list[Requirement]
    evaluation_criteria: list[Criterion]
    required_sections: list[SectionSpec]
    deadlines: list[Deadline]
    dropped_quotes: int            # items removed by quote verification
    model: str
    prompt_version: str

class RuleHit(BaseModel):
    rule_id: str                   # "E0".."E7"
    outcome: Literal["PASS", "INELIGIBLE", "NEEDS_REVIEW"]
    clause: Clause
    company_fact: str              # e.g. "employees=32"
    reason: str

class EligibilityVerdict(BaseModel):
    status: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"]
    hits: list[RuleHit]
    rules_version: str
```

The model never fills `document_id`. It returns the document's position in the input plus a page number, and code maps that to the ID.

### 3.3 Extraction (`app/analyze/extract.py`)

- **Model:** `gemini-3.8-flash` (from `app/config.py`), temperature 0, Gemini structured output against a response schema derived from the contracts, without UUID fields.
- **B0 (default):** one request per opportunity containing every document.
  - PDFs are sent as the original file (`application/pdf` part), so Gemini reads layout, tables and scanned pages natively.
  - HTML and DOCX are sent as their text-layer Markdown, with section markers `[§n]`.
  - Each document is introduced by a header line `DOCUMENT <k>: <title>`, so citations can name the document.
- **B1:** the text layer split into windows of 5 pages (overlap 1). The same prompt runs per window, then results are merged by de-duplicating on normalized quote text.
- **Prompt:** versioned in `app/analyze/prompts/brief_v1.md`. It defines each output field, the knockout categories with examples, and the rule "quote exactly; never paraphrase; omit rather than guess".
- **Untrusted input:** document text is wrapped in clearly delimited blocks, and the instructions say to treat it as data, never as instructions. The extractor has no tools.
- **Accounting:** each call records tokens, latency and estimated cost in `runs`.

### 3.4 Quote verification (`app/analyze/quotes.py`)

A citation is **verified** when the normalized quote (§3.1 normalization, case preserved) is a substring of the normalized text of the cited page, or of the adjacent page when the quote spans a page break.

- An unverified `Requirement`, `Criterion`, `SectionSpec` or `Deadline` is **dropped** and counted in `dropped_quotes`.
- An unverified eligibility `Clause` is **kept** with `constraint = None`, so rule E0 marks it `NEEDS_REVIEW`. A possible knockout is never silently discarded.
- Quotes citing a *no-text page* cannot be checked. They are handled the same way: dropped, or kept as NEEDS_REVIEW for clauses.

### 3.5 Workflow (`app/analyze/workflow.py`, ADK 2)

A workflow graph with deterministic nodes:

```
load_documents ─► extract_brief(variant) ─► verify_quotes ─► apply_rules ─► persist
```

- **Inputs:** `opportunity_id`, `variant` (default B0).
- **Outputs, written to session state and to the database:** `SolicitationBrief` → `solicitation_briefs`, `EligibilityVerdict` → `eligibility_verdicts` (with `rules_version`).
- The nodes are plain functions in `app/analyze/`, so the eval harness calls them directly without ADK.

**Q&A agent** (`app/analyze/qa.py`): an `LlmAgent` with one tool, `ask_solicitation(opportunity_id, question)`. It answers from the opportunity's documents, using a Gemini context cache keyed by opportunity so follow-up questions don't resend the documents, and cites `DOCUMENT k, page n` in every answer. Citations are verified with the same quote checker before the answer is returned.

The root agent (`app/agent.py`) routes "analyze / is this a fit / what does it require" requests to this workflow and agent.

### 3.6 SAM.gov documents in M1

SAM notices in the sample need their attachments. `SamGovAdapter` (quota-capped, M0) fetches `resourceLinks` on demand for sampled SAM notices only. The file name comes from the `Content-Disposition` header (M0 review minor), and a generic `application/octet-stream` MIME type falls back to the file suffix (M0 review minor). Budget: at most 8 requests per day; the sample is drawn so SAM attachment fetches fit across about two days.

## 4. Company facts

The rules read `data/company/profile.json`, which is unchanged from M0:

| Fact | Value |
|---|---|
| `entity_type` | `for_profit` |
| `employees` | 32 |
| `us_ownership_pct` | 100 |
| `foreign_affiliation` | false |
| `state` | `CO` |
| `sam_registered` | true |
| `uei` | present |
| `sbir_awards` | `{"I": 2, "II": 0}` |

## 5. Eligibility rules (`app/rules/eligibility.py`)

Constraint schemas per category. The model proposes the constraint; a schema failure becomes `constraint = None`.

| Category | Constraint schema | Rule | INELIGIBLE when |
|---|---|---|---|
| `entity_type` | `{"allowed": [entity…]}` or `{"excluded": [entity…]}` with entity ∈ {for_profit, small_business, nonprofit, university, government, tribal, individual} | E1 | the company's types ({for_profit, small_business} while employees ≤ 500) don't intersect `allowed`, or intersect `excluded` |
| `size` | `{"max_employees": int, "includes_affiliates": bool}` | E2 | employees > max_employees |
| `ownership` | `{"min_us_ownership_pct": number}` and/or `{"foreign_owned_allowed": bool}` | E3 | us_ownership_pct < min, or foreign affiliation where not allowed |
| `location` | `{"us_only": bool}` or `{"states": [code…]}` | E4 | the company's state isn't permitted |
| `registration` | `{"requires": ["sam", "uei", …]}` | E5 | a required registration is missing |
| `program_phase` | `{"requires_prior_phase": "I" \| "II"}` | E6 | the company holds no award of that phase |
| `cost_share` | `{"min_pct": number}` | E7 | never INELIGIBLE; always NEEDS_REVIEW (business decision) |
| any | `constraint is None` and category ≠ `other` | E0 | never INELIGIBLE; NEEDS_REVIEW |
| `other` | none | none | ignored by the rules; shown in the brief |

**Aggregation:** any INELIGIBLE gives INELIGIBLE; otherwise any NEEDS_REVIEW gives NEEDS_REVIEW; otherwise ELIGIBLE. `rules_version` is a constant bumped on every rule change. Each rule is a pure function with unit tests, including the edge wordings "500 or fewer employees including affiliates", "nonprofit or institution of higher education", "Phase II: prior Phase I awardees only", "U.S.-based small business" and "cost share of at least 20%".

## 6. Golden sets and labeling

### 6.1 Sampling (`python -m evals.sample m1 --seed 20261009`)

- 40 opportunities with ≥ 1 parsed document, stratified by source (about 28 Grants.gov, 12 SAM.gov) and capped at 4 per agency.
- About 15 of the 40 are drawn from a keyword prefilter for likely knockouts ("nonprofit", "institutions of higher education", "state governments", "tribal", "Phase II", "cost share"), so the set contains ≥ 10 real knockouts. The prefilter only selects; it never labels.
- 10 of the 40 (stratified by document length) also form the requirements set.
- The sample manifest (IDs, seed, query, date) is written to `evals/data/golden/m1_sample.json`.

### 6.2 Labeling page (`python -m evals.label`)

- FastAPI on `127.0.0.1:8765` serving a single HTML page; local only, with no authentication because it never leaves the machine.
- **Left pane:** opportunity metadata and its documents, with page navigation over the text layer (PDFs can also be opened as files).
- **Right pane, knockout form:** verdict, one or more clauses (quote, document, page, category), notes.
- **Requirements form:** a list of requirement rows (text, document, page).
- Saving appends one JSON line to `evals/data/golden/knockout.jsonl` or `requirements.jsonl`. Every file starts with a `{"_meta": …}` header (labeler, date, seed). Each label can be re-edited (the last write wins on reload).
- **The page never shows model output.**
- **Progress:** "labeled 12 / 40".

### 6.3 Dev set

`evals/data/dev/` holds LLM-drafted, human-reviewed labels on a *different* sample (seed + 1). It's used for prompt iteration and for the `ANALYZE` thresholds. Golden data is never used for tuning (LABELING.md rule zero).

## 7. Evaluation (`evals/suites/analyze.py`)

| Metric | Definition |
|---|---|
| Knockout flagged recall | labeled INELIGIBLE predicted INELIGIBLE or NEEDS_REVIEW ÷ labeled INELIGIBLE |
| Knockout strict recall | labeled INELIGIBLE predicted INELIGIBLE ÷ labeled INELIGIBLE |
| Knockout strict precision | predicted INELIGIBLE that are labeled INELIGIBLE ÷ predicted INELIGIBLE |
| Verdict agreement | 3-way confusion matrix and accuracy over all labeled solicitations |
| Clause-level recall | labeled knockout clauses matched by a predicted clause (match: same document, page ±1, normalized token Jaccard ≥ 0.6) ÷ labeled clauses |
| Requirement recall / precision | same matcher over requirements |
| Quote fidelity | stored quotes verified ÷ stored quotes (must be 1.0) |
| Cost and latency | per-solicitation tokens, USD, p50/p95 wall time |

- Suites register as `analyze_b0` and `analyze_b1`. A cached smoke subset (3 solicitations, recorded model responses) runs in CI with no network. The full suite runs manually.
- The **ablation report** (`reports/m1/ablation.md`) puts B0 and B1 side by side, overall and for long documents (more than 50 pages), and lists the 5 worst misses for each with a one-line cause.

## 8. Error handling

| Situation | Behavior |
|---|---|
| Gemini returns invalid JSON or a schema violation | One retry with the validation error appended; then the brief is marked failed and the run continues |
| Gemini 429 or 5xx | Retried with backoff (shared HTTP policy); a persistent failure is recorded in `runs.outcome` |
| Package over the context budget | Automatically switches to B1 for that opportunity; recorded on the brief |
| Document without a text layer | Extraction still runs (Gemini reads the PDF); its quotes can't be verified, so §3.4 applies |
| SAM quota exhausted mid-sample | Remaining SAM notices are labeled from documents already stored; the rest are fetched the next day |

## 9. Testing

| Layer | Tests |
|---|---|
| Unit | Text normalization; page splitting; HTML/DOCX section paging; every rule E0–E7 with edge wordings; constraint schemas; quote verifier (hyphenation, cross-page, no-text page); clause/requirement matcher; metric functions; prompt rendering |
| DB | `ingest parse` idempotence and status transitions; brief and verdict persistence |
| Workflow | Analyze graph run with a stubbed model client returning recorded responses (no network) |
| Eval | Smoke suite on recorded responses (CI); full suite manual |

LLM output text is never asserted in pytest. Behavior is judged by the eval suites.

## 10. Cost

| Item | Estimate |
|---|---|
| Text layer for the whole corpus | free (local, about 12 min) |
| B0 + B1 over 40 golden + 40 dev solicitations | about 80 × 2 × ~20k tokens (PDF pages are about 258 tokens) ≈ 3.2M input tokens, roughly **$1–3** |
| Q&A and development iterations | under $2 |
| Cloud | none required in M1 (local DB) |

## 11. Changes to existing decisions

- **ADR-0004 (parsing):** updated. PDFs are read natively by Gemini for extraction, with pypdf providing the verifiable text layer. Docling is used for HTML and DOCX. Docling's PDF pipeline and Document AI Layout Parser are compared in M5. The update records the measurements in §2.
- **ADR-0016 (long context vs. chunked):** the outcome is filled in from §7's ablation report.
- **M0 review minors addressed here:** SAM attachment names via `Content-Disposition`; MIME-type suffix fallback.
