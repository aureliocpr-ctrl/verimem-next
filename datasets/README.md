# Datasets

Labelled (source, claim) pairs used for regression tests, evaluation and calibration.
Labels: `S` = the source supports the claim, `N` = plausible but not stated by the source,
`C` = the source contradicts the claim.

| File | Pairs | Who wrote and labelled it | Use it for |
|---|---|---|---|
| `review-cases.csv` | 40 (15 S, 19 N, 6 C), IT/EN | Claude, during the independent review of the old verimem (2026-10-02) | regression: these are the cases the old judge failed |
| `qa-mini.json` | 20 facts, 50 questions (25 answerable), IT/EN | Claude (2026-10-02) | choosing the relevance threshold of `Memory.ask` |
| `qa-heldout.json` | 20 facts, 50 questions (25 answerable), IT/EN | Claude (2026-10-02), before any change it measures | checking that a change to `ask` designed on `qa-mini.json` generalises |
| `qa-heldout-2.json` | 20 facts, 50 questions (25 answerable), IT/EN | Claude (2026-10-02), before the next change it measures | the same check for the next change; `qa-heldout.json` was looked at in detail and no longer counts as held out |
| `crosslingual-cases.csv` | 18 (8 S, 5 N, 5 C): Italian sources with English claims and the reverse | Claude (2026-10-02) | memories extracted in another language than the conversation, as LLM extraction often does |
| `truthfulqa-pairs.jsonl` | 582 (282 S, 300 N), EN | TruthfulQA authors, reshaped into pairs (see below) | an external check written by people, not by the model under test |

`review-cases.csv` and the three QA sets were written by the same model that built the
verifier:
they catch regressions, they prove nothing about real-world performance. TruthfulQA is
written by people but is not agent memory. Real evidence comes from pairs taken from real use
and labelled by a person before seeing any score (CHECKLIST, phase 8).

Format: CSV with header `id,lang,source,claim,label`. The evaluation tools also accept the
Italian headers `fonte,fatto,etichetta` and `;` as separator.

## TruthfulQA attribution

`truthfulqa-pairs.jsonl` is derived from TruthfulQA (Lin, Hilton and Evans, 2021, "TruthfulQA:
Measuring How Models Mimic Human Falsehoods"), https://github.com/sylinrl/TruthfulQA, licensed
under Apache-2.0. Each row pairs a question with its correct answer (the source) and either a
paraphrase of a correct answer (`S`) or a common misconception (`N`). The pairs come from the
held-out split prepared in the previous verimem repository; the 18 rows whose claim repeats the
source verbatim were dropped.
