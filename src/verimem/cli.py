"""The `verimem` command. Thin: every decision lives in the library (ADR-0003)."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ._version import __version__

DEFAULT_DB = Path(os.environ.get("VERIMEM_DB", Path.home() / ".verimem" / "memory.db"))


def _policy(args: argparse.Namespace) -> Any:
    from .policy import Policy

    pol = Policy.load(args.policy) if args.policy else Policy.default()
    if getattr(args, "judge", None):
        from dataclasses import replace

        pol = replace(pol, judge=args.judge)
    return pol


def _verifier(args: argparse.Namespace, *, allow_download: bool = False) -> Any:
    from .verifier import Verifier

    return Verifier(policy=_policy(args), allow_download=allow_download)


def _memory(args: argparse.Namespace) -> Any:
    from .memory import Memory

    return Memory(args.db, verifier=_verifier(args))


def _read_source(args: argparse.Namespace) -> str | None:
    if getattr(args, "source", None):
        return Path(args.source).read_text(encoding="utf-8")
    return getattr(args, "source_text", None)


def _command(args: argparse.Namespace) -> str:
    """The command line as typed, for the provenance line of generated reports."""
    return "verimem " + shlex.join(args.argv)


def _emit(args: argparse.Namespace, data: Any, human: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(human)


def _fact_line(f: Any, score: float | None = None) -> str:
    head = f"[{f.status.value}] {f.text}" + (f"  (score {score:.2f})" if score is not None else "")
    ev = f"\n    evidence: “{f.evidence.text}”" if f.evidence else ""
    origin = f"  from {f.source_origin}" if f.source_origin else ""
    return f"{head}\n    id {f.id}{origin}{ev}"


# ---------------------------------------------------------------- commands

def _ready_verifier(args: argparse.Namespace) -> Any:
    """A verifier whose judge is loaded: commands that only judge stop here, with the reason,
    instead of producing a report where nothing was judged."""
    verifier = _verifier(args)
    verifier.warmup()
    return verifier


def cmd_check(args: argparse.Namespace) -> int:
    v = _ready_verifier(args).check(_read_source(args), args.claim)
    ev = f"\nevidence: “{v.evidence.text}”" if v.evidence else ""
    _emit(args, v.to_dict(), f"{v.label.value}: {v.reason}{ev}\njudge {v.judge}, "
                             f"policy {v.policy}")
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        r = m.remember(args.claim, source=_read_source(args), author=args.author,
                       origin=args.origin, subject=args.subject, observed_at=args.observed_at,
                       written_by=args.written_by)
        human = f"{r.status.value} (id {r.fact_id}): {r.verdict.reason}"
        if r.superseded:
            human += f"\nsuperseded: {', '.join(r.superseded)}"
        if r.duplicate_of:
            human += "\nalready known: nothing new stored"
        _emit(args, r.to_dict(), human)
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    from .types import Status

    include = list(Status) if args.all else [Status.VERIFIED]
    with _memory(args) as m:
        hits = m.recall(args.query, k=args.k, include=include)
        _emit(args, [h.to_dict() for h in hits],
              "\n".join(_fact_line(h.fact, h.score) for h in hits) or "nothing found")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        a = m.ask(args.question, k=args.k)
        if a.abstained:
            human = f"not in memory: {a.reason}"
        else:
            human = "\n".join(_fact_line(r.fact, r.score) for r in a.facts)
        _emit(args, a.to_dict(), human)
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        facts = m.review_queue(args.limit)
        _emit(args, [f.to_dict() for f in facts],
              "\n".join(f"{_fact_line(f)}\n    reason: {f.reason}" for f in facts)
              or "nothing to review")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        f = m.review(args.fact_id, approve=args.decision == "approve", reviewer=args.reviewer)
        _emit(args, f.to_dict(), f"{f.status.value}: {f.reason}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        m.forget(args.fact_id, reason=args.reason)
        _emit(args, {"forgotten": args.fact_id}, f"forgotten: {args.fact_id}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        s = m.stats()
        _emit(args, s, json.dumps(s, indent=2))
    return 0


def cmd_chain(args: argparse.Namespace) -> int:
    with _memory(args) as m:
        if args.action == "export":
            n = m.audit.export(args.out or sys.stdout)
            if args.out:
                print(f"{n} events written to {args.out}")
            return 0
        c = m.audit.verify()
        _emit(args, c.__dict__, f"audit chain {'OK' if c.ok else 'BROKEN'}: {c.events} events"
                                + ("" if c.ok else f", first bad event {c.first_bad}: {c.reason}"))
        return 0 if c.ok else 1


def cmd_audit(args: argparse.Namespace) -> int:
    from .report import audit_pairs, load_audit_rows, write_report

    rows = load_audit_rows(args.pairs)
    if not rows:
        print("no (source, memory) pairs found in the input", file=sys.stderr)
        return 2
    rep = audit_pairs(rows, _ready_verifier(args))
    paths = write_report(rep, args.out, lang=args.lang)
    lo, hi = rep.unsupported_ci
    if rep.total == rep.counts.get("unjudged", 0):
        print(f"{rep.total} memories read; no memory had a source, so none could be checked.")
    else:
        print(f"{rep.total} memories checked; not supported by their source: "
              f"{rep.unsupported_share:.0%} (95% CI {lo:.0%}-{hi:.0%}).")
    print("written: " + ", ".join(str(p) for p in paths))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from .evalkit import evaluate_verifier, load_pairs, render_verifier_report

    pairs = load_pairs(args.pairs)
    rep, _ = evaluate_verifier(_ready_verifier(args), pairs)
    md = render_verifier_report(rep, dataset=str(args.pairs), command=_command(args))
    if args.markdown:
        Path(args.markdown).write_text(md, encoding="utf-8")
    _emit(args, rep.to_dict(), md)
    return 0


def cmd_eval_ask(args: argparse.Namespace) -> int:
    from .evalkit import evaluate_ask, render_ask_report
    from .memory import Memory

    verifier = _ready_verifier(args)
    rep = evaluate_ask(lambda: Memory(":memory:", verifier=verifier), args.qa, k=args.k)
    if args.markdown:
        Path(args.markdown).write_text(
            render_ask_report(rep, dataset=str(args.qa), command=_command(args)), encoding="utf-8")
    human = (f"{rep.questions} questions ({rep.answerable} answerable), relevance threshold "
             f"{rep.threshold}:\n  answered with the right fact {rep.answered_right}/"
             f"{rep.answerable}, wrong abstentions {rep.wrong_abstentions}, wrong fact "
             f"{rep.wrong_fact}, retrieval misses {rep.retrieval_misses}\n  right abstentions "
             f"{rep.right_abstentions}/{rep.questions - rep.answerable}, false answers "
             f"{rep.false_answers}\n  AUROC answerable vs not {rep.auroc:.3f}")
    _emit(args, rep.to_dict(), human)
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from .evalkit import calibrate, load_pairs

    verifier = _ready_verifier(args)
    th, prov = calibrate(verifier, load_pairs(args.pairs), target_loss=args.target_loss)
    pol = verifier.policy.with_thresholds(th, version=args.version,
                                          calibration={"verifier": {"dataset": str(args.pairs),
                                                                    **prov}})
    pol.save(args.out)
    print(f"support >= {th.support}, uncertain >= {th.uncertain}; held-out: true lost "
          f"{prov['held_out_true_lost']:.0%}, unstated admitted "
          f"{prov['held_out_unstated_admitted']:.0%}. Policy written to {args.out}")
    return 0


def cmd_warmup(args: argparse.Namespace) -> int:
    v = _verifier(args, allow_download=True)
    print(f"downloading (first time only) and loading {v.policy.judge} ...", flush=True)
    print(f"ready: {v.warmup()}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    import importlib.util
    import sqlite3

    report: dict[str, Any] = {"verimem": __version__, "python": sys.version.split()[0],
                              "sqlite": sqlite3.sqlite_version}
    for mod in ("torch", "transformers", "mcp"):
        report[mod] = importlib.util.find_spec(mod) is not None
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        report["fts5"] = True
    except sqlite3.OperationalError:
        report["fts5"] = False
    pol = _policy(args)
    report["policy"] = pol.version
    report["judge"] = pol.judge
    from .judges import JudgeUnavailable

    try:
        _verifier(args).warmup()
        report["judge_ready"] = True
    except (JudgeUnavailable, ValueError) as e:
        report["judge_ready"] = False
        report["judge_problem"] = str(e)
    report["db"] = str(args.db)
    _emit(args, report, "\n".join(f"{k}: {v}" for k, v in report.items()))
    return 0 if report["fts5"] else 1


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import serve

    serve(db=str(args.db), policy=_policy(args), allow_review=args.allow_review)
    return 0


# ---------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="verimem", description="Verified memory for AI agents.")
    p.add_argument("--version", action="version", version=f"verimem {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name: str, fn: Any, help_: str, *, db: bool = False) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        sp.add_argument("--policy", help="policy JSON file (default: the bundled policy)")
        sp.add_argument("--judge", help="override the policy's judge, e.g. hf:<model> or lexical")
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        if db:
            sp.add_argument("--db", type=Path, default=DEFAULT_DB,
                            help=f"memory database (default {DEFAULT_DB}, or $VERIMEM_DB)")
        return sp

    def source_args(sp: argparse.ArgumentParser) -> None:
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--source", help="file with the source text")
        g.add_argument("--source-text", help="the source text itself")

    sp = add("check", cmd_check, "verify a claim against a source, without storing anything")
    sp.add_argument("claim")
    source_args(sp)

    sp = add("remember", cmd_remember, "verify a claim and store it", db=True)
    sp.add_argument("claim")
    source_args(sp)
    sp.add_argument("--author", default="user",
                    choices=["user", "document", "system", "agent", "tool", "web"])
    sp.add_argument("--origin", default="", help="where the source came from (free text)")
    sp.add_argument("--subject", help="key for supersession, e.g. user.city")
    sp.add_argument("--observed-at", help="when the source was produced (ISO 8601)")
    sp.add_argument("--written-by", default="cli")

    sp = add("recall", cmd_recall, "keyword search over verified facts", db=True)
    sp.add_argument("query")
    sp.add_argument("-k", type=int, default=5)
    sp.add_argument("--all", action="store_true", help="include unverified, quarantined, ...")

    sp = add("ask", cmd_ask, "answer from verified facts, or abstain", db=True)
    sp.add_argument("question")
    sp.add_argument("-k", type=int, default=5)

    sp = add("queue", cmd_queue, "facts waiting for human review", db=True)
    sp.add_argument("--limit", type=int, default=20)

    sp = add("review", cmd_review, "approve or reject a fact after human review", db=True)
    sp.add_argument("fact_id")
    sp.add_argument("decision", choices=["approve", "reject"])
    sp.add_argument("--reviewer", required=True)

    sp = add("forget", cmd_forget, "delete a fact for good", db=True)
    sp.add_argument("fact_id")
    sp.add_argument("--reason", default="")

    add("stats", cmd_stats, "counts and audit-chain status", db=True)

    sp = add("chain", cmd_chain, "verify or export the audit chain", db=True)
    sp.add_argument("action", choices=["verify", "export"])
    sp.add_argument("--out", help="file for export (default: stdout)")

    sp = add("audit", cmd_audit, "memory reliability report from (source, memory) pairs")
    sp.add_argument("pairs", help="CSV or JSONL with columns source and memory")
    sp.add_argument("--out", required=True, help="output folder")
    sp.add_argument("--lang", default="en", choices=["en", "it"])

    sp = add("eval", cmd_eval, "evaluate the verifier on labelled pairs (S/N/C)")
    sp.add_argument("pairs")
    sp.add_argument("--markdown", help="also write the Markdown report to this file")

    sp = add("eval-ask", cmd_eval_ask, "evaluate abstention on a QA set")
    sp.add_argument("qa")
    sp.add_argument("-k", type=int, default=5)
    sp.add_argument("--markdown", help="also write the Markdown report to this file")

    sp = add("calibrate", cmd_calibrate, "derive thresholds from labelled pairs")
    sp.add_argument("pairs")
    sp.add_argument("--out", required=True, help="policy JSON to write")
    sp.add_argument("--version", required=True, help="version string for the new policy")
    sp.add_argument("--target-loss", type=float, default=0.08)

    add("warmup", cmd_warmup, "download (once) and load the judge model")
    add("doctor", cmd_doctor, "check the installation", db=True)
    sp = add("mcp", cmd_mcp, "run the MCP server on stdio", db=True)
    sp.add_argument("--allow-review", action="store_true",
                    help="also expose the review tool, which lets the connected agent approve "
                         "facts the verifier did not verify (off by default)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    from .judges import JudgeUnavailable

    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    args.argv = argv
    try:
        return int(args.fn(args))
    except JudgeUnavailable as e:
        print(f"error: the judge is not available: {e}", file=sys.stderr)
        return 2
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
