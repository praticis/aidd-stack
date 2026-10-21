"""Go's two answers to "what type does the code declare for this value": the resolver's, which types call receivers
for `CALLS`, and the HTTP scanner's, which follows a router into a method of a typed value. Each answers cases the
other misses. A guard holds what one side answers today; a strict xfail holds what the other should answer too. One
answer for both sides has to pass every case here: it gains the xfails and loses no guard."""

import contextlib
import io

import pytest

GOMOD = "module example.com/x\n\ngo 1.22\n"

# -- the scanner: a group's prefix reaches the routes a method of a typed value registers ---------------------------
HANDLERS = """package handlers

import "github.com/gin-gonic/gin"

type Handlers struct{}

func New() *Handlers { return &Handlers{} }

func (h *Handlers) Register(g *gin.RouterGroup) {
	g.GET("/users", h.list)
}

func (h *Handlers) list(c *gin.Context) {}
"""
APP = """package app

import "example.com/x/handlers"

type Server struct{ API *handlers.Handlers }
"""
OTHER = "package other\n\ntype T struct{}\n"
MAIN = """package main

import (
	"github.com/gin-gonic/gin"
	"example.com/x/app"
	"example.com/x/handlers"
	"example.com/x/other"
)

var _, _, _ = app.Server{}, handlers.New, other.T{}
%s
func main() {
	r := gin.Default()
	v1 := r.Group("/api")
	wire(nil, v1)
	r.Run()
}
"""


def _xfail(why: str):
    return pytest.mark.xfail(strict=True, reason=f"the scanner {why}")


ROUTES = [
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := &handlers.Handlers{}\n\th.Register(v1)\n}\n",
                 id="composite-literal"),
    pytest.param("type Server struct{ API *handlers.Handlers }\n\n"
                 "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &Server{}\n\ts.API.Register(v1)\n}\n",
                 id="field"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\tvar h *handlers.Handlers\n"
                 "\th = &handlers.Handlers{}\n\th.Register(v1)\n}\n", id="assignment"),
    pytest.param("func wire(h *other.T, v1 *gin.RouterGroup) {\n\tif true {\n\t\th := &handlers.Handlers{}\n"
                 "\t\th.Register(v1)\n\t}\n}\n", id="block-shadows-a-parameter"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := &handlers.Handlers{}\n\tfunc() {\n"
                 "\t\tfunc() {\n\t\t\th.Register(v1)\n\t\t}()\n\t}()\n}\n", id="closure-in-a-closure"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := handlers.New()\n\th.Register(v1)\n}\n",
                 id="constructor-result", marks=_xfail("does not type a local by its constructor's declared result")),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\tvar h handlers.Handlers\n\th.Register(v1)\n}\n",
                 id="var-declaration", marks=_xfail("does not type a `var` declared without a value")),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) (h *handlers.Handlers) {\n\th.Register(v1)\n"
                 "\treturn\n}\n", id="named-result", marks=_xfail("does not type a named result")),
    pytest.param("type Deps struct{ API *handlers.Handlers }\n\ntype Server struct{ *Deps }\n\n"
                 "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &Server{}\n\ts.API.Register(v1)\n}\n",
                 id="promoted-field", marks=_xfail("does not read a field promoted from an embedded struct")),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &app.Server{}\n\ts.API.Register(v1)\n}\n",
                 id="field-of-another-package", marks=_xfail("reads the fields of its own package's structs only")),
]


def _write(root, files: dict[str, str]) -> None:
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)


def _extract(root):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root))
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(repo)


def _routes(root, wire: str, extra: dict[str, str] | None = None) -> set[tuple[str, str]]:
    _write(root, {"go.mod": GOMOD, "handlers/handlers.go": HANDLERS, "app/app.go": APP, "other/other.go": OTHER,
                  "main.go": MAIN % wire, **(extra or {})})
    res, _ = _extract(root)
    return {(e.method, e.path) for e in res.endpoints}


@pytest.mark.parametrize("wire", ROUTES)
def test_a_group_reaches_the_method_of_a_typed_value(tmp_path, wire):
    assert _routes(tmp_path, wire) == {("GET", "/api/users")}


@_xfail("resolves a field's type with the imports of the file it scans, not of the file that declares the struct")
def test_a_field_type_under_the_alias_of_the_file_that_declares_it(tmp_path):
    server = 'package main\n\nimport h2 "example.com/x/handlers"\n\ntype Server struct{ api *h2.Handlers }\n'
    wire = "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &Server{}\n\ts.api.Register(v1)\n}\n"
    assert _routes(tmp_path, wire, {"server.go": server}) == {("GET", "/api/users")}


def test_a_struct_declared_in_two_files_of_the_package(tmp_path):
    linux = "//go:build linux\n\npackage main\n\ntype Server struct{ other int }\n"
    other = ('//go:build !linux\n\npackage main\n\nimport "example.com/x/handlers"\n\n'
             "type Server struct{ API *handlers.Handlers }\n")
    wire = "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &Server{}\n\ts.API.Register(v1)\n}\n"
    assert _routes(tmp_path, wire, {"a_server.go": linux, "b_server.go": other}) == {("GET", "/api/users")}


# -- the resolver: a method call reaches the method of the receiver's declared type ---------------------------------
TYPES = """package main

type A struct{}

func (a *A) Run() {}

type B struct{}

func (b *B) Run() {}

func main() {}
"""


def _resolver_xfail(why: str):
    return pytest.mark.xfail(strict=True, reason=f"the resolver {why}")


CALLS = [
    pytest.param("func f() {\n\tvar x B\n\tx.Run()\n}\n", "B.Run", id="var-declaration"),
    pytest.param("func f() (x *B) {\n\tx.Run()\n\treturn\n}\n", "B.Run", id="named-result"),
    pytest.param("func f() {\n\tvar x B\n\tfunc() {\n\t\tx := &A{}\n\t\t_ = x\n\t}()\n\tx.Run()\n}\n", "B.Run",
                 id="a-closure-keeps-its-locals", marks=_resolver_xfail("reads a closure's locals as the function's")),
    pytest.param("func f(x *A) {\n\tif true {\n\t\tx := &B{}\n\t\tx.Run()\n\t}\n}\n", "B.Run",
                 id="block-shadows-a-parameter", marks=_resolver_xfail("prefers a parameter to a local that shadows it")),
    pytest.param("func f(x *A) {\n\tfunc() {\n\t\tfunc() {\n\t\t\tx.Run()\n\t\t}()\n\t}()\n}\n", "A.Run",
                 id="closure-in-a-closure", marks=_resolver_xfail("looks one function out, not every one")),
]


def _calls_of_f(root, files: dict[str, str]) -> set[tuple[str, str]]:
    _write(root, {"go.mod": GOMOD, "types.go": TYPES, **files})
    res, rv = _extract(root)
    names = {s.id: s.qualified_name for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id) == "f"}


@pytest.mark.parametrize("body,callee", CALLS)
def test_a_call_reaches_the_method_of_the_declared_type(tmp_path, body, callee):
    assert _calls_of_f(tmp_path, {"f.go": "package main\n\n" + body}) == {(callee, "receiver-type")}


def test_a_hash_in_the_text_of_a_call_is_no_result_number(tmp_path):
    f = ('package main\n\nfunc (a *A) Self() *A { return a }\n\nfunc find(sel string) *A { return &A{} }\n\n'
         'func f() {\n\tx := find("#id").Self()\n\tx.Run()\n}\n')
    assert ("A.Run", "receiver-type") not in _calls_of_f(tmp_path, {"f.go": f})


@_resolver_xfail("reads a struct's fields in the first file that declares it, not in the one that has the field")
def test_a_field_of_a_struct_declared_in_two_files(tmp_path):
    linux = "//go:build linux\n\npackage main\n\ntype S struct{ other int }\n"
    other = "//go:build !linux\n\npackage main\n\ntype S struct{ x *B }\n"
    f = "package main\n\nfunc f(s *S) {\n\ts.x.Run()\n}\n"
    assert _calls_of_f(tmp_path, {"a_s.go": linux, "b_s.go": other, "f.go": f}) == {("B.Run", "receiver-type")}
