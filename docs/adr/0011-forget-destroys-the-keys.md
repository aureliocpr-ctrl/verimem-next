# ADR-0011 — `forget` destroys the keys of a fact's hashes

Status: accepted (2026-10-02)

## Context
The audit chain must survive deletion, so it stores hashes, never text. The first version
keyed every hash with one store-wide key kept in the same file. Whoever held the file and
could guess the exact words of a forgotten fact (a short claim such as "Maria moved to Milan
in 2021.") could confirm the guess by recomputing the hash. The chain also logged the judge's
score, which rerunning the judge on a guessed claim and source reproduces.

## Decision
Each fact gets its own random key for its hashes in the chain (claim, source, reason for
forgetting). `forget` wipes that key together with the text; the source row is deleted when
no other fact uses it; the chain does not log scores and the tombstone keeps the label, not
the score. The store-wide key remains only for source ids, which exist only while a fact
uses the source.

## Consequences
- After `forget`, the chain still verifies, and nothing left in the file can confirm a guess
  of what the fact, its source or the reason said. A test intercepts every keyed hash
  computed during the writes and checks that any one derived from the forgotten words and
  still in the file has lost its key.
- The chain proves that a write happened, with its status, label, judge and policy, but no
  longer which score the judge gave.
- Store schema 2 (the per-fact key column); a store of another schema is refused.
