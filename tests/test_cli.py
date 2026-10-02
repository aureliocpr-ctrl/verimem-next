"""The CLI with the lexical baseline judge: it exercises every command without models.
The lexical judge can never verify (ADR-0004), which these tests also show."""

import csv
import json
import re
import shlex

import pytest

from verimem.cli import main


def run(capsys, *argv) -> tuple[int, str]:
    code = main(list(argv))
    return code, capsys.readouterr().out


def test_check_prints_a_verdict(capsys):
    code, out = run(capsys, "check", "Maria moved to Milan.", "--source-text",
                    "Maria moved from Rome to Milan.", "--judge", "lexical", "--json")
    assert code == 0
    assert json.loads(out)["label"] == "supported"


def test_remember_recall_queue_review_forget_chain(tmp_path, capsys):
    db = str(tmp_path / "m.db")
    common = ["--db", db, "--judge", "lexical", "--json"]
    code, out = run(capsys, "remember", "Maria moved to Milan.", "--source-text",
                    "Maria moved from Rome to Milan.", *common)
    fact = json.loads(out)
    assert code == 0 and fact["status"] == "unverified"  # a heuristic judge never verifies

    code, out = run(capsys, "recall", "Maria Milan", *common)
    assert json.loads(out) == []  # recall serves verified facts only
    code, out = run(capsys, "recall", "Maria Milan", "--all", *common)
    assert [h["id"] for h in json.loads(out)] == [fact["fact_id"]]

    code, out = run(capsys, "queue", *common)
    assert [f["id"] for f in json.loads(out)] == [fact["fact_id"]]
    code, out = run(capsys, "review", fact["fact_id"], "approve", "--reviewer", "aurelio",
                    *common)
    assert json.loads(out)["status"] == "verified"

    code, out = run(capsys, "forget", fact["fact_id"], *common)
    assert code == 0
    code, out = run(capsys, "chain", "verify", *common)
    assert code == 0 and json.loads(out)["ok"] is True
    code, out = run(capsys, "stats", *common)
    assert json.loads(out)["facts"] == {"forgotten": 1}


def test_errors_are_reported_without_a_traceback(tmp_path, capsys):
    code = main(["review", "missing-id", "approve", "--reviewer", "x", "--db",
                 str(tmp_path / "m.db"), "--judge", "lexical"])
    assert code == 2
    assert "no fact with id" in capsys.readouterr().err


def test_audit_command_writes_the_report(tmp_path, capsys):
    pairs = tmp_path / "pairs.jsonl"
    pairs.write_text(json.dumps({"source": "We hired 3 people.", "memory": "We hired 5 people."})
                     + "\n", encoding="utf-8")
    code, out = run(capsys, "audit", str(pairs), "--out", str(tmp_path / "rep"), "--judge",
                    "lexical", "--lang", "it")
    assert code == 0 and "100%" in out
    assert (tmp_path / "rep" / "report.md").read_text(encoding="utf-8").startswith(
        "# Rapporto di affidabilità della memoria")


def test_eval_command(tmp_path, capsys):
    data = tmp_path / "d.csv"
    data.write_text("source,claim,label\nThe sky is blue.,The sky is blue.,S\n"
                    "The sky is blue.,The grass is green.,N\n", encoding="utf-8")
    code, out = run(capsys, "eval", str(data), "--judge", "lexical", "--markdown",
                    str(tmp_path / "e.md"))
    assert code == 0 and "| 1 / 1 / 0 |" in out
    assert (tmp_path / "e.md").exists()


def test_eval_report_records_the_command_that_produced_it(tmp_path, capsys):
    folder = tmp_path / "eval out"  # a space, like a Windows backslash, needs quoting
    folder.mkdir()
    data = folder / "d.csv"
    data.write_text("source,claim,label\nThe sky is blue.,The sky is blue.,S\n", encoding="utf-8")
    md = folder / "e.md"
    run(capsys, "eval", str(data), "--judge", "lexical", "--markdown", str(md))
    text = md.read_text("utf-8")
    typed = ["eval", str(data), "--judge", "lexical", "--markdown", str(md)]
    assert f"`verimem {shlex.join(typed)}`" in text  # a command one can paste and rerun
    assert re.search(r"\bnan\b", text) is None  # only S pairs: AUROC is n/a, not nan


def test_audit_without_any_source_says_so(tmp_path, capsys):
    pairs = tmp_path / "p.jsonl"
    pairs.write_text(json.dumps({"memory": "Maria likes jazz."}) + "\n", encoding="utf-8")
    code, out = run(capsys, "audit", str(pairs), "--out", str(tmp_path / "r"), "--judge",
                    "lexical")
    assert code == 0 and "nan" not in out.lower()
    assert "no memory had a source" in out


def test_a_missing_judge_stops_with_an_error_instead_of_an_empty_report(tmp_path, capsys):
    pairs = tmp_path / "p.jsonl"
    pairs.write_text(json.dumps({"source": "We hired 3 people.", "memory": "We hired 3 people.",
                                 "label": "S"}) + "\n", encoding="utf-8")
    for argv in (["audit", str(pairs), "--out", str(tmp_path / "r")], ["eval", str(pairs)],
                 ["check", "We hired 3 people.", "--source-text", "We hired 3 people."]):
        code = main([*argv, "--judge", "hf:verimem-tests/no-such-model"])
        assert code == 2
        assert "judge is not available" in capsys.readouterr().err
    assert not (tmp_path / "r").exists()


def test_mcp_review_tool_is_opt_in(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    import verimem.mcp_server as mcp_server

    seen: list[bool] = []
    monkeypatch.setattr(mcp_server, "serve", lambda **kw: seen.append(kw["allow_review"]))
    main(["mcp", "--db", str(tmp_path / "m.db")])
    main(["mcp", "--db", str(tmp_path / "m.db"), "--allow-review"])
    assert seen == [False, True]


def test_eval_ask_writes_markdown_with_its_provenance(tmp_path, capsys):
    qa = tmp_path / "qa.json"
    qa.write_text(json.dumps({
        "facts": [{"id": "f1", "text": "Maria lives in Milan."}],
        "questions": [{"q": "Where does Maria live?", "answer": ["f1"]},
                      {"q": "What is the name of Maria's dog?", "answer": []}]}),
        encoding="utf-8")
    md = tmp_path / "ask out.md"
    code, _ = run(capsys, "eval-ask", str(qa), "--judge", "lexical", "--markdown", str(md))
    text = md.read_text("utf-8")
    assert code == 0
    typed = ["eval-ask", str(qa), "--judge", "lexical", "--markdown", str(md)]
    assert f"`verimem {shlex.join(typed)}`" in text
    assert "`lexical:v1`" in text and "| 2 (1) |" in text


def test_audit_review_turns_a_reviewed_sample_into_an_estimate(tmp_path, capsys):
    pairs = tmp_path / "pairs.jsonl"
    pairs.write_text("".join(json.dumps({"source": "We hired 3 people.", "memory": m}) + "\n"
                             for m in ("We hired 3 people.", "We hired 5 people.")),
                     encoding="utf-8")
    folder = tmp_path / "rep"
    run(capsys, "audit", str(pairs), "--out", str(folder), "--judge", "lexical")
    code, out = run(capsys, "audit-review", str(folder))
    assert code == 0 and "No estimate yet" in out

    review = folder / "review.csv"
    with review.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:  # the reviewer agrees with the judge on both
        r["stated_by_source"] = "no" if r["verdict"] == "not_supported" else "sì"
    with review.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    code, out = run(capsys, "audit-review", str(folder), "--lang", "it")
    assert code == 0 and "Memorie non dette dalla loro fonte: 50%" in out
    assert (folder / "review-summary.md").read_text("utf-8").startswith("# Revisione umana")


def test_recall_does_not_print_raw_keyword_scores(tmp_path, capsys):
    common = ["--db", str(tmp_path / "m.db"), "--judge", "lexical"]
    run(capsys, "remember", "Maria moved to Milan.", "--source-text",
        "Maria moved from Rome to Milan.", *common)
    code, out = run(capsys, "recall", "Maria Milan", "--all", *common)
    assert code == 0 and "Maria moved to Milan." in out and "score" not in out


def test_ask_output_separates_answers_from_related_facts():
    from verimem.cli import answer_text
    from verimem.types import Answer, Fact, Label, Recalled, Status

    def fact(text: str) -> Fact:
        return Fact(id="f1", text=text, status=Status.VERIFIED, label=Label.SUPPORTED,
                    support=1.0, subject=None, source_id=None, source_origin=None,
                    source_author="user", evidence=None, judge="fake:v1", policy="test",
                    reason="", created_at="2026-10-02T00:00:00Z", valid_from=None)

    a = Answer("Who leads the team?", (), True, "no verified fact answers the question",
               related=(Recalled(fact("Anna leads the data platform team."), 0.11),))
    text = answer_text(a)
    assert text.startswith("not in memory:")
    assert "related" in text and "Anna leads the data platform team." in text


def labelled(tmp_path):
    data = tmp_path / "d.csv"
    rows = ["source,claim,label"]
    for i in range(12):
        rows.append(f"Note {i}: alpha{i} beta{i}.,alpha{i} beta{i},S")
        rows.append(f"Note {i}: alpha{i}.,alpha{i} gamma{i},N")
    data.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return data


def test_eval_writes_one_line_per_pair(tmp_path, capsys):
    out = tmp_path / "scores.jsonl"
    code, _ = run(capsys, "eval", str(labelled(tmp_path)), "--judge", "lexical",
                  "--pairs-out", str(out))
    rows = [json.loads(line) for line in out.read_text("utf-8").splitlines()]
    assert code == 0 and len(rows) == 24
    assert set(rows[0]) == {"id", "label", "verdict", "support", "score", "lang"}


def test_calibrate_takes_a_loss_target_or_an_admission_cap(tmp_path, capsys):
    data, pol = labelled(tmp_path), tmp_path / "p.json"
    code, out = run(capsys, "calibrate", str(data), "--judge", "lexical", "--out", str(pol),
                    "--version", "t1", "--max-admitted", "0.05")
    written = json.loads(pol.read_text("utf-8"))
    assert code == 0 and written["version"] == "t1"
    assert written["calibration"]["verifier"]["objective"] == (
        "at most 5% of unsupported claims admitted")
    assert "at most 5% of unsupported claims admitted" in out
    with pytest.raises(SystemExit):
        main(["calibrate", str(data), "--out", str(pol), "--version", "t2",
              "--target-loss", "0.1", "--max-admitted", "0.05"])


def test_the_judge_precision_can_be_overridden_on_the_command_line(capsys):
    _, out = run(capsys, "doctor", "--judge-dtype", "bfloat16", "--json")
    assert json.loads(out)["judge_dtype"] == "bfloat16"
