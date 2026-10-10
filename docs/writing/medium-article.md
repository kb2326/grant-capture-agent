# Building a grant-capture agent by ablation, on a $10-a-month budget

*Draft for Medium. Every number below comes from the reports in the repository ([github.com/kb2326/grant-capture-agent](https://github.com/kb2326/grant-capture-agent)).*

A grants lead at a small research company has three jobs. Find funding that fits. Read a forty-page solicitation to learn whether the company may even apply. Then write a proposal from years of old proposals, reports and CVs scattered across shared drives. I built an AI system for all three on Google's Agent Development Kit (ADK) and Gemini, and set myself one rule: **no architecture choice without a measurement**.

Every module was built twice. A simple baseline (B0) and a richer variant (B1), the kind of design that looks impressive in a diagram: page-by-page extraction, a plan-execute-verify loop, corrective retrieval. Both ran on the same evaluation, and the richer one was kept only if it beat the baseline by a set margin without doubling cost or latency.

The richer design never clearly won. That turned out to be the most useful result of the project.

## Analyze: is the company even eligible?

A solicitation's eligibility section decides whether a week of writing is worth starting. The system reads the solicitation, extracts each eligibility clause with an **exact quote and page number**, and then plain Python rules, not the model, compare those clauses with the company's facts (size, ownership, entity type, registrations).

Two design rules mattered more than any prompt:

- **The model extracts, code decides.** A verdict like "ineligible" must be traceable to a rule and a quoted clause. Models summarize well; they should not be the ones saying no.
- **Quotes are verified.** Every quote must appear verbatim on its cited page, after normalizing whitespace and hyphenation. Quotes that fail are dropped, never shown.

The ablation compared reading each whole document in one long-context call against reading it in five-page windows and merging. For eligibility, whole documents were as accurate or better at about a quarter of the cost ($0.04 vs $0.15 per solicitation). Windows found far more of the "shall" requirements in long documents (0.69 vs 0.15 recall on a small sample), so that stays the plan for requirement lists.

Then the evaluation caught something I did not expect: **a bug in my own rules, not in the model.** Many solicitations list eligible applicants as bullets: universities, nonprofits, small businesses. My rules read each bullet as a separate "only this type may apply" rule, so a company that matched one bullet was failed by the others. Fixing the rules, without touching the model, raised knockout precision from 0.45 to 0.91, with recall at 1.00 (10 of 10 real knockouts caught). If I had only tuned prompts, I would never have found it.

## Discover: what should we even look at?

Search runs over 2,737 open opportunities from Grants.gov and SAM.gov. Each becomes a "card" (title, agency, dates, listings, summary) indexed twice: as embeddings in pgvector and as Postgres full text. One SQL statement runs both searches and blends them with Reciprocal Rank Fusion.

Three small ablations, each cheap:

1. **Cloud vs. free local embeddings.** Gemini's embedding model scored nDCG@10 0.514; the open EmbeddingGemma 2 scored 0.472, but did better on vague requests. Running the local model on a laptop CPU would have taken nine hours, so it ran on a free Kaggle GPU in six minutes, driven from the terminal.
2. **A reranker.** The Vertex AI Ranking API added nothing measurable (0.512 vs 0.514). It is built and switched off.
3. **Plan-Execute-Verify vs. a single pass.** This is the one I expected the loop to win. Instead it **never ran**: its verifier asked "did at least five results pass the rules?", and on a 2,700-row index the answer was always yes, so it never refined anything. The lesson: a loop is only as good as the judge that can say "not good enough". A count is not a judge.

There was also a measurement lesson. Gemini first looked slow because the timer included its one-off client sign-in; warming each option up before timing fixed the comparison.

## Draft: write it from our own evidence

This is the part people imagine when they hear "AI proposal writing", and the part where honesty matters most. Evaluators score what a company has proven, and false statements to the government are a legal risk. So the drafter must do three things: cite the company's documents for every claim, list as **gaps** the requirements it has no evidence for, and flag any sentence its own citations do not support. Every draft starts with "AI-assisted first draft. Human review and rewrite required before submission", and the system quotes any AI-use rule in the solicitation, because agencies like NIH now restrict applications substantially developed by AI.

To measure this without trusting another AI's opinion, I built the ground truth into the data. A synthetic company's library grew from 13 to 75 documents, generated from a checked-in plan in which each required fact had to appear as an exact phrase. Fifteen documents were deliberately **outdated** (an old headcount, a previous product generation) and twelve **off-topic** (a lease, a travel policy). Twelve drafting tasks asked for 46 requirements, 10 of which no document supports: hydrogen, cybersecurity, offshore wind. Code, not a model, scores whether gaps were flagged and whether citations point at outdated documents.

Long context (the whole library in a Gemini context cache, about 54k tokens) against corrective retrieval (search, have a cheap model grade each passage, rewrite the query up to twice):

- Both flagged **10 of 10 true gaps** and invented none.
- Long context was more faithful (0.83 vs 0.78 on a silver judge), cited outdated documents less (1.4% vs 3.5%), and was twice as fast.

The grader that decides relevance in corrective retrieval was checked against my own labels on 40 passages: Cohen's κ 0.63, above the 0.6 bar, and stricter than me when we disagreed, which is the safe direction for finding gaps.

At 75 documents, retrieval did not earn its place. It stays in the code for the day the library is ten times bigger.

## What it cost, and what that taught me

The budget was $10 a month. Analyze cost about $8.60, mostly from using a large model to label the evaluation set; Discover about $1; Draft about $2. October went over the target, and the reason was instructive: **thinking tokens**. Modern models reason before answering and those tokens are billed as output; a single drafted section used up to 17,000 of them. Drafting now caps them.

The bigger lesson was about guardrails. A budget alert sends an email; it does not stop anything. What stops spend is code that refuses the next call: dollar caps on every evaluation run (counting failed calls too), a session cap in the UI, and expensive operations as explicit, priced buttons. The UI taught that last one: a search silently ran five eligibility analyses as a side effect and cost about eighteen times a plain search ($0.147 instead of $0.008), until the checks became a button.

## Shipping without spending

The last milestone was deployment, and I chose not to deploy. Instead I designed it the way a team would review it: Cloud Run for the API and UI (scaling to zero), Agent Runtime for the agents with the Analyze agent as its own A2A service, Cloud SQL with pgvector switched off until needed, one service account per agent, secrets in Secret Manager. The Terraform passes `terraform plan` (nine resources to add, nothing created), the production container builds and serves the UI locally, and a runbook lists every step with its cost and how to undo it. A funded deployment is a day's work from here.

## What I would tell another builder

1. **Build the boring baseline first, then make the fancy version prove itself.** At this scale the simple design won or tied every time.
2. **Put ground truth in the data when you can.** Code-scored metrics are cheaper and more trustworthy than AI judges; calibrate the judges you keep against a few dozen human labels.
3. **Read every surprising number until you understand it.** The biggest win came from finding a bug in my own rules; the most misleading number came from a timer.
4. **Make cost a feature.** Show it per action, cap it in code, and never let an expensive call hide inside a cheap one.

The code, the evaluation reports and the architecture decisions are all in the repository. The company in it is fictional; the solicitations are real.
