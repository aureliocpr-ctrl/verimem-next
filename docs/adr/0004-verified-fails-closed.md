# ADR-0004 — "verified" fails closed

Status: accepted (2026-10-02)

## Context
The old gate admitted facts as `model_claim` when the judge was missing or still loading,
and minted `verified` from any existing file reference. Both turned uncertainty into trust.

## Decision
A fact becomes `verified` only when (a) a model judge scored it supported under the active
policy, with a trusted source, or (b) a named human approved it. Every other case stores the
fact as `unverified` (or `quarantined` when the judge says the source does not support it).
Heuristic judges (lexical baseline) can never verify.

## Consequences
- Without the `[nli]` extra, verimem works as a plain memory with no verified facts. The
  README says so.
- Reads default to verified facts only; callers opt in to see the rest.
