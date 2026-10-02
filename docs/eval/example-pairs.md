### `examples/audit/pairs.jsonl`

Produced by `verimem eval examples/audit/pairs.jsonl --markdown docs/eval/example-pairs.md`. Judge `hf:MoritzLaurer/bge-m3-zeroshot-v2.0-c@705510dfe0f3`, policy `0.9.0-provisional`.

| Pairs (S / N / C) | AUROC S vs N (95% CI) | AUROC S vs N+C | Verified at policy: S / N / C | Held-out, target 8% true loss: true lost / N admitted | s per pair |
|---|---|---|---|---|---|
| 14 / 8 / 8 | 0.973 (0.91-1.00) | 0.987 | 86% / 12% / 0% | 12% / 12% | 0.24 |

Verified although labelled N or C (1 of 1):

- `N` → `supported` (p=0.88): Davide è il responsabile IT di Logistica Po.

Not verified although labelled S (2 of 2):

- `S` → `uncertain` (p=0.279): Termoidraulica Ferri ha 12 tecnici sul campo.
- `S` → `uncertain` (p=0.237): The user does not want meetings scheduled before 9:30 on weekdays.
