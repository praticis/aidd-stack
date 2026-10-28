"""The attribution of changed CALLS edges to the answer that explains them (scripts/judgment/attribution.py), over
synthetic dry-runs and answers. No Docker, no network, no repository."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "judgment"))
import attribution as A  # noqa: E402
import edges_lib as L  # noqa: E402


def run(*edges):
    """A dry-run whose one caller makes the given calls: (line, callee, strategy)."""
    callees = sorted({callee for _, callee, _ in edges})
    return {"files": [{"id": "f", "path": "a.go"}],
            "symbols": [{"id": "s", "file_id": "f", "qualified_name": "F"}]
            + [{"id": c, "file_id": "f", "qualified_name": c} for c in callees],
            "calls": [{"caller_id": "s", "callee_id": c, "line": line, "strategy": st} for line, c, st in edges]}


def row(line, receiver, typ, closures=0):
    return {"repo": "r", "file": "a.go", "line": line, "receiver": receiver, "type": typ, "closures": closures,
            "src": f"{receiver}.Do()"}


def save_runs(tmp_path, before, after):
    for name, data in (("before", before), ("after", after)):
        (tmp_path / name).mkdir(exist_ok=True)
        with gzip.open(tmp_path / name / "r.json.gz", "wt") as fh:
            fh.write(json.dumps(data))
    return tmp_path / "before", tmp_path / "after"


def save_answers(tmp_path, old, new):
    for name, rows in (("old", old), ("new", new)):
        (tmp_path / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "old.jsonl", tmp_path / "new.jsonl"


@pytest.mark.parametrize("was,now,expected", [
    ({("A", "x")}, {("A", "y")}, "strategy"),
    (set(), {("A", "x")}, "added"),
    ({("A", "x")}, set(), "dropped"),
    ({("A", "x")}, {("A", "x"), ("B", "x")}, "widened"),
    ({("A", "x"), ("B", "x")}, {("A", "x")}, "narrowed"),
    ({("A", "x")}, {("B", "x")}, "changed"),
])
def test_a_site_changes_in_one_of_six_ways(was, now, expected):
    assert L.kind(was, now) == expected


def test_the_changed_sites_are_the_ones_whose_edges_differ_in_order_of_line():
    before = run((9, "A", "name"), (3, "B", "name"), (5, "C", "name"))
    after = run((9, "A", "name"), (3, "B", "typed"), (5, "D", "name"))
    assert [(site, kind) for site, was, now in L.changed(before, after) for kind in [L.kind(was, now)]] == [
        (("a.go", 3), "strategy"), (("a.go", 5), "changed")]


def test_a_site_with_the_same_answer_on_both_sides_is_not_a_difference():
    assert A.differences({("r", "a.go", 3): {"h": row(3, "h", "T")}}, {("r", "a.go", 3): {"h": row(3, "h", "T")}}) == {}


def test_an_answer_that_is_missing_on_one_side_is_untyped_there():
    old = {("r", "a.go", 3): {"h": row(3, "h", "T")}}
    new = {("r", "a.go", 4): {"g": row(4, "g", "U", closures=2)}}
    diffs = A.differences(old, new)
    assert (diffs[("r", "a.go", 3)]["old"], diffs[("r", "a.go", 3)]["new"]) == ("T", None)
    assert (diffs[("r", "a.go", 4)]["old"], diffs[("r", "a.go", 4)]["new"], diffs[("r", "a.go", 4)]["closures"]) == (None, "U", 2)


def test_a_site_with_two_receivers_reports_the_first_one_whose_answer_differs():
    old = {("r", "a.go", 3): {"a": row(3, "a", "T"), "b": row(3, "b", "U")}}
    new = {("r", "a.go", 3): {"a": row(3, "a", "T"), "b": row(3, "b", "V")}}
    assert A.differences(old, new)[("r", "a.go", 3)]["receiver"] == "b"


@pytest.mark.parametrize("old,new,case", [(None, "T", "typed-now"), ("T", None, "untyped-now"), ("T", "U", "retyped")])
def test_without_a_table_the_case_is_what_the_answer_did(old, new, case):
    assert A.default_case({"old": old, "new": new}) == case


def test_a_cases_file_names_the_case_and_a_none_falls_back_to_the_answer(tmp_path):
    path = tmp_path / "cases.py"
    path.write_text('def case_of(d):\n    return "closure-in-a-closure" if d["closures"] >= 2 else None\n')
    case_of = A.load_cases(str(path))
    assert case_of({"old": None, "new": "T", "closures": 2}) == "closure-in-a-closure"
    assert case_of({"old": None, "new": "T", "closures": 0}) == "typed-now"
    assert A.load_cases(None)({"old": None, "new": "T", "closures": 2}) == "typed-now"


def test_a_cases_file_without_case_of_is_an_error_that_names_it(tmp_path):
    path = tmp_path / "cases.py"
    path.write_text("x = 1\n")
    with pytest.raises(A.AttributionError, match="cases.py.*case_of"):
        A.load_cases(str(path))


def test_a_changed_site_is_explained_by_the_answer_that_differs_there_and_unexplained_otherwise():
    before = run((3, "A", "name"), (7, "X", "name"))
    after = run((3, "B", "typed"), (7, "Y", "name"))
    diffs = A.differences({}, {("r", "a.go", 3): {"h": row(3, "h", "T")}})
    rows = A.explain("r", before, after, diffs, A.load_cases(None))
    assert [(r["line"], r["kind"], r["case"]) for r in rows] == [(3, "changed", "typed-now"), (7, "changed", "unexplained")]
    assert rows[0]["answer"]["receiver"] == "h" and rows[1]["answer"] is None


def report(tmp_path, capsys, before, after, old, new, *more):
    b, a = save_runs(tmp_path, before, after)
    o, n = save_answers(tmp_path, old, new)
    assert A.main([str(b), str(a), str(o), str(n), "2", "r", *more]) == 0
    return capsys.readouterr().out


def test_the_report_counts_the_sites_by_case_and_kind_and_names_the_unexplained(tmp_path, capsys):
    before = run((3, "A", "name"), (5, "B", "name"), (7, "X", "name"))
    after = run((3, "A2", "typed"), (5, "B", "typed"), (7, "X2", "name"))
    out = report(tmp_path, capsys, before, after, [row(3, "h", "T")], [row(3, "h", "U"), row(5, "g", "V")])
    table = {tuple(w[:2]): w[2] for w in (line.split() for line in out.splitlines()) if len(w) == 3 and w[2].isdigit()}
    assert table[("retyped", "changed")] == "1" and table[("typed-now", "strategy")] == "1"
    assert table[("unexplained", "changed")] == "1"
    assert "3 changed site(s) in r, 1 unexplained" in out


def test_a_sample_shows_the_site_the_answer_and_the_edges_and_a_change_of_strategy_alone_is_not_sampled(tmp_path, capsys):
    before = run((3, "A", "name"), (5, "B", "name"))
    after = run((3, "A2", "typed"), (5, "B", "typed"))
    out = report(tmp_path, capsys, before, after, [row(3, "h", "T")], [row(3, "h", "U"), row(5, "g", "V")])
    assert "[retyped / changed] r a.go:3  h.Do()" in out and "type T -> U" in out
    assert "a.go:5" not in out


def test_the_unexplained_sites_show_their_source_line_when_the_repos_are_given(tmp_path, capsys):
    (tmp_path / "repos" / "r").mkdir(parents=True)
    (tmp_path / "repos" / "r" / "a.go").write_text("package a\n\nfunc F() {\n\tx.Do()\n}\n")
    out = report(tmp_path, capsys, run((4, "X", "name")), run((4, "Y", "name")), [], [], "--repos", str(tmp_path / "repos"))
    assert "[unexplained / changed] r a.go:4  x.Do()" in out


def test_the_samples_are_the_same_for_the_same_inputs(tmp_path, capsys):
    edges = [(n, f"A{n}", "name") for n in range(1, 31)]
    changed = [(n, f"B{n}", "typed") for n in range(1, 31)]
    answers = [row(n, "h", "T") for n in range(1, 31)]
    first = report(tmp_path, capsys, run(*edges), run(*changed), [], answers)
    again = report(tmp_path, capsys, run(*edges), run(*changed), [], answers)
    assert first == again and first.count("[typed-now / changed]") == 2
