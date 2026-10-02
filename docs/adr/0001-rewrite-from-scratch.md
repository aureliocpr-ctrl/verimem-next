# ADR-0001 — Rewrite from scratch

Status: accepted (2026-10-02)

## Context
The previous code base (`aureliocpr-ctrl/verimem`, commit 2635d28) has 130,000 lines in 396
modules, an 8,000-line MCP dispatcher, and at least five write paths that decide the same
verdict in different ways. An independent review measured that its central promise (no
unsupported fact is stored as verified) does not hold for plausible unstated details, and
that the fix is a different judge and a single decision point, not more patches.

## Decision
Start a new repository. No code is copied. The old repository is the reference for what was
learned: the quantity check, the receipts, quarantine instead of deletion, the audit chain,
the habit of writing the prediction before measuring.

## Consequences
- Small surface (target 5-8k lines of library code) that one person can hold in their head.
- Old users keep the old package until this one reaches parity on the features they use.
- Revisit if the rewrite stalls for more than four weeks without reaching the Gate-1 check
  (see CHECKLIST, phase 8).
