"""The micro graph's comparison (scripts/micro.py): whole records as multisets, and a set that stays pinned and out
of the hold-out. No network, no tree-sitter."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import http_corpus as H  # noqa: E402
import micro as M  # noqa: E402


def call(caller, callee, line, strategy="same-file"):
    return {"caller_id": caller, "callee_id": callee, "line": line, "strategy": strategy, "method": None}


RUN = {"repo": {"name": "r", "root": "/repo"}, "counts": {"calls_edges": 2},
       "symbols": [{"id": "s1", "kind": "function"}, {"id": "s2", "kind": "method"}],
       "calls": [call("s1", "s2", 3), call("s2", "s1", 9)],
       "warnings": []}


def test_identical_runs_have_no_diff():
    assert M.diff(RUN, {**RUN, "calls": list(reversed(RUN["calls"]))}) == {}


def test_a_field_changed_anywhere_shows():
    head = {**RUN, "calls": [call("s1", "s2", 3, "unique-name"), call("s2", "s1", 9)]}
    d = M.diff(RUN, head)
    assert list(d) == ["calls"]
    gone, new = d["calls"]
    assert sum(gone.values()) == sum(new.values()) == 1
    assert '"same-file"' in next(iter(gone)) and '"unique-name"' in next(iter(new))


def test_a_record_repeated_shows():
    head = {**RUN, "calls": RUN["calls"] + [call("s1", "s2", 3)]}
    gone, new = M.diff(RUN, head)["calls"]
    assert not gone and sum(new.values()) == 1


def test_the_run_metadata_is_not_the_graph():
    head = {**RUN, "repo": {"name": "r", "root": "/elsewhere"}, "counts": {"calls_edges": 3}}
    assert M.diff(RUN, head) == {}


def _save(d: Path, name: str, payload: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / f"{name}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(payload, fh)


def test_compare_exits_1_on_a_difference_or_a_missing_run(tmp_path, capsys):
    base, head = tmp_path / "base", tmp_path / "head"
    _save(base, "a", RUN)
    _save(head, "a", RUN)
    assert M.compare(base, head, ["a"], show=0) == 0
    assert "0 repo(s) differ" in capsys.readouterr().out
    _save(head, "a", {**RUN, "calls": RUN["calls"][:1]})
    assert M.compare(base, head, ["a"], show=0) == 1
    assert "1 repo(s) differ: a" in capsys.readouterr().out
    assert M.compare(base, head, ["a", "b"], show=0) == 1
    assert "not compared: b" in capsys.readouterr().err


def test_the_set_is_pinned_and_out_of_the_holdout():
    assert set(M.MICRO) <= set(M.PINS)
    assert not set(M.MICRO) & set(H.HOLDOUT)
