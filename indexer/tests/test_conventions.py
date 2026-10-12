"""The conventions seam: a declarative convention layers files, refines target hints and emits
Violation candidates — and with no convention configured the result is untouched."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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
    visible once a convention declares them (F0.4.5)."""
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


ROLE_REPO = {
    "src/Shop.Api/Shop.Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n',
    "src/Shop.Api/Controllers/OrdersController.cs": (
        "namespace Shop.Api.Controllers;\n\n[ApiController]\n[Route(\"api/[controller]\")]\n"
        "public class OrdersController : ControllerBase { }\n"),
    "src/Shop.Core/Shop.Core.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
    "src/Shop.Core/Handlers/HandlerBase.cs": "namespace Shop.Core.Handlers;\n\npublic abstract class HandlerBase<T> : ICommandHandler<T> { }\n",
    "src/Shop.Core/Handlers/PlaceOrderHandler.cs": (
        "namespace Shop.Core.Handlers;\n\npublic class PlaceOrderHandler\n    : HandlerBase<PlaceOrder>,\n      IDisposable\n{\n"
        "    public Task Handle(PlaceOrder c) => Task.CompletedTask;\n}\n"),
    "src/Shop.Core/Queries/IOrderQuery.cs": "namespace Shop.Core.Queries;\n\npublic interface IOrderQuery { }\n",
    "src/Shop.Core/Http/BillingClient.cs": "namespace Shop.Core.Http;\n\npublic class BillingClient(HttpClient http) { }\n",
    "src/Shop.Api/Misc/RefundHandler.cs": "namespace Shop.Api.Misc;\n\npublic class RefundHandler : ICommandHandler<Refund> { }\n",
}

ROLE_SPEC = {
    "id": "layouts",
    "roles": {"controller": {"extends": ["ControllerBase"], "layer": "api"},
              "command-handler": {"extends": ["ICommandHandler"], "layer": "core"},
              "query": {"name": ["I*Query"], "layer": "application"},
              "client": {"declares": ["(HttpClient "], "layer": "outbound"}},
    "architectures": {
        "split": {"detect": {"together": ["{svc}.Api", "{svc}.Core"]},
                  "layers": {"api": ["**/*.Api/Controllers/**"], "core": ["**/*.Core/Handlers/**"]}},
        "flat": {"layers": {"api": ["**/*.Api/**"]}}},
    "entry_points": {"roles": {"command-handler": ["Handle"]}},
    "rules": [{"id": "handlers-in-core", "roles_in": {"command-handler": ["core"]}}],
}


def test_roles_and_architectures(tmp_path: Path):
    """Roles come from the declaration (base list across lines and through in-repo bases, type name,
    header text) wherever the type lives; the layout is detected from the modules (or forced); a file
    the layout does not place takes its roles' layer; `roles_in` flags a role the layout puts elsewhere."""
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.config import ConfigError
    from aidd_indexer.core.model import RepoInfo

    root = tmp_path / "shop"
    for rel, text in ROLE_REPO.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    f = tmp_path / "convention.yaml"
    f.write_text(yaml.safe_dump(ROLE_SPEC))
    repo = RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=str(root))

    def run(options=None):
        convs = conventions.load([{"path": str(f), "options": options or {}}], "shop")
        res, _ = extract_and_resolve(repo, convs=convs)
        return convs[0], res, {x.path: x.layer for x in res.files}

    conv, res, layers = run()
    assert conv.architecture == "split" and conv.describe() == "layouts[split]"
    assert {s.name: s.role for s in res.symbols if s.role} == {
        "OrdersController": "controller", "HandlerBase": "command-handler", "PlaceOrderHandler": "command-handler",
        "RefundHandler": "command-handler", "IOrderQuery": "query", "BillingClient": "client"}
    assert layers["src/Shop.Core/Queries/IOrderQuery.cs"] == "application"       # unplaced: the role's layer
    assert layers["src/Shop.Core/Http/BillingClient.cs"] == "outbound"
    assert layers["src/Shop.Api/Misc/RefundHandler.cs"] == "core"                 # unplaced: inferred, not a violation
    assert [(v.rule, v.line) for v in res.violations] == []
    assert {s.name for s in res.symbols if s.is_entry_point} == {"Handle"}

    conv, res, layers = run({"architecture": "flat"})                             # forced: everything in .Api is `api`
    assert conv.architecture == "flat" and layers["src/Shop.Api/Misc/RefundHandler.cs"] == "api"
    assert [(v.rule, v.line) for v in res.violations] == [("handlers-in-core", 3)]
    with pytest.raises(ConfigError):
        run({"architecture": "huge"})

    from aidd_indexer.conventions.declarative import _detected
    mods = ["src/Shop.Api", "src/shared/Org.Bus.Core"]                          # a `.Core` library is not a split service
    assert not _detected({"together": ["{svc}.Api", "{svc}.Core"]}, mods)
    assert _detected({"together": ["{svc}.Api", "{svc}.Core"]}, mods + ["src/Shop.Core"])
    assert _detected({"modules": ["**/*.Core"]}, mods)
