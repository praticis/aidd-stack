"""The live graph against the dry-runs (scripts/live/graph_vs_dry.py) over synthetic pictures: a graph that holds each
dry-run's symbols, with every property the writer gives them, its CALLS, with their strategy, `virtual` and
`receivers`, and its EXTENDS, IMPLEMENTS and OVERRIDES, with an override's `receivers`, matches, and one that misses
any of them is a mismatch. No Docker, no live install."""
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
SYMBOL = {"id": A, "kind": "method", "line_start": 3, "line_end": 5, "role": None, "is_entry_point": False,
          "name": "f", "qualified_name": "A.f", "visibility": "public", "content_hash": "h1",
          "signature": 'f(a: "x" | 100%): Promise<void>', "doc": "One line.\nAnother."}
LINE = (f'"{A}", "method", 3, 5, NULL, FALSE, "f", "A.f", "public", "h1", "f(a: %22x%22 | 100%25): Promise<void>", '
        '"One line.%0AAnother."\n')


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



def _symbols(tmp_path: Path, lines: list[str], main: dict = SYMBOL) -> tuple[int, str]:
    dry = tmp_path / "dry"
    dry.mkdir(parents=True)
    for side, symbol in (("main", main), ("head", SYMBOL)):
        (dry / f"t__r__main__{side}.json").write_text(json.dumps({"calls": [], "symbols": [symbol]}))
    pictures = []
    for i, line in enumerate(lines):
        pictures.append(tmp_path / f"picture{i}")
        pictures[-1].mkdir()
        for name, text in (("calls_edges", ""), ("hierarchy_edges", ""), ("symbols", line)):
            (pictures[-1] / f"{name}.txt").write_text(text)
    ran = subprocess.run([sys.executable, str(SCRIPT), *map(str, pictures), str(dry)], capture_output=True, text=True)
    return ran.returncode, ran.stdout


def test_a_graph_that_holds_the_dry_runs_symbols_matches(tmp_path):
    rc, out = _symbols(tmp_path, [LINE])
    assert rc == 0 and "symbols 1; all match" in out


def test_a_symbol_whose_property_differs_or_that_is_missing_is_a_mismatch(tmp_path):
    for i, line in enumerate((LINE.replace("Promise<void>", "Promise<void"), LINE.replace("%0A", " "),
                              LINE.replace('"h1"', '"h2"'), LINE.replace("FALSE", "TRUE"), "")):
        rc, out = _symbols(tmp_path / str(i), [line])
        assert rc == 1 and "MISMATCH: symbols before = main" in out


def test_a_symbol_the_reinstall_leaves_as_mains_is_a_mismatch(tmp_path):
    old, old_line = SYMBOL | {"signature": SYMBOL["signature"][:-1]}, LINE.replace("Promise<void>", "Promise<void")
    rc, out = _symbols(tmp_path / "written", [old_line, LINE], main=old)
    assert rc == 0 and "symbols 1 -> 1, changed 1, dry changed 1; all match" in out
    rc, out = _symbols(tmp_path / "left", [old_line, old_line], main=old)
    assert rc == 1 and "MISMATCH: symbols after = head" in out
