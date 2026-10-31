"""The live graph against the dry-runs (scripts/live/graph_vs_dry.py) over synthetic pictures: a graph that holds each
dry-run's CALLS, with their strategy, `virtual` and `receivers`, and its EXTENDS, IMPLEMENTS and OVERRIDES, with an
override's `receivers`, matches, and one that misses any of them is a mismatch. No Docker, no live install."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live" / "graph_vs_dry.py"
A, B = "t/r@main/sym/A.f#method", "t/r@main/sym/B.f#method"
CALL = {"caller_id": "t/r@main/sym/A.f#method", "callee_id": "t/r@main/sym/B.g#method", "line": 3, "method": None,
        "strategy": "receiver-type"}
EDGE = '"t/r@main/sym/A.f#method", "t/r@main/sym/B.g#method", 3, "receiver-type", FALSE, NULL, {virtual}, "{on}"\n'
OVERRIDE = f'"{A}", "OVERRIDES", "{B}", "|t.Leaf"\n'


def _picture(d: Path, virtual: str, types: str, on: str = "") -> Path:
    d.mkdir(parents=True)
    (d / "calls_edges.txt").write_text(EDGE.format(virtual=virtual, on=on))
    (d / "hierarchy_edges.txt").write_text(types)
    return d


def _run(tmp_path: Path, virtual: str, types: str, on: str = "|t.Leaf") -> tuple[int, str]:
    dry = tmp_path / "dry"
    dry.mkdir(parents=True)
    (dry / "t__r__main__main.json").write_text(json.dumps({"calls": [CALL]}))
    (dry / "t__r__main__head.json").write_text(json.dumps({
        "calls": [CALL | {"virtual": False, "receivers": ["t.Leaf"]}],
        "hierarchy": [{"source_id": A, "target_id": B, "kind": "OVERRIDES", "receivers": ["t.Leaf"]}]}))
    before, after = _picture(tmp_path / "before", "NULL", ""), _picture(tmp_path / "after", virtual, types, on)
    ran = subprocess.run([sys.executable, str(SCRIPT), str(before), str(after), str(dry)], capture_output=True,
                         text=True)
    return ran.returncode, ran.stdout


def test_a_graph_that_holds_the_dry_runs_edges_matches(tmp_path):
    rc, out = _run(tmp_path, "FALSE", OVERRIDE)
    assert rc == 0 and "snapshot 1: graph 1 -> 1" in out and "all match" in out


def test_a_call_whose_virtual_or_receivers_differ_is_a_mismatch(tmp_path):
    for virtual, on in (("TRUE", "|t.Leaf"), ("FALSE", "")):
        rc, out = _run(tmp_path / virtual, virtual, OVERRIDE, on)
        assert rc == 1 and "MISMATCH: strategies, virtual and receivers after = head" in out


def test_a_missing_hierarchy_edge_or_an_overrides_receivers_is_a_mismatch(tmp_path):
    for i, types in enumerate(("", OVERRIDE.replace("|t.Leaf", ""))):
        rc, out = _run(tmp_path / str(i), "FALSE", types)
        assert rc == 1 and "MISMATCH: hierarchy after = head" in out
