"""Memory reliability report: audit (source, memory) pairs exported from any memory system.

The deliverable a customer reads: how many stored memories their sources actually support,
which do not (with the closest evidence), which add numbers the source never states, and
how far the judge itself can be trusted. Outputs JSON (everything), Markdown (the report)
and CSV (one row per flagged memory, with an empty column for a human reviewer).
"""

from __future__ import annotations

import csv
import html
import json
import math
import random
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._version import __version__
from .numbers import missing_quantities
from .records import read_records
from .types import Label, Verdict
from .verifier import Verifier

_ALIASES = {"fonte": "source", "memoria": "memory", "fatto": "memory", "claim": "memory",
            "fact": "memory", "lingua": "lang"}


@dataclass(frozen=True)
class AuditRow:
    id: str
    source: str
    memory: str
    lang: str = ""


def load_audit_rows(path: str | Path) -> list[AuditRow]:
    """Read (source, memory) pairs from JSON or CSV (`,`/`;`, English or Italian headers)."""
    rows = []
    for i, r in enumerate(read_records(path)):
        r = {_ALIASES.get(k.strip().lower(), k.strip().lower()): (v or "") for k, v in r.items()}
        if str(r.get("memory", "")).strip():
            rows.append(AuditRow(str(r.get("id") or i + 1), str(r.get("source", "")),
                                 str(r["memory"]), str(r.get("lang", ""))))
    return rows


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


@dataclass
class AuditReport:
    created_at: str
    verimem_version: str
    judge: str
    policy: str
    total: int
    counts: dict[str, int]
    unsupported_share: float
    unsupported_ci: tuple[float, float]
    numeric_violations: int
    rows: list[dict[str, Any]] = field(default_factory=list)
    calibration: dict[str, Any] | None = None
    judge_is_model: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def audit_pairs(rows: Sequence[AuditRow], verifier: Verifier) -> AuditReport:
    verdicts = verifier.check_many([(r.source or None, r.memory) for r in rows])
    counts = Counter(v.label.value for v in verdicts)
    flagged = {Label.NOT_SUPPORTED, Label.CONTRADICTED}
    judged = [v for v in verdicts if v.label is not Label.UNJUDGED]
    k = sum(v.label in flagged for v in judged)
    numeric = sum(1 for v in verdicts for c in v.checks if c.name == "quantities" and not c.passed)
    out_rows = [_row(r, v) for r, v in zip(rows, verdicts, strict=True)]
    return AuditReport(
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        verimem_version=__version__, judge=verifier.judge.id if judged else verifier.policy.judge,
        policy=verifier.policy.version, total=len(rows),
        counts={lab.value: counts.get(lab.value, 0) for lab in Label},
        unsupported_share=k / len(judged) if judged else float("nan"),
        unsupported_ci=wilson(k, len(judged)), numeric_violations=numeric, rows=out_rows,
        calibration=verifier.policy.calibration,
        judge_is_model=bool(judged) and bool(getattr(verifier.judge, "is_model", False)))


def _row(r: AuditRow, v: Verdict) -> dict[str, Any]:
    vetoed = any(c.name == "quantities" and not c.passed for c in v.checks)
    return {"id": r.id, "memory": r.memory, "source": r.source, "verdict": v.label.value,
            "support": round(v.support, 4),
            "contradiction": None if v.contradiction is None else round(v.contradiction, 4),
            "reason": v.reason, "evidence": v.evidence.text if v.evidence else "",
            "missing_quantities": missing_quantities(r.memory, r.source) if vetoed else []}


# ---------------------------------------------------------------- writing

_TEXT = {
    "en": {
        "title": "Memory reliability report",
        "baseline": ("**Warning: these verdicts come from {judge}, a word-overlap baseline, not "
                     "a model. The numbers below are not a reliability estimate.**"),
        "summary": "Summary",
        "pairs": "memories checked against the source they were extracted from",
        "supported": "supported by their source",
        "unsupported": "not supported by their source",
        "of_judged": "of the {n} that could be judged",
        "uncertain": "weakly supported (left for review, not counted as errors)",
        "unjudged": "had no source and could not be checked",
        "numbers": "add a number, amount or date the source does not contain",
        "what": "What this means",
        "what_text": ("A memory is *not supported* when the text it came from does not state it. "
                      "Such memories are usually details an LLM added while extracting facts: "
                      "plausible, often true-sounding, and served back later as if the user had "
                      "said them."),
        "examples": "Examples of unsupported memories",
        "closest": "closest passage in the source",
        "why_numbers": "numbers or dates not in the source: {q}",
        "why_contradicted": "the source contradicts it",
        "why_unstated": "the source does not say it (best support p={p:.2f})",
        "why_weak": "weak support (p={p:.2f})",
        "why_supported": "supported (p={p:.2f})",
        "review": ("`review.csv` lists every memory that could be judged with its source, "
                   "grouped by verdict (flagged first) and in random order within each group. "
                   "Read a few from the top of each group, write yes or no in "
                   "`stated_by_source`, then run `verimem audit-review` on this folder for an "
                   "estimate checked by a person."),
        "limits": "Limits of this report",
        "limits_text": ("Verdicts come from an automatic judge ({judge}), with policy {policy}. "
                        "The judge makes mistakes in both directions; its calibration is "
                        "described below. Before acting on the numbers, review a sample of the "
                        "flagged rows (`review.csv` has a column for it). The judge checks "
                        "consistency with the source, not truth: a wrong source makes a wrong "
                        "memory look supported."),
        "calibration": "Judge calibration",
        "made": "Generated by verimem {version} on {date}.",
    },
    "it": {
        "title": "Rapporto di affidabilità della memoria",
        "baseline": ("**Attenzione: questi verdetti vengono da {judge}, un confronto di parole, "
                     "non da un modello. I numeri qui sotto non sono una stima "
                     "dell'affidabilità.**"),
        "summary": "Sintesi",
        "pairs": "memorie confrontate con il testo da cui sono state estratte",
        "supported": "sostenute dalla fonte",
        "unsupported": "non sostenute dalla loro fonte",
        "of_judged": "sulle {n} giudicabili",
        "uncertain": "sostenute debolmente (da rivedere, non contate come errori)",
        "unjudged": "senza fonte, quindi non verificabili",
        "numbers": "aggiungono un numero, un importo o una data che la fonte non contiene",
        "what": "Cosa significa",
        "what_text": ("Una memoria è *non sostenuta* quando il testo da cui viene non la dice. "
                      "Di solito è un dettaglio aggiunto da un LLM durante l'estrazione: "
                      "plausibile, spesso verosimile, e poi restituito come se l'utente l'avesse "
                      "detto davvero."),
        "examples": "Esempi di memorie non sostenute",
        "closest": "passaggio più vicino nella fonte",
        "why_numbers": "numeri o date assenti nella fonte: {q}",
        "why_contradicted": "la fonte lo contraddice",
        "why_unstated": "la fonte non lo dice (sostegno massimo p={p:.2f})",
        "why_weak": "sostegno debole (p={p:.2f})",
        "why_supported": "sostenuta (p={p:.2f})",
        "review": ("`review.csv` elenca tutte le memorie giudicabili con la loro fonte, "
                   "raggruppate per verdetto (prima quelle segnalate) e in ordine casuale dentro "
                   "ogni gruppo. Leggetene alcune dall'inizio di ogni gruppo, scrivete sì o no "
                   "nella colonna `stated_by_source`, poi lanciate `verimem audit-review` su "
                   "questa cartella per una stima controllata da una persona."),
        "limits": "Limiti di questo rapporto",
        "limits_text": ("I verdetti vengono da un giudice automatico ({judge}), con la policy "
                        "{policy}. Il giudice sbaglia in entrambe le direzioni; la sua "
                        "calibrazione è descritta sotto. Prima di agire sui numeri, rivedete un "
                        "campione delle righe segnalate (`review.csv` ha una colonna apposta). Il "
                        "giudice controlla la coerenza con la fonte, non la verità: una fonte "
                        "sbagliata fa sembrare sostenuta una memoria sbagliata."),
        "calibration": "Calibrazione del giudice",
        "made": "Generato da verimem {version} il {date}.",
    },
}


def explain(row: dict[str, Any], lang: str = "en") -> str:
    """Why a memory got its verdict, in the report's language."""
    t = _TEXT.get(lang, _TEXT["en"])
    if row["missing_quantities"]:
        return t["why_numbers"].format(q=", ".join(row["missing_quantities"]))
    if row["verdict"] == Label.CONTRADICTED.value:
        return t["why_contradicted"]
    if row["verdict"] == Label.UNCERTAIN.value:
        return t["why_weak"].format(p=row["support"])
    if row["verdict"] == Label.SUPPORTED.value:
        return t["why_supported"].format(p=row["support"])
    return t["why_unstated"].format(p=row["support"])


def render_markdown(rep: AuditReport, *, lang: str = "en", examples: int = 10) -> str:
    t = _TEXT.get(lang, _TEXT["en"])
    judged = rep.total - rep.counts.get("unjudged", 0)
    flagged = rep.counts.get("not_supported", 0) + rep.counts.get("contradicted", 0)
    lo, hi = rep.unsupported_ci
    share = "n/a" if judged == 0 else f"{rep.unsupported_share:.0%} ({lo:.0%}-{hi:.0%})"
    lines = [f"# {t['title']}", ""]
    if not rep.judge_is_model and rep.total > rep.counts.get("unjudged", 0):
        lines += [t["baseline"].format(judge=rep.judge), ""]
    lines += [
        f"## {t['summary']}", "",
        f"- **{rep.total}** {t['pairs']}.",
        f"- **{rep.counts.get('supported', 0)}** {t['supported']}.",
        f"- **{flagged}** {t['unsupported']}: **{share}** {t['of_judged'].format(n=judged)}.",
        f"- **{rep.numeric_violations}** {t['numbers']}.",
        f"- **{rep.counts.get('uncertain', 0)}** {t['uncertain']}.",
        f"- **{rep.counts.get('unjudged', 0)}** {t['unjudged']}.",
        "", f"## {t['what']}", "", t["what_text"], "",
    ]
    bad = [r for r in rep.rows if r["verdict"] in ("not_supported", "contradicted")]
    bad.sort(key=lambda r: r["support"])
    if bad:
        lines += [f"## {t['examples']}", ""]
        for r in bad[:examples]:
            lines.append(f"- **{r['memory']}**  ")
            lines.append(f"  {explain(r, lang)}  ")
            if r["evidence"]:
                lines.append(f"  _{t['closest']}:_ “{r['evidence']}”")
            lines.append("")
    lines += [f"## {t['limits']}", "",
              t["limits_text"].format(judge=rep.judge, policy=rep.policy), "", t["review"], ""]
    if rep.calibration:
        lines += [f"### {t['calibration']}", ""]
        for part, info in rep.calibration.items():
            lines.append(f"**{part}**")
            lines.append("")
            items = info.items() if isinstance(info, dict) else [("", info)]
            lines += [f"- {k}: {v}" if k else f"- {v}" for k, v in items]
            lines.append("")
    lines.append(t["made"].format(version=rep.verimem_version, date=rep.created_at))
    return "\n".join(lines) + "\n"


_CSS = """
body{font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1d2125;margin:0;
background:#fff}main{max-width:820px;margin:0 auto;padding:32px 20px}h1{font-size:28px;
margin:0 0 4px}h2{font-size:20px;margin:32px 0 12px;border-bottom:1px solid #dde1e5;
padding-bottom:4px}.meta{color:#5f6b76;font-size:14px}.warn{background:#fdecea;border:1px
solid #f5c2c0;padding:12px 16px;border-radius:6px}.cards{display:grid;gap:12px;
grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.card{border:1px solid #dde1e5;
border-radius:8px;padding:12px 14px}.card b{display:block;font-size:26px}.card.bad{
border-color:#e8a29e;background:#fdf3f2}.bar{display:flex;height:14px;border-radius:7px;
overflow:hidden;margin:16px 0 4px;background:#eef0f2}.bar span{display:block}.ok{
background:#3f8f5b}.ko{background:#c4483d}.mid{background:#d7a33a}.na{background:#9aa5b1}
.ex{border-left:3px solid #c4483d;padding:4px 0 4px 14px;margin:14px 0;break-inside:avoid}
.ex p{margin:2px 0}.ex .src{color:#5f6b76;font-size:14px}code{background:#f2f4f6;
padding:1px 4px;border-radius:3px}dl{font-size:14px}dt{font-weight:600;margin-top:8px}
dd{margin:0 0 0 16px}@media print{main{padding:0}}
"""


def _inline(text: str) -> str:
    """Escape, then turn the few Markdown marks used in the report texts into HTML."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", out)


def render_html(rep: AuditReport, *, lang: str = "en", examples: int = 10) -> str:
    """The report as one self-contained HTML page (print it to get a PDF). Every text that
    comes from the audited data is escaped."""
    t = _TEXT.get(lang, _TEXT["en"])
    c = rep.counts
    judged = rep.total - c.get("unjudged", 0)
    flagged = c.get("not_supported", 0) + c.get("contradicted", 0)
    lo, hi = rep.unsupported_ci
    share = "n/a" if judged == 0 else f"{rep.unsupported_share:.0%}"
    made = t["made"].format(version=rep.verimem_version, date=rep.created_at)
    e = html.escape
    parts = [f'<!doctype html><html lang="{e(lang)}"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f"<title>{e(t['title'])}</title><style>{_CSS}</style></head><body><main>",
             f"<h1>{e(t['title'])}</h1>",
             f'<p class="meta">{e(made)}</p>']
    if not rep.judge_is_model and judged:
        parts.append(f'<p class="warn">{_inline(t["baseline"].format(judge=rep.judge))}</p>')
    cards = [(rep.total, t["pairs"], ""), (c.get("supported", 0), t["supported"], ""),
             (flagged, f"{t['unsupported']}: {share}"
              + ("" if judged == 0 else f" ({lo:.0%}-{hi:.0%})"), "bad"),
             (rep.numeric_violations, t["numbers"], ""),
             (c.get("uncertain", 0), t["uncertain"], ""), (c.get("unjudged", 0), t["unjudged"], "")]
    parts.append(f"<h2>{e(t['summary'])}</h2><div class=\"cards\">")
    parts += [f'<div class="card {cls}"><b>{n}</b>{e(label)}</div>' for n, label, cls in cards]
    parts.append("</div>")
    if rep.total:
        segs = [("ok", c.get("supported", 0)), ("ko", flagged), ("mid", c.get("uncertain", 0)),
                ("na", c.get("unjudged", 0))]
        parts.append('<div class="bar">' + "".join(
            f'<span class="{cls}" style="width:{100 * n / rep.total:.2f}%"></span>'
            for cls, n in segs if n) + "</div>")
    parts.append(f"<h2>{e(t['what'])}</h2><p>{_inline(t['what_text'])}</p>")
    bad = sorted((r for r in rep.rows if r["verdict"] in ("not_supported", "contradicted")),
                 key=lambda r: r["support"])
    if bad:
        parts.append(f"<h2>{e(t['examples'])}</h2>")
        for r in bad[:examples]:
            src = (f'<p class="src">{e(t["closest"])}: “{e(r["evidence"])}”</p>'
                   if r["evidence"] else "")
            parts.append(f'<div class="ex"><p><strong>{e(r["memory"])}</strong></p>'
                         f"<p>{e(explain(r, lang))}</p>{src}</div>")
    parts.append(f"<h2>{e(t['limits'])}</h2>"
                 f"<p>{_inline(t['limits_text'].format(judge=rep.judge, policy=rep.policy))}</p>"
                 f"<p>{_inline(t['review'])}</p>")
    if rep.calibration:
        parts.append(f"<h2>{e(t['calibration'])}</h2><dl>")
        for part, info in rep.calibration.items():
            parts.append(f"<dt>{e(str(part))}</dt>")
            items = info.items() if isinstance(info, dict) else [("", info)]
            parts += [f"<dd>{e(f'{k}: {v}' if k else str(v))}</dd>" for k, v in items]
        parts.append("</dl>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


_GROUP = {Label.NOT_SUPPORTED.value: "flagged", Label.CONTRADICTED.value: "flagged",
          Label.UNCERTAIN.value: "uncertain", Label.SUPPORTED.value: "verified"}
_GROUPS = ("flagged", "uncertain", "verified")


def write_report(rep: AuditReport, out_dir: str | Path, *, lang: str = "en") -> list[Path]:
    """Write report.json, report.md, report.html and review.csv into `out_dir`."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / "report.json", out / "report.md", out / "report.html", out / "review.csv"]
    paths[0].write_text(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    paths[1].write_text(render_markdown(rep, lang=lang), encoding="utf-8")
    paths[2].write_text(render_html(rep, lang=lang), encoding="utf-8")
    # Random order inside each group, so reading from the top of a group is a random sample
    # of it; the seed makes the file reproducible.
    rng = random.Random(7)
    ordered = []
    for group in _GROUPS:
        rows = [r for r in rep.rows if _GROUP.get(r["verdict"]) == group]
        rng.shuffle(rows)
        ordered += rows
    with paths[3].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "verdict", "why", "memory", "evidence", "source", "stated_by_source",
                    "reviewer_note"])
        for r in ordered:
            w.writerow([r["id"], r["verdict"], explain(r, lang), r["memory"], r["evidence"],
                        r["source"], "", ""])
    return paths


# ---------------------------------------------------------------- human review

_YES = frozenset({"yes", "y", "si", "sì", "true", "1"})
_NO = frozenset({"no", "n", "false", "0"})


@dataclass
class ReviewSummary:
    """A person's answers on a sample of review.csv, combined with the size of each group."""

    groups: dict[str, dict[str, int]]
    estimate: float | None
    ci: tuple[float, float] | None
    missing_groups: list[str]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def load_review(path: str | Path) -> dict[str, str]:
    """The reviewer's answers in review.csv: row id -> the `stated_by_source` value."""
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r["stated_by_source"].strip() for r in csv.DictReader(f)
                if (r.get("stated_by_source") or "").strip()}


def summarize_review(report: dict[str, Any], marks: dict[str, str], *, rounds: int = 4000,
                     seed: int = 13) -> ReviewSummary:
    """Estimate the share of memories their source does not state, from a reviewed sample.

    Each verdict group (flagged, uncertain, verified) contributes the reviewer's rate of
    "not stated" in it, weighted by the group's size. The 95% interval draws each group's
    rate from a Beta posterior with a Jeffreys prior, so a small sample with no errors still
    gets an honest width, shrunk by the finite-population correction: a group reviewed in
    full has no sampling error left."""
    verdict = {str(r["id"]): r["verdict"] for r in report["rows"]}
    sizes = Counter(_GROUP[v] for v in verdict.values() if v in _GROUP)
    outcomes: dict[str, list[int]] = {g: [] for g in _GROUPS}
    for id_, answer in marks.items():
        a = answer.strip().lower()
        if a not in _YES | _NO:
            raise ValueError(f"row {id_}: {answer!r} is not yes or no")
        if _GROUP.get(verdict.get(id_, "")) is None:
            raise ValueError(f"row {id_} is not a judged memory of this report")
        outcomes[_GROUP[verdict[id_]]].append(1 if a in _NO else 0)
    groups = {g: {"memories": sizes.get(g, 0), "reviewed": len(o), "not_stated": sum(o)}
              for g, o in outcomes.items()}
    missing = [g for g, c in groups.items() if c["memories"] and not c["reviewed"]]
    total = sum(sizes.values())
    if missing or not total:
        return ReviewSummary(groups, None, None, missing)
    used = [g for g in _GROUPS if sizes.get(g)]
    estimate = sum(sizes[g] / total * groups[g]["not_stated"] / groups[g]["reviewed"]
                   for g in used)
    rng = random.Random(seed)

    def draw(g: str) -> float:
        n, k, size = groups[g]["reviewed"], groups[g]["not_stated"], sizes[g]
        rate = k / n
        fpc = math.sqrt((size - n) / (size - 1)) if size > 1 else 0.0
        return min(1.0, max(0.0, rate + (rng.betavariate(k + 0.5, n - k + 0.5) - rate) * fpc))

    draws = sorted(sum(sizes[g] / total * draw(g) for g in used) for _ in range(rounds))
    ci = (draws[int(0.025 * rounds)], draws[min(rounds - 1, int(0.975 * rounds))])
    return ReviewSummary(groups, estimate, ci, missing)


_REVIEW_TEXT = {
    "en": {
        "title": "Human review of the memory reliability report",
        "intro": ("A person read a sample of the memories, with their source, and answered one "
                  "question for each: does the source state it?"),
        "head": "| Judge's verdict | Memories | Reviewed | Not stated by the source (reviewer) |",
        "names": {"flagged": "not supported", "uncertain": "uncertain", "verified": "verified"},
        "estimate": ("**Memories not stated by their source: {est:.0%} (95% interval "
                     "{lo:.0%}-{hi:.0%})**, from the reviewer's answers in each group weighted "
                     "by the size of the group."),
        "census": ("**Memories not stated by their source: {est:.0%}**; every memory was "
                   "reviewed, so there is no sampling error."),
        "missing": ("No estimate yet: review a few memories in every group (missing: {groups}). "
                    "Rows of review.csv are in random order within each group, so read them "
                    "from the top."),
        "agreement": "Agreement between the judge and the reviewer on the reviewed memories:",
        "flagged_ok": "- flagged as not supported, and indeed not stated: {k} of {n}",
        "verified_ok": "- verified, and indeed stated: {k} of {n}",
    },
    "it": {
        "title": "Revisione umana del rapporto di affidabilità della memoria",
        "intro": ("Una persona ha letto un campione delle memorie, con la loro fonte, e per "
                  "ognuna ha risposto a una domanda: la fonte lo dice?"),
        "head": "| Verdetto del giudice | Memorie | Riviste | Non dette dalla fonte (revisore) |",
        "names": {"flagged": "non sostenute", "uncertain": "incerte", "verified": "verificate"},
        "estimate": ("**Memorie non dette dalla loro fonte: {est:.0%} (intervallo al 95% "
                     "{lo:.0%}-{hi:.0%})**, dalle risposte del revisore in ogni gruppo pesate "
                     "con la dimensione del gruppo."),
        "census": ("**Memorie non dette dalla loro fonte: {est:.0%}**; tutte le memorie sono "
                   "state riviste, quindi non c'è errore di campionamento."),
        "missing": ("Ancora nessuna stima: rivedete qualche memoria in ogni gruppo (mancano: "
                    "{groups}). Le righe di review.csv sono in ordine casuale dentro ogni "
                    "gruppo: leggetele dall'inizio."),
        "agreement": "Accordo fra il giudice e il revisore sulle memorie riviste:",
        "flagged_ok": "- segnalate come non sostenute, e davvero non dette: {k} su {n}",
        "verified_ok": "- verificate, e davvero dette: {k} su {n}",
    },
}


def render_review_markdown(s: ReviewSummary, *, lang: str = "en") -> str:
    t = _REVIEW_TEXT.get(lang, _REVIEW_TEXT["en"])
    lines = [f"# {t['title']}", "", t["intro"], "", t["head"], "|---|---|---|---|"]
    for g in _GROUPS:
        c = s.groups[g]
        rate = f" ({c['not_stated'] / c['reviewed']:.0%})" if c["reviewed"] else ""
        lines.append(f"| {t['names'][g]} | {c['memories']} | {c['reviewed']} | "
                     f"{c['not_stated']}{rate} |")
    lines.append("")
    if s.estimate is None or s.ci is None:
        names = ", ".join(t["names"][g] for g in s.missing_groups)
        lines += [t["missing"].format(groups=names), ""]
    elif all(c["reviewed"] == c["memories"] for c in s.groups.values()):
        lines += [t["census"].format(est=s.estimate), ""]
    else:
        lines += [t["estimate"].format(est=s.estimate, lo=s.ci[0], hi=s.ci[1]), ""]
    f, v = s.groups["flagged"], s.groups["verified"]
    if f["reviewed"] or v["reviewed"]:
        lines += [t["agreement"], ""]
        if f["reviewed"]:
            lines.append(t["flagged_ok"].format(k=f["not_stated"], n=f["reviewed"]))
        if v["reviewed"]:
            lines.append(t["verified_ok"].format(k=v["reviewed"] - v["not_stated"],
                                                 n=v["reviewed"]))
        lines.append("")
    return "\n".join(lines)
