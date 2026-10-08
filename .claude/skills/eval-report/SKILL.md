---
name: eval-report
description: Run the grant-capture-agent evaluation suites and explain the results - which metrics passed, which failed, and how they compare with the previous report. Use when asked to "run evals", "how good is it", or before merging a change that affects agent behaviour.
---

1. Run `uv run python -m evals.run --suite full --out reports/local` (use `--suite smoke` for a quick check).
2. Open the newest `reports/local/eval-*.md` and the previous one, if any.
3. Report per suite: metric, value, target, pass/fail, and the change since the previous report.
4. For any failure, open the per-case output in the JSON report and name the three worst cases with a one-line hypothesis each.
5. Never edit golden data in `evals/data/golden/` to make a metric pass.
