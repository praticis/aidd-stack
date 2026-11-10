"""The bot of the floors (scripts/floors_bot.py): a bound moves only toward what the graph holds on main, a bound main does not hold
or a count with no bound is an alarm and never a change, and a pull request that only changes the bounds may only raise them."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scorecard_cases import make_tree

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
spec = importlib.util.spec_from_file_location("floors_bot", SCRIPTS / "floors_bot.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
S = F.S

FLOORS = """# the bounds
a.receiver-type.confirmed :: >= 100 :: measured on main at 1111111
a.receiver-type.contradicted :: <= 5 :: measured on main at 1111111

b.scopes.confirmed :: >= 10 :: measured on main at 1111111
b.scopes.contradicted :: <= 0 :: measured on main at 1111111
"""


HELD = {"a.receiver-type.confirmed": 100, "a.receiver-type.contradicted": 5, "b.scopes.confirmed": 10, "b.scopes.contradicted": 0}


def test_a_floor_goes_up_to_the_count_held_and_a_ceiling_goes_down_to_it():
    text, moved = F.raised(FLOORS, {**HELD, "a.receiver-type.confirmed": 130, "a.receiver-type.contradicted": 2})
    assert moved == ["a.receiver-type.confirmed: >= 100, now >= 130", "a.receiver-type.contradicted: <= 5, now <= 2"]
    assert "a.receiver-type.confirmed :: >= 130 :: measured on main at 1111111" in text and "a.receiver-type.contradicted :: <= 2 ::" in text


def test_a_bound_the_count_only_meets_stays_as_it_is_and_the_text_does_not_change():
    text, moved = F.raised(FLOORS, HELD)
    assert moved == [] and text == FLOORS


def test_the_comments_the_blank_lines_and_the_order_are_kept():
    text, _ = F.raised(FLOORS, {**HELD, "b.scopes.confirmed": 11})
    assert text.splitlines()[0] == "# the bounds" and text.splitlines()[3] == "" and text.splitlines()[4].startswith("b.scopes.confirmed :: >= 11")
    assert [b.name for b in S.load_floors(text)] == [b.name for b in S.load_floors(FLOORS)]


def test_the_note_is_replaced_only_on_a_bound_that_moves():
    text, _ = F.raised(FLOORS, {**HELD, "b.scopes.confirmed": 11}, "measured on main at 2222222")
    assert "b.scopes.confirmed :: >= 11 :: measured on main at 2222222" in text
    assert "b.scopes.contradicted :: <= 0 :: measured on main at 1111111" in text


def test_a_floor_never_goes_down_and_a_ceiling_never_goes_up():
    text, moved = F.raised(FLOORS, {**HELD, "a.receiver-type.confirmed": 90, "a.receiver-type.contradicted": 9})
    assert moved == [] and text == FLOORS


def test_raising_twice_is_raising_once():
    once, _ = F.raised(FLOORS, {**HELD, "a.receiver-type.confirmed": 130})
    twice, moved = F.raised(once, {**HELD, "a.receiver-type.confirmed": 130})
    assert twice == once and moved == []


def test_a_bound_main_does_not_hold_a_count_not_measured_and_a_count_with_no_bound_are_alarms():
    bounds = S.load_floors(FLOORS)
    got = F.alarms(bounds, {"a.receiver-type.confirmed": 99, "a.receiver-type.contradicted": 6, "b.scopes.confirmed": 10, "c.scopes.confirmed": 3})
    assert got == ["a.receiver-type.confirmed: >= 100, measured 99", "a.receiver-type.contradicted: <= 5, measured 6",
                   "b.scopes.contradicted: <= 0, not measured", "c.scopes.confirmed: measured 3, no bound"]
    assert F.alarms(bounds, HELD) == []


def test_a_bound_held_exactly_is_no_alarm():
    assert F.alarms(S.load_floors(FLOORS), HELD) == []


def test_the_measured_counts_are_read_from_the_lines_the_scorecard_prints():
    assert F.counts_of("a.receiver-type.confirmed :: >= 130 :: measured on the base\nb.scopes.contradicted :: <= 0 :: measured on the base\n") == {
        "a.receiver-type.confirmed": 130, "b.scopes.contradicted": 0}


def test_the_counts_the_scorecard_writes_are_the_ones_the_bot_reads_even_when_a_bound_is_broken(tmp_path):
    runs, rows = make_tree(tmp_path)()
    measured, floors = tmp_path / "measured.txt", tmp_path / "floors.txt"
    floors.write_text("r.receiver-type.confirmed :: >= 99 :: n\n")
    assert S.main([str(runs), "--rows", str(rows), "--floors", str(floors), "--measured", str(measured)]) == 1  # the other counts have no bound
    assert F.counts_of(measured.read_text()) == {
        "r.receiver-type.confirmed": 2, "r.receiver-type.contradicted": 1, "r.inherited.confirmed": 1, "r.inherited.contradicted": 0}
    assert F.alarms(S.load_floors(floors.read_text()), F.counts_of(measured.read_text()))[0] == "r.receiver-type.confirmed: >= 99, measured 2"


# -- a pull request that only changes the bounds ---------------------------------------------------------------------------

def only(base, head):
    return F.only_raises(S.load_floors(base), S.load_floors(head))


def test_a_raise_is_all_a_pull_request_of_the_bounds_may_do():
    assert only(FLOORS, FLOORS.replace(">= 100", ">= 130").replace("<= 5", "<= 2").replace("1111111", "2222222")) == []


@pytest.mark.parametrize("head,what", [
    (FLOORS.replace(">= 100", ">= 99"), "a.receiver-type.confirmed: >= 100, now >= 99"),
    (FLOORS.replace("<= 5", "<= 6"), "a.receiver-type.contradicted: <= 5, now <= 6"),
    (FLOORS.replace("b.scopes.contradicted :: <= 0 :: measured on main at 1111111\n", ""), "b.scopes.contradicted: <= 0, deleted"),
    (FLOORS + "c.scopes.confirmed :: >= 1 :: n\n", "c.scopes.confirmed: >= 1, added")])
def test_a_bound_lowered_deleted_or_added_is_what_a_raise_is_not(head, what):
    assert only(FLOORS, head) == [what]


# -- the body of the pull request ------------------------------------------------------------------------------------------

def test_the_body_names_each_bound_moved_with_what_it_was_and_what_it_is_and_follows_the_template():
    after = FLOORS.replace(">= 100", ">= 1,300".replace(",", "")).replace("<= 5", "<= 2")
    text = F.body(S.load_floors(FLOORS), S.load_floors(after), "abcdef0123456789")
    assert "| `a.receiver-type.confirmed` | >= 100 | >= 1,300 |" in text and "| `a.receiver-type.contradicted` | <= 5 | <= 2 |" in text
    assert "b.scopes" not in text and "beats 2 bound(s)" in text and "on main at abcdef0" in text
    lines = text.splitlines()
    assert [l.split(":")[0] for l in lines[:5]] == ["Kind", "Records", "Labels", "Gates", "Author decides"]
    assert [l for l in lines if l.startswith("## ")] == ["## What and why", "## Contracts, boundaries and proof", "## Measures", "## Left out on purpose"]
    assert lines[-1].startswith("Live validation:")


def test_the_body_without_a_commit_says_main_only_and_carries_no_line_the_project_refuses(tmp_path):
    text = F.body(S.load_floors(FLOORS), S.load_floors(FLOORS.replace(">= 10 ", ">= 12 ")), None)
    assert "on main" in text and "at " not in text.splitlines()[1]
    (tmp_path / "body").write_text(text)
    (tmp_path / "title").write_text("chore(scripts): raise the floors the graph holds")
    (tmp_path / "commits.json").write_text(json.dumps([{"sha": "0123456789abcdef", "commit": {"message": "chore(scripts): raise the floors the graph holds"}}]))
    done = subprocess.run([sys.executable, "-I", str(SCRIPTS / "checks" / "pr_text.py"), "--title-file", str(tmp_path / "title"),
                           "--body-file", str(tmp_path / "body"), "--commits-json", str(tmp_path / "commits.json")], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout


# -- the command ---------------------------------------------------------------------------------------------------------------

@pytest.fixture
def files(tmp_path):
    (tmp_path / "floors.txt").write_text(FLOORS)

    def write(**more):
        measured = {**HELD, **more}
        (tmp_path / "measured.txt").write_text("".join(f"{n} :: {'>=' if n.endswith('confirmed') else '<='} {v} :: measured on the base\n" for n, v in measured.items()))
        return tmp_path / "floors.txt", tmp_path / "measured.txt"
    return tmp_path, write


def test_raise_prints_the_bounds_it_moves_and_writes_them_only_with_write(files, capsys):
    tmp_path, write = files
    floors, measured = write(**{"a.receiver-type.confirmed": 130})
    assert F.main(["raise", str(floors), str(measured)]) == 0
    assert capsys.readouterr().out.splitlines() == ["a.receiver-type.confirmed: >= 100, now >= 130"] and floors.read_text() == FLOORS
    assert F.main(["raise", str(floors), str(measured), "--write", "--note", "measured on main at 2222222"]) == 0
    assert "a.receiver-type.confirmed :: >= 130 :: measured on main at 2222222" in floors.read_text()
    assert F.main(["raise", str(floors), str(measured), "--write"]) == 0 and capsys.readouterr().out.count("now") == 1  # the second run moves nothing


def test_raise_prints_nothing_when_there_is_nothing_to_raise(files, capsys):
    _, write = files
    floors, measured = write()
    assert F.main(["raise", str(floors), str(measured), "--write"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "" and floors.read_text() == FLOORS


def test_raise_ends_in_1_on_an_alarm_after_moving_what_it_could(files, capsys):
    _, write = files
    floors, measured = write(**{"a.receiver-type.confirmed": 90, "b.scopes.confirmed": 12})
    assert F.main(["raise", str(floors), str(measured), "--write"]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["b.scopes.confirmed: >= 10, now >= 12"]
    assert captured.err.splitlines() == ["a.receiver-type.confirmed: >= 100, measured 90"]
    assert "b.scopes.confirmed :: >= 12" in floors.read_text()


def test_only_raises_ends_in_1_with_what_is_not_a_raise(files, capsys):
    tmp_path, _ = files
    head = tmp_path / "head.txt"
    head.write_text(FLOORS.replace(">= 100", ">= 120"))
    assert F.main(["only-raises", str(tmp_path / "floors.txt"), str(head)]) == 0 and capsys.readouterr().out == ""
    head.write_text(FLOORS.replace(">= 100", ">= 50"))
    assert F.main(["only-raises", str(tmp_path / "floors.txt"), str(head)]) == 1
    assert capsys.readouterr().out.splitlines() == ["a.receiver-type.confirmed: >= 100, now >= 50"]


def test_body_prints_the_body(files, capsys):
    tmp_path, _ = files
    after = tmp_path / "after.txt"
    after.write_text(FLOORS.replace(">= 100", ">= 120"))
    assert F.main(["body", str(tmp_path / "floors.txt"), str(after), "--sha", "0123456789"]) == 0
    assert "| `a.receiver-type.confirmed` | >= 100 | >= 120 |" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["nothing"], ["raise", "/nowhere", "/nowhere"], ["raise"], ["only-raises", "/nowhere"]])
def test_a_wrong_input_ends_in_2(argv, capsys):
    assert F.main(argv) == 2


def test_a_wrong_list_of_bounds_or_of_counts_ends_in_2(files, capsys):
    tmp_path, write = files
    floors, measured = write()
    measured.write_text("not a line\n")
    assert F.main(["raise", str(floors), str(measured)]) == 2
    floors.write_text("a.receiver-type.confirmed 100\n")
    measured.write_text("a.receiver-type.confirmed :: >= 130 :: n\n")
    assert F.main(["raise", str(floors), str(measured)]) == 2 and "floors_bot.py:" in capsys.readouterr().err
