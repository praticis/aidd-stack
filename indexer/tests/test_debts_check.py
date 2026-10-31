"""The debts check (scripts/debts.py) over a synthetic repo: each finding fails on its case and only on it. No Docker, no
network: it reads files."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import debts as D  # noqa: E402

HEAD = "| ID | The debt | Seen at | Due | Case |\n|---|---|---|---|---|\n"
FIX = "a `fix(csharp)` PR before F1.2"
ROADMAP = ("- F1.2\n  - Debts due here: TD-001 to TD-002 (`docs/tech-debt.md`), C# defects\n"
           "- H5: the debts (`docs/tech-debt.md`, TD-001 to TD-003); TD-003 are due in `fix(csharp)` PRs before F1.2; "
           "none is due in an H5 step.\n")
TESTS = ('import pytest\n\n\ndef case(id, *rest):\n    return pytest.param(id=id, marks=pytest.mark.xfail(strict=True))\n\n\n'
         'CASES = [case("a-first-case"), case("a-second-case"), case("a-third-case")]\n')


def row(id_: str, due: str, cases: str) -> str:
    return f"| {id_} | a debt | somewhere | {due} | {cases} |\n"


ROWS = [row("TD-001", "F1.2", "`a-first-case`"), row("TD-002", "F1.2, or a compiler", "`a-second-case`"),
        row("TD-003", FIX, "`a-third-case`")]


def make(root: Path, rows=ROWS, roadmap=ROADMAP, tests=TESTS, other=""):
    (root / "docs").mkdir(parents=True)
    (root / "indexer" / "tests").mkdir(parents=True)
    (root / "docs" / "tech-debt.md").write_text("# Debts\n\n" + HEAD + "".join(rows))
    (root / "docs" / "ROADMAP.md").write_text(roadmap)
    (root / "docs" / "other.md").write_text(other)
    (root / "indexer" / "tests" / "test_x_debts.py").write_text(tests)
    return D.check(root)


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
    found, _ = make(tmp_path, rows=[ROWS[0], ROWS[1], row("TD-003", "closed in PR #9", "")],
                    roadmap=ROADMAP.replace("; TD-003 are due", "; none are due"))
    assert found == ["`a-third-case` (test_x_debts.py) is named by no debt"]
    found, _ = make(tmp_path / "again", rows=ROWS[:2] + [row("TD-003", FIX, "")])
    assert "TD-003: names no case" in found


def test_a_test_module_whose_cases_are_not_strict_is_found(tmp_path):
    found, _ = make(tmp_path, tests=TESTS.replace("strict=True", "strict=False"))
    assert found == ["test_x_debts.py: its cases are not strict xfails"]


def test_a_debt_missing_from_the_roadmaps_list_of_its_due_is_found(tmp_path):
    found, _ = make(tmp_path, roadmap=ROADMAP.replace("TD-001 to TD-002", "TD-001"))
    assert found == ["the ROADMAP's list of the debts due in F1.2 lacks TD-002"]


def test_a_closed_debt_still_listed_in_the_roadmap_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", "closed in PR #9", "`a-third-case`")])
    assert found == ["the ROADMAP's list of the debts due in a `fix(csharp)` PR before F1.2 names TD-003, which is not open and due there"]


def test_a_roadmap_without_the_list_of_a_due_is_found(tmp_path):
    found, _ = make(tmp_path, roadmap="- nothing\n")
    assert found == ["the ROADMAP has no `Debts due here:` list of the debts due in F1.2",
                     "the ROADMAP has no `due in a `fix(csharp)` PR before F1.2` list of the debts due in a `fix(csharp)` PR before F1.2",
                     "the ROADMAP has no `due in an H5 step` list of the debts due in an H5 step"]


def test_a_debt_due_in_a_fix_of_any_scope_is_checked_against_the_roadmaps_list_of_that_scope(tmp_path):
    rows = ROWS + [row("TD-004", "a `fix(go)` PR before F1.2", "`a-fourth-case`")]
    tests = TESTS.replace('case("a-third-case")]', 'case("a-third-case"), case("a-fourth-case")]')
    assert make(tmp_path / "listed", rows=rows, tests=tests,
                roadmap=ROADMAP + "- Go: TD-004 is due in a `fix(go)` PR before F1.2.\n")[0] == []
    assert make(tmp_path / "missing", rows=rows, tests=tests)[0] == [
        "the ROADMAP has no `due in a `fix(go)` PR before F1.2` list of the debts due in a `fix(go)` PR before F1.2"]
    assert make(tmp_path / "stray", roadmap=ROADMAP + "- Go: TD-001 is due in a `fix(go)` PR before F1.2.\n")[0] == [
        "the ROADMAP's list of the debts due in a `fix(go)` PR before F1.2 names TD-001, which is not open and due there"]


def test_a_debt_due_in_a_step_of_h5_is_checked_against_the_roadmaps_list_of_that_due(tmp_path):
    rows = ROWS + [row("TD-004", "H5 step 6", "`a-fourth-case`")]
    tests = TESTS.replace('case("a-third-case")]', 'case("a-third-case"), case("a-fourth-case")]')
    assert make(tmp_path / "listed", rows=rows, tests=tests,
                roadmap=ROADMAP.replace("none is due in an H5 step", "TD-004 is due in an H5 step"))[0] == []
    assert make(tmp_path / "missing", rows=rows, tests=tests)[0] == [
        "the ROADMAP's list of the debts due in an H5 step lacks TD-004"]


def test_a_due_the_check_does_not_know_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS[:2] + [row("TD-003", "someday", "`a-third-case`")])
    assert found[0].startswith("TD-003: a due the check does not know ('someday')")


def test_a_document_that_names_a_debt_the_register_lacks_is_found(tmp_path):
    found, _ = make(tmp_path, other="see TD-007 to TD-008\n")
    assert found == ["docs/other.md names TD-007, which the register lacks",
                     "docs/other.md names TD-008, which the register lacks"]


def test_a_debt_listed_twice_is_found(tmp_path):
    found, _ = make(tmp_path, rows=ROWS + [ROWS[0]])
    assert "TD-001: listed twice" in found


@pytest.mark.parametrize("text,ids", [("TD-001 to TD-003", {"TD-001", "TD-002", "TD-003"}),
                                      ("TD-005, TD-007 and TD-009 to TD-010", {"TD-005", "TD-007", "TD-009", "TD-010"}),
                                      ("no debts here", set())])
def test_a_range_is_expanded(text, ids):
    assert D.listed(text) == ids
