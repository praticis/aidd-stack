"""The cost of a change in pairs (scripts/protocol/cost_pairs.py and cost-pairs.sh): the arithmetic on runs made for the purpose,
and the order, the labels and the lock of the script, with a fake corpus.sh in each tree."""
import importlib.util
import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
spec = importlib.util.spec_from_file_location("cost_pairs", SCRIPTS / "protocol" / "cost_pairs.py")
cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cost)

MIB = 1048576


def write_run(home, label, rows):
    folder = Path(home) / "runs" / f"{label}.logs"
    folder.mkdir(parents=True)
    (folder / "summary.txt").write_text("".join(f"{repo} {status} {seconds}s {peak}\n" for repo, status, seconds, peak in rows))


def test_the_change_in_time_per_pair_the_two_medians_and_the_change_in_the_median_peak(tmp_path):
    for i, (m, b, pm, pb) in enumerate([(100, 110, 1500, 1000), (100, 120, 1100, 1000), (100, 100, 1000, 1100), (100, 190, 1000, 1000)], 1):
        write_run(tmp_path, f"p-m{i}", [("ghost", "ok", m, pm * MIB)])
        write_run(tmp_path, f"p-b{i}", [("ghost", "ok", b, pb * MIB)])
    (line,) = cost.report(str(tmp_path), [f"p-m{i}" for i in range(1, 5)], [f"p-b{i}" for i in range(1, 5)])
    assert line == ("ghost: time +10.0 +20.0 +0.0 +90.0 % | median of the first three +10.0 %, of all +15.0 % | memory -4.8 %")


def test_a_repo_under_thirty_seconds_on_main_is_reported_and_marked_not_deciding(tmp_path):
    for label, rows in (("p-m1", [("big", "ok", 80, 5), ("small", "ok", 12, 5)]), ("p-b1", [("big", "ok", 88, 5), ("small", "ok", 13, 5)])):
        write_run(tmp_path, label, rows)
    lines = cost.report(str(tmp_path), ["p-m1"], ["p-b1"])
    assert lines[0].startswith("big: time +10.0 %") and "not deciding" not in lines[0]
    assert lines[1].startswith("small: time +8.3 %") and lines[1].endswith("(under 30 s on main: reported, not deciding)")


def test_a_repo_that_failed_or_is_missing_in_any_run_is_left_out(tmp_path):
    write_run(tmp_path, "p-m1", [("a", "ok", 50, 5), ("b", "ok", 50, 5), ("c", "ok", 50, 5)])
    write_run(tmp_path, "p-b1", [("a", "ok", 55, 5), ("b", "failed(1)", 3, 5)])
    assert [line.split(":")[0] for line in cost.report(str(tmp_path), ["p-m1"], ["p-b1"])] == ["a"]


def test_a_run_with_no_summary_is_an_empty_run(tmp_path):
    write_run(tmp_path, "p-m1", [("a", "ok", 50, 5)])
    assert cost.report(str(tmp_path), ["p-m1"], ["p-b1"]) == []


def test_the_labels_come_from_a_prefix_and_a_count_or_from_two_lists_and_nothing_else_is_accepted():
    assert cost.labels(["p", "2"]) == (["p-m1", "p-m2"], ["p-b1", "p-b2"])
    assert cost.labels(["--main", "a", "b", "--branch", "c", "d"]) == (["a", "b"], ["c", "d"])
    for bad in (["p"], ["p", "0"], ["p", "x"], ["--main", "a", "--branch", "c", "d"], ["--branch", "c", "--main", "a"], ["--main", "--branch", "c"],
                ["--branch", "c", "d", "--main", "a", "b"]):
        assert cost.labels(bad) is None


def test_without_a_valid_argument_list_it_prints_its_usage_and_ends_with_2(capsys):
    assert cost.main([]) == 2 and cost.main(["home", "p"]) == 2
    assert "cost_pairs.py HOME PREFIX PAIRS" in capsys.readouterr().err


def test_with_no_repo_in_every_pair_it_says_so(tmp_path, capsys):
    assert cost.main([str(tmp_path), "p", "1"]) == 0
    assert "no repo has a run in every pair" in capsys.readouterr().out


FAKE_CORPUS = """#!/usr/bin/env bash
label=""; args=("$@")
while [ $# -gt 0 ]; do case "$1" in --label) label="$2"; shift 2 ;; *) shift ;; esac; done
echo "$label|${args[*]}|held=${AIDD_HEAVY_HELD:-no}" >> "$FAKE_ORDER"
[ "${FAKE_FAIL:-}" != "$label" ] || exit 1
mkdir -p "$AIDD_CORPUS_HOME/runs/$label.logs"
echo "ghost ok $FAKE_SECONDS 1048576" > "$AIDD_CORPUS_HOME/runs/$label.logs/summary.txt"
"""


@pytest.fixture
def trees(tmp_path):
    out = {}
    for side, seconds in (("main", 100), ("branch", 110)):
        corpus = tmp_path / side / "indexer" / "scripts" / "corpus.sh"
        corpus.parent.mkdir(parents=True)
        corpus.write_text(FAKE_CORPUS.replace("$FAKE_SECONDS", str(seconds)))
        corpus.chmod(corpus.stat().st_mode | stat.S_IEXEC)
        out[side] = str(tmp_path / side)
    return out


@pytest.fixture
def env(tmp_path):
    clean = {k: v for k, v in os.environ.items() if k != "AIDD_HEAVY_HELD"}
    return {**clean, "AIDD_CORPUS_HOME": str(tmp_path), "AIDD_HEAVY_LOCK": str(tmp_path / "lock"), "FAKE_ORDER": str(tmp_path / "order")}


def cost_pairs_sh(env, *args):
    return subprocess.run(["bash", str(SCRIPTS / "protocol" / "cost-pairs.sh"), *args], capture_output=True, text=True, env=env, timeout=60)


def test_the_side_that_goes_first_flips_each_pair_and_each_run_is_one_job_without_expected_lists(trees, env, tmp_path):
    done = cost_pairs_sh(env, trees["main"], trees["branch"], "--pairs", "3", "--prefix", "t", "ghost")
    assert done.returncode == 0, done.stderr
    runs = [line.split("|") for line in (tmp_path / "order").read_text().splitlines()]
    assert [r[0] for r in runs] == ["t-m1", "t-b1", "t-b2", "t-m2", "t-m3", "t-b3"]
    assert all(f"--label {r[0]} --jobs 1 --no-expected ghost" in r[1] for r in runs)
    assert "ghost: time +10.0 +10.0 +10.0 % | median of the first three +10.0 %, of all +10.0 % | memory +0.0 %" in done.stdout


def test_without_pairs_or_prefix_it_runs_three_pairs_under_a_label_made_of_the_date(trees, env, tmp_path):
    done = cost_pairs_sh(env, trees["main"], trees["branch"], "ghost")
    assert done.returncode == 0, done.stderr
    labels = [line.split("|")[0] for line in (tmp_path / "order").read_text().splitlines()]
    assert len(labels) == 6 and all(label.startswith("cost-") for label in labels)
    assert [label.rsplit("-", 1)[1] for label in labels] == ["m1", "b1", "b2", "m2", "m3", "b3"]


def test_each_side_runs_its_own_trees_corpus_script(trees, env, tmp_path):
    for side, seconds in (("main", 100), ("branch", 110)):
        script = Path(trees[side]) / "indexer" / "scripts" / "corpus.sh"
        script.write_text(script.read_text().replace('echo "$label|', f'echo "{side}:$label|'))
    cost_pairs_sh(env, trees["main"], trees["branch"], "--pairs", "2", "--prefix", "t", "ghost")
    assert [line.split("|")[0] for line in (tmp_path / "order").read_text().splitlines()] == ["main:t-m1", "branch:t-b1", "branch:t-b2", "main:t-m2"]


def test_the_corpus_script_it_starts_finds_the_heavy_lock_held_and_does_not_take_it_again(trees, env, tmp_path):
    cost_pairs_sh(env, trees["main"], trees["branch"], "--pairs", "1", "--prefix", "t", "ghost")
    assert all(line.endswith("held=1") for line in (tmp_path / "order").read_text().splitlines())


def test_a_held_lock_ends_it_with_75_before_any_run(trees, env, tmp_path):
    holder = subprocess.Popen(["bash", "-c", f'. "{SCRIPTS / "lib" / "heavy-lock.sh"}"\nheavy_lock other chat-b\nsleep 10'], env=env,
                              start_new_session=True)
    try:
        for _ in range(100):
            if (tmp_path / "lock").exists() and (tmp_path / "lock").read_text().strip():
                break
            time.sleep(0.05)
        done = cost_pairs_sh(env, trees["main"], trees["branch"], "--pairs", "1", "ghost")
        assert done.returncode == 75 and not (tmp_path / "order").exists()
    finally:
        os.killpg(holder.pid, 9)
        holder.wait()


def test_a_run_that_ends_in_an_error_is_named_and_the_others_go_on(trees, env, tmp_path):
    done = cost_pairs_sh({**env, "FAKE_FAIL": "t-b2"}, trees["main"], trees["branch"], "--pairs", "3", "--prefix", "t", "ghost")
    assert "t-b2 ended with an error" in done.stderr
    assert len((tmp_path / "order").read_text().splitlines()) == 6
    assert "no repo has a run in every pair" in done.stdout


def test_without_repos_or_trees_it_prints_its_usage_and_ends_with_2(trees, env):
    assert cost_pairs_sh(env, trees["main"], trees["branch"]).returncode == 2
    for args in ((), (trees["main"],)):
        done = cost_pairs_sh(env, *args)
        assert done.returncode == 2 and "cost-pairs.sh MAIN_TREE BRANCH_TREE" in done.stderr
    done = cost_pairs_sh(env, trees["main"], trees["branch"], "--pairs", "2")
    assert done.returncode == 2 and "name at least one repo" in done.stderr
