"""The Go probe of the attribution (scripts/judgment/go_answers.py): the type a tree's code gives each name a method is
called on, over a synthetic Go repo. The tree's own typing is the current one; a stand-in plays the older tree."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "judgment"))
import go_answers as G  # noqa: E402
from aidd_indexer.languages.go import locals as CURRENT  # noqa: E402

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


@pytest.fixture
def repos(tmp_path):
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "a.go").write_text(GO)
    (tmp_path / "r" / "vendor").mkdir()
    (tmp_path / "r" / "vendor" / "v.go").write_text(GO)
    (tmp_path / "r" / ".git").mkdir()
    (tmp_path / "r" / ".git" / "g.go").write_text(GO)
    return tmp_path


def rows(repos, typing=CURRENT):
    return list(G.answers(repos, "r", typing))


def test_a_method_called_on_a_typed_name_gets_the_type_its_declaration_gives(repos):
    got = {(r["line"], r["receiver"]): (r["type"], r["closures"]) for r in rows(repos)}
    assert got[(5, "h")] == ("T", 0) and got[(11, "s.repo")] == ("S", 0)


def test_the_closures_between_the_use_and_the_function_are_counted(repos):
    got = {(r["line"], r["receiver"]): r["closures"] for r in rows(repos)}
    assert got[(7, "h")] == 1 and got[(8, "h")] == 2


def test_a_name_the_code_does_not_type_gives_no_row(repos):
    assert all(r["receiver"] != "other" for r in rows(repos))


def test_a_row_carries_the_repo_the_file_and_the_source_line(repos):
    first = rows(repos)[0]
    assert (first["repo"], first["file"], first["src"]) == ("r", "a.go", "h.Do()")


def test_the_vendor_folder_and_git_are_not_read(repos):
    assert {r["file"] for r in rows(repos)} == {"a.go"}


def test_the_typing_is_the_trees_own(repos):
    older = SimpleNamespace(receiver_chain=CURRENT.receiver_chain, declared_type=lambda name, use, src: None)
    assert rows(repos, older) == []


def test_the_probe_prints_one_json_line_per_row_and_counts_on_stderr(repos, capsys):
    assert G.main([str(repos), "r"]) == 0
    out, err = capsys.readouterr()
    lines = [json.loads(line) for line in out.splitlines()]
    assert lines == rows(repos) and "r: 4 typed of 5 method calls on a name" in err
