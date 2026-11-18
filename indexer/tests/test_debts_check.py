"""The debts check (scripts/debts.py) over a synthetic repo: each finding fails on its case and only on it. No Docker, no
network: it reads files. The last test runs the workflow's own step in a git repository made for the purpose."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import debts as D  # noqa: E402

HEAD = "| ID | The debt | Seen at | Due | Case |\n|---|---|---|---|---|\n"
FIX = "a `fix(csharp)` PR before F1.2"
ROADMAP = "- [ ] F1.2 SCIP to the graph\n- [x] F1.8 a ticked item\n"
TESTS = ('import pytest\n\n\ndef case(id, *rest):\n    return pytest.param(id=id, marks=pytest.mark.xfail(strict=True))\n\n\n'
         'CASES = [case("a-first-case"), case("a-second-case"), case("a-third-case")]\n')


def row(id_: str, due: str, cases: str) -> str:
    return f"| {id_} | a debt | somewhere | {due} | {cases} |\n"


ROWS = [row("TD-001", "F1.2", "`a-first-case`"), row("TD-002", "F1.2, or a compiler", "`a-second-case`"),
        row("TD-003", FIX, "`a-third-case`")]
CLOSED = [row(f"TD-00{n}", "closed in PR #9", "") for n in (1, 2, 3)]
NO_TESTS = TESTS.split("CASES")[0] + "CASES = []\n"


def write(root: Path, rows=ROWS, roadmap=ROADMAP, tests=TESTS, other="", more: dict[str, str] | None = None) -> Path:
    files = {"docs/tech-debt.md": "# Debts\n\n" + HEAD + "".join(rows), "docs/ROADMAP.md": roadmap, "docs/other.md": other,
             "indexer/tests/test_x_debts.py": tests, **(more or {})}
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def make(root: Path, **kw):
    return D.check(write(root, **kw))


def test_a_register_that_agrees_with_its_tests_and_the_roadmap_has_no_finding(tmp_path):
    found, summary = make(tmp_path)
    assert found == []
    assert summary == "3 debts (3 open, 0 closed); 3 cases in the debts' tests"


def test_a_case_the_register_names_and_no_test_has_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", FIX, "`a-lost-case`")])
    assert found == ["TD-003: names `a-lost-case`, which no debts' test has",
                     "`a-third-case` (test_x_debts.py) is named by no debt"]


def test_a_case_in_the_tests_that_no_debt_names_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", FIX, "`a-second-case`")])
    assert found == ["`a-third-case` (test_x_debts.py) is named by no debt"]


def test_an_open_debt_without_a_case_is_found_and_a_closed_one_is_not(tmp_path):
    found, summary = make(tmp_path, rows=[ROWS[0], ROWS[1], row("TD-003", "closed in PR #9", "")])
    assert found == ["`a-third-case` (test_x_debts.py) is named by no debt"]
    assert summary == "3 debts (2 open, 1 closed); 3 cases in the debts' tests"
    found, _ = make(tmp_path / "again", rows=ROWS[:2] + [row("TD-003", FIX, "")])
    assert "TD-003: names no case" in found


def test_a_test_module_whose_cases_are_not_strict_is_found(tmp_path):
    found, _ = make(tmp_path, tests=TESTS.replace("strict=True", "strict=False"))
    assert found == ["test_x_debts.py: its cases are not strict xfails"]


def test_a_case_in_two_test_modules_is_found(tmp_path):
    found, _ = make(tmp_path, more={"indexer/tests/test_y_debts.py": TESTS})
    assert found == ["a-first-case: a case of two tests", "a-second-case: a case of two tests",
                     "a-third-case: a case of two tests"]


def test_a_row_without_five_columns_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + ["| TD-003 | a debt | somewhere | `a-third-case` |\n"])
    assert found[0] == "TD-003: a row has 4 columns, not 5"


def test_a_due_the_check_does_not_know_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", "someday", "`a-third-case`")])
    assert found == ["TD-003: a due the check does not know ('someday'): F1.2, a `fix(<scope>)` PR, an H5 step, or closed"]


def test_a_document_that_names_a_debt_the_register_lacks_is_found(tmp_path):
    found, _ = make(tmp_path, other="see TD-007 to TD-008\n")
    assert found == ["docs/other.md names TD-007, which the register lacks",
                     "docs/other.md names TD-008, which the register lacks"]


def test_a_file_of_the_roadmaps_folder_that_names_a_debt_the_register_lacks_is_found(tmp_path):
    found, _ = make(tmp_path, more={"docs/roadmap/phase-1-micro.md": "- [ ] F1.17 see TD-999\n"})
    assert found == ["docs/roadmap/phase-1-micro.md names TD-999, which the register lacks"]


def test_a_debt_listed_twice_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS + [ROWS[0]])
    assert "TD-001: listed twice" in found


@pytest.mark.parametrize("text,ids", [("TD-001 to TD-003", {"TD-001", "TD-002", "TD-003"}),
                                      ("TD-005, TD-007 and TD-009 to TD-010", {"TD-005", "TD-007", "TD-009", "TD-010"}),
                                      ("no debts here", set())])
def test_a_range_is_expanded(text, ids):
    assert D.listed(text) == ids


def test_an_open_debt_that_says_it_has_no_case_yet_is_counted_and_not_found(tmp_path):
    found, summary = make(tmp_path, rows=ROWS[:2] + [row("TD-003", FIX, "none yet: it needs a minimal interface")])
    assert found == ["`a-third-case` (test_x_debts.py) is named by no debt"]
    assert summary == "3 debts (3 open, 0 closed); 3 cases in the debts' tests; 1 open with no case yet"


def test_a_debt_that_says_it_has_no_case_yet_and_names_one_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", FIX, "none yet: but `a-third-case` is one")])
    assert found == ["TD-003: says there is no case yet and names one"]


def test_a_closed_debt_whose_case_is_still_a_strict_xfail_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", "closed in PR #9", "`a-third-case`")])
    assert found == ["TD-003: is closed, and its case `a-third-case` is still a strict xfail of test_x_debts.py"]


def test_an_open_debt_with_an_empty_case_cell_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", FIX, "")])
    assert found == ["`a-third-case` (test_x_debts.py) is named by no debt", "TD-003: names no case"]


def test_f12_ticked_while_a_debt_due_in_it_or_in_a_fix_before_it_is_open_is_found(tmp_path):
    found, _ = make(tmp_path, roadmap=ROADMAP.replace("[ ] F1.2", "[x] F1.2"))
    assert found == ["F1.2 is ticked in docs/ROADMAP.md, and TD-001, TD-002, TD-003 are open and due in it"]


def test_a_fix_due_written_without_before_f12_locks_f12_too(tmp_path):
    rows = ROWS[:2] + [row("TD-003", "`fix(typescript)`", "`a-third-case`")]
    found, _ = make(tmp_path, rows=rows, roadmap=ROADMAP.replace("[ ] F1.2", "[x] F1.2"))
    assert found == ["F1.2 is ticked in docs/ROADMAP.md, and TD-001, TD-002, TD-003 are open and due in it"]


def test_f12_ticked_when_every_debt_due_in_it_is_closed_passes(tmp_path):
    found, summary = make(tmp_path, rows=CLOSED, tests=NO_TESTS, roadmap=ROADMAP.replace("[ ] F1.2", "[x] F1.2"))
    assert found == []
    assert summary == "3 debts (0 open, 3 closed); 0 cases in the debts' tests"


def test_an_item_ticked_in_the_roadmaps_folder_is_read(tmp_path):
    found, _ = make(tmp_path, roadmap="- [ ] U4 another item\n",
                    more={"docs/roadmap/phase-1-micro.md": "## Phase 1\n\n- [x] F1.2 SCIP to the graph\n"})
    assert found == ["F1.2 is ticked in docs/roadmap/phase-1-micro.md, and TD-001, TD-002, TD-003 are open and due in it"]


def test_a_roadmap_without_the_item_its_open_debts_are_due_in_is_found(tmp_path):
    found, _ = make(tmp_path, roadmap="- [ ] U4 another item\n")
    assert found == ["the roadmap has no item F1.2, where 3 open debts are due"]


def test_a_debt_due_in_a_step_of_h5_locks_no_item_yet(tmp_path):
    rows = ROWS[:2] + [row("TD-003", "H5 step 6", "`a-third-case`")]
    assert make(tmp_path, rows=rows, roadmap=ROADMAP + "- [x] F1.17 the steps of H5\n")[0] == []
    assert make(tmp_path / "without", rows=rows)[0] == []


def rows_of(*lines: str) -> list[dict]:
    return D.register(HEAD + "".join(lines))[0]


def test_an_open_debt_whose_due_changed_is_listed_with_its_phase_when_the_phase_changed():
    base = rows_of(*ROWS)
    tree = rows_of(row("TD-001", "a `fix(go)` PR before F1.2", "`a-first-case`"), row("TD-002", "F1.2", "`a-second-case`"),
                   ROWS[2])
    assert D.moved(base, tree) == ['TD-001: "F1.2" → "a `fix(go)` PR before F1.2" (phase: F1.2 → fix(go))',
                                   'TD-002: "F1.2, or a compiler" → "F1.2"']


def test_a_new_debt_a_closed_one_and_a_reopened_one_did_not_move():
    base = rows_of(ROWS[0], CLOSED[1], ROWS[2])
    tree = rows_of(ROWS[0], ROWS[1], CLOSED[2], row("TD-004", "F1.2", "`a-fourth-case`"))
    assert D.moved(base, tree) == []


def test_the_moves_against_a_base_are_listed_warned_on_stderr_and_fail_nothing(tmp_path, capsys):
    root = write(tmp_path / "tree", rows=[row("TD-001", FIX, "`a-first-case`"), *ROWS[1:]])
    base = tmp_path / "base.md"
    base.write_text("# Debts\n\n" + HEAD + "".join(ROWS))
    assert D.main(["--root", str(root), "--base-register", str(base)]) == 0
    out, err = capsys.readouterr()
    assert f'- TD-001: "F1.2" → "{FIX}" (phase: F1.2 → fix(csharp))' in out
    assert "::warning" not in out
    assert err == f'::warning title=A debt\'s due moved::TD-001: "F1.2" → "{FIX}" (phase: F1.2 → fix(csharp))\n'


def test_an_empty_base_register_says_that_nothing_was_compared(tmp_path, capsys):
    (tmp_path / "base.md").write_text("")
    assert D.main(["--root", str(write(tmp_path / "tree")), "--base-register", str(tmp_path / "base.md")]) == 0
    out, err = capsys.readouterr()
    assert "The base register is empty or missing: no due was compared." in out and "No open debt" not in out and err == ""


def test_without_a_base_nothing_is_listed_and_the_check_passes(tmp_path, capsys):
    assert D.main(["--root", str(write(tmp_path))]) == 0
    out, err = capsys.readouterr()
    assert "moved" not in out and err == ""


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, capture_output=True, check=True)


def run_step(tmp_path: Path, pull_request: dict) -> tuple[subprocess.CompletedProcess, str]:
    """The `debts` step of the workflow, as GitHub runs a bash step, on a repository whose HEAD^1 is the base."""
    jobs = yaml.safe_load(Path(os.environ["AIDD_WORKFLOW"]).read_text())["jobs"]
    steps = [s for s in jobs["debts"]["steps"] if "debts.py" in s.get("run", "")]
    assert len(steps) == 1 and steps[0]["shell"] == "bash"
    repo = write(tmp_path / "repo")
    (repo / "indexer" / "scripts").mkdir()
    shutil.copy(SCRIPTS / "debts.py", repo / "indexer" / "scripts" / "debts.py")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    write(repo, **pull_request)
    git(repo, "commit", "-q", "-am", "the pull request")
    env = {**os.environ, "RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    done = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", steps[0]["run"]], cwd=repo, env=env,
                          capture_output=True, text=True)
    return done, (tmp_path / "summary.md").read_text()


def test_the_workflows_debts_step_lists_the_debt_a_pull_request_moved(tmp_path):
    done, summary = run_step(tmp_path, {"rows": [row("TD-001", FIX, "`a-first-case`"), *ROWS[1:]]})
    assert done.returncode == 0, done.stdout + done.stderr
    assert f'- TD-001: "F1.2" → "{FIX}" (phase: F1.2 → fix(csharp))' in summary
    assert "::warning title=A debt's due moved::TD-001" in done.stderr


def test_the_workflows_debts_step_fails_through_tee_when_the_check_finds_something(tmp_path):
    done, summary = run_step(tmp_path, {"roadmap": ROADMAP.replace("[ ] F1.2", "[x] F1.2")})
    assert done.returncode == 1
    assert "F1.2 is ticked in docs/ROADMAP.md" in summary
