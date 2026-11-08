"""The heavy-job lock (scripts/lib/heavy-lock.sh), with real processes.

One heavy Docker job at a time on the machine: a second one stops with status 75 and names the holder, or waits when it is
told to; the lock is the holder's process, so it goes when that process ends however it ends, and a lock whose process is
gone is taken over."""
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
LIB = SCRIPTS / "lib" / "heavy-lock.sh"
HEAVY = ["corpus.sh", "micro.sh", "mcp-it.sh", "protocol/protocol.sh", "protocol/time-alone.sh", "protocol/micro-fresh.sh",
         "live/dryrun-live.sh", "live/validate.sh", "judgment/attribution.sh", "test.sh"]


@pytest.fixture
def env(tmp_path):
    # no AIDD_HEAVY_HELD in the environment: an inherited one would stay exported and hide whether the library exports it
    clean = {k: v for k, v in os.environ.items() if k != "AIDD_HEAVY_HELD"}
    return {**clean, "AIDD_HEAVY_LOCK": str(tmp_path / "heavy.lock"), "AIDD_HEAVY_POLL": "0.2", "AIDD_AGENT": "chat-a"}


def bash(env, script, **kw):
    started = time.time()
    done = subprocess.run(["bash", "-c", f'. "{LIB}"\n{script}'], capture_output=True, text=True, env=env, timeout=60, **kw)
    done.elapsed = time.time() - started
    return done


def holder(env, script="sleep 30", label="the-job", who="chat-a"):
    proc = subprocess.Popen(["bash", "-c", f'. "{LIB}"\nheavy_lock {label} {who}\n{script}'], env=env, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lock = Path(env["AIDD_HEAVY_LOCK"])
    for _ in range(100):
        if lock.exists() and lock.read_text().strip():
            return proc
        time.sleep(0.05)
    raise AssertionError("the holder did not take the lock")


def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def gone(path, seconds=4):
    end = time.time() + seconds
    while time.time() < end:
        if not Path(path).exists():
            return True
        time.sleep(0.1)
    return False


def test_it_takes_the_lock_with_who_label_since_and_pid_and_releases_it_when_the_process_ends(env):
    done = bash(env, 'heavy_lock mylabel\ncat "$AIDD_HEAVY_LOCK"')
    assert done.returncode == 0, done.stderr
    assert re.fullmatch(r"chat-a \d+ \d{4}-\d\d-\d\dT[\d:]+Z mylabel", done.stdout.strip())
    assert gone(env["AIDD_HEAVY_LOCK"])


def test_a_second_job_stops_at_once_with_75_and_names_the_holder(env):
    proc = holder(env, label="corpus-x", who="chat-b")
    try:
        done = bash(env, "heavy_lock other")
        assert done.returncode == 75 and done.elapsed < 2.5
        assert "another heavy job runs: chat-b " in done.stderr and "corpus-x" in done.stderr and "AIDD_HEAVY_WAIT" in done.stderr
        lock = Path(env["AIDD_HEAVY_LOCK"]).read_text()
        assert lock.startswith("chat-b ") and lock.strip().endswith("corpus-x")
    finally:
        stop(proc)


def test_a_line_with_no_pid_is_a_holder_nobody_can_ask_and_is_never_taken_over(env):
    lock = Path(env["AIDD_HEAVY_LOCK"])
    for line in ("chat-b corpus 2026-11-08T10:00:00Z\n", ""):  # the old format, and an empty file
        lock.write_text(line)
        done = bash(env, "heavy_lock other")
        assert done.returncode == 75 and "the lock of a process that is gone" not in done.stderr
        assert "has no pid" in done.stderr and "remove" in done.stderr
        assert lock.read_text() == line


def test_many_takers_at_once_leave_exactly_one_winner_and_nobody_reads_a_half_written_lock(env):
    for _ in range(3):
        procs = [subprocess.Popen(["bash", "-c", f'. "{LIB}"\nheavy_lock taker\nsleep 1.2'], env=env, stderr=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, text=True) for _ in range(16)]
        codes = [p.wait(timeout=30) for p in procs]
        assert sorted(codes) == [0] + [75] * 15, codes
        assert gone(env["AIDD_HEAVY_LOCK"])


def test_a_label_with_spaces_does_not_hide_the_holders_pid(env):
    proc = holder(env, label='"corpus a long label with spaces"')
    try:
        done = bash(env, "heavy_lock other")
        assert done.returncode == 75 and "taken over" not in done.stderr
        assert Path(env["AIDD_HEAVY_LOCK"]).read_text().strip().endswith("corpus a long label with spaces")
    finally:
        stop(proc)


def test_a_who_with_spaces_is_written_with_underscores_so_the_pid_stays_in_its_column(env):
    done = bash({**env, "AIDD_AGENT": "chat with spaces"}, 'heavy_lock x\ncat "$AIDD_HEAVY_LOCK"')
    assert re.fullmatch(r"chat_with_spaces \d+ \S+ x", done.stdout.strip())


def test_with_a_wait_the_second_job_takes_the_lock_when_the_first_ends(env):
    proc = holder(env, script="sleep 1.5")
    try:
        done = bash({**env, "AIDD_HEAVY_WAIT": "20"}, 'heavy_lock second\necho got-it')
        assert done.returncode == 0 and "got-it" in done.stdout and done.elapsed > 0.5
    finally:
        stop(proc)


def test_a_wait_that_runs_out_ends_with_75(env):
    proc = holder(env)
    try:
        done = bash({**env, "AIDD_HEAVY_WAIT": "2"}, "heavy_lock second")  # the deadline counts whole seconds: 1 to 2 here
        assert done.returncode == 75 and 0.8 < done.elapsed < 5
    finally:
        stop(proc)


def test_a_lock_whose_process_is_gone_is_taken_over_with_a_notice(env):
    dead = subprocess.Popen(["true"])
    dead.wait()
    Path(env["AIDD_HEAVY_LOCK"]).write_text(f"ghost {dead.pid} 2020-01-01T00:00:00Z old-job\n")
    done = bash(env, 'heavy_lock mine\ncat "$AIDD_HEAVY_LOCK"')
    assert done.returncode == 0 and "taken over" in done.stderr and "ghost " in done.stderr and "old-job" in done.stderr
    assert done.stdout.startswith("chat-a ") and done.stdout.strip().endswith("mine")


def test_a_killed_holder_loses_the_lock_all_the_same(env):
    proc = holder(env)
    try:
        os.kill(proc.pid, signal.SIGKILL)
        assert gone(env["AIDD_HEAVY_LOCK"])
    finally:
        stop(proc)


def test_a_late_release_of_a_dead_holder_does_not_remove_the_lock_of_the_one_that_took_over(env):
    first = holder(env, label="first")
    second = None
    try:
        os.kill(first.pid, signal.SIGKILL)
        second = holder(env, label="second", script="sleep 6")  # takes over the lock of a process that is gone
        time.sleep(2.5)  # the first holder's watcher has looked by now
        assert Path(env["AIDD_HEAVY_LOCK"]).read_text().strip().endswith("second")
    finally:
        stop(first)
        if second:
            stop(second)


def test_exec_keeps_the_lock_for_the_process_that_replaces_the_script(env):
    proc = holder(env, script="exec sleep 2")
    try:
        time.sleep(0.5)
        assert Path(env["AIDD_HEAVY_LOCK"]).exists()
        assert gone(env["AIDD_HEAVY_LOCK"], seconds=6)
    finally:
        stop(proc)


def test_a_failing_script_releases_the_lock(env):
    done = bash(env, "heavy_lock failing\nexit 3")
    assert done.returncode == 3 and gone(env["AIDD_HEAVY_LOCK"])


def test_a_script_a_locked_script_starts_does_not_lock_again(env):
    inner = f'bash -c \'. "{LIB}"; heavy_lock inner; echo inner-ok; cat "$AIDD_HEAVY_LOCK"\''
    done = bash(env, f"heavy_lock outer\n{inner}")
    assert done.returncode == 0 and "inner-ok" in done.stdout
    assert done.stdout.strip().endswith("outer") and "inner\n" not in done.stdout.replace("inner-ok", "")


def test_the_lock_is_in_the_corpus_home_by_default(tmp_path, env):
    env = {k: v for k, v in env.items() if k != "AIDD_HEAVY_LOCK"} | {"AIDD_CORPUS_HOME": str(tmp_path / "home")}
    done = bash(env, 'heavy_lock x\nls "$AIDD_CORPUS_HOME"')
    assert "heavy.lock" in done.stdout.split()


def test_who_is_the_checkouts_folder_name_unless_the_agent_says_so(tmp_path, env):
    lib = tmp_path / "chat-b-checkout" / "indexer" / "scripts" / "lib"
    lib.mkdir(parents=True)
    shutil.copy(LIB, lib / "heavy-lock.sh")
    env = {k: v for k, v in env.items() if k != "AIDD_AGENT"}
    done = subprocess.run(["bash", "-c", f'. "{lib / "heavy-lock.sh"}"\nheavy_lock x\ncat "$AIDD_HEAVY_LOCK"'],
                          capture_output=True, text=True, env=env, timeout=60)
    assert done.stdout.startswith("chat-b-checkout ") and done.stdout.strip().endswith(" x")


RUNS = [
    ("corpus.sh", ["--label", "x"]), ("micro.sh", []), ("mcp-it.sh", []), ("test.sh", []), ("test.sh", ["-q"]),
    ("test.sh", ["-k", "something"]), ("test.sh", ["tests"]), ("protocol/protocol.sh", ["lbl"]),
    ("protocol/time-alone.sh", ["a", "b"]), ("protocol/micro-fresh.sh", ["lbl"]), ("live/dryrun-live.sh", ["s", "h", "m", "l"]),
    ("live/validate.sh", ["before", "a", "b"]), ("live/validate.sh", ["after"]),
    ("judgment/attribution.sh", ["go", "/tmp", "/tmp", "a", "b", "1", "repo"]),
]
NOT_HEAVY = [("test.sh", ["tests/test_a.py"]), ("test.sh", ["tests/test_a.py::test_b"]), ("test.sh", ["-q", "tests/"]),
             ("live/validate.sh", ["rotate"])]
STARTS = {"run", "build", "compose", "create", "rm", "stop", "network", "volume", "pull"}


@pytest.fixture
def fake_docker(tmp_path):
    """A `docker` that records its calls and fails, first in PATH: a script that reaches it has started a Docker job."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "docker-calls.log"
    docker = bin_dir / "docker"
    docker.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\nexit 99\n')
    docker.chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}"}, calls


def run_script(env, fake, script, args):
    # the scripts find the repo from where they sit (indexer/scripts/ under a checkout), so run a copy in that layout
    repo = fake[1].parent / "repo"
    if not repo.exists():
        shutil.copytree(SCRIPTS, repo / "indexer" / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    done = subprocess.run(["bash", str(repo / "indexer" / "scripts" / script), *args], capture_output=True, text=True, timeout=60,
                          env={**env, **fake[0]}, cwd="/tmp")
    started = [c for c in (fake[1].read_text().splitlines() if fake[1].exists() else []) if c.split()[0] in STARTS]
    return done, started


@pytest.mark.parametrize("script,args", RUNS, ids=[f"{s} {' '.join(a)}" for s, a in RUNS])
def test_every_heavy_script_ends_with_75_before_its_first_docker_job_when_the_lock_is_held(env, fake_docker, script, args):
    proc = holder(env, label="the-other-job", who="chat-b")
    try:
        done, started = run_script(env, fake_docker, script, args)
        assert done.returncode == 75, done.stderr
        assert "another heavy job runs: chat-b " in done.stderr and "the-other-job" in done.stderr
        assert started == []
    finally:
        stop(proc)


@pytest.mark.parametrize("script,args", NOT_HEAVY, ids=[f"{s} {' '.join(a)}" for s, a in NOT_HEAVY])
def test_a_test_or_two_and_a_rotation_do_not_take_the_lock(env, fake_docker, script, args):
    proc = holder(env)
    try:
        done, _ = run_script(env, fake_docker, script, args)
        assert done.returncode != 75 and "another heavy job runs" not in done.stderr
    finally:
        stop(proc)


def test_validate_locks_before_and_after_but_not_rotate():
    text = (SCRIPTS / "live" / "validate.sh").read_text()
    assert "before) heavy_lock" in text and "after) heavy_lock" in text and "rotate) heavy_lock" not in text
