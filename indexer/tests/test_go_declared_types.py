"""What Go's type service answers past a local's own declaration: a method promoted from an embedded struct, a type
parameter, which declares no type, and the result a method declares. A strict xfail holds what it should answer."""

import contextlib
import io

import pytest

GOMOD = "module example.com/x\n\ngo 1.22\n"
TYPES = """package main

type A struct{}

func (a *A) Run() {}

type B struct{}

func (b *B) Run() {}

func main() {}
"""


def _xfail(why: str):
    return pytest.mark.xfail(strict=True, reason=f"the resolver {why}")


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


def _calls_of_f(root, body: str, extra: dict[str, str] | None = None) -> set[tuple[str, str]]:
    _write(root, {"go.mod": GOMOD, "types.go": TYPES, "f.go": "package main\n\n" + body, **(extra or {})})
    res, rv = _extract(root)
    names = {s.id: s.qualified_name for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id) == "f"}


INNER = "package inner\n\ntype K struct{}\n\nfunc (k *K) Only() {}\n"

PROMOTED = [
    pytest.param("type C struct{ *A }\n\nfunc f(c *C) {\n\tc.Run()\n}\n", "A.Run", id="from-an-embedded-struct"),
    pytest.param('import "example.com/x/inner"\n\ntype P struct{ *inner.K }\n\ntype G struct{ *P }\n\n'
                 "func f(g *G) {\n\tg.Only()\n}\n", "inner.K.Only", id="two-levels-down-from-another-package"),
    pytest.param("type D struct{ *A }\n\nfunc (d *D) Run() {}\n\nfunc f(d *D) {\n\td.Run()\n}\n", "D.Run",
                 id="its-own-method-wins"),
    pytest.param("type X struct{ *A }\n\ntype E struct {\n\t*B\n\tX\n}\n\nfunc f(e *E) {\n\te.Run()\n}\n", "B.Run",
                 id="the-shallowest-wins"),
]


@pytest.mark.parametrize("body,callee", PROMOTED)
def test_a_call_reaches_a_method_its_receivers_type_promotes(tmp_path, body, callee):
    calls = _calls_of_f(tmp_path, body, {"inner/inner.go": INNER})
    assert {c for c in calls if c[0].endswith((".Run", ".Only"))} == {(callee, "receiver-type")}


GENERIC = [
    pytest.param("func load[T any](v T) T { return v }\n\nfunc f() {\n\tx := load(&A{})\n\tx.Only()\n}\n",
                 id="a-functions-result", marks=_xfail("takes a generic function's type parameter for a declared type")),
    pytest.param("func f[T any](x T) {\n\tx.Only()\n}\n", id="a-parameter",
                 marks=_xfail("takes a generic function's type parameter for a declared type")),
    pytest.param("type Box[T any] struct{ v T }\n\nfunc f(b *Box[*A]) {\n\tb.v.Only()\n}\n", id="a-field",
                 marks=_xfail("takes a generic struct's type parameter for a declared type")),
    pytest.param("type Box[T any] struct{ v T }\n\nfunc (b *Box[T]) get() T { return b.v }\n\n"
                 "func f(b *Box[*A]) {\n\tx := b.get()\n\tx.Only()\n}\n", id="a-methods-result"),
]


@pytest.mark.parametrize("body", GENERIC)
def test_a_type_parameter_types_nothing_so_the_call_is_found_by_name(tmp_path, body):
    calls = _calls_of_f(tmp_path, "func (a *A) Only() {}\n\n" + body)
    assert {c[0] for c in calls if c[0].endswith(".Only")} == {"A.Only"}


NEXT = "func (a *A) next() *B { return &B{} }\n\n"
RESULTS = [
    pytest.param(NEXT + "func f(x *A) {\n\ty := x.next()\n\ty.Run()\n}\n", "B.Run", id="a-methods-result"),
    pytest.param("func (a *A) load() (*B, error) { return &B{}, nil }\n\n"
                 "func f(x *A) {\n\ty, err := x.load()\n\t_ = err\n\ty.Run()\n}\n", "B.Run", id="one-of-two-results"),
    pytest.param("type I interface{ Next() *B }\n\nfunc f(x I) {\n\ty := x.Next()\n\ty.Run()\n}\n", "B.Run",
                 id="an-interfaces-method"),
    pytest.param(NEXT + "type C struct{ *A }\n\nfunc f(c *C) {\n\ty := c.next()\n\ty.Run()\n}\n", "B.Run",
                 id="a-promoted-method"),
    pytest.param(NEXT + "type S struct{ a *A }\n\nfunc f(s *S) {\n\ty := s.a.next()\n\ty.Run()\n}\n", "B.Run",
                 id="a-fields-method"),
    pytest.param(NEXT + "func (b *B) back() *A { return &A{} }\n\n"
                 "func f(x *A) {\n\ty := x.next()\n\tz := y.back()\n\tz.Run()\n}\n", "A.Run", id="a-chain"),
]


@pytest.mark.parametrize("body,callee", RESULTS)
@_xfail("does not type a local by the result its method declares")
def test_a_local_has_the_type_its_methods_result_declares(tmp_path, body, callee):
    calls = _calls_of_f(tmp_path, body)
    assert {c for c in calls if c[0].endswith(".Run")} == {(callee, "receiver-type")}


@_xfail("does not type a local by the result its method declares, so it guesses a homonym")
def test_an_error_a_method_returns_reaches_no_error_type_of_the_repo(tmp_path):
    body = ("type E struct{}\n\nfunc (E) Error() string { return \"\" }\n\nfunc (a *A) check() error { return nil }\n\n"
            "func f(x *A) {\n\terr := x.check()\n\t_ = err.Error()\n}\n")
    assert not {c for c in _calls_of_f(tmp_path, body) if c[0] == "E.Error"}


HANDLERS = """package handlers

import "github.com/gin-gonic/gin"

type Handlers struct{}

func (h *Handlers) Register(g *gin.RouterGroup) {
	g.GET("/users", h.list)
}

func (h *Handlers) list(c *gin.Context) {}
"""
APP = """package app

import "example.com/x/handlers"

type Server struct{ api *handlers.Handlers }

func (s *Server) Handlers() *handlers.Handlers { return s.api }
"""
MAIN = """package main

import (
	"github.com/gin-gonic/gin"
	"example.com/x/app"
)

func wire(s *app.Server, v1 *gin.RouterGroup) {
	h := s.Handlers()
	h.Register(v1)
}

func main() {
	r := gin.Default()
	v1 := r.Group("/api")
	wire(nil, v1)
	r.Run()
}
"""


@pytest.mark.xfail(strict=True, reason="the scanner does not type a local by the result its method declares")
def test_a_group_reaches_the_method_of_a_local_a_method_returns(tmp_path):
    _write(tmp_path, {"go.mod": GOMOD, "handlers/handlers.go": HANDLERS, "app/app.go": APP, "main.go": MAIN})
    res, _ = _extract(tmp_path)
    assert {(e.method, e.path) for e in res.endpoints} == {("GET", "/api/users")}
