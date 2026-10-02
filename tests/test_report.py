import csv
import json

from conftest import FakeJudge, make_policy
from verimem.report import (
    AuditRow,
    audit_pairs,
    load_audit_rows,
    render_html,
    render_markdown,
    wilson,
    write_report,
)
from verimem.verifier import Verifier

ROWS = [
    AuditRow("1", "Maria moved from Rome to Milan in 2021.", "Maria moved to Milan in 2021."),
    AuditRow("2", "Maria moved from Rome to Milan in 2021.", "Maria works as an analyst."),
    AuditRow("3", "We migrated the index last week.", "The migration cut latency by 40%."),
    AuditRow("4", "", "Maria likes jazz."),
]


def verifier() -> Verifier:
    return Verifier(judge=FakeJudge(), policy=make_policy())


def test_audit_counts_and_share():
    rep = audit_pairs(ROWS, verifier())
    assert rep.total == 4
    assert rep.counts["supported"] == 1 and rep.counts["not_supported"] == 2
    assert rep.counts["unjudged"] == 1
    assert abs(rep.unsupported_share - 2 / 3) < 1e-9
    assert rep.numeric_violations == 1
    lo, hi = rep.unsupported_ci
    assert lo < 2 / 3 < hi


def test_wilson_interval():
    lo, hi = wilson(50, 100)
    assert 0.40 < lo < 0.5 < hi < 0.60
    assert wilson(0, 0) != wilson(0, 0)  # NaN when there is nothing to estimate


def test_markdown_in_both_languages_names_the_judge_and_the_limits():
    rep = audit_pairs(ROWS, verifier())
    en = render_markdown(rep, lang="en")
    it = render_markdown(rep, lang="it")
    assert "Memory reliability report" in en and "fake:v1" in en and "Limits" in en
    assert "Rapporto di affidabilità della memoria" in it and "Limiti" in it
    assert "Maria works as an analyst." in en  # an example of an unsupported memory


def test_written_files(tmp_path):
    rep = audit_pairs(ROWS, verifier())
    paths = write_report(rep, tmp_path / "out", lang="it")
    assert [p.name for p in paths] == ["report.json", "report.md", "report.html", "review.csv"]
    data = json.loads(paths[0].read_text(encoding="utf-8"))
    assert data["total"] == 4
    with paths[3].open(encoding="utf-8-sig") as f:
        review = list(csv.DictReader(f))
    # Every judged memory, flagged ones first, with its source for the reviewer.
    assert {r["id"] for r in review[:2]} == {"2", "3"} and review[2]["id"] == "1"
    assert {r["source"] for r in review[:2]} == {ROWS[1].source, ROWS[2].source}
    assert all(r["stated_by_source"] == "" for r in review)


def test_italian_report_explains_in_italian():
    it = render_markdown(audit_pairs(ROWS, verifier()), lang="it")
    assert "**1** sostenute dalla fonte" in it
    assert "la fonte non lo dice" in it
    assert "numeri o date assenti nella fonte: 40%" in it
    assert "the source does not state this" not in it
    assert "quantities not in the source" not in it


def test_calibration_is_described_in_words_not_json():
    pol = make_policy(calibration={"verifier": {"dataset": "pairs.csv", "pairs": 300}})
    rep = audit_pairs(ROWS, Verifier(judge=FakeJudge(), policy=pol))
    md = render_markdown(rep, lang="en")
    assert "- dataset: pairs.csv" in md and "```" not in md


def test_load_rows_with_italian_headers(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("fonte;memoria\nLa fonte.;Una memoria.\n;Senza fonte.\n", encoding="utf-8")
    rows = load_audit_rows(p)
    assert [(r.source, r.memory) for r in rows] == [("La fonte.", "Una memoria."),
                                                   ("", "Senza fonte.")]


def test_a_report_made_with_the_word_overlap_baseline_says_so():
    from verimem.judges.lexical import LexicalJudge

    lexical = Verifier(judge=LexicalJudge(), policy=make_policy())
    for lang, warning in (("en", "not a reliability estimate"), ("it", "non sono una stima")):
        assert warning in render_markdown(audit_pairs(ROWS, lexical), lang=lang)
        assert warning not in render_markdown(audit_pairs(ROWS, verifier()), lang=lang)


def test_html_report_escapes_memories_and_carries_the_numbers(tmp_path):
    rows = [*ROWS, AuditRow("5", "We hired 3 people.", "<script>alert(1)</script> hired 9.")]
    rep = audit_pairs(rows, verifier())
    page = render_html(rep, lang="it")
    assert page.startswith("<!doctype html>") and "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; hired 9." in page
    assert "Rapporto di affidabilità della memoria" in page and f">{rep.total}<" in page
    assert "fake:v1" in page
    paths = write_report(rep, tmp_path / "out", lang="it")
    assert (tmp_path / "out" / "report.html").read_text(encoding="utf-8") == page
    assert [p.name for p in paths] == ["report.json", "report.md", "report.html", "review.csv"]


def test_html_report_warns_about_the_word_overlap_baseline():
    from verimem.judges.lexical import LexicalJudge

    rep = audit_pairs(ROWS, Verifier(judge=LexicalJudge(), policy=make_policy()))
    assert "not a reliability estimate" in render_html(rep, lang="en")


CONVERSATION_CSV = ('source,memory\n"User: hi\r\nAgent: hello, how can I help?\r\nUser: I live '
                    'in Turin, ""near the river""",The user lives in Turin.\n')
TURNS = ["User: hi", "Agent: hello, how can I help?", 'User: I live in Turin, "near the river"']


def test_a_multi_line_source_in_csv_keeps_its_lines(tmp_path):
    p = tmp_path / "m.csv"
    p.write_bytes(CONVERSATION_CSV.encode("utf-8"))
    [row] = load_audit_rows(p)
    assert row.source.splitlines() == TURNS and row.memory == "The user lives in Turin."


def test_audit_rows_read_json_lines_holding_a_unicode_line_separator(tmp_path):
    p = tmp_path / "m.jsonl"
    row = {"source": "Line one line two.", "memory": "Line one."}
    p.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    assert [r.source for r in load_audit_rows(p)] == ["Line one line two."]


def test_audit_rows_read_a_json_array(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps([{"source": "Maria lives in Turin.", "memory": "Maria lives in "
                              "Turin."}], indent=2), encoding="utf-8")
    assert [r.memory for r in load_audit_rows(p)] == ["Maria lives in Turin."]
