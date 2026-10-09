# M1 ablation: B0 (whole document) vs B1 (page windows)

Labels are a **silver set**: written by an independent AI labeler (see `evals/LABELING.md`), not by a person.
Read every number as agreement with that labeler. The labeler is a different Gemini model with its own
prompt, but it reads the same document input, so some errors are correlated and agreement may be
overstated. Cases skipped by the eval budget cap are not errors; n/a means nothing to measure.

## B0 on the full sample

| metric | B0 | target |
|---|---|---|
| knockout_flagged_recall | 1.000 | 0.950 |
| knockout_strict_precision | 0.909 | 0.850 |
| knockout_strict_recall | 1.000 |  |
| verdict_accuracy | 0.600 |  |
| clause_recall | 0.438 |  |
| requirement_recall | 0.145 | 0.850 |
| requirement_precision | 0.786 |  |
| quote_fidelity | 0.928 | 1.000 |
| cost_usd_per_solicitation | 0.040 |  |
| latency_p50_s | 61.000 |  |
| latency_p95_s | 561.312 |  |
| errors | 0.000 | 0.000 |
| cases_measured | 40.000 |  |

### B0 verdicts vs labels

| labeled \ predicted | ELIGIBLE | INELIGIBLE | NEEDS_REVIEW |
|---|---|---|---|
| ELIGIBLE | 10 | 0 | 13 |
| INELIGIBLE | 0 | 10 | 0 |
| NEEDS_REVIEW | 2 | 1 | 4 |

## Head to head on the 7 cases both variants completed

| metric | B0 | B1 | target |
|---|---|---|---|
| knockout_flagged_recall | 1.000 | 1.000 | 0.950 |
| knockout_strict_precision | 1.000 | 0.750 | 0.850 |
| knockout_strict_recall | 1.000 | 1.000 |  |
| verdict_accuracy | 0.714 | 0.714 |  |
| clause_recall | 0.300 | 0.300 |  |
| requirement_recall | 0.147 | 0.692 | 0.850 |
| requirement_precision | 0.840 | 0.572 |  |
| quote_fidelity | 0.923 | 0.922 | 1.000 |
| cost_usd_per_solicitation | 0.036 | 0.152 |  |
| latency_p50_s | 181.281 | 304.485 |  |
| latency_p95_s | 561.312 | 901.844 |  |
| errors | 0.000 | 0.000 | 0.000 |
| cases_measured | 7.000 | 7.000 |  |

## Effect of the rules fix

Before: rules 2026-10-09.1 on the first B0 run. After: the cases B0 had called INELIGIBLE were re-run
and every case re-scored offline with the current rules (a bulleted list of eligible applicant types
means any of them, merged only within one list). Re-runs are fresh model calls, so a few verdicts
may differ for reasons other than the rules.

| metric | before | after | target |
|---|---|---|---|
| knockout_flagged_recall | 1.000 | 1.000 | 0.950 |
| knockout_strict_precision | 0.455 | 0.909 | 0.850 |
| knockout_strict_recall | 1.000 | 1.000 |  |
| verdict_accuracy | 0.550 | 0.600 |  |
| clause_recall | 0.542 | 0.438 |  |
| requirement_recall | 0.119 | 0.145 | 0.850 |
| requirement_precision | 0.733 | 0.786 |  |
| quote_fidelity | 0.882 | 0.928 | 1.000 |
| cost_usd_per_solicitation | 0.040 | 0.040 |  |
| latency_p50_s | 64.391 | 61.000 |  |
| latency_p95_s | 283.937 | 561.312 |  |
| errors | 0.000 | 0.000 | 0.000 |
| cases_measured | 40.000 | 40.000 |  |

## B0: verdict disagreements (16)

- `0ddb2f62-68bd-4623-925c-f9f0e27c4bfe`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `13d9f633-0d5a-4001-84bb-c7b095927d44`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `207e68c3-8a8a-4c59-b956-b08fb3b7135b`: predicted ELIGIBLE, labeled NEEDS_REVIEW
- `26c041db-2529-4d14-89cb-bb10e3689a63`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `4621dc19-cbc0-4d6d-99ab-c91f1ebd85ea`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `5146d048-dd25-49eb-adef-0354f7e2aa3c`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `5c2ff7d2-a739-4197-8667-d9481ee1aa83`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `7eab5f76-65b3-4ec3-a16c-4d425bf3a80a`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `8fcd7b26-d2cc-4e2e-b54e-c1120452e209`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `a47d4ef1-93ba-4245-a9f7-5d492ae50fc4`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `c02dbab4-8efe-4d89-81ca-9b3ea7e6ae31`: predicted ELIGIBLE, labeled NEEDS_REVIEW
- `c50c3d11-5d58-49eb-9479-a4734a9f67b1`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `cbcba794-a028-473f-96c0-a69f10fd4ba7`: predicted INELIGIBLE, labeled NEEDS_REVIEW
- `d4dd8315-f23f-4c71-b043-b126d56fa457`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `da86fea7-77c8-4fe7-9280-249f095a024c`: predicted NEEDS_REVIEW, labeled ELIGIBLE
- `fa82a64f-2808-4626-ad09-d3b7d4e31236`: predicted NEEDS_REVIEW, labeled ELIGIBLE

## B1: verdict disagreements (2)

- `0ddb2f62-68bd-4623-925c-f9f0e27c4bfe`: predicted INELIGIBLE, labeled ELIGIBLE
- `13d9f633-0d5a-4001-84bb-c7b095927d44`: predicted NEEDS_REVIEW, labeled ELIGIBLE
