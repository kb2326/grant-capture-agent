# ADR-0016: Analyze reads whole documents in long context

- Status: Accepted (decision method); outcome measured in M1
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
