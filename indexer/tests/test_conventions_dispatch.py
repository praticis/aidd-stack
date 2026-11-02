"""A call on a mediator's bus reaches the handlers of its message: MediatR is built in, and an organization's own
bus is declared by its convention."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


MEDIATR_REPO = {
    "src/Shop/Shop.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n',
    "src/Shop/Orders/CreateOrder.cs": "namespace Shop.Orders;\n\npublic record CreateOrder(string Name) : IRequest<Guid>;\n",
    "src/Shop/Orders/OrderCreator.cs": (                # the handler's name says nothing about the request
        "namespace Shop.Orders;\n\npublic class OrderCreator : IRequestHandler<CreateOrder, Guid>\n{\n"
        "    public Task<Guid> Handle(CreateOrder request, CancellationToken ct) => Task.FromResult(Guid.NewGuid());\n}\n"),
    "src/Shop/Orders/OrderPlaced.cs": "namespace Shop.Orders;\n\npublic record OrderPlaced(Guid Id) : INotification;\n",
    "src/Shop/Orders/EmailOnOrderPlaced.cs": (
        "namespace Shop.Orders;\n\npublic class EmailOnOrderPlaced : INotificationHandler<OrderPlaced>\n{\n"
        "    public Task Handle(OrderPlaced n, CancellationToken ct) => Task.CompletedTask;\n}\n"),
    "src/Shop/Orders/AuditOnOrderPlaced.cs": (
        "namespace Shop.Orders;\n\npublic class AuditOnOrderPlaced : INotificationHandler<OrderPlaced>\n{\n"
        "    public Task Handle(OrderPlaced n, CancellationToken ct) => Task.CompletedTask;\n}\n"),
    "src/Shop/Orders/OrdersController.cs": (
        "namespace Shop.Orders;\n\npublic class OrdersController(IMediator mediator) : ControllerBase\n{\n"
        "    public async Task<Guid> Create(string name)\n    {\n"
        "        var id = await mediator.Send(new CreateOrder(name));\n"
        "        INotification placed = Placed(id);\n"
        "        await mediator.Publish(placed);\n"
        "        await mediator.Send(new Unknown());\n"
        "        return id;\n    }\n\n"
        "    private static OrderPlaced Placed(Guid id) => new OrderPlaced(id);\n}\n"),
    "tests/Shop.Tests/FakeCreator.cs": (               # a test double never receives production calls
        "namespace Shop.Tests;\n\nusing Shop.Orders;\n\npublic class FakeCreator : IRequestHandler<CreateOrder, Guid>\n{\n"
        "    public Task<Guid> Handle(CreateOrder request, CancellationToken ct) => Task.FromResult(Guid.Empty);\n}\n"),
}

BUS_REPO = {
    "src/Shop/Shop.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n',
    "src/Shop/Orders/ShipOrder.cs": "namespace Shop.Orders;\n\npublic record ShipOrder(Guid Id);\n",
    "src/Shop/Orders/Shipping.cs": (
        "namespace Shop.Orders;\n\npublic class Shipping : IHandles<ShipOrder>\n{\n"
        "    public Task Execute(ShipOrder message) => Task.CompletedTask;\n}\n"),
    "src/Shop/Orders/ShipController.cs": (
        "namespace Shop.Orders;\n\npublic class ShipController(IBus bus)\n{\n"
        "    public Task Ship(Guid id) => bus.Dispatch(new ShipOrder(id));\n}\n"),
}


def _write_repo(root: Path, files: dict[str, str]):
    from aidd_indexer.core.model import RepoInfo
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))


def _dispatched(repo, convs):
    from aidd_indexer.cli import extract_and_resolve
    res, rv = extract_and_resolve(repo, convs=convs)
    q = {s.id: s.qualified_name for s in res.symbols}
    return sorted((q[e.caller_id], q[e.callee_id]) for e in rv.calls if e.strategy == "dispatch")


def test_mediatr_is_built_in(tmp_path: Path):
    """`mediator.Send(new X())` reaches the Handle of whoever implements IRequestHandler<X, ..> — by the
    generic argument, never by name — and a published notification each of its handlers, with no
    convention configured: MediatR is a public library, like the HTTP frameworks."""
    repo = _write_repo(tmp_path / "shop", MEDIATR_REPO)
    assert _dispatched(repo, []) == [
        ("Shop.Orders.OrdersController.Create", "Shop.Orders.AuditOnOrderPlaced.Handle"),   # declared INotification,
        ("Shop.Orders.OrdersController.Create", "Shop.Orders.EmailOnOrderPlaced.Handle"),   # created as OrderPlaced
        ("Shop.Orders.OrdersController.Create", "Shop.Orders.OrderCreator.Handle"),
    ]                                                # `Send(new Unknown())`: no handler, no edge; FakeCreator is a test


def test_an_organizations_own_bus_is_declared_by_its_convention(tmp_path: Path):
    from aidd_indexer import conventions
    repo = _write_repo(tmp_path / "shop", BUS_REPO)
    assert _dispatched(repo, []) == []               # an in-house bus is invisible until declared
    f = tmp_path / "convention.yaml"
    f.write_text(yaml.safe_dump({"id": "bus", "dispatch": [{"calls": ["Dispatch"], "handlers": ["IHandles"], "method": "Execute"}]}))
    assert _dispatched(repo, conventions.load([{"path": str(f)}], "shop")) == [
        ("Shop.Orders.ShipController.Ship", "Shop.Orders.Shipping.Execute")]


@pytest.mark.parametrize("dispatch,message", [
    ({"calls": ["Send"]}, "`calls` (bus methods) and `handlers` (generic handler bases) are required"),
    ({"calls": ["Send"], "handlers": ["IRequestHandler"], "methods": "Handle"}, "unknown key(s) methods"),
    ("Send", "each entry is a mapping"),
])
def test_dispatch_config_errors(tmp_path: Path, dispatch, message):
    from aidd_indexer import conventions
    from aidd_indexer.core.config import ConfigError
    f = tmp_path / "convention.yaml"
    f.write_text(yaml.safe_dump({"id": "x", "dispatch": [dispatch]}))
    with pytest.raises(ConfigError, match="dispatch #1") as e:
        conventions.load([{"path": str(f)}], "shop")
    assert message in str(e.value)
