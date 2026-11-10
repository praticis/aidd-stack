"""How the scorecard (scripts/judgment/scorecard.py) judges the counts: the bounds' list, the statuses, the report and the
command's exit codes."""
import importlib.util
from pathlib import Path

import pytest

from scorecard_cases import BOUNDS, CALLS, FOO, IMPL, MAIN, OWNER, ROWS, THING, call, make_tree

spec = importlib.util.spec_from_file_location(
    "scorecard", Path(__file__).resolve().parent.parent / "scripts" / "judgment" / "scorecard.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
M = S.M


@pytest.fixture
def tree(tmp_path):
    return make_tree(tmp_path)


# -- the bounds -------------------------------------------------------------------------------------------------------------

def statuses(repos, bounds=BOUNDS, min_keyed=50.0):
    rows = S.judge(M.gated(repos), S.load_floors(bounds), M.keyed_of(repos), min_keyed)
    return {row.name: row.status for row in rows}


def test_every_count_at_its_bound_passes(tree):
    runs, rows = tree()
    assert set(statuses(M.measure(runs, rows)).values()) == {"ok"}


def test_a_floor_one_above_the_count_is_below_and_a_ceiling_one_under_it_is_above(tree):
    runs, rows = tree()
    repos = M.measure(runs, rows)
    assert statuses(repos, BOUNDS.replace(">= 2", ">= 3"))["r.receiver-type.confirmed"] == "below"
    assert statuses(repos, BOUNDS.replace("<= 1", "<= 0"))["r.receiver-type.contradicted"] == "above"


def test_a_count_with_room_to_spare_passes(tree):
    runs, rows = tree()
    assert set(statuses(M.measure(runs, rows), BOUNDS.replace(">= 2", ">= 1").replace("<= 1", "<= 4")).values()) == {"ok"}


def test_a_count_without_a_bound_and_a_bound_without_a_count_both_fail(tree):
    runs, rows = tree()
    got = statuses(M.measure(runs, rows), BOUNDS.replace("r.inherited.confirmed", "r.other.confirmed"))
    assert got["r.inherited.confirmed"] == "unbound" and got["r.other.confirmed"] == "not measured"


def test_when_the_keys_do_not_match_every_count_of_the_repo_is_invalid(tree):
    runs, rows = tree(rows=[{**r, "file": "packages/" + r["file"]} for r in ROWS])
    assert set(statuses(M.measure(runs, rows)).values()) == {"invalid"}


def test_the_threshold_given_is_the_one_that_judges_the_keys(tree):
    calls = [call(MAIN, FOO, 3, "receiver-type", "run"), call(MAIN, FOO, 4, "receiver-type", "run"),
             *[call(IMPL, FOO, 10 + i, "receiver-type", "run") for i in range(3)]]  # two of five calls are in a file with rows: 40 %
    runs, rows = tree(calls=calls, rows=ROWS[:1])
    repos = M.measure(runs, rows)
    assert set(statuses(repos, "r.receiver-type.confirmed :: >= 0 :: n\nr.receiver-type.contradicted :: <= 9 :: n").values()) == {"invalid"}
    assert set(statuses(repos, "r.receiver-type.confirmed :: >= 0 :: n\nr.receiver-type.contradicted :: <= 9 :: n", 30).values()) == {"ok"}


@pytest.mark.parametrize("text", [
    "r.receiver-type.confirmed >= 2 :: a note", "r.receiver-type.confirmed :: >= 2", "R.receiver-type.confirmed :: >= 2 :: n",
    "r.confirmed :: >= 2 :: n", "r.receiver-type.recall :: >= 2 :: n", "r.receiver-type.confirmed :: 2 :: n",
    "r.receiver-type.confirmed :: <= 2 :: n", "r.receiver-type.contradicted :: >= 2 :: n", "r.receiver-type.confirmed :: >= 2.5 :: n",
    "r.receiver-type.confirmed :: >= -1 :: n", "r.receiver-type.confirmed :: >= two :: n", "r.receiver-type.confirmed :: >= 2 ::  ",
    "r.receiver-type.confirmed :: >= 2 :: n\nr.receiver-type.confirmed :: >= 3 :: n"])
def test_a_wrong_list_of_bounds_is_an_error_with_its_line(text):
    with pytest.raises(ValueError, match="line"):
        S.load_floors(text)


def test_a_comment_and_a_blank_line_are_no_bound():
    assert [b.name for b in S.load_floors("# a\n\nr.receiver-type.confirmed :: >= 2 :: a note\n   # b\n")] == ["r.receiver-type.confirmed"]


def test_a_note_may_hold_the_separator():
    assert S.load_floors("r.receiver-type.confirmed :: >= 2 :: a :: b")[0].note == "a :: b"


def test_a_ceiling_of_zero_is_a_bound():
    assert S.load_floors("r.inherited.contradicted :: <= 0 :: n")[0].limit == 0


# -- the report -------------------------------------------------------------------------------------------------------------

def reported(repos, bounds=BOUNDS, base=None, lost_sites=None):
    rows = S.judge(M.gated(repos), S.load_floors(bounds), M.keyed_of(repos), 50.0)
    return S.report(rows, M.numbers(repos), M.numbers(base) if base else None, lost_sites or {}, M.keyed_of(repos))


def test_the_report_says_each_count_its_bound_and_its_room(tree):
    runs, rows = tree()
    text = reported(M.measure(runs, rows), BOUNDS.replace(">= 2", ">= 1").replace("<= 1", "<= 4"))
    assert "| `r.receiver-type.confirmed` | 2 | >= 1 | +1 | ok |" in text
    assert "| `r.receiver-type.contradicted` | 1 | <= 4 | +3 | ok |" in text
    assert "not ok" not in text and "The checker has rows for 100.0 % of r's TS calls." in text


def test_the_report_of_a_count_past_its_bound_says_how_a_bound_is_changed(tree):
    runs, rows = tree()
    text = reported(M.measure(runs, rows), BOUNDS.replace(">= 2", ">= 3"))
    assert "| `r.receiver-type.confirmed` | 2 | >= 3 | -1 | below |" in text
    assert "1 count(s) not ok" in text and "`graph-change`" in text and "reference_floors.txt" in text


def test_without_a_base_the_numbers_have_a_value_and_no_wins_section(tree):
    runs, rows = tree()
    text = reported(M.measure(runs, rows))
    assert "| Number | Value |" in text and "Wins lost" not in text
    assert "| `r.by-name-contradicted` | 50.00 % (1 of 2) |" in text


def test_with_a_base_the_numbers_have_the_base_the_tree_and_the_change(tree):
    base_dir, rows = tree(name="base")
    head_dir, _ = tree(calls=CALLS[:-1] + [call(MAIN, THING, 20, "unique-name", "m")], name="head",
                       rows=ROWS + [{"file": "src/use.ts", "line": 20, "method": "m", "declared": ["src/x:Thing.m"]}])
    text = reported(M.measure(head_dir, rows), base=M.measure(base_dir, rows))
    assert "| `r.typed-share` | 80.00 % (8 of 10) | 70.00 % (7 of 10) | -10.00 |" in text
    assert "| `r.receiver-type.indirect` | 1 | 1 | +0 |" in text
    assert "None: every site the base confirms, the tree confirms." in text


def test_the_report_lists_the_sites_of_the_wins_lost_up_to_a_limit(tree):
    runs, rows = tree()
    sites = [("src/use", n, "run") for n in range(1, 60)]
    text = reported(M.measure(runs, rows), base=M.measure(runs, rows), lost_sites={"r": sites})
    assert "r: 59 site(s) where the base has a confirmed typed edge and the tree has none (the first 50):" in text
    assert "- `src/use:3` `run`" in text and "src/use:51" not in text


# -- the command ------------------------------------------------------------------------------------------------------------

@pytest.fixture
def floors(tmp_path):
    path = tmp_path / "floors.txt"
    path.write_text(BOUNDS)
    return path


def test_main_ends_in_0_when_every_count_holds_and_in_1_when_one_does_not(tree, floors, capsys):
    runs, rows = tree()
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors)]) == 0
    floors.write_text(BOUNDS.replace(">= 2", ">= 3"))
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors)]) == 1
    assert "below" in capsys.readouterr().out


def test_main_ends_in_3_when_only_wins_are_lost_and_in_1_when_a_count_is_past_its_bound_as_well(tree, floors):
    base, rows = tree(name="base")
    head, _ = tree(calls=[call(MAIN, OWNER, 3, "inherited", "run") if c["line"] == 3 else c for c in CALLS if c["line"] != 4], name="head")
    floors.write_text(BOUNDS.replace(">= 2", ">= 1").replace("<= 0", "<= 9"))
    assert S.main([str(head), "--base", str(head), "--rows", str(rows), "--floors", str(floors)]) == 0
    lost_head, _ = tree(calls=[c for c in CALLS if c["line"] != 3], name="lost")
    assert S.main([str(lost_head), "--base", str(base), "--rows", str(rows), "--floors", str(floors)]) == 3
    floors.write_text(BOUNDS.replace(">= 2", ">= 9"))
    assert S.main([str(lost_head), "--base", str(base), "--rows", str(rows), "--floors", str(floors)]) == 1


def test_main_ends_in_2_for_a_wrong_list_a_missing_folder_or_an_unknown_option(tree, tmp_path, capsys):
    runs, rows = tree()
    bad = tmp_path / "bad.txt"
    bad.write_text("r.recall 50\n")
    assert S.main([str(runs), "--floors", str(bad)]) == 2
    assert S.main([str(runs), "--floors", str(tmp_path / "missing.txt")]) == 2
    assert S.main([str(runs), "--nope"]) == 2
    assert "scorecard.py RUN_DIR" in capsys.readouterr().err


def test_the_threshold_of_the_keys_is_an_option(tree, floors):
    runs, rows = tree(rows=[ROWS[0]])  # the row of one site: all the TS calls are in its file, so the keys match
    floors.write_text("\n".join(f"r.{n} :: {op} {v} :: n" for n, op, v in (
        ("receiver-type.confirmed", ">=", 0), ("receiver-type.contradicted", "<=", 9), ("inherited.confirmed", ">=", 0),
        ("inherited.contradicted", "<=", 9))))
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors), "--min-keyed", "100"]) == 0
    other = tree(rows=[{**ROWS[0], "file": "x/use.ts"}])[1]
    assert S.main([str(runs), "--rows", str(other), "--floors", str(floors), "--min-keyed", "1"]) == 1


def test_write_floors_prints_a_line_per_count_and_ends_in_0(tree, capsys):
    runs, rows = tree()
    assert S.main([str(runs), "--rows", str(rows), "--write-floors"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "r.receiver-type.confirmed :: >= 2 :: measured on the base" in lines
    assert "r.inherited.contradicted :: <= 0 :: measured on the base" in lines and len(lines) == 4
    assert len(S.load_floors("\n".join(lines))) == 4  # what it prints is a list it reads back


def test_the_real_list_of_bounds_loads_and_names_a_strategy_of_a_repo_each():
    bounds = S.load_floors((Path(__file__).resolve().parent.parent / "scripts" / "checks" / "reference_floors.txt").read_text())
    assert bounds and all(b.note and b.name.split(".")[1] in ("receiver-type", "inherited") for b in bounds)
    assert {b.op for b in bounds} == {">=", "<="}


def test_main_judges_the_keys_by_the_threshold_it_is_given(tree, floors):
    calls = [call(MAIN, FOO, 3, "receiver-type", "run"), call(MAIN, FOO, 4, "receiver-type", "run"),
             *[call(IMPL, FOO, 10 + i, "receiver-type", "run") for i in range(3)]]  # two of five calls are in a file with rows: 40 %
    runs, rows = tree(calls=calls, rows=ROWS[:1])
    floors.write_text("r.receiver-type.confirmed :: >= 0 :: n\nr.receiver-type.contradicted :: <= 9 :: n")
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors)]) == 1                       # under the default 50
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors), "--min-keyed", "30"]) == 0


# -- the bounds a change lowers ---------------------------------------------------------------------------------------------

def test_a_floor_that_falls_a_ceiling_that_rises_and_a_line_that_goes_are_lowered():
    head = BOUNDS.replace(">= 2", ">= 1").replace("<= 1", "<= 2").replace("r.inherited.confirmed :: >= 1 :: a note\n", "")
    assert S.lowered(S.load_floors(BOUNDS), S.load_floors(head)) == [
        "r.receiver-type.confirmed: >= 2, now >= 1", "r.receiver-type.contradicted: <= 1, now <= 2", "r.inherited.confirmed: >= 1, deleted"]


def test_a_floor_that_rises_a_ceiling_that_falls_a_new_line_and_an_equal_list_lower_nothing():
    head = BOUNDS.replace(">= 2", ">= 3").replace("<= 1", "<= 0") + "r.other.confirmed :: >= 5 :: a note\n"
    assert S.lowered(S.load_floors(BOUNDS), S.load_floors(head)) == []
    assert S.lowered(S.load_floors(BOUNDS), S.load_floors(BOUNDS)) == []


def test_every_bound_of_the_base_deleted_is_every_bound_lowered():
    assert len(S.lowered(S.load_floors(BOUNDS), [])) == 4


def test_main_prints_the_lowered_bounds_one_per_line_and_ends_in_0(tmp_path, capsys):
    base, head = tmp_path / "base.txt", tmp_path / "head.txt"
    base.write_text(BOUNDS)
    head.write_text(BOUNDS.replace(">= 2", ">= 1"))
    assert S.main(["--lowered", str(base), str(head)]) == 0
    assert capsys.readouterr().out == "r.receiver-type.confirmed: >= 2, now >= 1\n"


def test_lowered_ends_in_2_for_a_wrong_list_a_missing_file_or_the_wrong_number_of_files(tmp_path, capsys):
    base, bad = tmp_path / "base.txt", tmp_path / "bad.txt"
    base.write_text(BOUNDS)
    bad.write_text("r.recall 50\n")
    assert S.main(["--lowered", str(base), str(bad)]) == 2
    assert S.main(["--lowered", str(base), str(tmp_path / "missing.txt")]) == 2
    assert S.main(["--lowered", str(base)]) == 2
    assert "scorecard.py:" in capsys.readouterr().err
