"""The gate on the scorecard (scripts/reference_gate.py): its exit code and the bounds a change lowers, under the labels."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("reference_gate", Path(__file__).resolve().parent.parent / "scripts" / "reference_gate.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

HOLDS = "pass: every count of the graph holds its bound and no win is lost"


def test_a_run_that_did_not_measure_has_nothing_to_say():
    assert G.judge(None, None, set()) == (True, "")
    assert G.judge(None, 3, {"refactor"}) == (True, "")


def test_every_count_within_its_bound_and_no_bound_lowered_and_no_win_lost_passes():
    assert G.judge(0, 0, set()) == (True, HOLDS)
    assert G.judge(0, None, set()) == (True, HOLDS)  # no count of lowered bounds is none lowered


@pytest.mark.parametrize("labels", [set(), {"graph-change"}, {"refactor"}, {"graph-change", "holdout-measurement"}])
def test_a_count_past_its_bound_fails_under_every_label(labels):
    ok, line = G.judge(1, 0, labels)
    assert not ok and line.startswith("FAIL: a count of the graph is past its bound") and "reference_floors.txt" in line


@pytest.mark.parametrize("rc", [2, 4, 75, 99, 127])
def test_a_scorecard_that_did_not_run_fails_under_every_label(rc):
    ok, line = G.judge(rc, 0, {"graph-change"})
    assert not ok and line == "FAIL: the scorecard did not run (see the micro job)"


def test_a_lowered_bound_needs_the_graph_change_label():
    ok, line = G.judge(0, 2, set())
    assert not ok and "2 bound(s) lowered without the `graph-change` label" in line
    assert G.judge(0, 2, {"graph-change"}) == (True, "pass: every count holds its bound; 2 bound(s) lowered, under the `graph-change` label")


def test_a_win_lost_needs_the_graph_change_label_as_a_lowered_bound_does():
    ok, line = G.judge(3, 0, set())
    assert not ok and "wins lost without the `graph-change` label" in line
    assert G.judge(3, 0, {"graph-change"}) == (True, "pass: every count holds its bound; wins lost, under the `graph-change` label")


def test_a_win_lost_and_a_lowered_bound_are_both_named():
    ok, line = G.judge(3, 1, set())
    assert not ok and "1 bound(s) lowered and wins lost without the `graph-change` label" in line


@pytest.mark.parametrize("rc,lowered", [(0, 1), (3, 0), (3, 2)])
def test_a_refactor_moves_no_bound_and_loses_no_win_even_under_the_graph_change_label(rc, lowered):
    ok, line = G.judge(rc, lowered, {"refactor", "graph-change"})
    assert not ok and "in a `refactor`, which changes nothing" in line


def test_a_refactor_that_moves_nothing_passes():
    assert G.judge(0, 0, {"refactor"}) == (True, HOLDS)
