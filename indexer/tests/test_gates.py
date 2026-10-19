"""The method's gates (scripts/gates.py) over synthetic corpus runs: each gate fails on its case and only on it, and the
hold-out's items are never shown. No network, no tree-sitter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gates as G  # noqa: E402


def ep(method, path, line):
    return {"method": method, "path": path, "evidence": f"r:api/routes.go:{line}", "handler_id": f"h{line}"}


RUN = {"repo": "org/r", "sha": "abc", "endpoints": [ep("GET", "/items", 1), ep("POST", "/items", 2)], "calls": []}
LIST = {"sha": "abc", "endpoints": [{"method": "GET", "path": "/items"}, {"method": "POST", "path": "/items"},
                                    {"method": "DELETE", "path": "/items/{id}"}]}


def run(eps):
    return {**RUN, "endpoints": eps}


def check(tmp_path, base, head, labels=(), hold_base=None, hold_head=None, gab=LIST):
    (tmp_path / "r.json").write_text(json.dumps(gab))
    f = G.Findings()
    G.compare_corpus({"r": base} if base else {}, {"r": head} if head else {}, tmp_path, f)
    changed = G.holdout_changed(hold_base or {}, hold_head or {})
    G.judge_holdout(changed, set(labels), f)
    if "refactor" in labels and (f.differ or changed):
        f.failed["A refactor changes nothing"].append("differs")
    return f, G.render(f, set(labels), 100)


def failing(f):
    return {g for g, xs in f.failed.items() if xs}


def test_identical_runs_pass(tmp_path):
    f, out = check(tmp_path, RUN, RUN, labels=["refactor"])
    assert not failing(f) and "**0 repo(s) differ**" in out


def test_an_expected_pair_found_is_a_gain(tmp_path):
    f, out = check(tmp_path, RUN, run(RUN["endpoints"] + [ep("DELETE", "/items/{itemId}", 3)]))
    assert not failing(f) and len(f.gains) == 1 and "#L3" in f.gains[0]


def test_a_new_item_outside_the_list_lowers_precision(tmp_path):
    f, _ = check(tmp_path, RUN, run(RUN["endpoints"] + [ep("GET", "/debug", 4)]))
    assert failing(f) == {"Precision ratchet"}
    assert f.to_judge == [f.to_judge[0]] and f.to_judge[0].startswith("new, outside the list")


def test_an_expected_pair_missed_is_a_win_lost(tmp_path):
    f, _ = check(tmp_path, RUN, run(RUN["endpoints"][:1]))
    assert failing(f) == {"No win lost"}


def test_a_handler_change_is_to_judge(tmp_path):
    f, _ = check(tmp_path, RUN, run([ep("GET", "/items", 1), {**ep("POST", "/items", 2), "handler_id": None}]))
    assert not failing(f) and f.to_judge[0].startswith("handler_id changed")


def test_a_checked_item_judged_right_that_goes_is_a_win_lost(tmp_path):
    gab = {**LIST, "checked": {"endpoints": [{**ep("POST", "/items", 2), "ok": True}]}}
    del gab["endpoints"]
    f, _ = check(tmp_path, RUN, run(RUN["endpoints"][:1]), gab=gab)
    assert failing(f) == {"No win lost"}


def test_a_repo_without_a_branch_run_fails(tmp_path):
    f, _ = check(tmp_path, RUN, None)
    assert failing(f) == {"Every repo measured"}


def test_any_difference_fails_a_refactor(tmp_path):
    f, _ = check(tmp_path, RUN, run(RUN["endpoints"] + [ep("DELETE", "/items/{id}", 3)]), labels=["refactor"])
    assert failing(f) == {"A refactor changes nothing"}


def test_the_holdout_changes_only_under_its_label_and_is_never_listed(tmp_path):
    hb, hh = {"h": RUN}, {"h": run(RUN["endpoints"][:1])}
    f, out = check(tmp_path, RUN, RUN, hold_base=hb, hold_head=hh)
    assert failing(f) == {"Hold-out untouched"} and "/items" not in out
    f, out = check(tmp_path, RUN, RUN, labels=["holdout-measurement"], hold_base=hb, hold_head=hh)
    assert not failing(f) and "/items" not in out
