# ADR-0006: LLM extracts, rules decide

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
A wrong eligibility call can waste a whole proposal effort, or wrongly rule out a good opportunity. LLM judgements are non-deterministic and hard to audit: the same input can produce different verdicts, and nobody can point to the rule that fired. Solicitations state eligibility in prose, so some model help is still needed to read it.

## Decision
The model only extracts quoted clauses and proposes a structured constraint for each. Plain Python in `app/rules/` decides the verdict. Every quote must be a substring of the page text, or it is dropped. A clause the rules cannot parse yields NEEDS_REVIEW, never a silent pass.

## Alternatives considered
- LLM-judged eligibility: opaque and non-deterministic, with no clean way to test it in ordinary unit tests.

## Consequences
Verdicts are reproducible, explainable ("rule E3 failed on this quoted clause") and unit-testable without calling a model. The cost is maintenance: each clause category needs a rule and a JSON schema for its constraint. The risk moves to extraction recall, which we measure against a labeled golden set rather than assume. NEEDS_REVIEW is a deliberate escape hatch that keeps a human in the loop.
