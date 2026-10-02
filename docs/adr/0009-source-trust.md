# ADR-0009 — Source trust

Status: accepted (2026-10-02)

## Context
Verification against the source does not stop memory poisoning: a poisoned web page does
"say" what it plants. Documented attacks in 2026 used exactly this route.

## Decision
Every source has an author kind: `user`, `document`, `system`, `agent`, `tool`, `web`.
A trust policy says which kinds may verify a fact. Default: `user`, `document`, `system`.
Facts sourced only from untrusted kinds are stored `unverified`, labelled with the reason.

## Consequences
- Agents must pass the author kind; the MCP tool defaults to `user` and documents why.
- Operators can widen trust explicitly (for example, a curated internal tool).
