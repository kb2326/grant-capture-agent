# Labeling guide

How the evaluation data in `evals/data/` is labeled. Every number reported for this project comes from these labels, so they follow fixed rules.

## 1. Purpose and rule zero

- **Golden sets** (`evals/data/golden/`) are labeled **by hand**, then **frozen**. They are never used to tune prompts, thresholds or models. Their only job is to measure.
- **Dev sets** (`evals/data/dev/`) are for iteration. They may be drafted with LLM help, but a person reviews every label.
- If a golden label turns out to be wrong, fix it in a separate commit that explains why, and re-run every affected report. Never edit a golden label to make a metric pass.

### M1 exception: a silver set
For M1 the owner chose AI labels (prototype). `evals/data/golden/knockout.jsonl` and `requirements.jsonl` are a **silver set** written by `python -m evals.ai_label`, with three safeguards:
- a different, stronger model than the system under test (`model_labeler`, not `model_agent`);
- its own prompt (sections 1-4 of this guide), and its own verdict from the company facts, without our rules or outputs;
- every quote is checked against the stored text (`quote_verified` per clause).

Report M1 numbers as **agreement with an AI labeler**, not accuracy. Replacing the silver set with human labels (same file format, via `python -m evals.label`) turns them into accuracy numbers.

## 2. Knockout verdicts (for Lumen Grid Labs)

Use the facts in `data/company/profile.json` (32 employees, 100% U.S.-owned, for-profit LLC in Colorado, SAM-registered, two prior SBIR Phase I awards).

- **INELIGIBLE:** at least one clause rules the company out on those facts. Example: "Only nonprofit organizations may apply."
- **NEEDS_REVIEW:** a relevant clause exists but can't be decided from the profile. Examples: "must demonstrate prior DOE funding" with no further detail, or a cost-share requirement, which is a business decision rather than a knockout.
- **ELIGIBLE:** no disqualifying clause was found after reading the eligibility section **and** every attachment.

For every label, record the clause **verbatim**, with its document name and page number. A verdict without a quote is not a label.

## 3. What counts as a knockout

Knockouts are rules the company cannot change before the deadline:

| Category | Example |
|---|---|
| Entity type | "Only institutions of higher education are eligible." |
| Size standard | "500 or fewer employees, including affiliates." |
| Ownership and control | "More than 50% owned and controlled by U.S. citizens." |
| Location | "Applicants must be located in Alaska." |
| Registration | "Must be registered in SAM.gov with an active UEI at submission." |
| Program phase | "Only Phase I awardees may apply for this Phase II." |

**Not knockouts:** cost share, page limits, formatting rules, letters of support, budget caps. Record them as requirements (section 4), not as knockouts.

## 4. Requirements set

- A requirement is a **"shall", "must" or "will"** statement that the **proposer** has to satisfy.
- Use one row per statement, quoted verbatim, with document and page.
- Skip statements about the agency's own obligations ("The agency will notify applicants…") and generic legal boilerplate repeated across every solicitation.

## 5. Discover relevance grades

For each golden query, grade every candidate opportunity:

| Grade | Meaning |
|---|---|
| **2** | Strong fit: directly matches one of the company's stated capabilities |
| **1** | Plausible: adjacent topic the company could credibly propose to |
| **0** | Not a fit |

Grade fit only. Eligibility is measured separately by the knockout set.

## 6. Draft evidence labels

For each section prompt, list:
- the company documents and headings that contain **supporting evidence**, and
- the requirements that have **no evidence** in the corpus (expected gaps, which the drafter must flag rather than fill).

## 7. Sampling

- Stratify by source (Grants.gov vs. SAM.gov) and by agency, so one agency can't dominate.
- The knockout set must include **at least 10 known knockouts**.
- Record the sampling query, the date and the random seed in the set's header so the sample can be reproduced.

## 8. File formats

JSON Lines (one object per line), using the field names in `docs/design/system-design.md` §11. Each file starts with a header object `{"_meta": {...}}` recording the labeler, date, sampling query and seed.

## 9. Using the labeling page (M1)

1. `docker compose up -d db`, then `uv run python -m evals.label`. The page opens at http://127.0.0.1:8765 (local only).
2. Pick an item from the list (✓ = verdict saved). The left side shows every document of the opportunity, page by page, exactly as the system stored it; **open file** shows the original PDF. SAM.gov notices show their description as `notice-description.html`.
3. Read the eligibility section **and** every attachment. Choose the verdict, add one row per deciding clause (exact quote, document, page, category), and save.
4. Items marked for requirements show a second form: one row per proposer "shall / must / will" statement.
5. Labels append to `evals/data/golden/knockout.jsonl` and `requirements.jsonl`; saving again replaces your earlier label (last one wins). Stop and resume at any time.

The page never shows what the model extracted, so the labels can't be anchored to it. A clause about **who may apply** that fits no category (e.g. "only current program initiatives may apply") still decides the verdict: use category `other` and the verdict it implies.
