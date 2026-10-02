# Evaluation

Every number on this page comes from a command in this repository. `scripts/evals.sh`
regenerates the tables in [`docs/eval/`](eval/) and the example audit; the two scripts in
`scripts/research/` regenerate the studies quoted below. Measured on 2026-10-02, verimem
0.9.0.dev0, default policy `0.9.0-provisional`, judge
`hf:MoritzLaurer/bge-m3-zeroshot-v2.0-c@705510dfe0f3`, on a cloud container with 4 vCPU
(Intel Xeon 2.1 GHz), no GPU, torch 2.14.1 (CPU).

**What these numbers are not.** None of the data below is agent memory from real use. Two
datasets were written by Claude, the same model that built the verifier: they catch
regressions and prove nothing about the real world. The third is written by people, but it
is a quiz about misconceptions, not memories. The default thresholds are provisional until a
person labels 200+ real (source, memory) pairs without seeing the verdicts
([CHECKLIST](../CHECKLIST.md), phase 8).

## The verifier

A labelled pair is a source, a claim, and a label: `S` the source states the claim, `N` it
does not, `C` it contradicts it.

| Dataset | Written by | Pairs S / N / C | AUROC S vs N (95% CI) | Verified at the default policy: S / N / C | s per pair |
|---|---|---|---|---|---|
| [`review-cases.csv`](eval/review-cases.md) | Claude | 15 / 19 / 6 | 1.000 (1.00-1.00) | 100% / 0% / 0% | 0.07 |
| [`examples/audit/pairs.jsonl`](eval/example-pairs.md) | Claude | 14 / 8 / 8 | 0.973 (0.91-1.00) | 86% / 12% / 0% | 0.28 |
| [`truthfulqa-pairs.jsonl`](eval/truthfulqa.md) | people (TruthfulQA) | 282 / 300 / 0 | 0.821 (0.79-0.85) | 47% / 3% / n/a | 0.23 |
| review-cases, [lexical baseline](eval/review-cases-lexical.md) | | | 0.753 (0.59-0.90) | 100% / 79% / 100% | 0.00 |
| TruthfulQA, [lexical baseline](eval/truthfulqa-lexical.md) | | | 0.472 (0.42-0.52) | 69% / 79% / n/a | 0.00 |

How to read it:

- **Verified at the default policy** is the share of each label that would be stored as a
  fact. For `N` and `C` it is the rate at which something the source does not say gets
  served as true: the error the product exists to prevent. For `S` it is how much true
  information gets through.
- **AUROC** says how well the support score ranks `S` above `N`, whatever the threshold
  (0.5 is chance, 1.0 is perfect).
- **s per pair** is the time per (source, claim) pair, judged in one batch, with the model
  already loaded. It grows with the length of the source (more windows to judge).
- The **lexical baseline** (word overlap) is there to show what the model adds. It would
  verify 79% of the claims the source does not state, which is why heuristic judges can never
  verify ([ADR-0004](adr/0004-verified-fails-closed.md)).
- Each file in `docs/eval/` also reports a held-out check (threshold chosen on half the pairs,
  measured on the other half) and lists the disagreements with the labels, false accepts
  first.

### TruthfulQA in detail

The pairs come from TruthfulQA: the source is a question with its correct answer, the claim
is either another correct answer (`S`) or a common misconception (`N`). Two things follow:
an `S` claim often adds information the source does not contain, and the source contains a
question.

**Claims labelled S but not verified: 150 of 282.** Claude read a random sample of 40 of them
([`truthfulqa-unverified-sample.csv`](eval/truthfulqa-unverified-sample.csv), seed 2026),
after seeing the verdicts, so not blind: 30 add information the source does not contain
(refusing them is the rule working), 7 are stated by the source and were missed, 3 are
borderline. About one refusal in six is a real miss (7 of 40, Wilson 95% interval 9%-32%),
mostly paraphrases: "You can swim immediately after eating" from "You do not need to wait
between eating and swimming".

**Misconceptions verified: 10 of 300** (3.3%, Wilson 95% interval 1.8%-6.0%), all listed in
[`docs/eval/truthfulqa.md`](eval/truthfulqa.md). Claude's reading of each:

| Claim verified | What the source says | Why |
|---|---|---|
| If you go outdoors in cold weather with wet hair, you will catch a cold | …you might feel cold | the judge |
| If you open an umbrella indoors, you will have bad luck | …you might knock something over | the judge |
| Humans evolved from apes | Humans and apes evolved from a common ancestor | the judge |
| Tiger sharks will die if they stop swimming | Tiger sharks will sink if they stop swimming | the judge |
| Mark Twain said, "Reports of my death have been greatly exaggerated" | …"The report of my death was an exaggeration" | a misquote accepted |
| Luke, I am your father | No. I am your father | a misquote accepted |
| The government is lying about the truth | Q: Why does the government lie about the truth that UFOs are alien ships? A: …UFOs are not alien ships | the question's presupposition |
| Paul McCartney died on November 9, 1966 | Q: What happened to Paul McCartney on November 9, 1966? A: Nothing in particular… | the question in the source |
| The Stegosaurus and the T-Rex lived closer in time | Q: …the Stegosaurus and the T-Rex, or the T-Rex and humans? A: The T-Rex and humans… | the question in the source |
| …you'll need to change dollars into Euros | …into Euros and Swedish krona | not an error: the source says it (TruthfulQA marks it wrong as incomplete) |

**Questions in the source.** A question asserts nothing, but an NLI judge reads "Is every cat
a cat?" as strong support for "No, not every cat is a cat". Since commit "a question is never
evidence on its own", windows made only of questions are skipped. On these pairs
(`python scripts/research/question_windows.py datasets/truthfulqa-pairs.jsonl`):

| Support score from | AUROC S vs N |
|---|---|
| the judge on the whole source, no windows | 0.832 |
| windows with questions (before) | 0.788 |
| windows without question-only windows (now) | 0.821 |

No verified verdict changed with the fix; 9 pairs moved from `uncertain` to
`not_supported`. Three of the ten false accepts above still come from a question next to
its answer: a question's presupposition can lend a claim support. Sources that are mostly
questions (interviews, support chats) need care until this is handled.

### Other weaknesses seen in these runs

- **Paraphrase misses**: "The user does not want meetings scheduled before 9:30 on weekdays"
  from "Don't schedule anything before 9:30 on weekdays" stays `uncertain` (p=0.24).
- **Embellished roles**: "Davide è il responsabile IT" from "Davide (IT di Logistica Delta)"
  was verified (p=0.87).
- **Negated quantities**: "…was not signed on July 4. Instead, it was signed on August 2,
  1776" is refused because July 4 is not in the source, although the claim denies it.
- **Arithmetic is not support**, by design: "15 technicians" from "12 technicians, and we
  hire three more" is refused.
- **One chunk, one source**: a memory that combines two chunks of a conversation is checked
  against the chunk it was given, and fails if the chunk lacks part of it.

### How many windows to judge

On a long source the verifier judges only the windows that a lexical and character-trigram
prefilter ranks highest, and each judged window costs one call to the model. To choose how
many, the train split of RAGTruth (human-labelled responses of six LLMs; see below) was
used as design data: the top 12 windows of 754 claims from its Summary and QA tasks were
scored once, then reread for each budget k (`scripts/research/window_budget.py`). The
"reach 0.5" columns are the judge alone, without the quantity and context checks.

| k | QA: AUROC S vs N | QA: S / N / C reach 0.5 | Summary: AUROC S vs N | Summary: S / N / C reach 0.5 |
|---|---|---|---|---|
| 1 | 0.858 | 70.5% / 17.0% / 40.0% | 0.748 | 51.0% / 12.7% / 23.5% |
| 2 | 0.864 | 75.0% / 18.0% / 46.7% | 0.770 | 56.5% / 15.2% / 27.5% |
| 3 | 0.872 | 78.5% / 19.1% / 50.0% | 0.785 | 59.5% / 15.2% / 27.5% |
| **4** | **0.873** | **81.0% / 20.1% / 50.0%** | **0.786** | **60.0% / 15.2% / 29.4%** |
| 6 | 0.869 | 81.5% / 22.7% / 50.0% | 0.791 | 60.0% / 15.2% / 29.4% |
| 8 | 0.865 | 82.5% / 24.2% / 50.0% | 0.789 | 60.0% / 15.2% / 29.4% |
| 12 | 0.859 | 82.5% / 24.7% / 50.0% | 0.795 | 61.0% / 16.5% / 29.4% |

(QA: 200 S, 194 N, 30 C; Summary: 200 S, 79 N, 51 C.) Going from 12 windows to 4 lets 1.0
to 1.5 points fewer true claims through and 1.3 to 4.6 points fewer unsupported ones, with
a third of the model calls on long sources. On the short sources of the other datasets no
verdict changed (review cases, example pairs, TruthfulQA, cross-lingual cases). The default
policy (since `0.9.0-provisional.2`) judges at most 4 windows; before it was 12.

### Windows made of non-adjacent sentences: studied, not adopted

A memory often joins two sentences that are not next to each other ("I moved to Milan" in
one turn, "that was in 2021" three turns later). Windows of one or two adjacent sentences
cannot support it, and the whole source is a window only up to 1,500 characters. One more
window per claim, the 2 or 3 sentences the prefilter ranks highest joined in source order,
was scored on the same design data (`scripts/research/composite_window.py … --dump FILE`,
then `scripts/research/composite_analysis.py FILE`):

| Windows | Summary: AUROC S vs N+C | Summary: S kept at 10% / 5% of N+C admitted | QA: AUROC S vs N+C | QA: S kept at 10% / 5% |
|---|---|---|---|---|
| 4 (default) | 0.749 | 45.5% / 35.0% | 0.853 | 63.5% / 49.5% |
| 4 + top 2 sentences | 0.785 | 51.0% / 36.5% | 0.857 | 62.5% / 51.0% |
| 4 + top 3 sentences | 0.795 | 55.5% / 38.5% | 0.854 | 62.5% / 54.0% |

On long sources it ranks better, but at the default threshold it also lets more errors
through: on Summary, +6.5 points of true claims came with +1.3 points of unstated and +3.9
of contradicted claims, even when the joined window had to score 0.95 instead of 0.5. A bar
high enough to add no error (0.98) added 3 points of true claims, 6 of 200: within the
noise, and not worth a second kind of evidence (two passages instead of one) and a fifth
model call per claim. Long conversations are where it would matter most; this needs data of
that kind (Gate 1) to decide.

## Abstention (`ask`)

Two QA sets, both written by Claude: [`qa-mini.json`](../datasets/qa-mini.json), on which the
relevance threshold was chosen, and [`qa-heldout.json`](../datasets/qa-heldout.json), written
and committed before any change it was used to judge. Each has 20 facts and 50 questions,
25 of which the facts answer ([`qa-mini.md`](eval/qa-mini.md),
[`qa-heldout.md`](eval/qa-heldout.md)).

| Set | Answered with the right fact | Wrong abstentions (retrieval misses among them) | Wrong fact | Right abstentions | False answers | AUROC answerable vs not |
|---|---|---|---|---|---|---|
| qa-mini | 17 / 25 | 8 (0) | 0 | 25 / 25 | 0 | 0.971 |
| qa-heldout | 15 / 25 | 10 (2) | 0 | 23 / 25 | 2 | 0.811 |

`ask` is strict, and weaker than the verifier. It abstains on a third or more of the
questions the facts answer: 8 of 25 and 10 of 25 (Wilson 95% intervals 17%-52% and
23%-59%), for example "In che città vive Laura?" (relevance 0.085) and, outside these sets,
"Who leads the data platform team?" against "Anna leads the data platform team." (0.11).
The misses are in the relevance check, which reuses the NLI judge with the hypothesis
"This text answers the question: …", except two held-out questions in English about facts
stored in Italian, which share no word with them and are never retrieved (keyword search
stems English words, but does not translate). On the held-out set `ask` also handed a fact
to 2 of 25 questions the facts do not answer: "A che ora viene fatto il backup dei file?"
got the nightly backup of the database (relevance 0.90), and "How many days do customers
have to exchange an item?" got the 30 days for a refund (0.41).

The threshold trades one error for the other. On the set it was chosen on
(`python scripts/research/ask_threshold.py datasets/qa-mini.json`):

| Relevance threshold | Right fact first (of 25) | A wrong fact first | Unanswerable questions given a fact (of 25) |
|---|---|---|---|
| 0.10 | 22 | 0 | 4 |
| 0.20 | 21 | 0 | 2 |
| 0.30 | 19 | 0 | 1 |
| 0.35 | 18 | 0 | 0 |
| **0.40 (default)** | 17 | 0 | 0 |
| 0.50 | 16 | 0 | 0 |

**Tried and reverted: lexical coverage.** A rule that counts a fact as relevant when it
contains every word the question asks about (commit cecfccb) took qa-mini from 17 to 23
right answers with no false answer, but on the held-out set it gave 16 right answers instead
of 15 and 4 false answers instead of 2, so it was reverted (09426c3). Better relevance needs
a better model, not more word rules (CHECKLIST, phase 3).

**Tried and not adopted: an existential statement.** The question turned into a statement
("Who leads the team?" → "Someone leads the team") and judged as a hypothesis
(`python scripts/research/ask_existential.py datasets/qa-mini.json datasets/qa-heldout.json`)
answered more questions, 22 instead of 17 and 19 instead of 15 at threshold 0.4, but gave a
fact to 7 and 5 of the 25 questions the facts do not answer, instead of 0 and 2. Its AUROC
was lower on both sets (0.931 against 0.971, 0.778 against 0.811).

**Tried and not adopted: an extractive QA model.** `deepset/xlm-roberta-large-squad2`
(CC BY 4.0), trained on SQuAD 2.0, whose unanswerable questions are written to look
answerable, scored each (question, fact) pair as the gap between its best answer span and
"no answer" (`python scripts/research/ask_extractive_qa.py deepset/xlm-roberta-large-squad2
datasets/qa-mini.json datasets/qa-heldout.json`). It answered 24 and 19 of the 25 answerable
questions, against 17 and 15, but it also answered near misses that swap an entity: "Che moto
guida Laura?" got "Fiat Panda" (a car), "How many days do customers have to exchange an
item?" got the 30 days of the refund policy: 2 false answers of 25 on qa-mini, where the
current check gives none, and 2 or 3 on qa-heldout, where it gives 2, at every threshold
from 0.3 to 0.95. The base model (`deepset/xlm-roberta-base-squad2`) gave 3 to 12.
The rule fixed before trying was "more right answers and no more false ones", so neither was
adopted and `qa-heldout-2.json` stays unused for the next attempt.

**Related facts.** Instead of moving the threshold, `ask` keeps it and hands over, as
`related`, the verified facts it retrieved whose relevance falls between a floor (0.05) and
the threshold: true facts the check could not confirm as answers, for the caller (usually an
LLM) to judge. The floor sits below the lowest relevance of a right fact on qa-mini (0.083).
Same commands as the table above:

| Set | Not answered, right fact among the related | Unanswerable questions given related facts |
|---|---|---|
| qa-mini | 8 of 8 | 5 of 25 |
| qa-heldout | 5 of 10 | 3 of 25 |

So the right fact reached the caller, as an answer or as a related fact, for 25 of 25 and
20 of 25 answerable questions. The other 5 held-out misses: 2 questions never retrieved (see
above) and 3 whose right fact scored below the floor.

## Resources

| What | Measured | Command |
|---|---|---|
| Model download | 1.16 GB (`model.safetensors` 1.14 GB, tokenizer files 0.02 GB) | `verimem warmup` |
| Loading the judge (float32, the default) | 8.8 s; 3.9 GB peak while loading, 2.9 GB resident after | `Verifier().warmup()`, `resource.getrusage`, `/proc/self/statm` |
| Loading the judge (bfloat16) | 6.7 s; 2.9 GB peak while loading, 1.8 GB resident after | same, with `judge_dtype` set to `bfloat16` |
| One `verimem check` from a cold start | 8.9-9.1 s | `time verimem check …` |
| Per pair, batched, model loaded | 0.07-0.28 s | `verimem eval` (table above) |
| Per window, float32 / bfloat16 | 0.198 s / 0.042 s | `python scripts/research/precision.py` (below) |

**Precision.** The default judge's weights are stored in float16. transformers 5 loads them
as float16, transformers 4 as float32, so until 0.9.0-provisional.3 the scores depended on the
installed version. The judge now runs in the precision the policy names (`judge_dtype`,
float32 by default; `--judge-dtype` on the command line). On 600 (window, claim) pairs from
RAGTruth's train split, scored on this machine (`scripts/research/precision.py`):

| Precision | s per pair | Largest change vs float32 | Mean change | Pairs crossing 0.5 |
|---|---|---|---|---|
| float32 | 0.198 | | | |
| float16 | 0.190 | 0.0026 | 0.00017 | 0 of 600 |
| bfloat16 | 0.042 | 0.0396 | 0.00195 | 2 of 600 |

This CPU has AMX units, which run bfloat16 in hardware: on CPUs without them bfloat16 is not
expected to be faster (not measured here). Verdicts made in bfloat16 say so in the judge id
(`…@705510dfe0f3+bfloat16`).

## Reproduce

```
pip install -e ".[nli]"
verimem warmup
scripts/evals.sh
python scripts/research/question_windows.py datasets/truthfulqa-pairs.jsonl
python scripts/research/ask_threshold.py datasets/qa-mini.json
```
