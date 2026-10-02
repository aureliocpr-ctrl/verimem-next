# Changelog

## 0.9.0 (unreleased)

First release of the rewrite. Nothing from 0.7.x carries over: new code, new storage format,
new command line and new MCP tools (the old `hippo_*` tools are gone). The reasons are in
[ADR-0001](docs/adr/0001-rewrite-from-scratch.md).

### Added

- **Verifier**: sentence windows of the source (a window made only of questions is never
  evidence), a lexical and character-trigram prefilter that keeps 4 windows on long sources
  (chosen on RAGTruth's train split), a deterministic veto
  on numbers, amounts and dates the source does not contain (Italian and English, digits and
  words, 24- and 12-hour times), a context check for reversals, and a batched NLI judge.
  Default judge: `MoritzLaurer/bge-m3-zeroshot-v2.0-c` (MIT), loaded from the local cache
  only, in float32 whatever the installed transformers would default to (`judge_dtype`
  bfloat16 as an option for CPUs with AMX). Each verdict names the judge, the policy and the
  verimem version.
- **Memory**: one write path; statuses `verified`, `unverified`, `quarantined`, `rejected`,
  `superseded`, `forgotten`, decided by one function; trust by source author; supersession by
  subject; human review; `forget` that removes the text from the database file, the source
  when no other fact uses it, and the key of the fact's hashes in the audit chain, so nothing
  left in the file can confirm a guess of what the fact said; an audit hash chain that stores
  keyed hashes, never text.
- **Reads**: `recall` (SQLite FTS5, English stemming) and `ask`, which answers from verified
  facts or abstains with the reason, and hands over the verified facts it found related but
  could not confirm as answers.
- **Evaluation**: `verimem eval`, `eval-ask` and `calibrate`; thresholds chosen on half the
  pairs and measured on the other half; Markdown reports that record the command, the judge
  and the policy. `calibrate` aims at a share of true claims lost (`--target-loss`) or caps
  the share of unsupported claims admitted (`--max-admitted`); `eval --pairs-out` writes one
  line per pair. A claim the quantity check refuses is lost whatever the thresholds: it
  scores 0 in threshold analysis and never moves a calibrated threshold.
- **Policies**: `default` and `strict` (calibrated on RAGTruth's train split to admit at most
  5% of unsupported sentences), chosen with `--policy NAME` or a JSON file.
- **Memory reliability report**: `verimem audit` (Markdown in English or Italian, a
  self-contained HTML page, JSON, and a review sheet) and `verimem audit-review` (an estimate checked by a person, with a 95%
  interval).
- **Interfaces**: a command line with 17 commands and an MCP server on stdio; the tool that
  approves facts is off unless `--allow-review`, and `remember` must be told who wrote the
  source (no default author).
- **Data and documents**: regression cases, TruthfulQA pairs, three QA sets,
  [`docs/EVAL.md`](docs/EVAL.md), design notes and eleven ADRs.

### Known limitations

See [Limits](README.md#limits) in the README and [`docs/EVAL.md`](docs/EVAL.md).
