# ADR-0008: Demo access

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
The project will run as a public demo for portfolio reviewers. There is a single user at a time, no customer data, and a hard cost ceiling of $10/month. Every run calls paid models, so unrestricted public access could exhaust the budget. Reviewers should be able to try it with minimal friction.

## Decision
Protect the demo with a shared access code and cap usage at 30 runs per day.

## Alternatives considered
- Identity-Aware Proxy: strong, but it forces reviewers through a Google sign-in and allow-listing, which adds friction.
- Multi-tenant authentication: real user accounts, tenant isolation and per-user data are out of scope for a single-user demo.

## Consequences
Access is simple for reviewers and spend is bounded: the daily cap limits the worst-case model bill. The setup is not suitable for real customers, and the documentation says so plainly. The access code must be kept out of the repository (`.env` is never committed) and can be rotated if it leaks. Anyone with the code shares the same quota, so one heavy user can block others for the day.
