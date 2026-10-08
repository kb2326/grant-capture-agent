# ADR-0002: ADK 2 workflow graphs

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The Discover agent may follow a Plan, Execute, Verify pattern. That needs a loop (refine up to three times), branches (sufficient or not), and a human approval step that can pause the run and resume later, possibly after a long delay. We want explicit, inspectable control flow with typed state, not behaviour hidden inside one long prompt. The project already targets the Google Cloud managed stack and a $10/month budget.

## Decision
Build the agents with Google ADK 2.x workflows (graph-based) and deploy them on Agent Runtime.

## Alternatives considered
- LangGraph: a strong option for graph workflows, but it sits outside the Google Cloud managed stack, so we would lose managed sessions and deployment integration.
- ADK 1 `LoopAgent`: it handles simple loops but is being phased out in favour of workflows, so we would build on something already deprecated.

## Consequences
Control flow is explicit, state is typed and stored in sessions, and human approval is a first-class resumable step. We accept being tied to the ADK release cadence: breaking changes in ADK 2.x will land on us, so versions are pinned and upgrades are deliberate. Because the same workflow shape supports both the single-pass baseline and the Plan, Execute, Verify variant, the ablation in ADR-0017 can reuse the approval step unchanged.
