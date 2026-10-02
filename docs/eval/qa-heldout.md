### `datasets/qa-heldout.json`

Produced by `verimem eval-ask datasets/qa-heldout.json --markdown docs/eval/qa-heldout.md`. Judge `hf:MoritzLaurer/bge-m3-zeroshot-v2.0-c@705510dfe0f3`, policy `0.9.0-provisional`, relevance threshold 0.4.

| Questions (answerable) | Answered with the right fact | Wrong abstentions | Wrong fact | Retrieval misses | Right abstentions | False answers | AUROC answerable vs not |
|---|---|---|---|---|---|---|---|
| 50 (25) | 15 / 25 | 10 | 0 | 2 | 23 / 25 | 2 | 0.811 |

Not answered but handed over among the related facts: 5 of the 10 answerable questions not answered. Unanswerable questions that got related facts: 3 of 25.
