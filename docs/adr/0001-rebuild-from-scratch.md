# ADR-0001: Rebuild from scratch

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The v0 prototype had its logic almost entirely in prompts. It had no evaluations and no tests, so there was no way to tell whether a change made it better or worse. Of the three planned modules (Discover, Analyze, Draft), two were missing entirely. Nearly every part of the code would need to change to add contracts, typed state, data pipelines and measurement, so the old structure would not survive a refactor in any meaningful form.

## Decision
Start a new repository layout (`app/`, `ingest/`, `rag/`, `db/`, `evals/`). Keep the v0 code under `legacy/` and mark it with the git tag `v0-besi-prototype`.

## Alternatives considered
- Incremental refactor of v0: every module would change anyway, so refactoring in place would cost more than rewriting, and it would carry v0's untested assumptions forward.
- Delete v0 entirely: loses the baseline we want for a before-and-after comparison.

## Consequences
We get clean contracts between modules, tests and evals from day one, and architecture choices made by measurement rather than inheritance (see ADR-0016 to ADR-0018). The cost is that nothing works end to end until the first milestones land. Keeping v0 in `legacy/` lets us run a v0 versus v1 comparison for the write-up. We must make sure nothing in the new code imports from `legacy/`.
