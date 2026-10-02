"""Evaluation and calibration (DESIGN.md §7-8). Pure standard library.

Datasets are labelled (source, claim) pairs: S = supported, N = not stated, C = contradicted.
Every number this module prints comes with the size of the data behind it, and thresholds are
chosen on one half of the pairs and measured on the other.
"""

from __future__ import annotations

import json
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .policy import Thresholds
from .records import read_records
from .types import Label, Verdict
from .verifier import Verifier

_ALIASES = {"fonte": "source", "fatto": "claim", "etichetta": "label", "lingua": "lang",
            "memory": "claim", "premise": "source", "hypothesis": "claim"}


@dataclass(frozen=True)
class Pair:
    source: str
    claim: str
    label: str  # "S", "N" or "C"
    lang: str = ""
    id: str = ""


def load_pairs(path: str | Path) -> list[Pair]:
    """Read labelled pairs from CSV (`,` or `;`, English or Italian headers) or JSON."""
    pairs = []
    for i, raw in enumerate(read_records(path)):
        r = {_ALIASES.get(k.strip().lower(), k.strip().lower()): (v or "") for k, v in raw.items()}
        label = str(r.get("label", "")).strip().upper()[:1]
        if label not in {"S", "N", "C"} or not r.get("source") or not r.get("claim"):
            continue
        pairs.append(Pair(r["source"], r["claim"], label, str(r.get("lang", "")).lower(),
                          str(r.get("id", i))))
    return pairs


# ---------------------------------------------------------------- metrics

def auroc(pos: Sequence[float], neg: Sequence[float]) -> float:
    """Probability that a random positive scores above a random negative (ties count half)."""
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def bootstrap_ci(pos: Sequence[float], neg: Sequence[float], *, rounds: int = 1000,
                 seed: int = 7) -> tuple[float, float]:
    """95% interval for AUROC, resampling positives and negatives separately."""
    if not pos or not neg:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    vals = sorted(auroc(rng.choices(pos, k=len(pos)), rng.choices(neg, k=len(neg)))
                  for _ in range(rounds))
    return vals[int(0.025 * rounds)], vals[min(rounds - 1, int(0.975 * rounds))]


def threshold_for_loss(scores: Sequence[float], loss: float) -> float:
    """A threshold that a new supported claim falls below with probability ~`loss`
    (the k-th lowest score, k = loss * (n + 1))."""
    s = sorted(scores)
    k = max(1, int(loss * (len(s) + 1)))
    return s[min(k, len(s)) - 1]


@dataclass
class HeldOut:
    target_loss: float
    true_lost: float
    unstated_admitted: float
    contradicted_admitted: float | None
    rounds: int


def held_out(support: Sequence[float], labels: Sequence[str], *, target_loss: float = 0.08,
             rounds: int = 200, seed: int = 11) -> HeldOut:
    """Choose the support threshold on a random half of the pairs, measure on the other half."""
    rng = random.Random(seed)
    idx = {k: [i for i, lab in enumerate(labels) if lab == k] for k in "SNC"}
    lost, n_adm, c_adm = [], [], []
    for _ in range(rounds):
        halves = {k: rng.sample(v, len(v)) for k, v in idx.items()}
        cal = [support[i] for i in halves["S"][: len(halves["S"]) // 2]]
        if not cal:
            break
        th = threshold_for_loss(cal, target_loss)
        test = {k: v[len(v) // 2 :] for k, v in halves.items()}
        lost.append(statistics.fmean(support[i] < th for i in test["S"]))
        if test["N"]:
            n_adm.append(statistics.fmean(support[i] >= th for i in test["N"]))
        if test["C"]:
            c_adm.append(statistics.fmean(support[i] >= th for i in test["C"]))
    return HeldOut(target_loss, statistics.fmean(lost) if lost else float("nan"),
                   statistics.fmean(n_adm) if n_adm else float("nan"),
                   statistics.fmean(c_adm) if c_adm else None, len(lost))


# ---------------------------------------------------------------- verifier evaluation

@dataclass
class VerifierReport:
    judge: str
    policy: str
    n: dict[str, int]
    auroc_s_vs_n: float
    auroc_s_vs_n_ci: tuple[float, float]
    auroc_s_vs_nc: float
    supported_rate: dict[str, float]
    held_out: HeldOut
    per_language: dict[str, dict[str, Any]] = field(default_factory=dict)
    seconds_per_pair: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["held_out"] = dict(self.held_out.__dict__)
        return d


def evaluate_verifier(verifier: Verifier, pairs: Sequence[Pair], *,
                      bootstrap_rounds: int = 1000) -> tuple[VerifierReport, list[Verdict]]:
    import time

    t0 = time.perf_counter()
    verdicts = verifier.check_many([(p.source, p.claim) for p in pairs])
    elapsed = (time.perf_counter() - t0) / max(1, len(pairs))
    support = [v.support for v in verdicts]
    labels = [p.label for p in pairs]
    by = {k: [s for s, lab in zip(support, labels, strict=True) if lab == k] for k in "SNC"}
    rate = {k: (statistics.fmean(v.label is Label.SUPPORTED
                                 for v, lab in zip(verdicts, labels, strict=True) if lab == k)
                if by[k] else float("nan")) for k in "SNC"}
    langs = sorted({p.lang for p in pairs if p.lang})
    per_lang = {}
    for lang in langs:
        sel = [i for i, p in enumerate(pairs) if p.lang == lang]
        s = [support[i] for i in sel if labels[i] == "S"]
        n = [support[i] for i in sel if labels[i] == "N"]
        per_lang[lang] = {"pairs": len(sel), "auroc_s_vs_n": auroc(s, n)}
    errors = [{"id": p.id, "label": p.label, "verdict": v.label.value,
               "support": round(v.support, 3), "claim": p.claim, "reason": v.reason}
              for p, v in zip(pairs, verdicts, strict=True)
              if (p.label == "S") != (v.label is Label.SUPPORTED)]
    report = VerifierReport(
        judge=verifier.judge.id, policy=verifier.policy.version,
        n={k: len(v) for k, v in by.items()},
        auroc_s_vs_n=auroc(by["S"], by["N"]),
        auroc_s_vs_n_ci=bootstrap_ci(by["S"], by["N"], rounds=bootstrap_rounds),
        auroc_s_vs_nc=auroc(by["S"], by["N"] + by["C"]),
        supported_rate=rate, held_out=held_out(support, labels),
        per_language=per_lang, seconds_per_pair=elapsed, errors=errors)
    return report, verdicts


def calibrate(verifier: Verifier, pairs: Sequence[Pair], *, target_loss: float = 0.08,
              quarantine_loss: float = 0.02) -> tuple[Thresholds, dict[str, Any]]:
    """Thresholds from labelled pairs, with the held-out rates that justify them.

    `support` loses about `target_loss` of true claims (they become unverified); `uncertain`
    is set so that only about `quarantine_loss` of true claims fall low enough to be
    quarantined."""
    report, verdicts = evaluate_verifier(verifier, pairs, bootstrap_rounds=200)
    support = [v.support for v, p in zip(verdicts, pairs, strict=True) if p.label == "S"]
    if len(support) < 10:
        raise ValueError("calibration needs at least 10 supported (S) pairs")
    th_support = threshold_for_loss(support, target_loss)
    th_uncertain = min(th_support, threshold_for_loss(support, quarantine_loss))
    current = verifier.policy.thresholds
    thresholds = Thresholds(support=round(th_support, 4), uncertain=round(th_uncertain, 4),
                            contradiction=current.contradiction)
    provenance = {"pairs": report.n, "target_true_loss": target_loss,
                  "held_out_true_lost": round(report.held_out.true_lost, 4),
                  "held_out_unstated_admitted": round(report.held_out.unstated_admitted, 4),
                  "auroc_s_vs_n": round(report.auroc_s_vs_n, 4), "judge": report.judge}
    return thresholds, provenance


def _num(x: float, fmt: str) -> str:
    return "n/a" if x != x else format(x, fmt)


def render_verifier_report(r: VerifierReport, *, dataset: str, command: str) -> str:
    """Markdown for docs/EVAL.md."""
    lo, hi = r.auroc_s_vs_n_ci
    rate = {k: _num(v, ".0%") for k, v in r.supported_rate.items()}
    ci = "" if lo != lo else f" ({lo:.2f}-{hi:.2f})"
    ho = r.held_out
    lines = [
        f"### `{dataset}`",
        "",
        f"Produced by `{command}`. Judge `{r.judge}`, policy `{r.policy}`.",
        "",
        "| Pairs (S / N / C) | AUROC S vs N (95% CI) | AUROC S vs N+C | Verified at policy: "
        f"S / N / C | Held-out, target {ho.target_loss:.0%} true loss: true lost / N admitted "
        "| s per pair |",
        "|---|---|---|---|---|---|",
        f"| {r.n['S']} / {r.n['N']} / {r.n['C']} | {_num(r.auroc_s_vs_n, '.3f')}{ci} | "
        f"{_num(r.auroc_s_vs_nc, '.3f')} | {rate['S']} / {rate['N']} / {rate['C']} | "
        f"{_num(ho.true_lost, '.0%')} / {_num(ho.unstated_admitted, '.0%')} | "
        f"{r.seconds_per_pair:.2f} |",
        "",
    ]
    # False accepts first: a fact the source does not support is the costly error.
    accepted = [e for e in r.errors if e["verdict"] == Label.SUPPORTED.value]
    refused = [e for e in r.errors if e["verdict"] != Label.SUPPORTED.value]
    for title, errs in (("Verified although labelled N or C", accepted),
                        ("Not verified although labelled S", refused)):
        if errs:
            shown = errs[:15]
            lines += [f"{title} ({len(shown)} of {len(errs)}):", ""]
            lines += [f"- `{e['label']}` → `{e['verdict']}` (p={e['support']}): {e['claim']}"
                      for e in shown]
            lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- ask evaluation

@dataclass
class AskReport:
    questions: int
    answerable: int
    answered_right: int
    wrong_abstentions: int
    wrong_fact: int
    right_abstentions: int
    false_answers: int
    retrieval_misses: int
    auroc: float
    threshold: float
    judge: str = ""
    policy: str = ""
    right_in_related: int = 0  # answerable, not answered, but the right fact is in `related`
    unanswerable_with_related: int = 0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def evaluate_ask(memory_factory: Any, qa_path: str | Path, *, k: int = 5) -> AskReport:
    """Load the QA set's facts into a fresh memory and score `Memory.ask` on its questions."""
    from .memory import Item

    data = json.loads(Path(qa_path).read_text(encoding="utf-8"))
    mem = memory_factory()
    results = mem.remember_many([Item(f["text"], source=f["text"]) for f in data["facts"]])
    id_of = {f["id"]: r.fact_id for f, r in zip(data["facts"], results, strict=True)}
    counts = dict.fromkeys(("right", "wrong_abst", "wrong_fact", "right_abst", "false",
                            "miss", "right_related", "unans_related"), 0)
    pos: list[float] = []
    neg: list[float] = []
    for q in data["questions"]:
        want = {id_of[a] for a in q["answer"]}
        ans = mem.ask(q["q"], k=k)
        kept = {r.fact.id for r in ans.facts}
        related = {r.fact.id for r in ans.related}
        scores = dict(ans.candidates)
        if want:
            if not want & set(scores) and not want & kept:
                counts["miss"] += 1
            pos.append(max((scores.get(i, 0.0) for i in want), default=0.0))
            if not kept:
                counts["wrong_abst"] += 1
            elif want & kept:
                counts["right"] += 1
            else:
                counts["wrong_fact"] += 1
            if not want & kept and want & related:
                counts["right_related"] += 1
        else:
            neg.append(max(scores.values(), default=0.0))
            counts["false" if kept else "right_abst"] += 1
            counts["unans_related"] += bool(related)
    mem.close()
    n_ans = sum(1 for q in data["questions"] if q["answer"])
    return AskReport(len(data["questions"]), n_ans, counts["right"], counts["wrong_abst"],
                     counts["wrong_fact"], counts["right_abst"], counts["false"],
                     counts["miss"], auroc(pos, neg),
                     mem.policy.relevance_threshold, mem.verifier.judge.id, mem.policy.version,
                     counts["right_related"], counts["unans_related"])


def render_ask_report(r: AskReport, *, dataset: str, command: str) -> str:
    """Markdown for docs/EVAL.md."""
    unanswerable = r.questions - r.answerable
    return "\n".join([
        f"### `{dataset}`",
        "",
        f"Produced by `{command}`. Judge `{r.judge}`, policy `{r.policy}`, relevance "
        f"threshold {r.threshold}.",
        "",
        "| Questions (answerable) | Answered with the right fact | Wrong abstentions | "
        "Wrong fact | Retrieval misses | Right abstentions | False answers | AUROC answerable "
        "vs not |",
        "|---|---|---|---|---|---|---|---|",
        f"| {r.questions} ({r.answerable}) | {r.answered_right} / {r.answerable} | "
        f"{r.wrong_abstentions} | {r.wrong_fact} | {r.retrieval_misses} | "
        f"{r.right_abstentions} / {unanswerable} | {r.false_answers} | {_num(r.auroc, '.3f')} |",
        "",
        f"Not answered but handed over among the related facts: {r.right_in_related} of the "
        f"{r.answerable - r.answered_right} answerable questions not answered. Unanswerable "
        f"questions that got related facts: {r.unanswerable_with_related} of {unanswerable}.",
        "",
    ])
