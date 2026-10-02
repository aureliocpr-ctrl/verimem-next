# ADR-0007 — Default judge: bge-m3-zeroshot-v2.0-c

Status: provisional (2026-10-02) — to be confirmed by Gate 1 on real data

## Context
Measured on 380 pairs (independent review, 2026-10-02; scripts in the review attachments):

| judge | own IT/EN cases | README battery | TruthfulQA | HaluEval | s/pair CPU | license / data |
|---|---|---|---|---|---|---|
| old verimem judge | 0.76 | 0.45 | 0.81 | 0.69 | 0.16 | AGPL / own |
| bge-m3-zeroshot-v2.0-c | 1.00 | 1.00 | 0.90 | 0.78 | 0.17 | MIT / synthetic + MNLI + FEVER |
| DeBERTa-v3-large NLI | 1.00 | 1.00 | 0.90 | 0.80 | 0.38 | MIT / includes ANLI (CC BY-NC) |
| Horizon hallucination-guard-base | 0.99 | 1.00 | 0.83 | 0.79 | 0.08 | Apache-2.0 / RAGTruth, WANLI |
| mDeBERTa-v3-base XNLI | 0.99 | 1.00 | 0.80 | 0.69 | 0.13 | MIT / includes ANLI |

(AUROC. On TruthfulQA only bge-m3 and DeBERTa-large beat the old judge beyond the bootstrap
margin. HaluEval is solved by answer length and does not count.)

## Decision
Default to `MoritzLaurer/bge-m3-zeroshot-v2.0-c`: best or tied-best everywhere it counts,
multilingual, and the only strong candidate whose training data is declared commercially
friendly. Horizon is the documented fast alternative.

## Consequences
- The default is binary, so contradictions are reported as `not_supported` unless a
  three-way judge is configured.
- Revisit when Gate 1 (200+ real pairs labelled by the owner) is run: the default is the
  judge that passes it with the cleanest license.
