"""The conventions seam: a declarative convention layers files, refines target hints and emits
Violation candidates — and with no convention configured the result is untouched."""
from __future__ import annotations

from pathlib import Path

import yaml

import convention_records as R
from aidd_indexer.conventions.base import Convention

FIX = Path(__file__).parent / "fixtures" / "go-http-mix"


def _run(convs):
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo

    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    return extract_and_resolve(repo, convs=convs)


def test_without_conventions_is_untouched():
    res, _ = _run([])
    assert all(f.layer is None for f in res.files) and all(m.layer is None for m in res.modules)
    assert res.violations == []


def test_declarative_convention(tmp_path: Path):
    from aidd_indexer import conventions
    spec = {
        "id": "hex",
        "layers": {"adapters-in": ["internal/adapters/inbound/**"], "adapters-out": ["internal/adapters/outbound/**"]},
        "targets": {"internal/adapters/outbound/billing/**": "billing-svc"},
        "rules": [
            {"id": "routes-in", "endpoints_only_in": ["adapters-in"], "severity": "warning"},
            {"id": "clients-wrong-layer", "http_calls_only_in": ["adapters-in"], "severity": "error"},   # deliberately wrong → fires
        ],
    }
    p = tmp_path / "convention.yaml"
    p.write_text(yaml.safe_dump(spec))
    convs = conventions.load([{"path": str(p), "repos": ["go-*"]}], FIX.name)
    assert [c.id for c in convs] == ["hex"]
    assert conventions.load([{"path": str(p), "repos": ["other-*"]}], FIX.name) == []   # repo filter

    res, _ = _run(convs)
    layers = {f.path: f.layer for f in res.files if f.layer}
    assert layers["internal/adapters/outbound/billing/client.go"] == "adapters-out"
    assert layers["internal/adapters/inbound/http/server.go"] == "adapters-in"
    assert {m.path: m.layer for m in res.modules}["internal/adapters/outbound/billing"] == "adapters-out"
    assert {c.target_hint for c in res.http_calls} == {"billing-svc"}
    rules = {v.rule for v in res.violations}
    assert rules == {"clients-wrong-layer"}, res.violations           # every route is in adapters-in → no `routes-in`
    assert len(res.violations) == len(res.http_calls)
    v = res.violations[0]
    assert v.convention == "hex" and v.severity == "error" and v.id.startswith("t/go-http-mix@main/violation/hex.clients-wrong-layer/")


SDK_GO = '''package api

import "context"

type Server struct{}
type Gateway struct{}

func (s *Server) Route(method, path string, h func()) {}
func (g *Gateway) DoJSON(ctx context.Context, method, path string, out any) error { return nil }
func (g *Gateway) Do(ctx context.Context, path string) error { return nil }

func ping() {}

func Register(srv *Server, gw *Gateway, ctx context.Context) {
	srv.Route("GET", "/v1/ping", ping)
	_ = gw.DoJSON(ctx, "POST", "/v1/orders", nil)
	_ = gw.Do(ctx, "/v1/health")
}
'''


def _sdk_repo(tmp_path: Path) -> Path:
    root = tmp_path / "svc"
    (root / "internal").mkdir(parents=True)
    (root / "go.mod").write_text("module example.com/svc\n\ngo 1.22\n")
    (root / "internal" / "api.go").write_text(SDK_GO)
    return root


def _http(root: Path, convs):
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.integrations import extract_http
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))
    res, ex = extract_tree(repo, conventions.scan_patterns(convs))
    return extract_http(repo, ex, conventions.scan_patterns(convs))


def test_convention_route_and_client_patterns(tmp_path: Path):
    """An internal SDK's registrar / client methods are invisible to the generic scanner and
    visible once a convention declares them."""
    from aidd_indexer import conventions
    root = _sdk_repo(tmp_path)
    plain = _http(root, [])
    assert plain.endpoints == [] and plain.calls == []

    spec = {"id": "sdk",
            "route_patterns": {"registrars": {"Route": None}},
            "client_patterns": {"methods": {"DoJSON": None}, "receivers": ["gw"]}}
    f = tmp_path / "convention.yaml"
    f.write_text(yaml.safe_dump(spec))
    hr = _http(root, conventions.load([{"path": str(f)}], root.name))
    assert [(e.method, e.path, e.handler_name, e.framework) for e in hr.endpoints] == [("GET", "/v1/ping", "ping", "convention")]
    assert sorted((c.method, c.path, c.via) for c in hr.calls) == [("ANY", "/v1/health", "gw.Do"), ("POST", "/v1/orders", "gw.DoJSON")]


CS_REPO = {
    "src/Shop.Api/Shop.Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n',
    "src/Shop.Api/Domain/Order.cs": "using Shop.Api.Infra;\nusing Shop.Api.Shared;\n\nnamespace Shop.Api.Domain;\n\npublic class Order { }\n",
    "src/Shop.Api/Domain/Money.cs": "namespace Shop.Api.Shared;\n\npublic class Money { }\n",
    "src/Shop.Api/Infra/Store.cs": "namespace Shop.Api.Infra;\n\npublic class Store { }\n",
    "src/Shop.Api/Infra/Clock.cs": "namespace Shop.Api.Shared;\n\npublic class Clock { }\n",
    "src/Shop.Api/Core/PlaceOrderHandler.cs": (
        "namespace Shop.Api.Core;\n\n"
        "public class PlaceOrderHandler(IServiceProvider provider) : ICommandHandler<PlaceOrder>\n{\n"
        "    public Task<bool> Handle(PlaceOrder command, CancellationToken ct) => Task.FromResult(true);\n\n"
        "    public void Dispose() { }\n}\n"),
}


def test_namespace_imports_and_handler_entry_points(tmp_path: Path):
    """C# `using X;` targets X's Module; the rule sees the layer of the files declaring X (one layer
    only), and `members_of` marks `Handle` of a type whose base list names a handler interface."""
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo

    root = tmp_path / "shop"
    for rel, text in CS_REPO.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    spec = {"id": "cs",
            "layers": {"domain": ["src/*/Domain/**"], "infra": ["src/*/Infra/**"], "core": ["src/*/Core/**"]},
            "entry_points": {"members_of": {"signature_contains": ["ICommandHandler<"], "names": ["Handle"]}},
            "rules": [{"id": "domain-is-pure", "forbid_import": {"from": "domain", "to": ["infra"]}, "severity": "error"}]}
    f = tmp_path / "convention.yaml"
    f.write_text(yaml.safe_dump(spec))
    repo = RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=str(root))
    res, rv = extract_and_resolve(repo, convs=conventions.load([{"path": str(f)}], "shop"))

    assert rv.namespace_files["Shop.Api.Infra"] and len(rv.namespace_files["Shop.Api.Shared"]) == 2
    paths = {x.id: x.path for x in res.files}
    # `Shop.Api.Infra` lives only in infra → violation; `Shop.Api.Shared` spans domain and infra → says nothing
    assert [(v.rule, paths[v.file_id], v.line) for v in res.violations] == [("domain-is-pure", "src/Shop.Api/Domain/Order.cs", 1)]
    assert "Shop.Api.Infra" in res.violations[0].message
    eps = {s.name: s.is_entry_point for s in res.symbols if s.kind == "method"}
    assert eps == {"Handle": True, "Dispose": False}

    res2, _ = extract_and_resolve(repo, convs=[])                    # no convention: language heuristic only
    assert not any(s.is_entry_point for s in res2.symbols) and res2.violations == []


def test_dotnet_praticis_extension_is_registered():
    """The packaged convention publishes itself as `dotnet-praticis` in `aidd.conventions` and loads
    its bundled convention.yaml (no path in atlas.yaml)."""
    import tomllib
    from aidd_indexer import conventions
    pkg = Path(__file__).resolve().parents[1] / "conventions" / "dotnet-praticis"
    eps = tomllib.loads((pkg / "pyproject.toml").read_text())["project"]["entry-points"]["aidd.conventions"]
    assert eps == {"dotnet-praticis": "aidd_conventions_dotnet_praticis:DotnetPraticis"}
    conv = conventions.load_one({"id": eps["dotnet-praticis"]})
    assert conv.id == "dotnet-praticis" and [a[0] for a in conv.architectures] == ["layered", "split", "flat"]


class Stub(Convention):
    """Answers each hook from a table, by the element's name or path, and records what it was asked."""

    def __init__(self, id: str, answers: dict, architecture: str | None = None, violations=()):
        self.id, self.architecture, self.answers, self.violations = id, architecture, answers, list(violations)
        self.asked: list[tuple[str, str]] = []
        self.owners: dict[str, str | None] = {}
        self.seen: tuple[dict, dict] | None = None

    def _answer(self, hook: str, key: str):
        self.asked.append((hook, key))
        return self.answers.get((hook, key))

    def role_of(self, symbol, file):
        return self._answer("role", symbol.name)

    def layer_of(self, file, module):
        return self._answer("layer", file.path)

    def target_of(self, call, file):
        return self._answer("target", call.path)

    def is_entry_point(self, symbol, file, owner=None):
        self.owners[symbol.name] = owner.role if owner else None
        return self._answer("entry", symbol.name)

    def check(self, ctx):
        self.seen = (dict(ctx.file_layer), dict(ctx.module_layer))
        return self.violations


def _combined():
    """Two stubs over one repo: `a` is asked first, `b` where `a` gives no answer."""
    files = [R.file(p, m) for p, m in (("a.cs", "m1"), ("b.cs", "m1"), ("c.cs", "m2"), ("d.cs", "m2"),
                                        ("e.cs", "m3"), ("f.cs", "m4"), ("g.cs", "m4"))]
    handler = R.symbol("Handler", "a.cs")
    symbols = [handler, R.symbol("Blank", "a.cs"), R.symbol("Nobody", "a.cs", kind="interface"),
               R.symbol("handle", "a.cs", kind="method", parent_id=handler.id),
               R.symbol("run", "b.cs", kind="function"), R.symbol("go", "b.cs", kind="function"),
               R.symbol("keep", "b.cs", kind="function", is_entry_point=True), R.symbol("LIMIT", "b.cs", kind="const"),
               R.symbol("Orphan", "gone.cs"), R.symbol("lost", "gone.cs", kind="function")]
    calls = [R.http_call("POST", "/a", "a.cs"), R.http_call("POST", "/b", "gone.cs", target_hint="hint")]
    res = R.result(modules=[R.module(m) for m in ("m1", "m2", "m3", "m4")], files=files, symbols=symbols,
                   http_calls=calls)
    a = Stub("a", {("role", "Handler"): "handler", ("role", "Blank"): "", ("layer", "a.cs"): "core",
                   ("layer", "b.cs"): "", ("layer", "c.cs"): "core", ("layer", "f.cs"): "core",
                   ("target", "/a"): "", ("entry", "run"): False}, violations=["va"])
    b = Stub("b", {("role", "Handler"): "other", ("role", "Blank"): "blank", ("layer", "a.cs"): "edge",
                   ("layer", "b.cs"): "core", ("layer", "d.cs"): "edge", ("target", "/a"): "billing",
                   ("entry", "run"): True, ("entry", "go"): True, ("entry", "handle"): True},
             architecture="split", violations=["vb"])
    return res, a, b


def test_the_first_answer_wins_and_the_conventions_after_it_are_not_asked():
    """An empty answer is no answer; for an entry point, False is one. Roles are asked of types only, entry points of
    functions and methods, and an element whose file the extraction lacks is not asked."""
    from aidd_indexer import conventions
    res, a, b = _combined()
    conventions.apply([a, b], res, R.resolved())
    sym = {s.name: s for s in res.symbols}
    assert {n: sym[n].role for n in ("Handler", "Blank", "Nobody", "Orphan")} == {
        "Handler": "handler", "Blank": "blank", "Nobody": None, "Orphan": None}
    assert {f.path: f.layer for f in res.files} == {
        "a.cs": "core", "b.cs": "core", "c.cs": "core", "d.cs": "edge", "e.cs": None, "f.cs": "core", "g.cs": None}
    assert [c.target_hint for c in res.http_calls] == ["billing", "hint"]
    assert {n: sym[n].is_entry_point for n in ("handle", "run", "go", "keep", "LIMIT", "lost")} == {
        "handle": True, "run": False, "go": True, "keep": True, "LIMIT": False, "lost": False}
    eligible = [("role", "Handler"), ("role", "Blank"), ("role", "Nobody"),
                *(("layer", f.path) for f in res.files), ("target", "/a"),
                ("entry", "handle"), ("entry", "run"), ("entry", "go"), ("entry", "keep")]
    assert a.asked == eligible
    assert b.asked == [("role", "Blank"), ("role", "Nobody"), ("layer", "b.cs"), ("layer", "d.cs"), ("layer", "e.cs"),
                       ("layer", "g.cs"), ("target", "/a"), ("entry", "handle"), ("entry", "go"), ("entry", "keep")]


def test_the_rules_run_last_and_see_each_files_and_modules_layer():
    """A module takes the layer its layered files agree on. Entry points are asked after roles, so a method's owner
    has its role."""
    from aidd_indexer import conventions
    res, a, b = _combined()
    conventions.apply([a, b], res, R.resolved())
    layers = {"a.cs": "core", "b.cs": "core", "c.cs": "core", "d.cs": "edge", "f.cs": "core"}
    assert a.seen == b.seen == (layers, {"m1": "core", "m4": "core"})
    assert {m.id: m.layer for m in res.modules} == {"m1": "core", "m2": None, "m3": None, "m4": "core"}
    assert b.owners["handle"] == "handler"
    assert res.violations == ["va", "vb"]
    assert res.conventions == ["a", "b"] and res.architecture == "split"
