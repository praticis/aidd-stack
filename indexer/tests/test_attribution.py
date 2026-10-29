"""The attribution of changed CALLS edges to the answer that explains them (scripts/judgment/attribution.py), over
synthetic dry-runs and answers. No Docker, no network, no repository."""
from __future__ import annotations

import gzip
import json
import re
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


def made_in(*calls):
    """A dry-run of a Python file and a Vue file whose calls are (file, line, strategy); the calls on line 9 are made
    from the file itself, not from one of its symbols."""
    files = [{"id": "py", "path": "a.py", "language": "python"}, {"id": "vue", "path": "b.vue", "language": "vue"}]
    return {"files": files, "symbols": [{"id": f"s-{f}", "file_id": f, "qualified_name": f} for f in ("py", "vue")],
            "calls": [{"caller_id": f if line == 9 else f"s-{f}", "callee_id": f"c{i}", "line": line, "strategy": st}
                      for i, (f, line, st) in enumerate(calls)]}


def test_the_edges_are_counted_by_strategy_and_a_site_is_ambiguous_when_one_of_its_edges_is():
    s = L.strategies(made_in(("py", 3, "same-module-ambiguous"), ("py", 3, "same-file"), ("py", 5, "receiver-type"),
                             ("py", 7, "same-module-ambiguous"), ("py", 7, "same-module-ambiguous"),
                             ("py", 9, "unique-name")))
    assert s.edges == {"same-module-ambiguous": 3, "same-file": 1, "receiver-type": 1, "unique-name": 1}
    assert (s.ambiguous_edges, s.sites, s.ambiguous_sites) == (3, 4, 2)


def test_a_language_keeps_only_the_calls_made_in_its_files():
    run_ = made_in(("py", 3, "same-file"), ("vue", 3, "same-module-ambiguous"), ("vue", 9, "unique-name"))
    assert L.strategies(run_, "python") == ({"same-file": 1}, 1, 0)
    assert L.strategies(run_) == ({"same-file": 1, "same-module-ambiguous": 1, "unique-name": 1}, 3, 1)


def strategy_section(out: str, title: str) -> list:
    lines = out[out.index(title):].split("\n\n")[0].splitlines()[1:]
    return [tuple(c.strip() for c in re.fullmatch(r"  (.{26}) (.{9}) (.{9})", line).groups()) for line in lines]


def test_the_report_ends_with_the_languages_calls_by_strategy_and_the_shares_found_among_homonyms(tmp_path, capsys):
    before = made_in(("py", 3, "same-module-ambiguous"), ("py", 3, "same-module-ambiguous"), ("py", 5, "same-file"),
                     ("vue", 3, "same-module-ambiguous"))
    after = made_in(("py", 3, "receiver-type"), ("py", 5, "same-file"), ("vue", 3, "same-module-ambiguous"))
    out = report(tmp_path, capsys, before, after, [], [], "--language", "python")
    assert strategy_section(out, "python's CALLS in r, by strategy") == [
        ("", "before", "after"), ("receiver-type", "0", "1"), ("same-file", "1", "1"),
        ("same-module-ambiguous", "2", "0"), ("edges", "3", "2"), ("ambiguous edges", "66.7 %", "0.0 %"),
        ("sites", "2", "2"), ("ambiguous sites", "50.0 %", "0.0 %")]


def test_without_a_language_the_report_counts_every_file_and_a_share_of_nothing_is_a_dash(tmp_path, capsys):
    out = report(tmp_path, capsys, made_in(("vue", 3, "same-module-ambiguous")), made_in(), [], [])
    assert strategy_section(out, "every language's CALLS in r, by strategy")[-4:] == [
        ("edges", "1", "0"), ("ambiguous edges", "100.0 %", "-"), ("sites", "1", "0"), ("ambiguous sites", "100.0 %", "-")]


def untyped(line, why):
    return {**row(line, "h", None), "unknown": why}


def test_the_report_ends_with_the_receivers_each_side_leaves_untyped_by_the_reason_it_gives(tmp_path, capsys):
    old = [untyped(3, "a for target")]
    new = [untyped(3, "a for target"), untyped(5, "bindings that disagree"), row(7, "g", "T")]
    out = report(tmp_path, capsys, run(), run(), old, new)
    assert strategy_section(out, "receivers with no type, by the reason the language gives") == [
        ("", "before", "after"), ("a for target", "1", "1"), ("bindings that disagree", "0", "1")]


def test_a_language_that_gives_no_reason_says_so(tmp_path, capsys):
    out = report(tmp_path, capsys, run(), run(), [row(3, "h", "T")], [row(3, "h", "T")])
    assert out.rstrip().endswith("receivers with no type, by the reason the language gives\n"
                                 f"  {'':26} {'before':>9} {'after':>9}\n  no side gives one")
