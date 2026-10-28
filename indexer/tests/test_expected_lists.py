"""The expected-list tools (scripts/lists/): editing a list and reconciling its checked sample with a corpus run. The
guard is the byte-for-byte round trip of every real list: a tool that reorders a key or an item turns one edit into a
diff of the whole file. The rest runs over synthetic lists and runs. No Docker, no network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path[:0] = [str(SCRIPTS / "lists"), str(SCRIPTS)]
import lists_edit as E  # noqa: E402
import lists_store as S  # noqa: E402
import lists_sync as Y  # noqa: E402

REAL = Path(__file__).resolve().parent / "corpus_expected"


def item(method, path, **more):
    return {"method": method, "path": path, **more}


def checked(method, path, line, ok=None, category=None):
    return {"evidence": f"r:api.go:{line}", "method": method, "path": path, "raw": path, "ok": ok, "category": category}


def run_item(method, path, line):
    return {"method": method, "path": path, "evidence": f"r:api.go:{line}", "raw_path": path}


def listing(**more):
    return {"source": "manual", "sha": "abc", "endpoints": [item("GET", "/b"), item("GET", "/a")], **more}


@pytest.mark.parametrize("path", sorted(REAL.glob("*.json")), ids=lambda p: p.stem)
def test_a_real_list_survives_a_round_trip_byte_for_byte(path):
    assert S.dumps(json.loads(path.read_text())) == path.read_text()


def test_saving_keeps_the_order_of_keys_and_items(tmp_path):
    g = {"notes": "n", "sha": "abc", "endpoints": [item("POST", "/z"), item("GET", "/a")]}
    S.save("x", g, tmp_path)
    back = S.load("x", tmp_path)
    assert list(back) == ["notes", "sha", "endpoints"] and back["endpoints"][0]["path"] == "/z"


def test_a_list_that_is_not_there_is_an_error_that_names_it(tmp_path):
    with pytest.raises(S.ListError, match="no expected list 'ghost'"):
        S.load("ghost", tmp_path)


def test_a_new_list_from_a_spec_takes_its_routes_and_scope():
    spec = {"spec": ["openapi.json"], "endpoints": [item("GET", "/a")], "scope": ["api/"]}
    assert E.new_list("abc", spec) == {"source": "openapi", "sha": "abc", "spec": ["openapi.json"], "scope": ["api/"],
                                       "endpoints": [item("GET", "/a")]}
    assert E.new_list("abc") == {"sha": "abc", "endpoints": []}


def test_an_item_joins_a_sorted_list_in_its_place_and_an_unsorted_one_at_the_end():
    sorted_list = {"endpoints": [item("GET", "/a"), item("GET", "/c")]}
    assert E.add_item(sorted_list, "endpoints", "GET", "/b") is True
    assert [i["path"] for i in sorted_list["endpoints"]] == ["/a", "/b", "/c"]
    loose = {"endpoints": [item("GET", "/c"), item("GET", "/a")]}
    E.add_item(loose, "endpoints", "GET", "/b", "reason")
    assert loose["endpoints"][-1] == item("GET", "/b", category="reason")


def test_an_item_already_there_is_not_added_twice():
    g = {"endpoints": [item("GET", "/a")]}
    assert E.add_item(g, "endpoints", "GET", "/a") is False and len(g["endpoints"]) == 1


def test_a_category_is_set_by_path_pattern_and_method_and_cleared_with_a_dash():
    g = {"endpoints": [item("GET", "/v1/a"), item("POST", "/v1/a"), item("GET", "/v2/a")]}
    assert E.set_category(g, "endpoints", "mounted", r"^/v1/", "GET") == 1
    assert [i.get("category") for i in g["endpoints"]] == ["mounted", None, None]
    assert E.set_category(g, "endpoints", "-", r"^/v1/") == 2 and all("category" not in i for i in g["endpoints"])


def test_fields_are_set_from_json_values():
    g = {"sha": "abc"}
    E.set_fields(g, ["scope=[\"api/\"]", "notes=\"n\""])
    assert g == {"sha": "abc", "scope": ["api/"], "notes": "n"}


def test_a_category_goes_when_the_run_finds_the_item_and_stays_when_it_does_not():
    g = {"endpoints": [item("GET", "/a", category="missed"), item("GET", "/b", category="missed")]}
    found = E.found_with_category(g, {"endpoints": [run_item("GET", "/a", 1)]})
    assert [(kind, i["path"]) for kind, i in found] == [("endpoints", "/a")]


def test_pending_items_are_listed_with_their_position():
    g = {"checked": {"endpoints": [checked("GET", "/a", 1, True), checked("GET", "/b", 2)]}}
    assert [(kind, n, i["path"]) for kind, n, i in E.pending(g)] == [("endpoints", 1, "/b")]


def test_a_verdict_goes_to_the_pending_items_only_and_never_over_a_judged_one():
    g = {"checked": {"endpoints": [checked("GET", "/a", 1, True), checked("GET", "/b", 2), checked("GET", "/c", 3)]}}
    assert E.judge(g, "endpoints", "ok", {2: "wrong:prefix"}) == 2
    assert [(i["ok"], i["category"]) for i in g["checked"]["endpoints"]] == [(True, None), (True, None), (False, "prefix")]
    with pytest.raises(E.VerdictError, match="already judged"):
        E.judge(g, "endpoints", "ok", {0: "wrong"})
    with pytest.raises(E.VerdictError, match="not a verdict"):
        E.judge({"checked": {"endpoints": [checked("GET", "/a", 1)]}}, "endpoints", "maybe", {})


def sync_list():
    g = listing(checked={"endpoints": [checked("GET", "/b", 1, True), checked("GET", "/gone", 2, True),
                                       checked("GET", "/old", 3, False, "x"), checked("GET", "/two", 4, True)]})
    run = {"endpoints": [run_item("GET", "/b", 1), run_item("GET", "/a", 3), run_item("GET", "/twoA", 4),
                         run_item("GET", "/twoB", 4)]}
    return g, run


def test_a_checked_item_the_run_still_has_is_kept_untouched():
    g, run = sync_list()
    kept = dict(g["checked"]["endpoints"][0])
    Y.reconcile(g, run)
    assert g["checked"]["endpoints"][0] == kept


def test_a_checked_item_the_run_lost_at_its_evidence_is_dropped():
    g, run = sync_list()
    changes = Y.reconcile(g, run)
    assert ("endpoints", "gone", "/gone") in [(c.kind, c.status, c.old["path"]) for c in changes]
    assert all(i["path"] != "/gone" for i in g["checked"]["endpoints"])


def test_a_changed_route_replaces_the_item_and_is_right_only_if_the_list_expects_it():
    g, run = sync_list()
    changes = Y.reconcile(g, run)
    moved = [c for c in changes if c.status == "changed"]
    assert [(c.old["path"], c.new["path"], c.new["ok"], c.new["category"]) for c in moved] == [("/old", "/a", True, None)]
    g2, run2 = sync_list()
    g2["endpoints"] = [item("GET", "/b")]
    Y.reconcile(g2, run2)
    assert [i["ok"] for i in g2["checked"]["endpoints"] if i["path"] == "/a"] == [None]


def test_two_routes_at_one_evidence_leave_the_item_for_the_author():
    g, run = sync_list()
    changes = Y.reconcile(g, run)
    assert [c.status for c in changes if c.old["path"] == "/two"] == ["ambiguous"]
    assert any(i["path"] == "/two" for i in g["checked"]["endpoints"])


def test_a_resample_has_the_size_and_seed_of_the_sample_and_carries_verdicts_over():
    g = {"endpoints": [item("GET", "/a")], "checked_seed": "7",
         "checked": {"endpoints": [checked("GET", "/b", 1, False, "x"), checked("GET", "/a", 3)]}}
    run = {"endpoints": [run_item("GET", "/b", 1), run_item("GET", "/a", 3)]}
    assert Y.resample(g, run, "endpoints", "r") == []
    by_path = {i["path"]: i for i in g["checked"]["endpoints"]}
    assert (by_path["/a"]["ok"], by_path["/b"]["ok"], by_path["/b"]["category"]) == (True, False, "x")


def test_a_resample_needs_a_sample_and_a_seed():
    with pytest.raises(Y.SyncError, match="no checked"):
        Y.resample({"endpoints": []}, {"endpoints": []}, "endpoints", "r")


def run_cli(tmp_path, *argv):
    import expected_lists as C
    return C.main(list(argv), lists=tmp_path / "lists", runs=tmp_path / "runs")


def test_sync_prints_what_it_would_change_and_writes_only_with_apply(tmp_path, capsys):
    g, run = sync_list()
    S.save("repo", g, tmp_path / "lists")
    (tmp_path / "runs" / "label").mkdir(parents=True)
    (tmp_path / "runs" / "label" / "repo.json").write_text(json.dumps(run))
    before = (tmp_path / "lists" / "repo.json").read_text()
    assert run_cli(tmp_path, "sync", "label") == 0
    assert (tmp_path / "lists" / "repo.json").read_text() == before and "gone" in capsys.readouterr().out
    run_cli(tmp_path, "sync", "label", "--apply")
    assert (tmp_path / "lists" / "repo.json").read_text() != before


def test_an_unknown_list_is_reported_without_a_traceback(tmp_path, capsys):
    (tmp_path / "lists").mkdir()
    assert run_cli(tmp_path, "pending", "ghost") == 2
    assert "no expected list 'ghost'" in capsys.readouterr().err
