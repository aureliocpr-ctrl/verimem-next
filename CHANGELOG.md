# Changelog

## 0.9.0 (unreleased)

First release of the rewrite. Nothing from 0.7.x carries over: new code, new storage format,
new command line and new MCP tools (the old `hippo_*` tools are gone). The reasons are in
[ADR-0001](docs/adr/0001-rewrite-from-scratch.md).

### Added

- **Verifier**: sentence windows of the source (a window made only of questions is never
  evidence), a lexical and character-trigram prefilter for long sources, a deterministic veto
  on numbers, amounts and dates the source does not contain (Italian and English, digits and
  words), a context check for reversals, and a batched NLI judge. Default judge:
  `MoritzLaurer/bge-m3-zeroshot-v2.0-c` (MIT), loaded from the local cache only.
- **Memory**: one write path; statuses `verified`, `unverified`, `quarantined`, `rejected`,
  `superseded`, `forgotten`, decided by one function; trust by source author; supersession by
  subject; human review; `forget` that removes the text from the database file; an audit hash
  chain that stores keyed hashes, never text.
- **Reads**: `recall` (SQLite FTS5, English stemming) and `ask`, which answers from verified
  facts or abstains with the reason.
- **Evaluation**: `verimem eval`, `eval-ask` and `calibrate`; thresholds chosen on half the
  pairs and measured on the other half; Markdown reports that record the command, the judge
  and the policy.
- **Memory reliability report**: `verimem audit` (Markdown in English or Italian, JSON, and a
  review sheet) and `verimem audit-review` (an estimate checked by a person, with a 95%
  interval).
- **Interfaces**: a command line with 17 commands and an MCP server on stdio; the tool that
  approves facts is off unless `--allow-review`.
- **Data and documents**: regression cases, TruthfulQA pairs, two QA sets,
  [`docs/EVAL.md`](docs/EVAL.md), design notes and nine ADRs.

### Known limitations

See [Limits](README.md#limits) in the README and [`docs/EVAL.md`](docs/EVAL.md).
