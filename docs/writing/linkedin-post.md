# LinkedIn post (draft)

I built an AI agent that finds federal funding, checks eligibility and drafts proposals, and made every design choice prove itself with a measurement.

Each module was built twice: a simple baseline and the "impressive" version. The results:

🔎 Eligibility: reading whole documents beat page-by-page extraction at a quarter of the cost. Knockout recall 1.00, precision 0.91.
🧭 Search: a Plan-Execute-Verify loop never fired. Its check only counted results, and with 2,700 opportunities the count always passed. A loop needs a judge that can say "not good enough".
✍️ Drafting: putting the whole 75-document library in context beat corrective RAG. Both caught 10 of 10 requirements with no evidence and invented none; long context was more faithful and twice as fast.

The lesson that surprised me most: the evaluation found a bug in my own rules, not the model. Fixing it took precision from 0.45 to 0.91 without touching a prompt.

Also learned the hard way: thinking tokens are billed as output, and a budget alert doesn't stop spending. Caps in code do.

Built on Google ADK, Gemini, Postgres + pgvector, with an MCP server and a production deployment designed and validated with Terraform.

Repo: github.com/kb2326/grant-capture-agent
Full write-up: [Medium link]

#AIEngineering #GoogleCloud #RAG
