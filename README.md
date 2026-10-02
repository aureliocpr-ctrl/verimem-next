# verimem

**Verified memory for AI agents.** A memory is stored as a fact only if the text it came
from says it. Every fact carries the passage that supports it. When nothing in memory
answers a question, `ask` says so instead of guessing.

Status: alpha (0.9.0.dev0). The thresholds are provisional until they are calibrated on
real data; the numbers below say what has and has not been measured.

## Why

Memory layers for agents use an LLM to turn conversations and documents into "memories".
Some of what gets stored was never said: a job title guessed from a surname, a percentage,
a reason, a date off by a year. Later the agent serves it back as if the user had said it.

verimem checks each memory against the text it came from before it counts as a fact:

```
claim + source ──► verifier ──► verified | unverified | quarantined | rejected
                                + evidence: the passage, its offsets, the judge's score
```

The verifier splits the source into sentence windows, asks a local NLI model whether a
window entails the claim, and vetoes any claim with a number, amount or date the source
does not contain. After the one-time model download, nothing leaves your machine.

## What it does

- **Gated writes.** `remember(claim, source=...)` stores a claim as `verified` only when
  the source supports it, the source was written by someone you trust (the user, a
  document, the system; not the agent itself, a tool or the web) and the judge is a model.
  Everything else is kept, with its status and the reason.
- **Evidence on every read.** `recall` and `ask` return facts with the supporting passage,
  its exact offsets in the source, and the judge and policy that verified it.
- **Abstention.** `ask` answers only from verified facts that pass a relevance check, and
  otherwise says "not in memory" and why.
- **Human review.** A person can approve or reject quarantined facts. The agent cannot,
  unless you allow it.
- **Audit trail.** Every write, review and deletion is appended to a hash chain that stores
  keyed hashes, never text. `verimem chain verify` finds the first tampered event.
- **Real deletion.** `forget` removes the text from the database file, not only from the
  index, and destroys the key of the fact's hashes in the audit chain: nothing left in the
  file can confirm a guess of what the fact said.
- **Memory reliability report.** `verimem audit` checks memories exported from any memory
  system against their sources and writes a report, plus a sheet for a person to check a
  sample and turn it into an estimate checked by a human.

## Install

Not on PyPI yet: `pip install verimem` currently installs the previous implementation
(0.7.x). From source:

```
git clone https://github.com/aureliocpr-ctrl/verimem-next
cd verimem-next
pip install -e ".[nli,mcp]"
verimem warmup        # downloads the default judge once: 1.16 GB
```

Python 3.10 or later. The core has no dependencies; the `nli` extra brings torch and
transformers, the `mcp` extra the MCP server. The default judge needs about 1.4 GB of memory
and runs on CPU.

## Quickstart

```python
from verimem import Memory

memory = Memory(":memory:")  # Memory("memory.db") keeps it in a file

source = ("User: I moved from Rome to Milan in 2021 for a job at a bank. "
          "I still go back to Rome most weekends.")

for claim in ["The user moved to Milan in 2021.",
              "The user works as a financial analyst.",
              "The user moved to Milan in 2019."]:
    result = memory.remember(claim, source=source, author="user")
    print(f"{result.status.value:<12} {claim}  ({result.verdict.reason})")

for question in ["When did the user move to Milan?",
                 "Which city did the user move to?",
                 "What is the name of the user's dog?"]:
    answer = memory.ask(question)
    print(f"\n{question}")
    if answer.abstained:
        print(f"  not in memory: {answer.reason}")
    for hit in answer.facts:
        print(f"  {hit.fact.text}  (relevance {hit.score:.2f})")
        print(f"  evidence: {hit.fact.evidence.text!r}")
```

Output ([`examples/quickstart.py`](examples/quickstart.py), run on 2026-10-02):

```
verified     The user moved to Milan in 2021.  (supported by the source (p=1.00))
quarantined  The user works as a financial analyst.  (the source does not state this (best support p=0.01))
quarantined  The user moved to Milan in 2019.  (quantities not in the source: 2019)

When did the user move to Milan?
  The user moved to Milan in 2021.  (relevance 0.64)
  evidence: 'User: I moved from Rome to Milan in 2021 for a job at a bank.'

Which city did the user move to?
  not in memory: no verified fact answers the question (best relevance p=0.32)

What is the name of the user's dog?
  not in memory: no verified fact answers the question (best relevance p=0.00)
```

The second question shows the main weakness: `ask` is strict and sometimes abstains
although the answer is stored (see [Limits](#limits)).

### In an agent

The usual loop, sketched (`extract_memories` stands for your own LLM extraction step):

```python
memory = Memory("memory.db")

# After a user turn: store what the extractor proposes, with the turn as its source.
for claim in extract_memories(user_message):
    memory.remember(claim, source=user_message, author="user", origin=f"chat:{chat_id}")

# Before answering: verified facts with their evidence, and an explicit "not in memory".
answer = memory.ask(question)
facts = [(r.fact.text, r.fact.evidence.text) for r in answer.facts]
maybe = [r.fact.text for r in answer.related]  # verified, but not confirmed as answers
```

Text the agent read on the web or got from a tool goes in with `author="web"` or
`author="tool"`: it is kept, but never verified (see `examples/poisoning.py`).

### Command line

```
$ verimem check "Anna leads the data platform team." \
    --source-text "Marco: Anna leads the data platform team since March; she reports to the CTO."
supported: supported by the source (p=1.00)
evidence: “Marco: Anna leads the data platform team since March; she reports to the CTO.”
judge hf:MoritzLaurer/bge-m3-zeroshot-v2.0-c@705510dfe0f3, policy 0.9.0-provisional

$ verimem remember "Anna is a senior data engineer." \
    --source-text "Marco: Anna leads the data platform team since March; she reports to the CTO."
quarantined (id 01a0fc8669ebca0825f032): the source does not state this (best support p=0.15)
```

Other commands: `recall`, `ask`, `queue`, `review`, `forget`, `stats`, `chain verify|export`,
`audit`, `audit-review`, `eval`, `eval-ask`, `calibrate`, `warmup`, `doctor`, `mcp`.
`verimem <command> --help` explains each; `--json` gives machine-readable output.

### MCP server (Claude Desktop, Claude Code, any MCP client)

```json
{
  "mcpServers": {
    "verimem": { "command": "verimem", "args": ["mcp", "--db", "/path/to/memory.db"] }
  }
}
```

Tools: `remember`, `recall`, `ask`, `check`, `review_queue`, `forget`, `stats`. `remember`
requires `source_author` (user, document, system, agent, tool or web): there is no default,
so web text the agent forgot to label cannot pass for the user's words. The `review` tool,
which lets the agent approve facts the verifier did not verify, is only there with
`verimem mcp --allow-review`.

## Audit the memories you already have

```
verimem audit memories.jsonl --out report/ --lang en     # or --lang it
```

The input has one memory per line with the text it was extracted from:
`{"id": "...", "source": "...", "memory": "..."}` (or CSV with `source,memory`, also
`fonte,memoria`). The output folder holds `report.md` (how many memories their source
supports, which it does not, with the closest passage, and which add numbers the source
never states), the same report as a self-contained `report.html` (print it to PDF for a
client), `report.json`, and `review.csv`: every memory that could be checked, with its source,
grouped by verdict and shuffled inside each group. A person answers yes or no for a few rows from the
top of each group, then

```
verimem audit-review report/
```

combines those answers with the size of each group into an estimate of the share of
memories their source does not state, with a 95% interval.
[`examples/audit/`](examples/audit/) is a complete run on invented data, in English and
Italian.

## How well it works

All from [`docs/EVAL.md`](docs/EVAL.md), where every number has the command that produced
it. None of the data is agent memory from real use.

| Data | Written by | Claims the source does not state, verified anyway | True claims verified |
|---|---|---|---|
| 40 review cases (IT/EN) | Claude | 0 of 25 | 15 of 15 |
| 30 example memories (IT/EN) | Claude | 1 of 16 | 12 of 14 |
| 582 TruthfulQA pairs (EN) | people | 10 of 300 (3.3%) | 132 of 282 (47%)* |

\* TruthfulQA's "true" claims are other correct answers to the same question and often add
information the source does not contain; in a sample of 40 refused ones, 30 did. About one
refusal in six was a real miss.

`ask` (two sets of 50 questions written by Claude): it answered 17 and 15 of the 25 questions
the facts answer, and handed a fact to 0 and 2 of the 25 they do not.

Speed on 4 CPU cores without GPU: 7.4 s to load the judge, then 0.07-0.28 s per claim.

## Limits

- **It checks consistency with the source, not truth.** A wrong source gives a wrong
  verified fact. Over MCP, the agent supplies the source: verimem checks that the claim
  follows from the text it was given, not that the text is what the user really said. For
  provenance you can rely on, call `remember` from your application with the text you hold.
- **`ask` abstains too often.** On the two QA sets it missed 8 and 10 of 25 answerable
  questions, for example "Who leads the data platform team?" against "Anna leads the data
  platform team." (relevance 0.11). It then hands over the verified facts it found related,
  with their relevance, and leaves the judgement to the caller: the right fact was among
  them for 8 of the 8 and 5 of the 10 misses.
- **The judge makes mistakes.** It accepted "Davide è il responsabile IT" (head of IT) from
  "Davide (IT di Logistica Delta)", and misses some paraphrases. Questions in the source can lend
  a claim support ("Why does the government lie about…?").
- **Contradictions come out as `not_supported`**, not `contradicted`: the default judge is
  binary.
- **No arithmetic or inference**, by design: "15 technicians" is not supported by "12
  technicians, and we hire three more".
- **Keyword retrieval.** `recall` and `ask` find facts that share words with the query
  (English words are stemmed); a question in English does not find a fact stored in Italian.
- **Provisional thresholds**, set on data written by Claude. Calibrate on your own labelled
  pairs with `verimem calibrate`.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md): the design and its invariants; [`docs/adr/`](docs/adr/):
  the decisions and why.
- [`docs/EVAL.md`](docs/EVAL.md): every measurement, with commands.
- [`CHECKLIST.md`](CHECKLIST.md) and [`HANDOFF.md`](HANDOFF.md) (Italian): the plan and the
  current state, for whoever picks the work up.

## License

Apache-2.0 ([LICENSE](LICENSE)). The default judge,
[MoritzLaurer/bge-m3-zeroshot-v2.0-c](https://huggingface.co/MoritzLaurer/bge-m3-zeroshot-v2.0-c),
is a separate download under the MIT license.

Audits of existing agent memory and integration work: Aurelio Capriello,
[verimem.com](https://verimem.com), or open an issue.
