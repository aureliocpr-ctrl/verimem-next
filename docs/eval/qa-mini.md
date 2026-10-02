### `datasets/qa-mini.json`

Produced by `verimem eval-ask datasets/qa-mini.json --markdown docs/eval/qa-mini.md`. Judge `hf:MoritzLaurer/bge-m3-zeroshot-v2.0-c@705510dfe0f3`, policy `0.9.0-provisional`, relevance threshold 0.4.

| Questions (answerable) | Answered with the right fact | Wrong abstentions | Wrong fact | Retrieval misses | Right abstentions | False answers | AUROC answerable vs not |
|---|---|---|---|---|---|---|---|
| 50 (25) | 17 / 25 | 8 | 0 | 0 | 25 / 25 | 0 | 0.971 |
