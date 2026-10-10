# ADR-0013: Analyze as an A2A service

- Status: Accepted for M2 as a local service behind a direct/A2A switch (`discover_v4_transport`, M2 spec §3.9); deployment on Agent Runtime in M4
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The Analyze agent is useful to more than one caller: Discover uses it to check candidates, Draft uses the resulting brief, and external clients could call it directly. Its load profile is also different, because reading a 150-page solicitation with a large context is slower and more expensive than a search. Whether to deploy it separately is a question we can answer better once Discover exists.

## Decision
Proposed: deploy Analyze as its own service and call it from other agents over the Agent2Agent (A2A) protocol. The final decision is made in M2, when Discover first needs it.

## Alternatives considered
- Single deployment with Analyze as an in-process sub-agent: simpler, with no network hop, but it couples scaling and releases of Analyze to every other agent.

## Consequences
If accepted, Analyze can be versioned, scaled and secured independently, and external callers reuse it. We pay for a network hop, authentication between agents and a more complex local development setup. This ties in with per-agent identity (ADR-0014). If the hop turns out to cost too much latency or complexity in M2, we fall back to a single deployment and record that here.

## Notes from M2 (2026-10-10)
Running it locally surfaced three real integration issues, now fixed: the standalone server had no Vertex AI configuration, the client rejects an agent card whose URL origin differs from where the card was fetched (`localhost` vs `127.0.0.1`), and the remote agent's default HTTP client timed out before Analyze (~60 s) finished. Both transports return the same verdict on a live check.
