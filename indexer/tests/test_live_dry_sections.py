"""main's and head's dry-runs of each live snapshot, section by section (scripts/live/dry_sections.py): a record whose
key both keep and whose fields differ is counted by field, as one added or removed is by its key. No Docker, no live
install."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "live" / "dry_sections.py"
FILE = {"path": "a.ts", "language": "typescript"}
SYMBOL = {"id": "t/r@main/sym/a:f#function", "signature": "function f(): Promise<void>"}
CALL = {"caller_id": "t/r@main/sym/a:f#function", "callee_id": "t/r@main/sym/a:g#function", "line": 3,
        "strategy": "same-file", "receivers": [], "virtual": True}


def _run(tmp_path: Path, head: dict) -> str:
    for side, run in (("main", {"symbols": [SYMBOL], "calls": [CALL]}), ("head", head)):
        (tmp_path / f"t__r__main__{side}.json").write_text(json.dumps({"files": [FILE], **run}))
    return subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True,
                          check=True).stdout


def test_the_same_records_are_identical(tmp_path):
    assert _run(tmp_path, {"symbols": [SYMBOL], "calls": [CALL]}).endswith(": identical\n")


def test_a_kept_records_fields_that_differ_are_counted_by_field(tmp_path):
    out = _run(tmp_path, {"symbols": [SYMBOL | {"signature": "function f(): Promise<void"}],
                          "calls": [CALL | {"virtual": False}]})
    assert "symbols changed signature 1" in out and "calls changed virtual 1" in out and "by strategy" not in out


def test_a_record_added_is_counted_by_its_key(tmp_path):
    out = _run(tmp_path, {"symbols": [SYMBOL, SYMBOL | {"id": "t/r@main/sym/a:g#function"}], "calls": [CALL]})
    assert "symbols -0 +1" in out and "changed" not in out
