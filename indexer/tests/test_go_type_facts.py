"""Go's type facts of a file: values with no tree node, so they travel between processes, naming types as the file
writes them; and a symbol of another language never has its facts read as Go's, nor Go's as another language's."""

import contextlib
import io
import pickle

from tree_sitter_language_pack import get_parser

from aidd_indexer.languages.go.type_facts import NONE, GoInterface, GoStruct, GoTypes, type_facts

SRC = b"""package app

import (
	"net/http"
	pw "example.com/x/password"
	"example.com/x/store/v2"
)

type Base struct{ ID int }

type Server struct {
	*Base
	pw.Policy
	api, admin *http.ServeMux
	cfg        struct{ Port int }
	handlers   map[string]func()
}

type Store interface {
	Reader
	Save(x int) error
}

type Number interface{ ~int | ~float64 }

func (s *Server) Run()  {}
func (s Server) Stop()  {}
func (s *Server) Run2() {}

func New() *Server                         { return nil }
func Pair() (a, b *Server, err error)      { return }
func Handler() func()                      { return nil }
func Nothing()                             {}
"""


def _facts(src: bytes) -> GoTypes:
    return type_facts(get_parser("go").parse(src).root_node, src)


def test_a_file_s_facts_name_types_as_the_file_writes_them():
    facts = _facts(SRC)
    assert facts.structs == {
        "Base": GoStruct({"ID": "int"}, ()),
        "Server": GoStruct({"Base": "Base", "Policy": "pw.Policy", "api": "http.ServeMux", "admin": "http.ServeMux",
                            "Port": "int"}, ("Base", "pw.Policy")),
    }
    assert facts.interfaces == {"Store": GoInterface(("Save",), ("Reader",)), "Number": GoInterface((), None)}
    assert facts.methods == {"Server": ("Run", "Stop", "Run2")}
    assert facts.funcs == {"New": ("Server",), "Pair": ("Server", "Server", "error")}
    assert facts.imports == {"http": "net/http", "pw": "example.com/x/password", "store": "example.com/x/store/v2"}


def test_the_facts_travel_between_processes():
    facts = _facts(SRC)
    assert pickle.loads(pickle.dumps(facts)) == facts


def test_facts_of_another_language_are_no_go_facts():
    assert GoTypes.of({"types": {}}) is NONE and GoTypes.of({}) is NONE and GoTypes.of(None) is NONE


def test_a_csharp_call_does_not_read_a_go_homonym_s_facts(tmp_path):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    (tmp_path / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
    (tmp_path / "s.go").write_text("package main\n\ntype S struct{}\n\nfunc (s *S) Configure() {}\n\nfunc main() {}\n")
    (tmp_path / "App.cs").write_text("namespace App;\n\npublic class Startup\n{\n"
                                     "    public void Run(object builder)\n    {\n        builder.Configure<int>();\n"
                                     "    }\n}\n")
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(tmp_path))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    names = {s.id: s.qualified_name for s in res.symbols}
    assert not [c for c in rv.calls if names.get(c.callee_id) == "S.Configure"]
