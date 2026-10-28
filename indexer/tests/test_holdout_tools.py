"""The tools for a new hold-out (scripts/lists/): the first sample of a list, and the guards that keep a measured hold-out
unopened. The last tests read the real pins and lists. No Docker, no network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path[:0] = [str(SCRIPTS / "lists"), str(SCRIPTS)]
import expected_lists as C  # noqa: E402
import http_corpus as H  # noqa: E402
import lists_holdout as HO  # noqa: E402
import lists_store as S  # noqa: E402
import lists_sync as Y  # noqa: E402

REAL = Path(__file__).resolve().parent / "corpus_expected" / "holdout"
PIN = "a" * 40


def item(method, path):
    return {"method": method, "path": path}


def checked(path, line, ok=None, category=None):
    return {"evidence": f"r:api.go:{line}", "method": "GET", "path": path, "raw": path, "ok": ok, "category": category}


def run_item(path, line):
    return {"method": "GET", "path": path, "evidence": f"r:api.go:{line}", "raw_path": path}


def routes(n):
    return [run_item(f"/r{i}", i) for i in range(n)]


def test_a_first_sample_marks_the_routes_the_list_has_right_and_leaves_the_rest_to_judge():
    g = {"sha": "abc", "endpoints": [item("GET", "/a")]}
    assert Y.draw(g, {"endpoints": [run_item("/a", 1), run_item("/b", 2)]}, "r", 20) == ["endpoints"]
    assert [(i["path"], i["ok"]) for i in g["checked"]["endpoints"]] == [("/a", True), ("/b", None)]
    assert list(g) == ["sha", "endpoints", "checked", "checked_seed"] and g["checked_seed"] == "0"


def test_a_sample_has_the_given_size_and_the_same_seed_gives_the_same_sample():
    run = {"endpoints": routes(30)}
    a, b, c = ({"endpoints": []} for _ in range(3))
    Y.draw(a, run, "r", 20, "0")
    Y.draw(b, run, "r", 20, "0")
    Y.draw(c, run, "r", 20, "1")
    assert len(a["checked"]["endpoints"]) == 20 and a["checked"] == b["checked"] and a["checked"] != c["checked"]


def test_every_kind_the_run_has_is_drawn_and_a_kind_it_lacks_is_not():
    both = {"endpoints": [run_item("/a", 1)], "calls": [run_item("/c", 2)]}
    g = {"endpoints": []}
    assert Y.draw(g, both, "r", 20) == ["endpoints", "calls"] and set(g["checked"]) == {"endpoints", "calls"}
    g = {"endpoints": []}
    assert Y.draw(g, {**both, "calls": []}, "r", 20) == ["endpoints"] and set(g["checked"]) == {"endpoints"}


def test_a_kind_with_a_sample_is_kept_and_the_other_is_drawn():
    kept = [checked("/a", 1, True)]
    g = {"endpoints": [], "checked": {"endpoints": kept}, "checked_seed": "1"}
    assert Y.draw(g, {"endpoints": routes(3), "calls": [run_item("/c", 2)]}, "r", 20) == ["calls"]
    assert g["checked"]["endpoints"] is kept and g["checked_seed"] == "1"


def test_a_seed_other_than_the_lists_is_refused_and_the_same_one_as_a_number_is_not():
    run = {"endpoints": routes(3)}
    with pytest.raises(Y.SyncError, match="seed"):
        Y.draw({"endpoints": [], "checked_seed": "1"}, run, "r", 20, "2")
    assert Y.draw({"endpoints": [], "checked_seed": 0}, run, "r", 20, "0") == ["endpoints"]


def test_nothing_to_draw_says_what_to_do():
    with pytest.raises(Y.SyncError, match="nothing to draw.*resample"):
        Y.draw({"checked": {"endpoints": [checked("/a", 1)]}}, {"endpoints": routes(3)}, "r", 20)
    with pytest.raises(Y.SyncError, match="nothing to draw"):
        Y.draw({"endpoints": []}, {"endpoints": [], "calls": []}, "r", 20)


@pytest.mark.parametrize("sample,measured", [
    (None, False),
    ({}, False),
    ({"endpoints": [checked("/a", 1)]}, False),
    ({"endpoints": [checked("/a", 1, True), checked("/b", 2)]}, False),
    ({"endpoints": [checked("/a", 1, True), checked("/b", 2, False, "x")]}, True),
    ({"endpoints": [checked("/a", 1, True)], "calls": []}, True),
])
def test_a_list_is_measured_once_every_item_of_its_sample_has_a_verdict(sample, measured):
    assert HO.measured({"checked": sample} if sample is not None else {}) is measured


def test_the_overlap_of_two_sets_is_by_name_and_by_repo_in_any_case():
    pins = {"x": ("Own/Repo", "s"), "y": ("own/other", "s"), "z": ("own/clean", "s")}
    corpus = {"x": ("a/b", "t"), "w": ("own/repo", "t"), "v": ("own/other", "t")}
    assert HO.overlap(pins, corpus) == ["x: a name in the corpus", "x: its repo own/repo is the corpus's w",
                                        "y: its repo own/other is the corpus's v"]




@pytest.fixture
def pins(monkeypatch):
    monkeypatch.setattr(H, "HOLDOUT", {"fresh": ("owner/fresh", PIN), "old": ("owner/old", PIN), "twin": ("owner/Twin", PIN)})
    monkeypatch.setattr(H, "CORPUS", {"old": ("owner/else", "b" * 40), "dup": ("Owner/twin", "c" * 40)})


def cli(tmp_path, *argv):
    return C.main(list(argv), lists=tmp_path / "lists", runs=tmp_path / "runs")


def holdout_dir(tmp_path):
    return tmp_path / "lists" / "holdout"


def test_a_new_holdout_list_is_written_in_the_holdouts_folder_from_its_pin(tmp_path, pins):
    assert cli(tmp_path, "--holdout", "new", "fresh", PIN) == 0
    assert S.load("fresh", holdout_dir(tmp_path)) == {"sha": PIN, "endpoints": []}
    assert not (tmp_path / "lists" / "fresh.json").exists()


@pytest.mark.parametrize("name,sha,message", [
    ("ghost", PIN, "not pinned in HOLDOUT"),
    ("fresh", "d" * 40, "pinned at aaaaaaaaaaaa, not dddddddddddd"),
    ("old", PIN, "a name in the corpus"),
    ("twin", PIN, "owner/twin is the corpus's dup"),
])
def test_a_new_holdout_list_needs_a_pin_at_its_sha_and_a_repo_the_corpus_lacks(tmp_path, pins, capsys, name, sha, message):
    assert cli(tmp_path, "--holdout", "new", name, sha) == 2
    assert message in capsys.readouterr().err and not holdout_dir(tmp_path).exists()


def measured(tmp_path, ok=True):
    sample = {"endpoints": [checked("/a", 1, True), checked("/b", 2, ok or None)]}
    S.save("fresh", {"sha": PIN, "endpoints": [item("GET", "/a")], "checked": sample, "checked_seed": "0"},
           holdout_dir(tmp_path))
    return (holdout_dir(tmp_path) / "fresh.json").read_text()


@pytest.mark.parametrize("argv", [
    ["add", "fresh", "endpoints", "GET", "/z"], ["cat", "fresh", "endpoints", "x", "^/a"], ["set", "fresh", 'notes="n"'],
    ["found", "r", "fresh"], ["sync", "r", "fresh"], ["resample", "r", "fresh", "endpoints"], ["sample", "r", "fresh"],
])
def test_a_measured_holdout_list_is_not_opened_by_a_command_that_reads_or_changes_items(tmp_path, capsys, argv):
    before = measured(tmp_path)
    assert cli(tmp_path, "--holdout", *argv) == 2
    assert "'fresh' is measured" in capsys.readouterr().err
    assert (holdout_dir(tmp_path) / "fresh.json").read_text() == before


def test_the_same_commands_work_while_the_holdout_list_is_still_being_judged(tmp_path, capsys):
    measured(tmp_path, ok=False)
    assert cli(tmp_path, "--holdout", "pending") == 0 and "/b" in capsys.readouterr().out
    assert cli(tmp_path, "--holdout", "add", "fresh", "endpoints", "GET", "/z") == 0


def test_the_commands_without_the_flag_do_not_reach_the_holdouts_lists(tmp_path, capsys):
    measured(tmp_path, ok=False)
    assert cli(tmp_path, "pending") == 0 and capsys.readouterr().out == ""
    assert cli(tmp_path, "add", "fresh", "endpoints", "GET", "/z") == 2


def test_a_new_holdout_list_goes_from_its_pin_to_a_measured_one(tmp_path, pins, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"spec": ["openapi.json"], "endpoints": [item("GET", "/a"), item("GET", "/b")]}))
    run = {"endpoints": [run_item("/a", 1), run_item("/b", 2), run_item("/c", 3)]}
    (tmp_path / "runs" / "r").mkdir(parents=True)
    (tmp_path / "runs" / "r" / "fresh.json").write_text(json.dumps(run))
    assert cli(tmp_path, "--holdout", "new", "fresh", PIN, "--spec", str(spec)) == 0
    capsys.readouterr()
    assert cli(tmp_path, "--holdout", "sample", "r", "fresh") == 0
    out = capsys.readouterr().out
    assert "endpoints: 3 drawn, 2 match the list, 1 to judge" in out and "/c" not in out
    assert "checked" not in S.load("fresh", holdout_dir(tmp_path))
    assert cli(tmp_path, "--holdout", "sample", "r", "fresh", "--apply") == 0
    capsys.readouterr()
    assert cli(tmp_path, "--holdout", "pending") == 0 and "/c" in capsys.readouterr().out
    assert cli(tmp_path, "--holdout", "judge", "fresh", "endpoints", "wrong:x") == 0
    assert cli(tmp_path, "--holdout", "add", "fresh", "endpoints", "GET", "/z") == 2


def test_the_holdout_and_the_corpus_share_no_repo():
    assert HO.overlap(H.HOLDOUT, H.CORPUS) == []


def test_every_pinned_holdout_repo_has_a_list_at_its_sha_and_every_list_has_a_pin():
    assert S.names(REAL) == sorted(H.HOLDOUT)
    assert {n: S.load(n, REAL)["sha"] for n in H.HOLDOUT} == {n: sha for n, (_, sha) in H.HOLDOUT.items()}
