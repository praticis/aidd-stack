"""checks/reference.sh with a `docker` made for the purpose: which repos it makes rows for and which it checks the scope index on,
that the rows are kept by content, that a clone it cannot make stops it, and what it leaves for gates.py."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scorecard_cases import BOUNDS, CALLS, ROWS, make_tree

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FAKE = """#!/bin/bash
case "$*" in
  "image inspect -f"*) exit 1 ;;
  "image inspect"*) exit 0 ;;
  build*) cat > /dev/null; exit 0 ;;
esac
case "$*" in
  *--references*) printf '%s\\n' $FAKE_REPOS ;;
  *--symtable*) printf '%s\\n' $FAKE_PY_REPOS ;;
  *python_scopes.py*) echo "scopes $(echo "$*" | sed 's/.*--repos //; s/ --json.*//')" >> "$FAKE_LOG"; echo "files: 3"
    for arg in "$@"; do case "$arg" in *:/out) [ -n "${FAKE_NO_SCOPES:-}" ] || cp "$FAKE_SCOPES" "${arg%:/out}/scopes.json" ;; esac; done ;;
  *--prepare*) if [ -z "${FAKE_NO_CLONE:-}" ]; then
      for repo in "${@: -1}"; do mkdir -p "$AIDD_CORPUS_HOME/repos/$repo" && git -C "$AIDD_CORPUS_HOME/repos/$repo" init -q &&
        git -C "$AIDD_CORPUS_HOME/repos/$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m pin; done; fi ;;
  *ts_checker.js*) echo "checker ${@: -1}" >> "$FAKE_LOG"; cat "$FAKE_ROWS" ;;
esac
"""
SCOPES = {"dispatch": {"files": 6, "files compared": 5, "files differing": 0}, "netbox": {"files compared": 8, "files differing": 0}}
SCOPE_BOUNDS = """dispatch.scopes.confirmed :: >= 5 :: a note
dispatch.scopes.contradicted :: <= 0 :: a note
netbox.scopes.confirmed :: >= 8 :: a note
netbox.scopes.contradicted :: <= 0 :: a note
"""
FLOORS = BOUNDS.replace("r.", "ghost.") + BOUNDS.replace("r.", "outline.") + SCOPE_BOUNDS


@pytest.fixture
def world(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text(FAKE)
    (bin_dir / "docker").chmod(0o755)
    (tmp_path / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    (tmp_path / "scopes.json").write_text(json.dumps(SCOPES))
    shutil.copytree(SCRIPTS, tmp_path / "indexer" / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    home = tmp_path / "home"
    for repo in ("ghost", "outline", "dispatch", "netbox"):
        (home / "repos" / repo).mkdir(parents=True)
        subprocess.run(["git", "-C", str(home / "repos" / repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(home / "repos" / repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "pin"], check=True)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "AIDD_CORPUS_HOME": str(home), "AIDD_HEAVY_HELD": "1",
           "FAKE_REPOS": "ghost outline", "FAKE_PY_REPOS": "dispatch netbox", "FAKE_LOG": str(tmp_path / "calls.log"),
           "FAKE_ROWS": str(tmp_path / "rows.jsonl"), "FAKE_SCOPES": str(tmp_path / "scopes.json")}

    def runs(name, calls=CALLS):
        for repo in ("ghost", "outline"):
            make_tree(tmp_path)(calls=calls, repo=repo, name=name)
        return tmp_path / name

    def run(*args, **more):
        return subprocess.run(["bash", str(tmp_path / "indexer" / "scripts" / "checks" / "reference.sh"), *map(str, args)], env={**env, **more}, capture_output=True, text=True)

    def logged(kind):
        log = tmp_path / "calls.log"
        return [line for line in log.read_text().splitlines() if line.startswith(kind)] if log.exists() else []

    return tmp_path, runs, run, lambda: logged("checker"), lambda: logged("scopes")


def floors_file(tmp_path, text=FLOORS, name="floors.txt"):
    (tmp_path / name).write_text(text)
    return tmp_path / name


def test_the_rows_are_made_for_the_repos_the_micro_set_names_and_kept_by_content(world):
    tmp_path, runs, run, checker_calls, _ = world
    assert run("--rows-only").returncode == 0
    assert sorted(checker_calls()) == ["checker /corpus/ghost", "checker /corpus/outline"]
    assert run("--rows-only").returncode == 0
    assert len(checker_calls()) == 2  # the second run reads them back


def test_a_repo_of_the_micro_set_is_measured_even_when_its_bounds_are_gone(world):
    tmp_path, runs, run, _, _ = world
    floors = floors_file(tmp_path, BOUNDS.replace("r.", "ghost."))
    result = run("--run", runs("head"), "--floors", floors)
    assert result.returncode == 1 and "`outline.receiver-type.confirmed` | 2 |  | " in result.stdout and "unbound" in result.stdout


def test_a_clone_that_cannot_be_made_stops_it_with_a_message(world):
    tmp_path, runs, run, _, _ = world
    subprocess.run(["rm", "-rf", str(tmp_path / "home" / "repos" / "ghost")], check=True)
    result = run("--run", runs("head"), "--floors", floors_file(tmp_path), FAKE_NO_CLONE="1")
    assert result.returncode == 2 and "no clone of ghost" in result.stderr


def test_a_clone_that_is_missing_is_made_at_its_pin(world):
    tmp_path, runs, run, _, _ = world
    subprocess.run(["rm", "-rf", str(tmp_path / "home" / "repos" / "ghost")], check=True)
    assert run("--run", runs("head"), "--floors", floors_file(tmp_path)).returncode == 0


@pytest.mark.parametrize("args", [["--run", "/nowhere"], ["--run", "{head}", "--floors", "/nowhere"], ["--run", "{head}", "--base", "/nowhere"]])
def test_a_wrong_input_ends_in_2(world, args):
    tmp_path, runs, run, _, _ = world
    head = runs("head")
    assert run(*[a.replace("{head}", str(head)) for a in args]).returncode == 2


def test_it_leaves_what_the_gates_read(world):
    tmp_path, runs, run, _, _ = world
    out = tmp_path / "out"
    base_floors = floors_file(tmp_path, name="base-floors.txt")
    floors = floors_file(tmp_path, FLOORS.replace(">= 2", ">= 1"), "floors.txt")
    result = run("--run", runs("head"), "--base", runs("base"), "--floors", floors, "--base-floors", base_floors, "--out", out)
    assert result.returncode == 0
    assert (out / "reference-rc.txt").read_text() == "0\n"
    assert (out / "reference-lowered.txt").read_text().splitlines() == [
        "ghost.receiver-type.confirmed: >= 2, now >= 1", "outline.receiver-type.confirmed: >= 2, now >= 1"]
    assert "### The graph against its references" in (out / "reference.txt").read_text() and "Bounds this change lowers:" in result.stdout


def test_a_count_past_its_bound_ends_in_1_and_a_win_lost_alone_ends_in_3(world):
    tmp_path, runs, run, _, _ = world
    out = tmp_path / "out"
    assert run("--run", runs("head"), "--floors", floors_file(tmp_path, FLOORS.replace(">= 2", ">= 3"), "f2.txt"), "--out", out).returncode == 1
    assert (out / "reference-rc.txt").read_text() == "1\n"
    fewer = [c for c in CALLS if c["line"] != 3]
    loose = floors_file(tmp_path, FLOORS.replace(">= 2", ">= 0").replace(">= 1", ">= 0"), "f3.txt")
    assert run("--run", runs("head2", fewer), "--base", runs("base2"), "--floors", loose, "--out", out).returncode == 3
    assert (out / "reference-rc.txt").read_text() == "3\n"


def test_the_rows_follow_the_clones_commit_and_the_checkers_code(world):
    tmp_path, runs, run, checker_calls, _ = world
    assert run("--rows-only").returncode == 0 and len(checker_calls()) == 2
    ghost = tmp_path / "home" / "repos" / "ghost"
    subprocess.run(["git", "-C", str(ghost), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "moved"], check=True)
    assert run("--rows-only").returncode == 0 and checker_calls()[2:] == ["checker /corpus/ghost"]   # only the clone that moved
    with open(tmp_path / "indexer" / "scripts" / "checks" / "ts_checker.js", "a") as js:
        js.write("\n// another checker\n")
    assert run("--rows-only").returncode == 0 and len(checker_calls()) == 5                           # both, for the new code


def test_only_the_rows_are_made_without_the_trees_dry_runs(world):
    _, _, run, checker_calls, _ = world
    assert run("--rows-only", "--floors", "/nowhere").returncode == 0 and len(checker_calls()) == 2


def test_a_wrong_input_is_found_before_any_row_is_made(world):
    tmp_path, runs, run, checker_calls, _ = world
    assert run("--run", runs("head"), "--floors", "/nowhere").returncode == 2
    assert checker_calls() == []



# -- the scope index against CPython's symbol table -------------------------------------------------------------------------

def test_the_scope_index_is_checked_on_the_python_repos_the_micro_set_names_in_a_run_and_not_in_one_for_the_rows(world):
    tmp_path, runs, run, _, scope_calls = world
    assert run("--rows-only").returncode == 0 and scope_calls() == []
    result = run("--run", runs("head"), "--floors", floors_file(tmp_path))
    assert result.returncode == 0 and scope_calls() == ["scopes dispatch netbox"]
    assert "| `netbox.scopes.confirmed` | 8 | >= 8 | +0 | ok |" in result.stdout
    assert "files: 3" in result.stderr  # what the check printed is in the log


def test_a_file_whose_scopes_differ_is_a_count_past_its_bound(world):
    tmp_path, runs, run, _, _ = world
    (tmp_path / "scopes.json").write_text(json.dumps({**SCOPES, "netbox": {"files compared": 8, "files differing": 2}}))
    result = run("--run", runs("head"), "--floors", floors_file(tmp_path), "--out", tmp_path / "out")
    assert result.returncode == 1 and (tmp_path / "out" / "reference-rc.txt").read_text() == "1\n"
    assert "| `netbox.scopes.contradicted` | 2 | <= 0 | -2 | above |" in result.stdout
    assert "| `netbox.scopes.confirmed` | 6 | >= 8 | -2 | below |" in result.stdout


def test_a_python_repo_with_no_bound_is_a_count_with_no_floor(world):
    tmp_path, runs, run, _, _ = world
    result = run("--run", runs("head"), "--floors", floors_file(tmp_path, FLOORS.replace(SCOPE_BOUNDS, "")))
    assert result.returncode == 1 and "| `dispatch.scopes.confirmed` | 5 |  |  | unbound |" in result.stdout


def test_a_scope_check_that_wrote_no_counts_is_a_run_that_did_not_finish(world):
    tmp_path, runs, run, _, _ = world
    result = run("--run", runs("head"), "--floors", floors_file(tmp_path), FAKE_NO_SCOPES="1")
    assert result.returncode == 2 and "scorecard.py" in result.stderr


def test_the_clone_of_a_python_repo_is_made_at_its_pin_and_one_that_cannot_be_made_stops_it(world):
    tmp_path, runs, run, _, scope_calls = world
    subprocess.run(["rm", "-rf", str(tmp_path / "home" / "repos" / "dispatch")], check=True)
    assert run("--run", runs("head"), "--floors", floors_file(tmp_path)).returncode == 0
    assert (tmp_path / "home" / "repos" / "dispatch" / ".git").is_dir()
    subprocess.run(["rm", "-rf", str(tmp_path / "home" / "repos" / "netbox")], check=True)
    result = run("--run", runs("head2"), "--floors", floors_file(tmp_path), FAKE_NO_CLONE="1")
    assert result.returncode == 2 and "no clone of netbox" in result.stderr and len(scope_calls()) == 1


def test_the_micro_set_must_name_a_python_repo(world):
    tmp_path, runs, run, _, _ = world
    result = run("--run", runs("head"), "--floors", floors_file(tmp_path), FAKE_PY_REPOS="")
    assert result.returncode == 2 and "no repo CPython's symbol table is the reference of" in result.stderr
