"""The attribution's probe (scripts/judgment/answers.py): what a tree's extraction records as the type of each method
call's receiver, over synthetic repos. The tree's own typing is the current one; a stand-in plays another tree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "judgment"))
import answers as A  # noqa: E402
import aidd_indexer  # noqa: E402
from aidd_indexer import languages  # noqa: E402

GO = '''package a

func f() {
	h := &T{}
	h.Do()
	g := func() {
		h.Do()
		func() { h.Undo() }()
	}
	s := &S{}
	s.repo.Find()
	other.Call()
	_ = g
}
'''

PY = '''class Repo:
    def find(self):
        return self.db.get()


def handler(repo):
    repo.find()

    def inner():
        repo.find()
        go = lambda: repo.find()
    return inner


later = lambda r: r.find()
other.call()
print(later)
'''


def make(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        path = root / "r" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def rows(root: Path, lang: str) -> list:
    return A.survey(root, "r", lang)[0]


def every_receiver_but_other(call, receiver, src, index=None):
    return None if src[receiver.start_byte:receiver.end_byte] == b"other" else ("T", ())


@pytest.fixture
def go(tmp_path):
    return make(tmp_path, {"a.go": GO, "vendor/v.go": GO, ".git/g.go": GO})


@pytest.fixture
def py(tmp_path):
    return make(tmp_path, {"a.py": PY, ".venv/v.py": PY, "b.go": GO})


@pytest.fixture
def typed_python(monkeypatch):
    monkeypatch.setattr(languages.by_id("python"), "call_receiver", every_receiver_but_other)


def test_a_method_called_on_a_typed_name_gets_the_type_its_declaration_gives(go):
    got = {(r["line"], r["receiver"]): r["type"] for r in rows(go, "go")}
    assert got[(5, "h")] == "T" and got[(11, "s.repo")] == "S"


def test_the_go_closures_between_the_use_and_the_function_are_counted(go):
    got = {(r["line"], r["receiver"]): r["closures"] for r in rows(go, "go")}
    assert (got[(5, "h")], got[(7, "h")], got[(8, "h")], got[(11, "s.repo")]) == (0, 1, 2, 0)


def test_a_receiver_the_tree_does_not_type_gives_no_row(go):
    assert all(r["receiver"] != "other" for r in rows(go, "go"))


def test_a_row_carries_the_repo_the_file_and_the_source_line(go):
    first = rows(go, "go")[0]
    assert (first["repo"], first["file"], first["line"], first["src"]) == ("r", "a.go", 5, "h.Do()")


def test_only_the_files_the_extraction_reads_are_surveyed(go):
    assert {r["file"] for r in rows(go, "go")} == {"a.go"}


def test_the_type_is_the_trees_own(go, monkeypatch):
    monkeypatch.setattr(languages.by_id("go"), "call_receiver", lambda call, receiver, src, index=None: None)
    assert rows(go, "go") == []


def test_a_python_closure_is_a_lambda_or_a_function_defined_in_another(py, typed_python):
    got = {(r["line"], r["receiver"]): r["closures"] for r in rows(py, "python")}
    assert got == {(3, "self.db"): 0, (7, "repo"): 0, (10, "repo"): 1, (11, "repo"): 2, (15, "r"): 1}


def test_only_the_languages_files_are_surveyed(py, typed_python):
    assert {r["file"] for r in rows(py, "python")} == {"a.py"}


def test_a_tree_that_types_nothing_gives_no_row_and_still_counts_the_calls_on_a_receiver(py, monkeypatch, capsys):
    monkeypatch.setattr(languages.by_id("python"), "call_receiver", lambda call, receiver, src, index=None: None)
    assert A.main(["python", str(py), "r"]) == 0
    out, err = capsys.readouterr()
    assert out == "" and "r: 0 typed of 6 method calls on a receiver" in err


def test_the_probe_prints_a_json_line_per_row_the_counts_and_the_tree_it_imported(go, capsys):
    assert A.main(["go", str(go), "r"]) == 0
    out, err = capsys.readouterr()
    assert [json.loads(line) for line in out.splitlines()] == rows(go, "go")
    assert "r: 4 typed of 5 method calls on a receiver" in err
    assert f"aidd_indexer from {Path(aidd_indexer.__file__).parent}" in err


def test_a_file_the_tree_cannot_extract_is_left_out_and_named(py, typed_python, monkeypatch, capsys):
    (py / "r" / "c.py").write_text("x.y()\n")
    real = A.extract_file
    monkeypatch.setattr(A, "extract_file",
                        lambda repo, file: (None, ["a.py: extraction failed"]) if file.path == "a.py" else real(repo, file))
    assert A.main(["python", str(py), "r"]) == 0
    out, err = capsys.readouterr()
    assert [json.loads(line)["file"] for line in out.splitlines()] == ["c.py"] and "r: a.py: extraction failed" in err


def test_a_query_that_finds_fewer_calls_than_the_extractor_recorded_is_an_error(go, monkeypatch, capsys):
    real = A.call_nodes
    monkeypatch.setattr(A, "call_nodes", lambda fx: real(fx)[:-1])
    assert A.main(["go", str(go), "r"]) == 2
    assert "r/a.go" in capsys.readouterr().err


def test_calls_the_query_finds_on_other_lines_than_the_extractor_recorded_are_an_error(go, monkeypatch, capsys):
    real = A.call_nodes
    monkeypatch.setattr(A, "call_nodes", lambda fx: real(fx)[::-1])
    assert A.main(["go", str(go), "r"]) == 2
    assert "r/a.go" in capsys.readouterr().err


def test_an_unknown_language_is_an_error(go, capsys):
    assert A.main(["cobol", str(go), "r"]) == 2
    assert "cobol" in capsys.readouterr().err
