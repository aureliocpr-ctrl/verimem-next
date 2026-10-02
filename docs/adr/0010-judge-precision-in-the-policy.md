# ADR-0010 — The judge's numeric precision is part of the policy

Status: accepted (2026-10-02)

## Context
The default judge's weights are stored in float16. transformers 5 loads such a checkpoint as
float16, transformers 4 as float32: the same claim and source got slightly different scores
depending on the library installed, and the speed on a CPU without float16 arithmetic was
unknown. Precision was an accident of the environment, not a decision.

## Decision
The policy names the precision (`judge_dtype`): `float32` by default, `bfloat16` as an
option. The model is loaded straight into it. A judge that does not run in float32 says so
in its id (`hf:<model>@<revision>+bfloat16`), so every verdict records it.

## Consequences
- Same scores on every CPU and with either transformers major version.
- float32 costs memory: about 3 GB resident for the default judge, 4 GB at peak while
  loading (measurements in docs/EVAL.md).
- On CPUs with AMX units, bfloat16 is about five times faster and moves scores by up to
  0.04 (2 of 600 pairs crossed 0.5 in the measurement): an operator choice, recorded in
  each verdict, never a silent default.
