"""The mutants runner (scripts/checks/mutants.py): what it makes, what it asks, what it says.

The tests run it on a small tree of its own whose test.sh is a script that fails when a marker line is gone, so no Docker
and no real suite is involved: what is under test is the tool, not any mutant."""
import importlib.util
import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mutants", HERE.parent / "scripts" / "checks" / "mutants.py")
mutants = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mutants)

APP = "value = 1\nother = 5\n# note\ntwice = a\ntwice = a\n"
TEST_SH = """#!/usr/bin/env bash
root="$(cd "$(dirname "$0")/.." && pwd)"
echo "args: $*"
[ -z "${FAKE_NO_PYTEST:-}" ] || { echo "ERROR: failed to solve: the image does not build"; exit 1; }
[ -z "${FAKE_BAD_PATH:-}" ] || { echo "ERROR: file or directory not found: tests/x.py"; exit 4; }
[ -z "${FAKE_ODD:-}" ] || { echo "1 failed in 0.01s"; exit 1; }
[ -z "${FAKE_HANG:-}" ] || { sleep 20 & child=$!; trap 'kill $child; echo term > "$FAKE_HANG"; exit 143' TERM; wait; }
[ -z "${FAKE_RED:-}" ] || { echo "FAILED tests/test_app.py::test_old - it was red"; echo "1 failed, 2 passed in 0.01s"; exit 1; }
[ -z "${FAKE_ERROR:-}" ] || { echo "ERROR tests/test_app.py - collection failed"; echo "1 error in 0.01s"; exit 2; }
grep -q 'value = 1' "$root/app.py" || { echo "FAILED tests/test_app.py::test_value - the value is not 1"; echo "1 failed, 2 passed in 0.01s"; exit 1; }
echo "3 passed in 0.01s"
"""


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "indexer"
    (root / "scripts").mkdir(parents=True)
    (root / "app.py").write_text(APP)
    sh = root / "scripts" / "test.sh"
    sh.write_text(TEST_SH)
    sh.chmod(sh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(mutants, "INDEXER", root)
    monkeypatch.setenv("AIDD_MUTANTS_DIR", str(tmp_path))
    return root


def write_mutants(tmp_path, body, tests=None):
    file = tmp_path / "set.py"
    file.write_text(f"MUTANTS = [\n{body}\n]\n" + (f"TESTS = {tests!r}\n" if tests else ""))
    return str(file)


DIES = '("1 the value changes", "app.py", "value = 1", "value = 2"),'
SURVIVES = '("2 a comment changes", "app.py", "# note", "# other"),'


def test_a_mutant_a_test_notices_dies_and_one_nothing_notices_survives(tree, tmp_path, capsys):
    status = mutants.main([write_mutants(tmp_path, DIES + SURVIVES)])
    out = capsys.readouterr().out
    assert "1 the value changes: DIES | FAILED tests/test_app.py::test_value" in out
    assert "2 a comment changes: SURVIVES | 3 passed" in out
    assert "2 mutants, 1 die (0 by timeout), 1 survive (0 allowed), 0 broken" in out
    assert status == 1


def test_every_mutant_dying_is_status_zero(tree, tmp_path, capsys):
    assert mutants.main([write_mutants(tmp_path, DIES)]) == 0
    assert "1 mutants, 1 die" in capsys.readouterr().out


def test_a_survivor_named_by_allow_is_status_zero_and_a_survivor_not_named_is_still_one(tree, tmp_path, capsys):
    file = write_mutants(tmp_path, DIES + SURVIVES)
    assert mutants.main([file, "--allow", "2"]) == 0
    assert "1 survive (1 allowed)" in capsys.readouterr().out
    assert mutants.main([file, "--allow", "1"]) == 1   # naming a mutant that died allows nothing: 2 still survives


def test_allow_can_be_given_more_than_once_and_an_unknown_id_is_an_error(tree, tmp_path, capsys):
    file = write_mutants(tmp_path, DIES + SURVIVES)
    assert mutants.main([file, "--allow", "2", "--allow", "1"]) == 0
    assert mutants.main([file, "--allow", "9"]) == 2
    assert "no mutant has the id 9" in capsys.readouterr().err


def test_ids_select_the_mutants_to_run_and_an_unknown_id_is_an_error(tree, tmp_path, capsys):
    file = write_mutants(tmp_path, DIES + SURVIVES)
    assert mutants.main([file, "1"]) == 0
    out = capsys.readouterr().out
    assert "1 the value changes" in out and "a comment changes" not in out
    assert mutants.main([file, "9"]) == 2
    assert "no mutant has the id 9" in capsys.readouterr().err


@pytest.mark.parametrize("anchor,found", [("absent text", 0), ("twice = a", 2)])
def test_an_anchor_found_not_once_is_the_authors_error_not_a_verdict(tree, tmp_path, capsys, anchor, found):
    body = f'("3 bad anchor", "app.py", "{anchor}", "x"),'
    assert mutants.main([write_mutants(tmp_path, body)]) == 2
    assert f"the anchor is found {found} times in app.py" in capsys.readouterr().err


@pytest.mark.parametrize("body,message", [
    ("", "non-empty list"),
    ('("1 short", "app.py", "value = 1"),', "not a (name, file, old, new)"),
    ('("1 numbers", "app.py", 1, 2),', "not a (name, file, old, new)"),
    ('("", "app.py", "value = 1", "x"),', "not a (name, file, old, new)"),
    ('("1 no anchor", "app.py", "", "x"),', "not a (name, file, old, new)"),
    (DIES + '("1 again", "app.py", "other = 5", "other = 6"),', "share an id"),
    ('("1 missing", "nope.py", "a", "b"),', "no file nope.py"),
])
def test_a_wrong_mutants_file_is_status_two_with_a_message_and_never_a_survivor(tree, tmp_path, capsys, body, message):
    assert mutants.main([write_mutants(tmp_path, body)]) == 2
    assert message in capsys.readouterr().err


def test_a_file_that_does_not_run_or_has_no_mutants_is_status_two(tree, tmp_path, capsys):
    broken = tmp_path / "broken.py"
    broken.write_text("MUTANTS = [\n")
    assert mutants.main([str(broken)]) == 2 and "cannot read" in capsys.readouterr().err
    empty = tmp_path / "none.py"
    empty.write_text("X = 1\n")
    assert mutants.main([str(empty)]) == 2 and "must define MUTANTS" in capsys.readouterr().err


def test_a_mutant_whose_file_is_outside_the_tree_is_refused_and_the_file_is_not_touched(tree, tmp_path, capsys):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret = 1\n")
    for path in (str(outside), "../outside.txt"):
        assert mutants.main([write_mutants(tmp_path, f'("1 out", "{path}", "secret = 1", "secret = 2"),')]) == 2
        assert "is outside the tree" in capsys.readouterr().err
    assert outside.read_text() == "secret = 1\n"


def test_tests_that_do_not_run_are_broken_not_a_death_and_not_a_survivor(tree, tmp_path, capsys, monkeypatch):
    for variable, why in (("FAKE_NO_PYTEST", "failed to solve"), ("FAKE_BAD_PATH", "file or directory not found")):
        monkeypatch.setenv(variable, "1")
        assert mutants.main([write_mutants(tmp_path, DIES), "--no-baseline"]) == 2
        out = capsys.readouterr().out
        assert "BROKEN | pytest did not give a result" in out and why in out and "1 broken" in out
        monkeypatch.delenv(variable)


def test_an_error_while_collecting_the_tests_is_a_mutant_that_dies(tree, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_ERROR", "1")
    assert mutants.main([write_mutants(tmp_path, DIES), "--no-baseline"]) == 0
    assert "DIES | ERROR tests/test_app.py - collection failed" in capsys.readouterr().out


def test_a_suite_that_is_red_before_any_mutant_is_status_two_and_the_baseline_can_be_skipped(tree, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_RED", "1")
    assert mutants.main([write_mutants(tmp_path, DIES)]) == 2
    assert "do not pass on the unchanged tree" in capsys.readouterr().err
    assert mutants.main([write_mutants(tmp_path, DIES), "--no-baseline"]) == 0


def test_the_baseline_runs_once_before_the_mutants(tree, tmp_path, monkeypatch):
    calls = []
    real = mutants.run_tests
    monkeypatch.setattr(mutants, "run_tests", lambda root, tests, limit: (calls.append(1), real(root, tests, limit))[1])
    mutants.main([write_mutants(tmp_path, DIES + SURVIVES)])
    assert len(calls) == 3
    calls.clear()
    mutants.main([write_mutants(tmp_path, DIES + SURVIVES), "--no-baseline"])
    assert len(calls) == 2


def test_a_run_with_no_result_in_the_time_given_is_a_timeout_counted_as_dead_and_is_asked_to_stop(tree, tmp_path, capsys, monkeypatch):
    marker = tmp_path / "got-term"
    monkeypatch.setenv("FAKE_HANG", str(marker))
    started = time.time()
    assert mutants.main([write_mutants(tmp_path, DIES), "--no-baseline", "--timeout", "1"]) == 0
    out = capsys.readouterr().out
    assert "1 the value changes: TIMEOUT | no result in 1 s" in out and "1 die (1 by timeout)" in out
    assert time.time() - started < 15
    assert marker.read_text().strip() == "term", "the run was asked to stop (SIGTERM), not killed"


def test_a_failing_status_with_no_failed_test_listed_is_no_verdict(tree, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_ODD", "1")
    assert mutants.main([write_mutants(tmp_path, DIES), "--no-baseline"]) == 2
    assert "BROKEN | pytest did not give a result (status 1)" in capsys.readouterr().out


def test_the_original_tree_is_untouched_and_no_copy_is_left_behind(tree, tmp_path):
    mutants.main([write_mutants(tmp_path, DIES + SURVIVES)])
    assert (tree / "app.py").read_text() == APP
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("mutant-")]


def test_the_tests_argument_goes_to_test_sh_and_the_default_is_the_whole_suite(tree, tmp_path, monkeypatch):
    calls = []
    real = mutants.subprocess.Popen
    monkeypatch.setattr(mutants.subprocess, "Popen", lambda cmd, **kw: (calls.append(cmd[1:]), real(cmd, **kw))[1])
    mutants.main([write_mutants(tmp_path, DIES), "--no-baseline"])
    mutants.main([write_mutants(tmp_path, DIES, tests=["tests/test_a.py"]), "--no-baseline"])
    mutants.main([write_mutants(tmp_path, DIES), "--no-baseline", "--tests", "tests/test_b.py", "-k", "x"])
    assert calls == [["tests", "-x", "--no-header", "-rf"], ["tests/test_a.py", "-x", "--no-header", "-rf"],
                     ["tests/test_b.py", "-k", "x", "-x", "--no-header", "-rf"]]


def test_the_wrapper_ends_with_75_when_a_heavy_job_holds_the_lock(tmp_path):
    scripts = HERE.parent / "scripts"
    env = {k: v for k, v in os.environ.items() if k != "AIDD_HEAVY_HELD"} | {"AIDD_HEAVY_LOCK": str(tmp_path / "heavy.lock")}
    holder = subprocess.Popen(["bash", "-c", f'. "{scripts / "lib" / "heavy-lock.sh"}"\nheavy_lock other-job chat-b\nsleep 10'],
                              env=env, start_new_session=True)
    try:
        for _ in range(100):
            if (tmp_path / "heavy.lock").exists() and (tmp_path / "heavy.lock").read_text().strip():
                break
            time.sleep(0.05)
        done = subprocess.run(["bash", str(scripts / "checks" / "mutants.sh"), "does-not-matter.py"], env=env,
                              capture_output=True, text=True, timeout=30)
        assert done.returncode == 75 and "another heavy job runs: chat-b " in done.stderr
    finally:
        os.killpg(holder.pid, 9)
        holder.wait()


def test_the_tool_runs_on_the_hosts_older_python_so_its_annotations_are_not_evaluated():
    # the wrapper runs it with the host's python3 (3.9 on the author's machine), where `int | None` fails at definition
    assert "from __future__ import annotations" in (HERE.parent / "scripts" / "checks" / "mutants.py").read_text()
