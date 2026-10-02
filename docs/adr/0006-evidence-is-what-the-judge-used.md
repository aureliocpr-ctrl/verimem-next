# ADR-0006 — Evidence is what the judge used

Status: accepted (2026-10-02)

## Context
The old "grounding span" was chosen by word overlap before judging, so the "proof" shown on
read was the most similar text, not the text that supports the fact.

## Decision
The verifier scores candidate windows of the source and returns the window with the highest
support score as evidence, with character offsets into the stored source.

## Consequences
- Evidence costs one judge call per window; windows are capped (`max_windows`) and batched.
- When the verdict is not `supported`, the evidence is the closest window, labelled as such.
