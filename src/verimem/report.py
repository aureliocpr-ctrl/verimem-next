"""Memory reliability report: audit (source, memory) pairs exported from any memory system.

The deliverable a customer reads: how many stored memories their sources actually support,
which do not (with the closest evidence), which add numbers the source never states, and
how far the judge itself can be trusted. Outputs JSON (everything), Markdown (the report)
and CSV (one row per flagged memory, with an empty column for a human reviewer).
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._version import __version__
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
    """Read (source, memory) pairs from JSON lines or CSV (`,`/`;`, English or Italian headers)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".jsonl", ".json"}:
        raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        first = text.splitlines()[0] if text else ""
        delim = ";" if first.count(";") > first.count(",") else ","
        raw = list(csv.DictReader(text.splitlines(), delimiter=delim))
    rows = []
    for i, r in enumerate(raw):
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
        calibration=verifier.policy.calibration)


def _row(r: AuditRow, v: Verdict) -> dict[str, Any]:
    missing = next((c.detail for c in v.checks if c.name == "quantities" and not c.passed), "")
    return {"id": r.id, "memory": r.memory, "verdict": v.label.value,
            "support": round(v.support, 4), "reason": v.reason,
            "evidence": v.evidence.text if v.evidence else "", "quantities": missing}


# ---------------------------------------------------------------- writing

_TEXT = {
    "en": {
        "title": "Memory reliability report",
        "summary": "Summary",
        "pairs": "memories checked against the source they were extracted from",
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
        "summary": "Sintesi",
        "pairs": "memorie confrontate con il testo da cui sono state estratte",
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


def render_markdown(rep: AuditReport, *, lang: str = "en", examples: int = 10) -> str:
    t = _TEXT.get(lang, _TEXT["en"])
    judged = rep.total - rep.counts.get("unjudged", 0)
    flagged = rep.counts.get("not_supported", 0) + rep.counts.get("contradicted", 0)
    lo, hi = rep.unsupported_ci
    share = "n/a" if judged == 0 else f"{rep.unsupported_share:.0%} ({lo:.0%}-{hi:.0%})"
    lines = [
        f"# {t['title']}", "",
        f"## {t['summary']}", "",
        f"- **{rep.total}** {t['pairs']}.",
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
            lines.append(f"  {r['reason']}  ")
            if r["evidence"]:
                lines.append(f"  _{t['closest']}:_ “{r['evidence']}”")
            lines.append("")
    lines += [f"## {t['limits']}", "",
              t["limits_text"].format(judge=rep.judge, policy=rep.policy), ""]
    if rep.calibration:
        lines += [f"### {t['calibration']}", "", "```json",
                  json.dumps(rep.calibration, indent=2, ensure_ascii=False), "```", ""]
    lines.append(t["made"].format(version=rep.verimem_version, date=rep.created_at))
    return "\n".join(lines) + "\n"


def write_report(rep: AuditReport, out_dir: str | Path, *, lang: str = "en") -> list[Path]:
    """Write report.json, report.md and review.csv into `out_dir`; return the paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / "report.json", out / "report.md", out / "review.csv"]
    paths[0].write_text(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    paths[1].write_text(render_markdown(rep, lang=lang), encoding="utf-8")
    with paths[2].open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "memory", "verdict", "support", "reason", "evidence", "reviewer_ok"])
        for r in rep.rows:
            if r["verdict"] != "supported":
                w.writerow([r["id"], r["memory"], r["verdict"], r["support"], r["reason"],
                            r["evidence"], ""])
    return paths
