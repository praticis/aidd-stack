"""The gate on the scorecard (scripts/reference_gate.py): its exit code and the floors a change lowers, under the labels."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("reference_gate", Path(__file__).resolve().parent.parent / "scripts" / "reference_gate.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def test_a_run_that_did_not_measure_has_nothing_to_say():
    assert G.judge(None, None, set()) == (True, "")
    assert G.judge(None, 3, {"refactor"}) == (True, "")


def test_every_number_at_its_floor_and_no_floor_lowered_passes():
    ok, line = G.judge(0, 0, set())
    assert ok and line == "pass: every number of the graph holds its floor"
    assert G.judge(0, None, set())[0]


@pytest.mark.parametrize("labels", [set(), {"graph-change"}, {"refactor"}, {"graph-change", "holdout-measurement"}])
def test_a_number_under_its_floor_fails_under_every_label(labels):
    ok, line = G.judge(1, 0, labels)
    assert not ok and line.startswith("FAIL: a number of the graph is under its floor") and "reference_floors.txt" in line


@pytest.mark.parametrize("rc", [2, 3, 75, 127])
def test_a_scorecard_that_did_not_run_fails(rc):
    ok, line = G.judge(rc, 0, {"graph-change"})
    assert not ok and line == "FAIL: the scorecard did not run (see the micro job)"


def test_a_lowered_floor_needs_the_graph_change_label():
    ok, line = G.judge(0, 2, set())
    assert not ok and "2 floor(s) lowered without the `graph-change` label" in line
    ok, line = G.judge(0, 2, {"graph-change"})
    assert ok and line == "pass: every number holds its floor, 2 floor(s) lowered under the `graph-change` label"


def test_a_refactor_lowers_no_floor_even_under_the_graph_change_label():
    ok, line = G.judge(0, 1, {"refactor", "graph-change"})
    assert not ok and "1 floor(s) lowered in a `refactor`" in line


def test_a_missing_count_of_lowered_floors_is_none_lowered():
    assert G.judge(0, None, set()) == (True, "pass: every number of the graph holds its floor")
