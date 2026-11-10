"""scripts/floors.sh with a real git (a bare origin and a clone) and a `gh` made for the purpose: it raises the bounds main beats, carries
them in the one branch `chore/raise-floors` rebuilt from main, opens or updates its pull request, closes it when nothing is left to raise,
refuses a branch someone else has pushed to, and pushes nothing without --push."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FAKE_GH = """#!/bin/bash
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr list") echo "${FAKE_OPEN_PR:-}" ;;
esac
while [ $# -gt 0 ]; do
  if [ "$1" = --body-file ]; then cp "$2" "$GH_LOG.body"; fi
  shift
done
"""
FLOORS = """# the bounds
a.receiver-type.confirmed :: >= 100 :: measured on main at 1111111
a.receiver-type.contradicted :: <= 5 :: measured on main at 1111111
b.scopes.confirmed :: >= 10 :: measured on main at 1111111
"""
HELD = {"a.receiver-type.confirmed": 100, "a.receiver-type.contradicted": 5, "b.scopes.confirmed": 10}
SHA = "0123456789abcdef0123456789abcdef01234567"
TITLE = "chore(scripts): raise the floors the graph holds"


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=a person", "-c", "user.email=p@e.org", *args], cwd=cwd, capture_output=True, text=True, check=check)


@pytest.fixture
def world(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    git(tmp_path, "clone", "-q", str(origin), str(work))
    shutil.copytree(SCRIPTS, work / "indexer" / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    (work / "indexer" / "scripts" / "checks" / "reference_floors.txt").write_text(FLOORS)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "main")
    git(work, "branch", "-M", "main")
    git(work, "push", "-q", "-u", "origin", "main")
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "GH_LOG": str(tmp_path / "gh.log")}

    def measure(**more):
        (tmp_path / "measured.txt").write_text("".join(
            f"{n} :: {'>=' if n.endswith('confirmed') else '<='} {v} :: measured on the base\n" for n, v in {**HELD, **more}.items()))
        return tmp_path / "measured.txt"

    def run(*args, **more):
        return subprocess.run(["bash", str(work / "indexer" / "scripts" / "floors.sh"), *map(str, args)], cwd=work, env={**env, **more},
                              capture_output=True, text=True)

    def gh_calls():
        log = tmp_path / "gh.log"
        return log.read_text().splitlines() if log.exists() else []

    floors = work / "indexer" / "scripts" / "checks" / "reference_floors.txt"
    return tmp_path, work, floors, measure, run, gh_calls


def test_without_push_it_says_what_it_would_raise_and_leaves_the_file_and_the_remote_as_they_were(world):
    tmp_path, work, floors, measure, run, gh_calls = world
    result = run("--measured", measure(**{"a.receiver-type.confirmed": 130}), "--sha", SHA)
    assert result.returncode == 0 and "- a.receiver-type.confirmed: >= 100, now >= 130" in result.stdout and "nothing was pushed" in result.stdout
    assert floors.read_text() == FLOORS and gh_calls() == []
    assert git(work, "branch", "--show-current").stdout.strip() == "main" and git(work, "ls-remote", "--heads", "origin").stdout.count("\n") == 1


def test_with_push_the_raise_is_one_commit_on_the_bot_branch_over_main_and_a_pull_request_is_opened(world):
    tmp_path, work, floors, measure, run, gh_calls = world
    main = git(work, "rev-parse", "main").stdout.strip()
    result = run("--measured", measure(**{"a.receiver-type.confirmed": 130, "b.scopes.confirmed": 12}), "--sha", SHA, "--push")
    assert result.returncode == 0, result.stderr
    pushed = git(tmp_path / "origin.git", "log", "--format=%H %an %s", "chore/raise-floors", "-2").stdout.splitlines()
    assert pushed[0].endswith(f"floors bot {TITLE}") and pushed[1].startswith(main)
    on_branch = git(tmp_path / "origin.git", "show", "chore/raise-floors:indexer/scripts/checks/reference_floors.txt").stdout
    assert "a.receiver-type.confirmed :: >= 130 :: measured on main at 0123456" in on_branch and "b.scopes.confirmed :: >= 12 ::" in on_branch
    assert "a.receiver-type.contradicted :: <= 5 :: measured on main at 1111111" in on_branch  # a bound that does not move keeps its note
    create = [c for c in gh_calls() if c.startswith("pr create")]
    assert len(create) == 1 and f"--base main --head chore/raise-floors --title {TITLE} --body-file" in create[0]
    body = (tmp_path / "gh.log.body").read_text()
    assert "| `a.receiver-type.confirmed` | >= 100 | >= 130 |" in body and "on main at 0123456" in body


def test_an_open_pull_request_is_updated_and_not_opened_again(world):
    _, _, _, measure, run, gh_calls = world
    assert run("--measured", measure(**{"b.scopes.confirmed": 12}), "--sha", SHA, "--push", FAKE_OPEN_PR="7").returncode == 0
    assert [c.split()[1] for c in gh_calls() if c.startswith("pr ") and not c.startswith("pr list")] == ["edit"]
    assert f"pr edit chore/raise-floors --title {TITLE} --body-file" in "\n".join(gh_calls())


def test_the_branch_is_rebuilt_from_main_each_time_and_the_old_raise_is_gone(world):
    tmp_path, work, _, measure, run, _ = world
    assert run("--measured", measure(**{"b.scopes.confirmed": 12}), "--sha", SHA, "--push").returncode == 0
    git(work, "switch", "-q", "main")
    (work / "NEWS").write_text("main moved\n")
    git(work, "add", "NEWS")
    git(work, "commit", "-q", "-m", "main moves")
    git(work, "push", "-q", "origin", "main")
    assert run("--measured", measure(**{"b.scopes.confirmed": 14}), "--sha", SHA, "--push").returncode == 0
    log = git(tmp_path / "origin.git", "log", "--format=%s", "chore/raise-floors", "-3").stdout.splitlines()
    assert log[:2] == [TITLE, "main moves"]   # one commit over the new main: the first raise was dropped, not stacked
    assert "b.scopes.confirmed :: >= 14" in git(tmp_path / "origin.git", "show", "chore/raise-floors:indexer/scripts/checks/reference_floors.txt").stdout


def test_with_nothing_to_raise_it_pushes_nothing_and_closes_the_open_pull_request(world):
    tmp_path, work, floors, measure, run, gh_calls = world
    result = run("--measured", measure(), "--sha", SHA, "--push")
    assert result.returncode == 0 and "Nothing to raise" in result.stdout and gh_calls() == [
        "pr list --head chore/raise-floors --state open --json number --jq .[0].number // empty"]
    assert git(work, "ls-remote", "--heads", "origin").stdout.count("\n") == 1 and floors.read_text() == FLOORS
    assert run("--measured", measure(), "--sha", SHA, "--push", FAKE_OPEN_PR="7").returncode == 0
    assert any(c.startswith("pr close 7 --delete-branch --comment") for c in gh_calls())


def test_a_bound_main_does_not_hold_is_an_alarm_that_ends_in_1_after_the_raise_is_carried(world):
    tmp_path, _, _, measure, run, gh_calls = world
    result = run("--measured", measure(**{"a.receiver-type.confirmed": 90, "b.scopes.confirmed": 12}), "--sha", SHA, "--push")
    assert result.returncode == 1 and "a.receiver-type.confirmed: >= 100, measured 90" in result.stderr
    assert any(c.startswith("pr create") for c in gh_calls())
    assert "b.scopes.confirmed :: >= 12" in git(tmp_path / "origin.git", "show", "chore/raise-floors:indexer/scripts/checks/reference_floors.txt").stdout


def test_an_alarm_with_nothing_to_raise_ends_in_1_and_pushes_nothing(world):
    _, work, _, measure, run, gh_calls = world
    result = run("--measured", measure(**{"a.receiver-type.confirmed": 90}), "--sha", SHA, "--push")
    assert result.returncode == 1 and git(work, "ls-remote", "--heads", "origin").stdout.count("\n") == 1
    assert not any(c.startswith("pr create") for c in gh_calls())


def test_a_branch_someone_else_has_pushed_to_is_not_overwritten(world):
    tmp_path, work, _, measure, run, gh_calls = world
    git(work, "switch", "-q", "-c", "chore/raise-floors")
    (work / "mine.txt").write_text("a person's work\n")
    git(work, "add", "mine.txt")
    git(work, "commit", "-q", "-m", "a person's commit")
    git(work, "push", "-q", "origin", "chore/raise-floors")
    git(work, "switch", "-q", "main")
    before = git(tmp_path / "origin.git", "rev-parse", "chore/raise-floors").stdout
    result = run("--measured", measure(**{"b.scopes.confirmed": 12}), "--sha", SHA, "--push")
    assert result.returncode == 2 and "not the bot's (a person)" in result.stderr
    assert git(tmp_path / "origin.git", "rev-parse", "chore/raise-floors").stdout == before and not any(c.startswith("pr create") for c in gh_calls())


@pytest.mark.parametrize("args", [[], ["--measured", "/nowhere"], ["--nothing"]])
def test_a_wrong_input_ends_in_2(world, args):
    assert world[4](*args).returncode == 2


def test_a_wrong_list_of_counts_ends_in_2_and_changes_nothing(world):
    tmp_path, _, floors, _, run, gh_calls = world
    (tmp_path / "measured.txt").write_text("not a line\n")
    assert run("--measured", tmp_path / "measured.txt", "--push").returncode == 2
    assert floors.read_text() == FLOORS and gh_calls() == []
