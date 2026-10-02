import csv
import json

from conftest import FakeJudge, make_policy
from verimem.report import (
    AuditRow,
    audit_pairs,
    load_audit_rows,
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
    assert [p.name for p in paths] == ["report.json", "report.md", "review.csv"]
    data = json.loads(paths[0].read_text(encoding="utf-8"))
    assert data["total"] == 4
    with paths[2].open(encoding="utf-8-sig") as f:
        review = list(csv.DictReader(f))
    assert {r["id"] for r in review} == {"2", "3", "4"}  # everything not supported or unjudged
    assert all(r["reviewer_ok"] == "" for r in review)


def test_load_rows_with_italian_headers(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("fonte;memoria\nLa fonte.;Una memoria.\n;Senza fonte.\n", encoding="utf-8")
    rows = load_audit_rows(p)
    assert [(r.source, r.memory) for r in rows] == [("La fonte.", "Una memoria."),
                                                   ("", "Senza fonte.")]
