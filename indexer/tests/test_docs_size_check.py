"""The check of the growth files of docs/ (scripts/checks/docs_size.py): how a ceiling is written, what passes and what does
not, and how the script ends. No Docker, no network: it reads files. The real files are not under the mount of the tests,
so the real list is read for its shape, and the files are made here."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
spec = importlib.util.spec_from_file_location("docs_size", CHECKS / "docs_size.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def make(tmp_path, files: dict[str, int], rules: str):
    for path, size in files.items():
        f = tmp_path / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * size)
    r = tmp_path / "rules.txt"
    r.write_text(rules)
    return ["--root", str(tmp_path), "--rules", str(r)]


def test_the_real_list_is_a_list_of_the_growth_files_with_a_reason_each():
    ceilings = D.load_ceilings((CHECKS / "docs_ceilings.txt").read_text())
    assert {c.path for c in ceilings} == {"docs/golden-questions.md", "docs/handoffs/H5-indexer-refactor.md", "docs/decisions.md",
                                         "docs/ROADMAP.md", "docs/history.md"}
    assert all(c.limit > 40 * 1024 and c.reason for c in ceilings)


def test_a_size_is_in_bytes_or_in_kb_of_1024_bytes_and_a_comment_or_blank_line_is_no_ceiling():
    got = D.load_ceilings("# note\n\n  # another\na.md :: 5 KB :: r\nb.md :: 7 b :: r\nc.md :: 12 :: r\nd.md :: 2kb :: r\n")
    assert [(c.path, c.limit) for c in got] == [("a.md", 5120), ("b.md", 7), ("c.md", 12), ("d.md", 2048)]


def test_the_reason_of_a_ceiling_may_hold_the_separator():
    [c] = D.load_ceilings("a.md :: 1 KB :: one :: two\n")
    assert c.reason == "one :: two"


@pytest.mark.parametrize("text, message", [
    ("a.md\n", "line 1: expected"),
    ("a.md :: 1 KB\n", "line 1: expected"),
    ("a.md ::  :: why\n", "line 1: expected"),
    ("a.md :: big :: why\n", "line 1: the size 'big'"),
    ("a.md :: 0 KB :: why\n", "line 1: the size '0 KB'"),
    ("a.md :: 1.5 KB :: why\n", "line 1: the size '1.5 KB'"),
    ("# c\na.md :: 1 KB :: why\na.md :: 2 KB :: why\n", "line 3: 'a.md' already has a ceiling"),
])
def test_a_ceiling_that_is_wrong_is_refused_with_its_line(text, message):
    with pytest.raises(ValueError, match=message):
        D.load_ceilings(text)


def test_a_file_at_its_ceiling_passes_and_one_byte_over_does_not(tmp_path, capsys):
    args = make(tmp_path, {"docs/a.md": 1024, "docs/b.md": 1025}, "docs/a.md :: 1 KB :: r\ndocs/b.md :: 1 KB :: r\n")
    assert D.main(args) == 1
    out = capsys.readouterr().out
    assert "| `docs/a.md` | 1,024 | 1,024 | 0 | ok |" in out
    assert "| `docs/b.md` | 1,025 | 1,024 | -1 | over |" in out
    assert "`docs/b.md` is 1 bytes over its ceiling (r)" in out


def test_files_under_their_ceilings_end_in_zero_and_the_report_says_the_headroom(tmp_path, capsys):
    args = make(tmp_path, {"docs/a.md": 100}, "docs/a.md :: 1 KB :: r\n")
    assert D.main(args) == 0
    assert "| `docs/a.md` | 100 | 1,024 | 924 | ok |" in capsys.readouterr().out


def test_a_ceiling_whose_file_is_gone_is_a_finding_not_a_silent_pass(tmp_path, capsys):
    args = make(tmp_path, {}, "docs/gone.md :: 1 KB :: r\n")
    assert D.main(args) == 1
    out = capsys.readouterr().out
    assert "| `docs/gone.md` | missing | 1,024 |  | missing |" in out and "has a ceiling and no file" in out


def test_a_directory_is_not_a_file_with_a_size(tmp_path, capsys):
    args = make(tmp_path, {"docs/x/inner.md": 5}, "docs/x :: 1 KB :: r\n")
    assert D.main(args) == 1
    assert "missing" in capsys.readouterr().out


def test_a_list_that_is_wrong_ends_in_two_without_measuring(tmp_path, capsys):
    args = make(tmp_path, {"docs/a.md": 10 ** 6}, "broken\n")
    assert D.main(args) == 2
    assert "line 1: expected" in capsys.readouterr().err


def test_the_size_is_the_bytes_of_the_file_not_its_characters(tmp_path):
    f = tmp_path / "docs" / "u.md"
    f.parent.mkdir()
    f.write_text("·" * 600)
    [row] = D.measure(tmp_path, D.load_ceilings("docs/u.md :: 1 KB :: r\n"))
    assert row.size == 1200 and row.status == "over"
