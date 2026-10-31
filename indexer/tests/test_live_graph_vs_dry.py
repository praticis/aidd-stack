"""The live graph against the dry-runs (scripts/live/graph_vs_dry.py) over synthetic pictures: a graph that holds each
dry-run's CALLS, with their strategy and `virtual`, and its EXTENDS, IMPLEMENTS and OVERRIDES matches, and one that misses any of
them is a mismatch. No Docker, no live install."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live" / "graph_vs_dry.py"
A, B = "t/r@main/sym/A#class", "t/r@main/sym/B#class"
CALL = {"caller_id": "t/r@main/sym/A.f#method", "callee_id": "t/r@main/sym/B.g#method", "line": 3, "method": None,
        "strategy": "receiver-type"}
EDGE = '"t/r@main/sym/A.f#method", "t/r@main/sym/B.g#method", 3, "receiver-type", FALSE, NULL, {virtual}\n'


def _picture(d: Path, virtual: str, types: str) -> Path:
    d.mkdir(parents=True)
    (d / "calls_edges.txt").write_text(EDGE.format(virtual=virtual))
    (d / "hierarchy_edges.txt").write_text(types)
    return d


def _run(tmp_path: Path, virtual: str, types: str) -> tuple[int, str]:
    dry = tmp_path / "dry"
    dry.mkdir()
    (dry / "t__r__main__main.json").write_text(json.dumps({"calls": [CALL]}))
    (dry / "t__r__main__head.json").write_text(json.dumps({
        "calls": [CALL | {"virtual": False}], "hierarchy": [{"source_id": A, "target_id": B, "kind": "EXTENDS"}]}))
    before, after = _picture(tmp_path / "before", "NULL", ""), _picture(tmp_path / "after", virtual, types)
    ran = subprocess.run([sys.executable, str(SCRIPT), str(before), str(after), str(dry)], capture_output=True,
                         text=True)
    return ran.returncode, ran.stdout


def test_a_graph_that_holds_the_dry_runs_edges_matches(tmp_path):
    rc, out = _run(tmp_path, "FALSE", f'"{A}", "EXTENDS", "{B}"\n')
    assert rc == 0 and "snapshot 1: graph 1 -> 1" in out and "all match" in out


def test_a_call_whose_virtual_differs_is_a_mismatch(tmp_path):
    rc, out = _run(tmp_path, "TRUE", f'"{A}", "EXTENDS", "{B}"\n')
    assert rc == 1 and "MISMATCH: strategies and virtual after = head" in out


def test_a_missing_hierarchy_edge_is_a_mismatch(tmp_path):
    rc, out = _run(tmp_path, "FALSE", "")
    assert rc == 1 and "MISMATCH: hierarchy after = head" in out
