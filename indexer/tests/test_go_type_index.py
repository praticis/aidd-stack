"""Go's answers to the type questions across files: a type of the repo by its package's dotted directory and its name,
and `Unknown`, with its reason, for what the repo does not declare."""

import contextlib
import io

from aidd_indexer.core.types import Field, TypeRef
from aidd_indexer.languages.go.type_index import NO_FIELD, NO_METHODS, NOT_REQUIRED, OUTSIDE, UNDECLARED

APP = """package app

import (
	"io"

	"example.com/x/store"
	"github.com/gin-gonic/gin"
)

type Deps struct{ Repo *store.Mem }

type Server struct {
	*Deps
	router *gin.Engine
}

type Reader interface{ io.Reader }

type Saver interface{ Save() }

type Both interface {
	Saver
	Load()
}

func New() (*Server, error) { return nil, nil }
"""
STORE = "package store\n\ntype Mem struct{}\n\nfunc (m *Mem) Save() {}\n\nfunc (m *Mem) Load() {}\n"
SERVER, BOTH = TypeRef("app", "Server"), TypeRef("app", "Both")


def _index(root):
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.model import RepoInfo
    for rel, body in {"go.mod": "module example.com/x\n\ngo 1.22\n", "app/app.go": APP, "store/store.go": STORE}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_tree(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))
    return res.types.of("go")


def test_a_type_by_the_package_its_name_points_to(tmp_path):
    go = _index(tmp_path)
    assert go.type_named("store.Mem", "app/app.go") == TypeRef("store", "Mem")
    assert go.type_named("gin.Engine", "app/app.go") == OUTSIDE
    assert go.return_type("New", "app/app.go") == SERVER and go.return_type("Old", "app/app.go") == UNDECLARED


def test_a_field_its_own_or_promoted(tmp_path):
    go = _index(tmp_path)
    assert go.field(SERVER, "Repo") == Field(TypeRef("store", "Mem"), "store.Mem", True)
    assert go.field(SERVER, "router") == Field(OUTSIDE, "gin.Engine", False)
    assert go.field(SERVER, "nope") == NO_FIELD
    assert go.bases(SERVER) == [TypeRef("app", "Deps")] and go.bases(TypeRef("app", "Reader")) == [OUTSIDE]


def test_an_interface_its_methods_and_who_implements_it(tmp_path):
    go = _index(tmp_path)
    assert go.implementers(BOTH) == [TypeRef("store", "Mem")]
    assert go.method(BOTH, "Save") == TypeRef("app", "Saver") and go.method(BOTH, "Load") == BOTH
    assert go.method(BOTH, "Run") == NOT_REQUIRED
    assert go.implementers(TypeRef("app", "Reader")) == NO_METHODS      # `io.Reader`'s methods are not the repo's
