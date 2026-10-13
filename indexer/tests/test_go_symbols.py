"""Go declarations: every item of a `const ( ... )` / `type ( ... )` / `var ( ... )` block is a symbol."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

SRC = '''package ports

// EntryKind is the kind of a statement entry.
type EntryKind string

const Single = 1

const (
	EntryKindPix           EntryKind = "pix"
	EntryKindPixDevolution EntryKind = "pix_devolution"
)

const X, Y = 1, 2

type (
	Entry struct{ Kind EntryKind }
	Reader interface{ Read() Entry }
	Alias = string
)

var ErrNotFound = errors.New("not found")

var (
	ErrA       = errors.New("a")
	ErrB, ErrC = errors.New("b"), errors.New("c")
)

func Load() {
	var local = 1
	_ = local
}
'''


def _symbols(tmp_path: Path) -> dict[str, tuple[str, int, str, str]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    (tmp_path / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
    (tmp_path / "ports").mkdir()
    (tmp_path / "ports" / "statement.go").write_text(SRC)
    repo = RepoInfo(tenant="t", name="x", ref="main", commit_sha="x", root=str(tmp_path))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_and_resolve(repo, convs=[])
    return {s.name: (s.kind, s.line_start, s.signature, s.doc) for s in res.symbols}


def test_every_item_of_a_block_is_a_symbol(tmp_path: Path):
    s = _symbols(tmp_path)
    assert s["EntryKindPix"][:2] == ("const", 9)
    assert s["EntryKindPixDevolution"][:2] == ("const", 10)       # used to be lost: one symbol per block
    assert s["X"][0] == s["Y"][0] == "const"                      # several names in one spec
    assert s["Entry"][0] == "struct" and s["Reader"][0] == "interface" and s["Alias"][0] == "type"


def test_package_vars_are_symbols_locals_are_not(tmp_path: Path):
    s = _symbols(tmp_path)
    assert {"ErrNotFound", "ErrA", "ErrB", "ErrC"} <= {n for n, v in s.items() if v[0] == "var"}
    assert "local" not in s


def test_a_lone_declaration_keeps_keyword_and_doc(tmp_path: Path):
    s = _symbols(tmp_path)
    assert s["EntryKind"][2] == "type EntryKind string"
    assert s["EntryKind"][3] == "EntryKind is the kind of a statement entry."
    assert s["Single"][2] == "const Single = 1"
    assert s["EntryKindPix"][2] == 'EntryKindPix EntryKind = "pix"'
