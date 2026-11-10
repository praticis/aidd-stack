"""How the scorecard (scripts/judgment/scorecard_measure.py) measures a tree on dry-runs and checker rows made for the purpose:
how an edge is classed, the counts, the numbers with no bound, the keys and the wins lost."""
import importlib.util
from pathlib import Path

import pytest

from scorecard_cases import BAR, CALLS, FOO, MAIN, OWNER, ROWS, THING, call, make_tree

spec = importlib.util.spec_from_file_location(
    "scorecard", Path(__file__).resolve().parent.parent / "scripts" / "judgment" / "scorecard.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
M = S.M


@pytest.fixture
def tree(tmp_path):
    return make_tree(tmp_path)


def counts_of(repos, repo="r"):
    return dict(repos[repo].reference.counts)


# -- how an edge is classed ----------------------------------------------------------------------------------------------

def test_the_checkers_verdict_on_each_typed_edge_is_one_of_four_classes_by_strategy(tree):
    runs, rows = tree()
    assert counts_of(M.measure(runs, rows)) == {
        ("receiver-type", "confirmed"): 2, ("receiver-type", "contradicted"): 1, ("receiver-type", "indirect"): 1,
        ("receiver-type", "undecided"): 2, ("inherited", "confirmed"): 1,
        ("unique-name", "confirmed"): 1, ("same-module", "contradicted"): 1}


@pytest.mark.parametrize("verdict,expected", [
    ("agrees", "confirmed"), ("agrees (via .d.ts pair)", "confirmed"), ("agrees (owner of the member)", "confirmed"),
    ("checker: another declaration", "contradicted"), ("checker: a declaration file's member", "indirect"),
    ("checker: none", "undecided"), ("checker: outside", "undecided"), ("no checker site", "undecided")])
def test_each_verdict_has_one_class(verdict, expected):
    assert M.klass(verdict) == expected


def test_an_edge_to_the_type_that_owns_a_member_is_confirmed_by_the_method_it_records(tree):
    runs, rows = tree(calls=[call(MAIN, OWNER, 5, "inherited", "get")], rows=[ROWS[2]])
    assert counts_of(M.measure(runs, rows)) == {("inherited", "confirmed"): 1}


def test_a_declaration_file_stands_for_the_js_beside_it(tree):
    runs, rows = tree(calls=[call(MAIN, THING, 7, "receiver-type", "m")],
                      rows=[{"file": "src/use.ts", "line": 7, "method": "m", "declared": ["src/x.d:Thing.m"]}])
    assert counts_of(M.measure(runs, rows)) == {("receiver-type", "confirmed"): 1}


def test_a_declaration_outside_the_repo_is_undecided_and_no_decided_site(tree):
    runs, rows = tree(rows=[{"file": "src/use.ts", "line": 3, "method": "run", "declared": ["outside"]}])
    ref = M.measure(runs, rows)["r"].reference
    assert ref.counts[("receiver-type", "undecided")] == 6 and ref.recall[2] == 0


def test_the_python_calls_are_no_ts_calls(tree):
    runs, rows = tree()
    ref = M.measure(runs, rows)["r"].reference
    assert sum(n for (f, _), n in ref.counts.items() if f == "receiver-type") == 6  # the seven typed edges, minus the Python one


def test_a_repo_with_no_rows_has_only_the_typed_share_and_each_dry_run_is_a_repo(tree):
    runs, rows = tree(rows=None)
    tree(repo="a", rows=None)
    repos = M.measure(runs, rows)
    assert list(repos) == ["a", "r"] and all(r.reference is None for r in repos.values())
    assert M.gated(repos) == {} and M.keyed_of(repos) == {}


# -- the counts -------------------------------------------------------------------------------------------------------------

def test_the_gated_counts_are_the_confirmed_and_the_contradicted_typed_edges_by_strategy(tree):
    runs, rows = tree()
    assert M.gated(M.measure(runs, rows)) == {
        "r.receiver-type.confirmed": 2, "r.receiver-type.contradicted": 1, "r.inherited.confirmed": 1, "r.inherited.contradicted": 0}


def test_a_strategy_the_repo_has_no_edge_of_has_no_count(tree):
    runs, rows = tree(calls=[call(MAIN, FOO, 3, "receiver-type", "run")], rows=[ROWS[0]])
    assert set(M.gated(M.measure(runs, rows))) == {"r.receiver-type.confirmed", "r.receiver-type.contradicted"}


def test_a_call_form_the_graph_learns_to_read_moves_no_count_of_the_typed_edges(tree):
    runs, rows = tree()
    more = [call(MAIN, THING, 20 + i, "unique-name", "m") for i in range(5)]
    wider, _ = tree(calls=CALLS + more, rows=ROWS + [{"file": "src/use.ts", "line": 20 + i, "method": "m", "declared": ["src/x:Thing.m"]}
                                                       for i in range(5)], name="wider")
    assert M.gated(M.measure(runs, rows)) == M.gated(M.measure(wider, rows))


def test_the_numbers_with_no_bound(tree):
    runs, rows = tree()
    got = {n: (round(m.value, 1), m.hit, m.of) for n, m in M.numbers(M.measure(runs, rows)).items()}
    assert got["r.typed-share"] == (80.0, 8, 10)                 # eight of the ten calls are typed, the Python one too
    assert got["r.by-name-contradicted"] == (50.0, 1, 2)         # of the two by-name edges the checker decides, one is another declaration
    # the checker names a declaration at seven sites (lines 3, 4, 5, 6, 7, 9, 10); an edge is confirmed at four (3, 5, 7, 9), a typed one at three
    assert got["r.recall"] == (57.1, 4, 7) and got["r.typed-recall"] == (42.9, 3, 7)
    assert got["r.receiver-type.indirect"] == (1, 1, 0) and got["r.receiver-type.undecided"] == (2, 2, 0)
    assert got["r.inherited.indirect"] == (0, 0, 0)


def test_keyed_is_the_share_of_the_ts_calls_in_a_file_with_rows(tree):
    runs, rows = tree()
    assert M.keyed_of(M.measure(runs, rows)) == {"r": 100.0}
    runs, rows = tree(rows=[{**r, "file": "packages/" + r["file"]} for r in ROWS])
    assert M.keyed_of(M.measure(runs, rows)) == {"r": 0.0}


# -- the wins lost ----------------------------------------------------------------------------------------------------------

def lost(tree, head_calls):
    base, rows = tree(name="base")
    head, _ = tree(calls=head_calls, name="head")
    return M.lost_wins(M.measure(base, rows), M.measure(head, rows))


def test_a_tree_that_keeps_every_confirmed_site_loses_no_win(tree):
    assert lost(tree, CALLS) == {}


def test_a_confirmed_typed_edge_that_goes_leaves_its_site_lost(tree):
    sites = lost(tree, [c for c in CALLS if c["line"] != 3])["r"]
    assert [(line, method) for _, line, method in sites] == [(3, "run")]


def test_a_confirmed_edge_replaced_by_a_contradicted_one_is_a_win_lost(tree):
    sites = lost(tree, [call(MAIN, BAR, 3, "receiver-type", "run") if c["line"] == 3 else c for c in CALLS])["r"]
    assert [line for _, line, _ in sites] == [3]


def test_a_confirmed_edge_replaced_by_another_confirmed_one_at_the_site_is_no_win_lost(tree):
    swapped = [call(MAIN, OWNER, 3, "inherited", "run") if c["line"] == 3 else c for c in CALLS]  # the owner of Foo.run, confirmed
    assert lost(tree, swapped) == {}


def test_a_win_gained_elsewhere_does_not_pay_for_one_lost(tree):
    head = [c for c in CALLS if c["line"] != 3] + [call(MAIN, FOO, 30, "receiver-type", "run")]
    rows = ROWS + [{"file": "src/use.ts", "line": 30, "method": "run", "declared": ["src/a:Foo.run"]}]
    base, _ = tree(name="base")
    head_dir, rows_dir = tree(calls=head, rows=rows, name="head")
    got = M.lost_wins(M.measure(base, rows_dir), M.measure(head_dir, rows_dir))
    assert [line for _, line, _ in got["r"]] == [3]
