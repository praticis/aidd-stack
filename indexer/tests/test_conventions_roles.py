"""A declarative convention's roles and layouts: what a type is, from its declaration and its bases in the repo,
and which layout the repo uses, detected from its modules or forced."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import convention_records as R


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


@pytest.mark.parametrize("header,bases", [
    ("public class PlaceOrderHandler(IServiceProvider provider) : ICommandHandler<PlaceOrder>", ["ICommandHandler"]),
    ("public class Repo<T> : Base<Dictionary<string, T>>, IRepo<T> where T : class, new()", ["Base", "IRepo"]),
    ('[Route("api/[controller]")] public class OrdersController : ControllerBase', ["ControllerBase"]),
    ("public class Maybe : IComparer<Order?>, IEquatable?", ["IComparer", "IEquatable"]),
    ("public class Handler : Shop.Core.HandlerBase<PlaceOrder>", ["HandlerBase"]),
    ("public record CreateOrder(string Name) : IRequest<Guid>;", ["IRequest"]),
    ("public class Plain", []),
    ("export class Store extends Base<Order> implements Reader, Writer<Order> {", ["Base", "Reader", "Writer"]),
    ("public interface Repo extends Reader, Writer {", ["Reader", "Writer"]),
    ("class Order(Base, mixins.Audited):", ["Base", "Audited"]),
    ("class Order(Base, metaclass=ABCMeta):", ["Base"]),
    ("class Order:", []),
])
def test_the_simple_names_of_a_declarations_bases(header, bases):
    from aidd_indexer.conventions.declarative import base_names
    assert base_names(header) == bases


DECLARATIONS = {
    "Multi.cs": "namespace Shop;\n\npublic class PlaceOrderHandler\n    : HandlerBase<PlaceOrder>,\n      IAudited\n{\n}\n",
    "Records.cs": "public record PlaceOrder(string Id) : IRequest;\npublic class Gateway(HttpClient http) { }\n",
    "Late.cs": "public class Late\n" + "\n" * 14 + "    : IAudited\n{\n}\n",
    "Cycle.cs": "public class Left : Right { }\npublic class Right : Left, IAudited { }\n",
}

# (name, file, line, signature); Missing.cs is in the extraction but not on disk, Elsewhere.cs is in neither
DECLARED = [
    ("PlaceOrderHandler", "Multi.cs", 3, "public class PlaceOrderHandler"),
    ("PlaceOrder", "Records.cs", 1, "public record PlaceOrder(string Id) : IRequest"),
    ("Gateway", "Records.cs", 2, "public class Gateway(HttpClient http)"),
    ("Late", "Late.cs", 1, "public class Late : IAudited"),
    ("Left", "Cycle.cs", 1, "public class Left : Right"),
    ("Right", "Cycle.cs", 2, "public class Right : Left, IAudited"),
    ("GhostA", "Missing.cs", 1, "class  GhostA  (HttpClient  http)"),
    ("GhostB", "Elsewhere.cs", 1, "class  GhostB  (HttpClient  http)"),
    ("GhostC", "Records.cs", 9, "class  GhostC  (HttpClient  http)"),
]


def test_a_types_declaration_is_read_from_its_source(tmp_path: Path):
    """From its line to the first that opens its body or ends with `;`, at most 15 lines, whitespace collapsed. With no
    such line, the signature, collapsed too; as written when the extraction lacks its file. A cycle of bases ends."""
    from aidd_indexer.conventions.declarative import DeclarativeConvention
    for rel, text in DECLARATIONS.items():
        (tmp_path / rel).write_text(text)
    symbols = [R.symbol(name, f, line, sig) for name, f, line, sig in DECLARED]
    res = R.result(str(tmp_path), files=[R.file(p) for p in (*DECLARATIONS, "Missing.cs")], symbols=symbols)
    spec = tmp_path / "convention.yaml"
    spec.write_text(yaml.safe_dump({"id": "decl", "roles": {"audited": {"extends": ["IAudited"]},
                                                             "client": {"declares": ["(HttpClient http)"]}}}))
    conv = DeclarativeConvention(spec)
    conv.prepare(R.context(res))
    assert {s.name: conv.role_of(s, None) for s in symbols} == {
        "PlaceOrderHandler": "audited", "PlaceOrder": None, "Gateway": "client", "Late": None,
        "Left": "audited", "Right": "audited", "GhostA": "client", "GhostB": None, "GhostC": "client"}
