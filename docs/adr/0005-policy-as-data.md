# ADR-0005 — Policy as data

Status: accepted (2026-10-02)

## Context
The old thresholds were constants in code, overridden at runtime with warnings (a shipped
99.64 replaced by 40), and calibrated on the same data used to report results.

## Decision
Thresholds live in versioned JSON policies with their calibration provenance. Calibration
chooses thresholds on one half of a labelled set and reports rates on the other half. Every
verdict records the policy version.

## Consequences
- Changing behaviour means shipping a new policy file, not editing code.
- Customers can calibrate on their own labelled data (`verimem calibrate`).
