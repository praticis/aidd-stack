"""A declarative convention's roles and layouts: what a type is, from its declaration and its bases in the repo,
and which layout the repo uses, detected from its modules or forced."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


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
    assert res.architecture == "split" and res.conventions == ["layouts[split]"]      # what the snapshot records
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
