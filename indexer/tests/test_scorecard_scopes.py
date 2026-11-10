"""The scorecard's counts for a Python repo (scripts/judgment/scorecard_measure.scopes): the files whose scopes the index classifies
as CPython's symbol table does, and the files where one differs, read from what `checks/python_scopes.py --json` writes, bounded
and judged as the counts of the typed edges are."""
import importlib.util
import json
from pathlib import Path

import pytest

from scorecard_cases import make_tree

spec = importlib.util.spec_from_file_location(
    "scorecard", Path(__file__).resolve().parent.parent / "scripts" / "judgment" / "scorecard.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
M = S.M

COUNTS = {"app": {"files": 12, "files compared": 10, "files differing": 1}, "lib": {"files compared": 4, "files differing": 0}}
BOUNDS = """app.scopes.confirmed :: >= 9 :: a note
app.scopes.contradicted :: <= 1 :: a note
lib.scopes.confirmed :: >= 4 :: a note
lib.scopes.contradicted :: <= 0 :: a note
"""


@pytest.fixture
def world(tmp_path):
    runs, _ = make_tree(tmp_path)(rows=None)

    def write(counts=COUNTS, bounds=BOUNDS):
        (tmp_path / "scopes.json").write_text(json.dumps(counts))
        (tmp_path / "floors.txt").write_text(bounds)
        return ["--scopes", str(tmp_path / "scopes.json"), "--floors", str(tmp_path / "floors.txt")]

    return runs, tmp_path, write


def test_a_files_that_agree_are_the_compared_ones_less_the_ones_that_differ_and_the_others_are_the_ceiling(world):
    _, tmp_path, write = world
    write()
    assert M.scopes(tmp_path / "scopes.json") == {
        "app.scopes.confirmed": 9, "app.scopes.contradicted": 1, "lib.scopes.confirmed": 4, "lib.scopes.contradicted": 0}


def test_a_repo_with_no_file_compared_has_counts_of_zero(world):
    _, tmp_path, write = world
    write({"empty": {"files": 3, "files CPython 3.12 does not compile": 3}})
    assert M.scopes(tmp_path / "scopes.json") == {"empty.scopes.confirmed": 0, "empty.scopes.contradicted": 0}


@pytest.mark.parametrize("text", ["not json", "[1, 2]", '{"a": [1]}', '{"a": {"files compared": "ten"}}'])
def test_a_file_that_is_not_the_counts_of_the_check_is_a_wrong_input(world, text):
    _, tmp_path, _ = world
    (tmp_path / "scopes.json").write_text(text)
    with pytest.raises(ValueError):
        M.scopes(tmp_path / "scopes.json")


def test_the_counts_of_a_python_repo_are_judged_against_its_bounds(world, capsys):
    runs, _, write = world
    assert S.main([str(runs), *write()]) == 0
    out = capsys.readouterr().out
    assert "| `app.scopes.confirmed` | 9 | >= 9 | +0 | ok |" in out and "| `app.scopes.contradicted` | 1 | <= 1 | +0 | ok |" in out


def test_a_file_that_comes_to_differ_is_a_count_past_both_bounds(world, capsys):
    runs, _, write = world
    worse = {**COUNTS, "lib": {"files compared": 4, "files differing": 1}}
    assert S.main([str(runs), *write(worse)]) == 1
    out = capsys.readouterr().out
    assert "| `lib.scopes.confirmed` | 3 | >= 4 | -1 | below |" in out and "| `lib.scopes.contradicted` | 1 | <= 0 | -1 | above |" in out


def test_a_python_repo_with_no_bound_is_unbound_and_a_bound_with_no_count_is_not_measured(world, capsys):
    runs, tmp_path, write = world
    assert S.main([str(runs), *write(bounds="")]) == 1
    assert "| `app.scopes.confirmed` | 9 |  |  | unbound |" in capsys.readouterr().out
    write()
    assert S.main([str(runs), "--floors", str(tmp_path / "floors.txt")]) == 1  # no --scopes: nothing measured the Python repos
    assert "| `app.scopes.confirmed` |  | >= 9 |  | not measured |" in capsys.readouterr().out


def test_a_scopes_file_that_is_wrong_or_missing_ends_in_2(world, tmp_path):
    runs, tmp, write = world
    args = write()
    (tmp / "scopes.json").write_text("not json")
    assert S.main([str(runs), *args]) == 2
    (tmp / "scopes.json").unlink()
    assert S.main([str(runs), *args]) == 2


def test_write_floors_prints_a_line_for_each_scope_count(world, capsys):
    runs, _, write = world
    assert S.main([str(runs), *write(), "--write-floors"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "app.scopes.confirmed :: >= 9 :: measured on the base", "app.scopes.contradicted :: <= 1 :: measured on the base",
        "lib.scopes.confirmed :: >= 4 :: measured on the base", "lib.scopes.contradicted :: <= 0 :: measured on the base"]


def test_a_scope_bound_that_is_lowered_or_gone_is_listed_with_the_others():
    base = S.load_floors(BOUNDS)
    now = S.load_floors(BOUNDS.replace("app.scopes.contradicted :: <= 1", "app.scopes.contradicted :: <= 2").replace(
        "lib.scopes.confirmed :: >= 4 :: a note\n", ""))
    assert S.lowered(base, now) == ["app.scopes.contradicted: <= 1, now <= 2", "lib.scopes.confirmed: >= 4, deleted"]


def test_the_real_list_of_bounds_loads_and_bounds_each_python_repo_of_the_micro_set():
    text = (Path(__file__).resolve().parent.parent / "scripts" / "checks" / "reference_floors.txt").read_text()
    names = {b.name for b in S.load_floors(text)}
    for repo in ("dispatch", "netbox"):
        assert {f"{repo}.scopes.confirmed", f"{repo}.scopes.contradicted"} <= names
