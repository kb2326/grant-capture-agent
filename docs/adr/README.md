# Architecture decision records

An architecture decision record (ADR) is a short note that captures one significant technical decision: the context, the choice, the alternatives rejected and the consequences. ADR-0010 and ADR-0011 are written in M5, after their experiments. Start from [0000-template.md](0000-template.md) for new records.

| Number | Title | Status |
|---|---|---|
| [0001](0001-rebuild-from-scratch.md) | Rebuild from scratch | Accepted |
| [0002](0002-adk-2-workflow-graphs.md) | ADK 2 workflow graphs | Accepted |
| [0003](0003-postgres-pgvector.md) | Postgres + pgvector | Accepted |
| [0004](0004-document-parsing.md) | Document parsing: Gemini reads PDFs natively; pypdf/HTML/DOCX text layer for quote checks (revised M1) | Accepted |
| [0005](0005-embeddings.md) | Embeddings | Accepted |
| [0006](0006-llm-extracts-rules-decide.md) | LLM extracts, rules decide | Accepted |
| [0007](0007-offline-index-live-fallback.md) | Offline index + live fallback | Accepted |
| [0008](0008-demo-access.md) | Demo access | Accepted |
| [0009](0009-single-prod-project.md) | Single prod project | Accepted |
| [0012](0012-runtime-choice.md) | Runtime choice | Accepted |
| [0013](0013-analyze-as-a2a-service.md) | Analyze as an A2A service | Proposed (decided in M2) |
| [0014](0014-per-agent-identity.md) | Per-agent identity | Proposed (decided in M4) |
| [0015](0015-sources-and-normalized-format.md) | Sources and normalized format | Accepted |
| [0016](0016-analyze-long-context.md) | Analyze reads whole documents in long context | Accepted (decision method); outcome measured in M1 |
| [0017](0017-discover-architecture-by-ablation.md) | Discover architecture chosen by ablation | Accepted (decision method); outcome measured in M2 |
| [0018](0018-draft-architecture-by-ablation.md) | Draft architecture chosen by ablation | Accepted (decision method); outcome measured in M3 |
| [0019](0019-local-docker-terraform-cloud.md) | Docker locally, Terraform-managed Google Cloud for anything shared or deployed | Accepted |
