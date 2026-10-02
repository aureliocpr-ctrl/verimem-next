# verimem — design

This document describes what verimem is, the invariants it must never break, and how the
pieces fit. Decisions with alternatives are recorded in [`docs/adr/`](adr/). The work plan
lives in [`CHECKLIST.md`](../CHECKLIST.md); the current state in [`HANDOFF.md`](../HANDOFF.md).

## 1. The problem

AI agents with long-term memory store facts that an LLM extracted from conversations,
documents and tool output. Measured on public benchmarks, a large share of those facts are
wrong, and the commonest kind of error is not an invented entity but a plausible detail the
source never stated ("Anna joined the data team" becomes "Anna is a senior data engineer").
Once stored, the detail is served back as fact, with no way to tell it from what the user
actually said. Memory is also an attack surface: untrusted content (a web page, an email, a
tool result) can plant "memories" that later sessions treat as trusted.

## 2. What verimem is

A memory layer for agents built around one rule:

> **Nothing is served as a fact unless its source says it.**

Concretely:

1. **Gated writes.** Every candidate memory is checked against the source it came from. Only
   a claim the source supports becomes `verified`. Everything else is kept, labelled, and
   never served as fact by default.
2. **Evidence on every read.** A recalled fact carries the exact sentence of its source that
   supports it, where it came from, and which judge and policy admitted it.
3. **Abstention.** When no verified memory answers a question, the answer is an explicit
   "not in memory", not the nearest fact.
4. **Tamper-evident audit trail.** Every write, review and deletion is recorded in a
   hash-chained log that can be verified and exported.

The same verifier is usable on its own, in front of any other memory store, and in batch
to audit an existing memory (the "memory reliability report").

### Non-goals

- verimem checks **consistency with the source**, not truth. A wrong source produces a
  verified wrong fact. Source trust (section 6.4) limits which sources can verify.
- It is not a general RAG framework, an agent framework or a vector database.
- It does not decide what is worth remembering; the extractor does.

## 3. Invariants (tests must enforce these)

1. **Verified fails closed.** A fact is `verified` only if a model judge (not a heuristic)
   scored it `supported` under the active policy, or a named human approved it. No judge, no
   source, judge error, untrusted source → never `verified`.
2. **One write path, one read path.** Every surface (Python API, CLI, MCP, adapters) calls
   `Memory.remember` / `Memory.recall` / `Memory.ask`. No surface re-implements a decision.
3. **Every verdict is reproducible.** It records judge id (model, revision and, when not
   float32, the precision the model ran in), policy version, verimem version, scores and
   evidence offsets. The precision is set by the policy, never left to the installed
   library's default.
4. **Evidence is what the judge used**: the source window with the highest support score,
   not the window with the most words in common.
5. **No silent network calls.** Nothing contacts a remote service unless configured
   explicitly. Model downloads happen only in `verimem warmup` or with explicit consent.
6. **Numbers come from commands.** Every metric in README or docs is produced by
   `verimem eval` and committed with the command that produced it.
7. **Deletion deletes.** `forget` removes the fact text and, when no other fact uses it, the
   source. The audit log stores hashes, never raw text, so it survives deletion intact. A
   fact's hashes are keyed with its own key, which `forget` destroys, and the judge's score
   is not logged: nothing left in the file can confirm a guess of what the fact, its source
   or the reason for forgetting it said.

## 4. Architecture

```
            ┌────────────── surfaces ──────────────┐
            │ Python API   CLI   MCP server   (HTTP, adapters: later)
            └───────────────┬──────────────────────┘
                            ▼
                 ┌──────── Memory ────────┐
   remember ───► │ trust → Verifier → status │──► Store (SQLite + FTS5) ──► AuditLog
   recall/ask ─► │ retrieve → Relevance gate │◄── Store                    (hash chain)
                 └───────────┬───────────────┘
                             ▼
                        Verifier ──► Judge (pluggable: HF NLI model | rules | LLM opt-in)
                             └─────► quantity check (deterministic)
```

Modules (`src/verimem/`):

| Module | Responsibility |
|---|---|
| `types.py` | Public dataclasses and enums: `Label`, `Status`, `Verdict`, `Evidence`, `WriteResult`, `Recalled`, `Answer` |
| `text.py` | Sentence splitting with character offsets, whitespace normalisation, language guess, content tokens |
| `numbers.py` | Quantity and date extraction (IT/EN, digits and words), matching claim quantities against the source |
| `judges/` | `Judge` protocol; `HFNLIJudge` (transformers); `LexicalJudge` (baseline, never trusted to verify) |
| `policy.py` | Versioned thresholds per judge and language, loaded from JSON |
| `verifier.py` | `Verifier.check(source, claim) → Verdict`; batch `check_many` |
| `relevance.py` | Answerability scoring for `ask` (abstention) |
| `store.py` | SQLite schema, migrations, FTS5 search |
| `audit.py` | Append-only hash-chained event log: append, verify, export |
| `memory.py` | `Memory`: remember, recall, ask, review, forget, history, stats |
| `evalkit.py` | Labelled datasets, metrics (AUROC, bootstrap CI, held-out thresholds), calibration |
| `report.py` | Batch audit of (source, memory) pairs → JSON + Markdown report |
| `cli.py` | `verimem` command |
| `mcp_server.py` | MCP server exposing the same operations |

## 5. The verifier

Input: `source` (text), `claim` (one atomic statement). Output: `Verdict`.

1. **Windows.** The source is split into sentences with offsets. Candidate windows are
   single sentences and pairs of adjacent sentences, plus the whole source when short. A
   window made only of questions is skipped: a question asserts nothing (next to its answer
   it is still context). When there are many windows, a lexical and character-trigram
   prefilter keeps the `max_windows` most relevant (4 in the default policy, chosen on
   RAGTruth's train split: [EVAL.md](EVAL.md#how-many-windows-to-judge)), always including
   the whole source when it is short enough to be a window.
2. **Quantity check.** Every number, percentage, amount and date in the claim must appear in
   the source (digits or words, IT/EN, with thousands/decimal ambiguity resolved both ways).
   A missing quantity is a deterministic `not_supported`, whatever the model says. This is
   the one deterministic layer kept from the old code base: measured, it stopped every
   invented number.
3. **Judge.** All windows are scored in one batched call: entailment probability, and
   contradiction probability when the judge is three-way.
4. **Decision** with the policy thresholds for the claim's language, in this order: a missing
   quantity gives `not_supported` (unless a three-way judge finds a contradiction); a
   contradiction ≥ `contradiction` with weak support gives `contradicted`; best entailment ≥
   `support` gives `supported`, unless a larger window around the best one scores below
   `uncertain` (the context reverses it: "moved to Friday"), which gives `uncertain`;
   entailment ≥ `uncertain` gives `uncertain`; otherwise `not_supported`.
5. **Evidence**: the best-supporting window (or the contradicting one).

Default judge: `MoritzLaurer/bge-m3-zeroshot-v2.0-c` (MIT, commercially-friendly training
data, multilingual). It is binary (entailment / not entailment), so by default contradictions
surface as `not_supported`. See ADR-0007 for the measurements behind the choice and the
conditions to change it.

## 6. The memory

### 6.1 Data model (SQLite)

- `sources(id, text, origin, author, observed_at, created_at, meta)`: the id is a keyed hash
  of author, origin and normalised text, so each fact keeps the provenance of its own write
- `facts(id, text, norm, subject, status, reason, label, support, verdict JSON (with the
  evidence), source_id, written_by, created_at, valid_from, superseded_by, superseded_at,
  reviewed_by, meta, hash_key)` + FTS5 index on `text` (Porter stemming, diacritics
  removed); `hash_key` keys the fact's hashes in the audit chain and is wiped by `forget`
- `events(seq, ts, kind, fact_id, payload JSON, prev_hash, hash)` — the audit chain
- `meta(key, value)` — schema version, store id, the key for source ids

### 6.2 Statuses

| Status | Meaning | Served by default |
|---|---|---|
| `verified` | the source supports it (model judge) or a human approved it | yes |
| `unverified` | no source, untrusted source, uncertain verdict, or no judge available | no |
| `quarantined` | the source does not support it, or contradicts it | no |
| `rejected` | a human rejected it after review | no |
| `superseded` | replaced by a newer verified fact on the same subject | no (history only) |
| `forgotten` | deleted on request; text removed, tombstone kept | no |

### 6.3 Write path — `remember(claim, source=..., author=..., subject=...)`

1. Validate input.
2. Source trust: sources whose author is not trusted for verification (by default `web`
   and `tool`) can never produce `verified`; the fact is stored `unverified`.
3. Verify with the verifier; map the label to a status.
4. If verified and a `subject` is given, earlier verified facts on that subject are
   superseded when the new source is not older.
5. Insert source (one row per author, origin and text), fact, FTS row and audit event in
   one transaction. A verified fact identical to one already verified on the same subject is
   not stored twice (`duplicate_of`), and neither is its source: the known fact keeps its
   own evidence, and forgetting it leaves nothing behind.

### 6.4 Human review

`review(fact_id, approve|reject, reviewer)` turns an `unverified` or `quarantined` fact into
`verified` (reason recorded: human) or `rejected`. This is the escape hatch for judge
mistakes and the basis of a review queue.

### 6.5 Read path

- `recall(query, k)`: full-text search (BM25 via FTS5) over facts with the requested
  statuses (default: `verified`), excluding superseded and forgotten. Each result carries
  status, evidence sentence, source origin and verdict summary.
- `ask(question, k)`: recall candidates, then score answerability with a relevance model;
  return the facts above `relevance_threshold`, or abstain with a reason. Verified facts
  between `relevance_related_threshold` and the threshold come back as `related`: true, not
  confirmed as answers, left to the caller's judgement.

## 7. Policy and calibration

Thresholds are data (`policies/*.json`), versioned, with the calibration provenance
(dataset, size, target loss, measured rates). `verimem calibrate labelled.csv` produces a
new policy from a labelled set: the support threshold is chosen on half of the pairs to lose
a target share of true facts and measured on the other half. Every verdict records the policy
version that produced it.

## 8. Evaluation as part of the product

`verimem eval labelled.csv` reports, per judge: AUROC supported-vs-unsupported with
bootstrap confidence intervals, held-out admission and loss rates at the policy thresholds,
per-language results and latency, plus a lexical baseline as a sanity control (if the
baseline is as good as the model, the dataset is too easy). The numbers in README and
`docs/EVAL.md` are produced by this command.

## 9. Interfaces

- **Python:** `Memory`, `Verifier`, `Policy`, `audit_pairs`, `summarize_review`.
- **CLI:** `verimem check | remember | recall | ask | queue | review | forget | stats | chain |
  audit | audit-review | eval | eval-ask | calibrate | warmup | doctor | mcp`.
- **MCP:** tools `remember`, `recall`, `ask`, `check`, `review_queue`, `forget`, `stats`, and
  `review` only with `--allow-review`. The judge starts loading when the server starts.

## 10. Dependencies

The core uses only the Python standard library. Heavy dependencies are optional extras:
`[nli]` (torch, transformers) for model judges, `[mcp]` for the MCP server, `[dev]` for tests
and lint. Without `[nli]`, verimem still stores and recalls, but nothing becomes `verified`
except by human review.
