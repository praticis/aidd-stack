"""Go's one answer to "what type does the code declare for this value", which the resolver asks to type call
receivers for `CALLS` and the HTTP scanner to follow a router into a method of a typed value. The two sides once had
answers of their own, and each case here is one they gave differently; both sides now pass every one."""

import contextlib
import io

import pytest

GOMOD = "module example.com/x\n\ngo 1.22\n"

# -- the scanner: a group's prefix reaches the routes a method of a typed value registers ---------------------------
HANDLERS = """package handlers

import "github.com/gin-gonic/gin"

type Handlers struct{}

func New() *Handlers { return &Handlers{} }

func NewE() (*Handlers, error) { return &Handlers{}, nil }

func (h *Handlers) With(prefix string) *Handlers { return h }

func (h *Handlers) Copy() (*Handlers, error) { return h, nil }

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
    pytest.param("func wire(h *handlers.Handlers, v1 *gin.RouterGroup) {\n\tif true {\n\t\th := &other.T{}\n\t\t_ = h\n"
                 "\t}\n\th.Register(v1)\n}\n", id="a-block-local-out-of-scope"),
    pytest.param("func wire(h *handlers.Handlers, v1 *gin.RouterGroup) {\n\th, err := h.Copy()\n\t_ = err\n"
                 "\th.Register(v1)\n}\n", id="a-redeclaration-keeps-a-parameters-type"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := &handlers.Handlers{}\n\th, err := h.Copy()\n"
                 "\t_ = err\n\th.Register(v1)\n}\n", id="a-redeclaration-keeps-its-type"),
    pytest.param("func wire(h *handlers.Handlers, v1 *gin.RouterGroup) {\n\th = h.With(\"/v\")\n\th.Register(v1)\n}\n",
                 id="a-plain-assignment-keeps-the-type"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := &handlers.Handlers{}\n\tfunc() {\n"
                 "\t\tfunc() {\n\t\t\th.Register(v1)\n\t\t}()\n\t}()\n}\n", id="closure-in-a-closure"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := handlers.Handlers{}\n\th.Register(v1)\n}\n",
                 id="value-literal"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\tvar h = &handlers.Handlers{}\n\th.Register(v1)\n}\n",
                 id="var-with-a-value"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := handlers.New()\n\th.Register(v1)\n}\n",
                 id="constructor-result"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th, _ := handlers.NewE()\n\th.Register(v1)\n}\n",
                 id="constructor-of-two-results"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\tvar h = handlers.New()\n\th.Register(v1)\n}\n",
                 id="var-with-a-constructor"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\tvar h handlers.Handlers\n\th.Register(v1)\n}\n",
                 id="var-declaration"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) (h *handlers.Handlers) {\n\th.Register(v1)\n"
                 "\treturn\n}\n", id="named-result"),
    pytest.param("type Deps struct{ API *handlers.Handlers }\n\ntype Server struct{ *Deps }\n\n"
                 "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &Server{}\n\ts.API.Register(v1)\n}\n",
                 id="promoted-field"),
    pytest.param("func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &app.Server{}\n\ts.API.Register(v1)\n}\n",
                 id="field-of-another-package"),
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


def test_a_field_type_under_the_alias_of_the_file_that_declares_it(tmp_path):
    server = 'package main\n\nimport h2 "example.com/x/handlers"\n\ntype Server struct{ api *h2.Handlers }\n'
    wire = "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\ts := &Server{}\n\ts.api.Register(v1)\n}\n"
    assert _routes(tmp_path, wire, {"server.go": server}) == {("GET", "/api/users")}


def test_a_generic_type_reaches_its_method(tmp_path):
    box = ('package handlers\n\nimport "github.com/gin-gonic/gin"\n\ntype Box[T any] struct{}\n\n'
           'func (b *Box[T]) Register(g *gin.RouterGroup) {\n\tg.GET("/boxes", b.list)\n}\n\n'
           'func (b *Box[T]) list(c *gin.Context) {}\n')
    wire = "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := &handlers.Box[int]{}\n\th.Register(v1)\n}\n"
    assert _routes(tmp_path, wire, {"handlers/box.go": box}) == {("GET", "/api/boxes"), ("GET", "/users")}


def test_a_package_in_a_directory_with_a_dot(tmp_path):
    main = MAIN.replace('"example.com/x/handlers"', 'handlers "example.com/x/web.handlers"')
    wire = "func wire(_ *other.T, v1 *gin.RouterGroup) {\n\th := &handlers.Handlers{}\n\th.Register(v1)\n}\n"
    _write(tmp_path, {"go.mod": GOMOD, "web.handlers/handlers.go": HANDLERS, "app/app.go": APP.replace(
        '"example.com/x/handlers"', 'handlers "example.com/x/web.handlers"'), "other/other.go": OTHER, "main.go": main % wire})
    res, _ = _extract(tmp_path)
    assert {(e.method, e.path) for e in res.endpoints} == {("GET", "/api/users")}


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


CALLS = [
    pytest.param("func f() {\n\tvar x B\n\tx.Run()\n}\n", "B.Run", id="var-declaration"),
    pytest.param("func f() (x *B) {\n\tx.Run()\n\treturn\n}\n", "B.Run", id="named-result"),
    pytest.param("func f() {\n\tx := B{}\n\tx.Run()\n}\n", "B.Run", id="value-literal"),
    pytest.param("type G[T any] struct{}\n\nfunc (g *G[T]) Run() {}\n\nfunc f() {\n\tx := &G[int]{}\n\tx.Run()\n}\n",
                 "G.Run", id="generic-literal"),
    pytest.param("func newB() (*B, error) { return &B{}, nil }\n\nfunc f() {\n\tx, _ := newB()\n\tx.Run()\n}\n", "B.Run",
                 id="constructor-of-two-results"),
    pytest.param("func f() {\n\tvar x = &B{}\n\tx.Run()\n}\n", "B.Run", id="var-with-a-value"),
    pytest.param("func newB() *B { return &B{} }\n\nfunc f() {\n\tvar x = newB()\n\tx.Run()\n}\n", "B.Run",
                 id="var-with-a-constructor"),
    pytest.param("func f() {\n\tvar x B\n\tfunc() {\n\t\tx := &A{}\n\t\t_ = x\n\t}()\n\tx.Run()\n}\n", "B.Run",
                 id="a-closure-keeps-its-locals"),
    pytest.param("func f(x *A) {\n\tif true {\n\t\tx := &B{}\n\t\tx.Run()\n\t}\n}\n", "B.Run",
                 id="block-shadows-a-parameter"),
    pytest.param("func f(x *A) {\n\tif true {\n\t\tx := &B{}\n\t\t_ = x\n\t}\n\tx.Run()\n}\n", "A.Run",
                 id="a-block-local-out-of-scope"),
    pytest.param("func f(x *A) {\n\tfunc() {\n\t\tfunc() {\n\t\t\tx.Run()\n\t\t}()\n\t}()\n}\n", "A.Run",
                 id="closure-in-a-closure"),
    pytest.param("func (a *A) copy() (*A, error) { return a, nil }\n\nfunc f(x *A) {\n\tx, err := x.copy()\n\t_ = err\n"
                 "\tx.Run()\n}\n", "A.Run", id="a-redeclaration-keeps-a-parameters-type"),
    pytest.param("func (a *A) copy() (*A, error) { return a, nil }\n\nfunc f() {\n\tx := &A{}\n\tx, err := x.copy()\n"
                 "\t_ = err\n\tx.Run()\n}\n", "A.Run", id="a-redeclaration-keeps-its-type"),
    pytest.param("func (a *A) self() *A { return a }\n\nfunc f(x *A) {\n\tx = x.self()\n\tx.Run()\n}\n", "A.Run",
                 id="a-plain-assignment-keeps-the-type"),
]


def _calls_of_f(root, files: dict[str, str]) -> set[tuple[str, str]]:
    _write(root, {"go.mod": GOMOD, "types.go": TYPES, **files})
    res, rv = _extract(root)
    names = {s.id: s.qualified_name for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id) == "f"}


@pytest.mark.parametrize("body,callee", CALLS)
def test_a_call_reaches_the_method_of_the_declared_type(tmp_path, body, callee):
    calls = _calls_of_f(tmp_path, {"f.go": "package main\n\n" + body})
    assert {c for c in calls if c[0].endswith(".Run")} == {(callee, "receiver-type")}


def test_a_hash_in_the_text_of_a_call_is_no_result_number(tmp_path):
    f = ('package main\n\nfunc (a *A) Self() *A { return a }\n\nfunc find(sel string) *A { return &A{} }\n\n'
         'func f() {\n\tx := find("#id").Self()\n\tx.Run()\n}\n')
    assert ("A.Run", "receiver-type") not in _calls_of_f(tmp_path, {"f.go": f})


def test_a_field_of_a_package_in_a_directory_with_a_dot(tmp_path):
    _write(tmp_path, {"go.mod": GOMOD, "types.go": TYPES,
                      "api.v1/f.go": "package apiv1\n\ntype A struct{}\n\nfunc (a *A) Run() {}\n\ntype B struct{}\n\n"
                                     "func (b *B) Run() {}\n\ntype S struct{ x *B }\n\nfunc f(s *S) {\n\ts.x.Run()\n}\n"})
    res, rv = _extract(tmp_path)
    names = {s.id: s.qualified_name for s in res.symbols}
    calls = {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id) == "api.v1.f"}
    assert calls == {("api.v1.B.Run", "receiver-type")}


def test_a_field_of_a_struct_declared_in_two_files(tmp_path):
    linux = "//go:build linux\n\npackage main\n\ntype S struct{ other int }\n"
    other = "//go:build !linux\n\npackage main\n\ntype S struct{ x *B }\n"
    f = "package main\n\nfunc f(s *S) {\n\ts.x.Run()\n}\n"
    assert _calls_of_f(tmp_path, {"a_s.go": linux, "b_s.go": other, "f.go": f}) == {("B.Run", "receiver-type")}
