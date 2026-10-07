# PRD: grant-capture-agent v1

| | |
|---|---|
| Owner | Karthick Balaje (kb2326) |
| Status | In review |
| Date | 2026-10-06 |
| System design | [`docs/design/system-design.md`](../design/system-design.md) |

## 1. Problem

Small R&D companies compete for federal funding (SBIR/STTR, agency grants, R&D contracts) with no capture team. One person does three jobs:

1. **Find** opportunities across Grants.gov and SAM.gov, each with its own search UI and vocabulary.
2. **Qualify** each one by reading long solicitations. A single eligibility clause (size limit, ownership, entity type, registration) can make the company ineligible, and it is often buried deep in an attachment.
3. **Draft** technical sections from scattered past proposals, CVs and project reports.

Commercial GovCon platforms solve this for paying customers. This project rebuilds the AI core of that workflow in the open and measures each part.

## 2. Users

**Primary:** the grants or capture lead at a 15–50 person deep-tech company.

**Test company:** *Lumen Grid Labs*, a fictional grid-storage and power-electronics R&D firm. Its profile is an ordinary 32-person, U.S.-owned, for-profit LLC, registered in SAM, with two prior SBIR Phase I awards. It also has a capability statement, five past-proposal excerpts, three project reports and four staff bios. All of it is synthetic and lives in `data/company/`.

## 3. Jobs to be done and user stories

| ID | Story | Module |
|---|---|---|
| D1 | As a grants lead, I describe what we do in plain English and get a shortlist of open opportunities that fit, each with the reason it fits. | Discover |
| D2 | I review and edit the search plan before the agents run it. | Discover |
| A1 | For any opportunity, I get a one-page brief: eligibility, "shall" requirements, evaluation criteria, page limits, deadlines, required sections. | Analyze |
| A2 | I see a clear eligible / ineligible / needs-review verdict for my company, with the exact clause quoted and the page it came from. | Analyze |
| A3 | I can ask follow-up questions about a solicitation and get answers with citations. | Analyze |
| R1 | For each required section, I get a first draft built only from our own documents, with every claim cited. | Draft |
| R2 | Where we have no evidence, the draft says so instead of making something up. | Draft |
| R3 | I approve or edit each draft before it can be exported. | Draft |
| S1 | I keep a saved list of opportunities I'm pursuing. | Saved list |

## 4. Success metrics

Targets are hypotheses. The measured values go into the eval report and the résumé, whether they hit the target or not.

| Module | Metric | Target |
|---|---|---|
| Discover | Median time to a qualified shortlist, agent vs. manual search, on 10 benchmark tasks | ≥ 50% reduction |
| Discover | Precision@10 on 20 golden queries | ≥ 0.70 |
| Analyze | Knockout recall on the golden set (≥ 30 solicitations) | ≥ 0.95 |
| Analyze | Knockout precision on the golden set | ≥ 0.85 |
| Analyze | Requirement extraction recall (10 solicitations, hand-listed "shall" statements) | ≥ 0.85 |
| Analyze | Quote fidelity: extracted clauses that appear verbatim in the source | 100% (enforced in code) |
| Draft | Context relevance of graded passages | ≥ 0.60 |
| Draft | Faithfulness: sentences supported by their citations | ≥ 0.90 |
| Draft | Time to an acceptable first draft of 3 sections, agent-assisted vs. manual | ≥ 40% reduction |
| System | Cost per full Discover → Analyze → Draft run | < $0.25 |
| System | p95 latency of a Discover run, excluding human approval time | < 90 s |

## 5. Guardrails

- A person approves the search plan and every draft. The system never submits anything anywhere.
- Every eligibility verdict and every drafted claim cites its source passage.
- Ineligibility is decided by deterministic rules, never by a free-form model judgement. Clauses the rules can't parse become **needs review**, never **eligible**.
- Solicitation text is treated as untrusted input (prompt-injection defence).
- Only synthetic company data and public government data are used.

## 6. Scope

**In v1:** Discover, Analyze (Solicitation agent and knockout screen), Draft (corrective RAG), saved list, web UI, deployment on Google Cloud, evals and CI eval gate.

**Not in v1:** multiple customer accounts and auth beyond one demo user, state and local portals, proposal submission, full pipeline/CRM (tasks, teammates), FedRAMP/SOC 2, A2A interoperability (stretch).

## 7. Data sources

| Source | Access | Used for |
|---|---|---|
| Simpler Grants API (Grants.gov) | Free API key, `X-API-Key` header | Grant opportunities and NOFO attachments |
| SAM.gov Opportunities API | Free api.data.gov key | Federal contract solicitations in R&D NAICS codes (5417xx), including DoD and NASA SBIR/STTR notices |
| USAspending API | Public, no key | Incumbents and past awards in a topic area (context only) |
| NIH RePORTER API | Public, no key | Previously funded research on a topic: likely competition (context only) |
| NSF Awards API | Public, no key | Previously funded research on a topic: likely competition (context only) |

The SBIR.gov API (403, "under maintenance") and the DoD SBIR/STTR Innovation Portal (blocks programmatic access) were tested on 2026-10-07 and are not used. Their solicitations are also posted to Grants.gov or SAM.gov. Opportunities are normalized to fields compatible with the CommonGrants protocol.

## 8. Positioning against commercial capture platforms

| Typical commercial capability | v1 equivalent | Difference |
|---|---|---|
| AI search over 1M+ opportunities | Discover over a focused R&D index (~5k opportunities) | Smaller index; quality is measured with P@10 |
| Bid/no-bid Q&A on any solicitation | Analyze: brief, knockout verdict, cited Q&A | Knockouts are rule-based and measured for recall |
| Proposal copilot on company data | Draft: corrective RAG with faithfulness check | Gaps are flagged explicitly; faithfulness is measured |
| Pipeline management | Saved list | Deliberately minimal |
| SOC 2 / CMMC / FedRAMP | Not in scope | Portfolio project |

## 9. Risks

| Risk | Mitigation |
|---|---|
| Attachment PDFs are scanned or badly formatted | Docling OCR fallback; mark unparseable documents and report how many there are |
| Label quality limits how trustworthy the metrics are | Hand-labeled golden set with written labeling guidelines; LLM-assisted labels kept to a separate dev set |
| The timing benchmark has one participant (the author) | Report it as a single-user study with the protocol published; never present it as a user study |
| GCP cost creep | Budget alert at $50/month; smallest Cloud SQL tier; stop the instance when idle |
| API rate limits or outages | Offline index with incremental nightly sync; retries with backoff |
