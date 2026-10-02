### `datasets/review-cases.csv`

Produced by `verimem eval datasets/review-cases.csv --judge lexical --markdown docs/eval/review-cases-lexical.md`. Judge `lexical:v1`, policy `0.9.0-provisional`.

| Pairs (S / N / C) | AUROC S vs N (95% CI) | AUROC S vs N+C | Verified at policy: S / N / C | Held-out, target 8% true loss: true lost / N admitted | s per pair |
|---|---|---|---|---|---|
| 15 / 19 / 6 | 0.753 (0.59-0.90) | 0.641 | 100% / 79% / 100% | 8% / 71% | 0.00 |

Verified although labelled N or C (15 of 21):

- `N` → `supported` (p=0.6): The user is presenting a talk at the conference in Lisbon.
- `N` → `supported` (p=0.5): Anna is a senior data engineer.
- `N` → `supported` (p=0.6): The user's daughter attends a private school.
- `N` → `supported` (p=0.5): The incident was caused by a memory leak in the cache nodes.
- `N` → `supported` (p=0.75): Marco approved the pull request.
- `N` → `supported` (p=0.5): The team prefers Linear because it is faster.
- `N` → `supported` (p=0.75): L'utente si è trasferito a Bologna per lavoro.
- `N` → `supported` (p=0.75): Il fornitore ha consegnato i pezzi in ritardo.
- `N` → `supported` (p=0.75): Il comitato ha approvato il progetto di Giulia.
- `N` → `supported` (p=0.75): Il vecchio server di posta era stato compromesso.
- `N` → `supported` (p=0.5): L'utente sta imparando lo spagnolo per trasferirsi a Madrid.
- `N` → `supported` (p=0.6): La riunione di oggi è stata annullata perché il cliente era malato.
- `N` → `supported` (p=0.6): The user's dog Toby is a golden retriever.
- `N` → `supported` (p=0.667): La versione 2.3 dell'app mobile ha ricevuto recensioni positive.
- `N` → `supported` (p=0.75): The board approved the budget unanimously.
