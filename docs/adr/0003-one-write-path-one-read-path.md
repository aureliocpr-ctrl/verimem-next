# ADR-0003 — One write path, one read path

Status: accepted (2026-10-02)

## Context
In the old code base the same score led to different outcomes depending on the port used
(SDK, transcript promotion, conversation ingest, MCP). Each port re-implemented the decision.

## Decision
`Memory.remember` is the only code that turns a verdict into a status. `Memory.recall` and
`Memory.ask` are the only read paths. CLI, MCP and adapters are thin and call these methods.

## Consequences
- A test asserts that the status mapping lives in one function (`memory._status_for`).
- New surfaces add no decision logic; reviewers reject one that does.
