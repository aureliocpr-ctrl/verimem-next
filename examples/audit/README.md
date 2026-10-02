# Example: a memory reliability audit

This folder is a complete audit run on invented data, so you can see what the deliverable
looks like before running it on your own memories.

| File | What it is |
|---|---|
| `pairs.jsonl` | the input: 32 memories, each with the text it was extracted from |
| `report-en/`, `report-it/` | the output of `verimem audit`, in English and Italian |
| `report-*/report.md` | the report a person reads |
| `report-*/report.html` | the same report as a self-contained page, to print to PDF |
| `report-*/report.json` | everything, one row per memory, for your own analysis |
| `report-*/review.csv` | the memories that could be judged, with their source, for a person to check |
| `report-*/review-summary.md` | the output of `verimem audit-review` once `review.csv` is filled |
| `fill_review_from_labels.py` | fills `review.csv` from the answer key (only for this example) |

## The data is invented, and built to show every kind of finding

`pairs.jsonl` holds 32 memories as an LLM-based memory layer might have extracted them:
20 from sales calls and emails of an Italian company, 12 from a personal assistant's chats
in English. People and companies are fictional. Claude wrote the pairs to cover each case
the report distinguishes: faithful memories, details the source never states (a job title,
a percentage, a reason), numbers that differ from the source, statements the source
contradicts, and memories whose source was not kept.

**The share of unsupported memories in this example (53%) says nothing about any real
system.** It reflects how the example was built.

Each row also carries the label Claude intended (`label`: `S` stated, `N` not stated, `C`
contradicted) and, for edge cases, a `note`. `verimem audit` ignores both fields;
`verimem eval` uses the label as an answer key.

## How it was generated

```
verimem audit examples/audit/pairs.jsonl --out examples/audit/report-en --lang en
verimem audit examples/audit/pairs.jsonl --out examples/audit/report-it --lang it
python examples/audit/fill_review_from_labels.py examples/audit/report-en
verimem audit-review examples/audit/report-en --lang en
```

(and the same for `report-it`; `scripts/evals.sh` runs all of it). In a real audit a person
fills the `stated_by_source` column of `review.csv` by reading each memory next to its
source, top-down in each group; here it is filled from the answer key so that the last step
has something to show.

## Where the verifier and the answer key disagree

`verimem eval examples/audit/pairs.jsonl` ([`docs/eval/example-pairs.md`](../../docs/eval/example-pairs.md))
compares the verdicts with the labels: 12 of 14 `S` verified, 1 of 8 `N` and 0 of 8 `C`
verified. The three disagreements:

- **crm-20**, "Davide è il responsabile IT di Logistica Delta", verified (p=0.87). The
  source says Davide works in IT ("Davide (IT di Logistica Delta)"); "head of IT" is added.
  This is a real error of the judge, of exactly the kind the product exists to catch, and
  the reason the report asks a person to check a sample.
- **pa-05**, "The user does not want meetings scheduled before 9:30 on weekdays", left
  `uncertain` (p=0.24). The source says "Don't schedule anything before 9:30 on weekdays":
  a paraphrase the judge missed.
- **crm-05**, "Termoidraulica Alfa ha 12 tecnici sul campo", not supported (p=0.02).
  Labelled `S` when written, but the source chunk only says "Paolo Ferri: … abbiamo 12
  tecnici"; the company's name is in a different chunk of the same call. The verifier is
  right that this chunk does not say it. When a memory combines several parts of a
  conversation, pass the whole conversation as its source. (With the first, real-sounding
  company names of this example the same memory scored 0.28 and stayed `uncertain`: names
  move the judge's scores.)

## Running it on your own memories

Export one row per memory with the text it was extracted from, as JSON lines
(`{"id": ..., "source": ..., "memory": ...}`) or CSV with the columns `source,memory`
(`fonte,memoria` works too, with `,` or `;`). If your memory layer does not keep the text
each memory came from, replay a sample of conversations through its extraction step and log
what goes in and what comes out.
