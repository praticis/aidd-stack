"""The parts of .github/workflows/indexer.yml that guard the bounds of the graph, run as the workflow runs them, in a git repository made
for the purpose: which pull requests skip the heavy jobs, what the `debts` job refuses in one that changes only the bounds, and how the
`floors` job is set up (read-only token for the checks, the bot's own secret for writing, one run at a time, passing without the secret)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
# test.sh mounts the workflow, which is outside the tree it mounts, and says where
WORKFLOW_FILE = Path(os.environ["AIDD_WORKFLOW"])
FLOORS = "indexer/scripts/checks/reference_floors.txt"
BOUNDS = "a.receiver-type.confirmed :: >= 100 :: n\na.receiver-type.contradicted :: <= 5 :: n\n"

WORKFLOW = yaml.safe_load(WORKFLOW_FILE.read_text())
JOBS = WORKFLOW["jobs"]


def step(job: str, contains: str) -> dict:
    found = [s for s in JOBS[job]["steps"] if contains in (s.get("name", "") + s.get("run", "") + s.get("id", ""))]
    assert len(found) == 1, f"{job}: {len(found)} steps with {contains!r}"
    return found[0]


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, capture_output=True, text=True, check=True)


def pull_request(tmp_path, files: dict[str, str], base: dict[str, str] | None = None):
    """A repository whose HEAD^1 is main (with BASE's files) and whose HEAD is the merge of the pull request that writes FILES."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "indexer" / "scripts" / "checks").mkdir(parents=True)
    shutil.copytree(SCRIPTS, repo / "indexer" / "scripts", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    for name, text in {FLOORS: BOUNDS, "docs/a.md": "a\n", **(base or {})}.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "main")
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the pull request")
    return repo


def bash(repo, script, tmp_path, **env):
    summary = tmp_path / "summary.md"
    output = tmp_path / "output.txt"
    done = subprocess.run(["bash", "-eo", "pipefail", "-c", script], cwd=repo, capture_output=True, text=True,
                          env={**os.environ, "RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_OUTPUT": str(output), **env})
    return done, (output.read_text() if output.exists() else "")


# -- which pull requests run the heavy jobs ----------------------------------------------------------------------------------

def indexer_output(tmp_path, files):
    repo = pull_request(tmp_path, files)
    script = step("changes", "diff")["run"].replace("${{ github.event_name }}", "pull_request")
    done, output = bash(repo, script, tmp_path)
    assert done.returncode == 0, done.stderr
    return dict(line.split("=") for line in output.splitlines())["indexer"]


@pytest.mark.parametrize("files,runs", [
    ({FLOORS: BOUNDS.replace(">= 100", ">= 130")}, "false"),                                   # the bounds alone: a raise by the bot
    ({FLOORS: BOUNDS.replace(">= 100", ">= 130"), "docs/a.md": "b\n"}, "false"),                # and a doc
    ({FLOORS: BOUNDS.replace(">= 100", ">= 130"), "indexer/scripts/judgment/x.py": "x = 1\n"}, "true"),   # a change of the code carries its bounds
    ({"indexer/scripts/checks/docs_ceilings.txt": "x\n"}, "false"),
    ({"indexer/scripts/checks/reference.sh": "#!/bin/sh\n"}, "true"),
    ({"docs/a.md": "b\n"}, "false")])
def test_a_pull_request_that_only_changes_the_bounds_runs_no_heavy_job_and_one_that_changes_the_code_does(tmp_path, files, runs):
    assert indexer_output(tmp_path, files) == runs


# -- what the debts job refuses in one that runs none ---------------------------------------------------------------------------

def refuses(tmp_path, floors_text):
    repo = pull_request(tmp_path, {FLOORS: floors_text})
    needs_none = step("debts", "only-raises")
    assert needs_none["if"] == "github.event_name == 'pull_request' && needs.changes.outputs.indexer != 'true'"
    done, _ = bash(repo, needs_none["run"], tmp_path)
    return done


def test_a_raise_passes_the_check_of_a_pull_request_that_changes_only_the_bounds(tmp_path):
    assert refuses(tmp_path, BOUNDS.replace(">= 100", ">= 130").replace("<= 5", "<= 2")).returncode == 0


@pytest.mark.parametrize("floors_text,says", [
    (BOUNDS.replace(">= 100", ">= 99"), "now >= 99"),
    (BOUNDS.replace("<= 5", "<= 6"), "now <= 6"),
    ("a.receiver-type.confirmed :: >= 100 :: n\n", "deleted"),
    (BOUNDS + "b.scopes.confirmed :: >= 1 :: n\n", "added")])
def test_a_bound_lowered_deleted_or_added_fails_it(tmp_path, floors_text, says):
    done = refuses(tmp_path, floors_text)
    assert done.returncode != 0 and says in (tmp_path / "summary.md").read_text()


def test_a_pull_request_that_does_not_touch_the_bounds_passes_it(tmp_path):
    repo = pull_request(tmp_path, {"docs/a.md": "b\n"})
    assert bash(repo, step("debts", "only-raises")["run"], tmp_path)[0].returncode == 0


def test_the_debts_job_waits_for_the_changes_it_reads_and_looks_at_the_pull_requests_parent():
    assert JOBS["debts"]["needs"] == "changes"
    assert next(s for s in JOBS["debts"]["steps"] if s.get("uses", "").startswith("actions/checkout"))["with"]["fetch-depth"] == 2


# -- the floors job -----------------------------------------------------------------------------------------------------------

def test_the_floors_job_runs_on_main_after_the_graph_and_the_rows_are_made_and_never_on_a_pull_request():
    job = JOBS["floors"]
    assert set(job["needs"]) == {"changes", "micro", "rows"}
    assert "github.event_name != 'pull_request'" in job["if"] and "github.ref == 'refs/heads/main'" in job["if"]


def test_the_floors_job_has_one_run_at_a_time_and_a_newer_one_replaces_the_older():
    assert JOBS["floors"]["concurrency"] == {"group": "floors", "cancel-in-progress": True}


def test_nothing_writes_with_the_workflows_own_token_and_the_bot_has_a_token_of_its_own():
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert all("permissions" not in job or "write" not in str(job["permissions"]) for job in JOBS.values())
    env = JOBS["floors"]["env"]
    assert env["GH_TOKEN"] == "${{ secrets.FLOORS_BOT_TOKEN || github.token }}" and env["HAS_TOKEN"] == "${{ secrets.FLOORS_BOT_TOKEN != '' }}"
    assert next(s for s in JOBS["floors"]["steps"] if s.get("uses", "").startswith("actions/checkout"))["with"]["token"] == env["GH_TOKEN"]


def test_the_floors_job_pushes_only_with_the_secret_and_otherwise_says_what_it_would_raise(tmp_path):
    script = step("floors", "floors.sh")["run"]
    stub = tmp_path / "indexer" / "scripts"
    stub.mkdir(parents=True)
    (stub / "floors.sh").write_text('#!/bin/bash\necho "args: $*"\n')
    (stub / "floors.sh").chmod(0o755)
    (tmp_path / "out").mkdir()
    for token, pushes in (("true", True), ("false", False)):
        done, _ = bash(tmp_path, script, tmp_path, HAS_TOKEN=token, GITHUB_SHA="abc", RUNNER_TEMP=str(tmp_path))
        text = (tmp_path / "summary.md").read_text()
        assert done.returncode == 0 and (" --push" in text.split("args:")[-1]) is pushes and ("No FLOORS_BOT_TOKEN" in text) is not pushes
        (tmp_path / "summary.md").unlink()


def test_the_floors_job_fails_when_the_bot_does_a_bound_main_does_not_hold_or_the_scorecard_did_not_run(tmp_path):
    script = step("floors", "floors.sh")["run"]
    stub = tmp_path / "indexer" / "scripts"
    stub.mkdir(parents=True)
    (stub / "floors.sh").write_text("#!/bin/bash\necho an alarm >&2\nexit 1\n")
    (stub / "floors.sh").chmod(0o755)
    assert bash(tmp_path, script, tmp_path, HAS_TOKEN="false", GITHUB_SHA="abc")[0].returncode == 1   # through `tee`, by pipefail
    measure = step("floors", "reference.sh")["run"]
    (tmp_path / "indexer" / "scripts" / "checks").mkdir(parents=True)
    ref = tmp_path / "indexer" / "scripts" / "checks" / "reference.sh"
    for code, ok in ((1, True), (2, False)):
        ref.write_text(f"#!/bin/bash\necho report\nexit {code}\n")
        ref.chmod(0o755)
        done, _ = bash(tmp_path, measure.replace("${{ steps.key.outputs.dir }}", "base-x"), tmp_path, AIDD_CORPUS_HOME=str(tmp_path / "home"))
        assert (done.returncode == 0) is ok   # a bound broken (1) is the bot's to say; anything else did not finish
