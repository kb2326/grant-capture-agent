# ADR-0016: Analyze reads whole documents in long context

- Status: Accepted. Outcome measured in M1 (2026-10-09): B0 stays the default for eligibility; page windows are the better tool for requirement lists
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
A solicitation package is typically 30 to 150 pages, roughly 25k to 120k tokens, well inside Gemini's long-context window. Chunking a document can separate a clause from the heading that gives it meaning, for example an eligibility exception under a section title. The design method (system design section 8.0) says every workflow ships a simple baseline and a richer variant, and the variant is kept only if evals show a gain.

## Decision
The baseline (B0) extracts from each whole document in one long-context pass, with page-tagged text. Chunk-and-merge extraction (B1) is used only when a package exceeds `ANALYZE_CONTEXT_BUDGET` (default 300k tokens). M1 measures both on the golden knockout and requirements sets.

## Alternatives considered
- Always chunk: splits clauses from their headings and adds a merge step that can drop or duplicate clauses.
- Always long context: fails on very large packages that exceed the window.

## Consequences
The simple path is the default and is easy to evaluate. We need a size router and a second code path for oversized packages. M1 reports knockout recall and precision, requirement recall, p50 and p95 latency and cost for both variants, overall and on the very-long-solicitation slice. If B1 wins on quality at acceptable cost, this ADR is superseded.

## Outcome (measured 2026-10-09)
Full numbers: `reports/m1/ablation.md`. Labels are an AI-labeled silver set (`evals/LABELING.md`), so these are agreement figures, not accuracy. B1 was measured on 7 opportunities only (budget cap), so the head-to-head is directional.

| On the 7 shared opportunities | B0 whole document | B1 5-page windows |
|---|---|---|
| Knockout flagged recall | 1.00 | 1.00 |
| Knockout strict precision | 1.00 | 0.75 |
| Requirement recall | 0.15 | 0.69 |
| Requirement precision | 0.84 | 0.57 |
| Cost per solicitation | $0.036 | $0.152 (4x) |
| Median latency | 181 s | 304 s |

**Decision.**
- **Eligibility: B0.** It is as good as B1 at finding knockouts, makes fewer false ones, and costs a quarter as much. Eligibility rules are short and concentrated, so reading the whole document at once suits them.
- **Requirements: B0 under-extracts.** Asked for everything in one pass, the model returns a short list (recall 0.15). Focused windows recover most of it (0.69) but add noise and cost.
- **Next step (Draft, M3):** a hybrid: B0 for eligibility and the brief, window extraction only for the requirements of a solicitation the user decides to pursue. The cost is then paid only where it matters.
- B1 remains the automatic fallback when a package exceeds `ANALYZE_CONTEXT_BUDGET`.

The eval also exposed a rules bug, now fixed: each bullet of an eligible-applicant list was judged on its own. On all 40 opportunities, B0 strict knockout precision went from 0.45 to 0.91 once lists were treated as "any of these"; flagged recall stayed at 1.00 (10 of 10).
