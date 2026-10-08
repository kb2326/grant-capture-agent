# ADR-0014: Per-agent identity

- Status: Proposed (decided in M4)
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The system will have several agents with different needs: Discover reads the opportunity index, Analyze reads documents and writes briefs, Draft reads company documents that may be sensitive. Least privilege says each should hold only the access it needs, so that one compromised or misbehaving agent cannot reach everything. This matters most once company data and external callers are involved, which is why the decision is deferred to M4.

## Decision
Proposed: give each agent its own Agent Identity, restricted by principal access boundary policies. The final decision is made in M4.

## Alternatives considered
- One shared service account for all agents: far simpler to set up, but a leak or bug in any agent exposes every resource, and audit logs cannot tell agents apart.

## Consequences
If accepted, access is narrower and the audit trail shows which agent did what. The price is more IAM to design, test and maintain, which is real work on a personal project with a small budget. A security review is required before cloud and infrastructure changes merge. If the policies prove too costly to maintain, we will document the narrower compromise we chose.
