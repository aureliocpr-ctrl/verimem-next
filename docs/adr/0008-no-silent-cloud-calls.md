# ADR-0008 — No silent network calls

Status: accepted (2026-10-02)

## Context
The old gate escalated uncertain cases to any `claude` CLI found on PATH, sending source and
fact to a cloud service by default, even with offline flags set.

## Decision
verimem never contacts a remote service unless configured explicitly in code or config.
Model files are downloaded only by `verimem warmup` or when the caller passes
`allow_download=True`. An LLM judge for uncertain cases is an explicit, opt-in component.

## Consequences
- First use needs one explicit download step; the error message says exactly which.
