# Datasets

Labelled (source, claim) pairs used for regression tests, evaluation and calibration.
Labels: `S` = the source supports the claim, `N` = plausible but not stated by the source,
`C` = the source contradicts the claim.

| File | Pairs | Who wrote and labelled it | Use it for |
|---|---|---|---|
| `review-cases.csv` | 40 (15 S, 19 N, 6 C), IT/EN | Claude, during the independent review of the old verimem (2026-10-02) | regression: these are the cases the old judge failed |

None of these files is evidence about real-world performance: they were written by the same
model that built the verifier. Real evidence comes from pairs taken from real use and
labelled by a person before seeing any score (CHECKLIST, phase 8).

Format: CSV with header `id,lang,source,claim,label`. The evaluation tools also accept the
Italian headers `fonte,fatto,etichetta` and `;` as separator.
