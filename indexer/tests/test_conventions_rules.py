"""What each kind of rule of a declarative convention reports: the message, the place and the symbol of each violation,
in the order of the rules and, within one, of the records it reads."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import convention_records as R

SPEC = {"id": "hex",
        "layers": {"domain": ["src/domain/**"], "infra": ["src/infra/**"], "api": ["src/api/**"]},
        "roles": {"repository": {"name": ["*Repository"]}},
        "rules": [{"id": "pure", "forbid_import": {"from": "domain", "to": ["infra"]}, "severity": "error"},
                  {"id": "routes", "endpoints_only_in": ["gateway", "api"]},
                  {"id": "repos", "roles_in": {"repository": ["infra"]}},
                  {"http_calls_only_in": ["infra"]}]}

DOMAIN, INFRA, API, SHARED = "src/domain/Order.cs", "src/infra/Db.cs", "src/api/Orders.cs", "src/shared/Money.cs"


def _violation(rule: str, path: str, line: int, message: str, symbol_id: str | None = None,
               severity: str = "warning"):
    from aidd_indexer.core.model import ViolationInfo
    return ViolationInfo(id=f"t/shop@main/violation/hex.{rule}/{path}:{line}", convention="hex", rule=rule,
                         severity=severity, message=message, file_id=path, line=line, symbol_id=symbol_id,
                         evidence=f"shop:{path}:{line}")


def test_each_kind_of_rule_reports_its_violations(tmp_path: Path):
    """An import of a namespace reaches the layer of the files that declare it, when they share one. A role is checked
    only where the layout puts its file. A file no layer holds is shown as `(none)`."""
    from aidd_indexer import conventions
    spec = tmp_path / "convention.yaml"
    spec.write_text(yaml.safe_dump(SPEC))
    repository = R.symbol("OrderRepository", DOMAIN, line=12)
    symbols = [repository, R.symbol("UserRepository", INFRA), R.symbol("CacheRepository", SHARED)]
    res = R.result(files=[R.file(p) for p in (DOMAIN, INFRA, API, SHARED)], symbols=symbols,
                   endpoints=[R.endpoint("GET", "/orders", DOMAIN, 10, handler_id=repository.id),
                              R.endpoint("GET", "/health", API, 4), R.endpoint("POST", "/misc", SHARED, 2)],
                   http_calls=[R.http_call("POST", "/v1/pay", API, 8, caller_id=f"{API}#Pay"),
                               R.http_call("GET", "/v1/ok", INFRA, 5),
                               R.http_call("GET", "/v1/where", SHARED, 3, caller_id=SHARED)])
    imports = [R.import_edge(DOMAIN, "File", INFRA, 3), R.import_edge(DOMAIN, "Module", "m", 4, "Shop.Infra"),
               R.import_edge(DOMAIN, "Module", "m", 5, "Shop.Shared"), R.import_edge(DOMAIN, "Package", "pkg", 6),
               R.import_edge(DOMAIN, "File", "src/gone.cs", 7), R.import_edge(API, "File", INFRA, 2)]
    rv = R.resolved(imports, namespace_files={"Shop.Infra": [INFRA], "Shop.Shared": [DOMAIN, INFRA]})
    conventions.apply(conventions.load([{"path": str(spec)}], "shop"), res, rv)
    assert res.violations == [
        _violation("pure", DOMAIN, 3, f"domain imports infra ({INFRA})", severity="error"),
        _violation("pure", DOMAIN, 4, "domain imports infra (Shop.Infra)", severity="error"),
        _violation("routes", DOMAIN, 10, "GET /orders declared in layer domain, allowed: api, gateway", repository.id),
        _violation("routes", SHARED, 2, "POST /misc declared in layer (none), allowed: api, gateway"),
        _violation("repos", DOMAIN, 12, "repository OrderRepository lives in layer domain, expected: infra",
                   repository.id),
        _violation("rule4", API, 8, "outbound POST /v1/pay from layer api, allowed: infra", f"{API}#Pay"),
        _violation("rule4", SHARED, 3, "outbound GET /v1/where from layer (none), allowed: infra", SHARED),
    ]


@pytest.mark.parametrize("rule,message", [
    ({"id": "two", "endpoints_only_in": ["api"], "http_calls_only_in": ["infra"]},
     "rule #1 'two' names 2 kinds (endpoints_only_in, http_calls_only_in): a rule has one"),
    ({"endpoints_only_in": ["api"], "roles_in": {"handler": ["core"]}},
     "rule #1 names 2 kinds (endpoints_only_in, roles_in): a rule has one"),
])
def test_a_rule_that_names_two_kinds_is_refused(tmp_path: Path, rule, message):
    """The check would run only one of them, so loading refuses the rule, by its id when it has one."""
    from aidd_indexer import conventions
    from aidd_indexer.core.config import ConfigError
    spec = tmp_path / "convention.yaml"
    spec.write_text(yaml.safe_dump({"id": "x", "rules": [rule]}))
    with pytest.raises(ConfigError) as e:
        conventions.load([{"path": str(spec)}], "shop")
    assert message in str(e.value)


HANDLER = "src/Shop/Infra/PlaceOrderHandler.cs"
LAYOUT = {"id": "layout", "layers": {"infra": ["src/*/Infra/**"]}}
HANDLERS = {"id": "handlers", "layers": {"infra": ["src/*/Infra/**"]},
            "roles": {"command-handler": {"extends": ["ICommandHandler"]}},
            "rules": [{"id": "handlers-in-core", "roles_in": {"command-handler": ["core"]}}]}
ROLES_ONLY = {"id": "roles", "roles": {"command-handler": {"extends": ["ICommandHandler"]}}}
RULE_ONLY = {"id": "rule", "layers": {"infra": ["src/*/Infra/**"]},
             "rules": [{"id": "handlers-in-core", "roles_in": {"command-handler": ["core"]}}]}


def _load(tmp_path: Path, *specs: dict) -> list:
    from aidd_indexer import conventions
    for spec in specs:
        (tmp_path / f"{spec['id']}.yaml").write_text(yaml.safe_dump(spec))
    return conventions.load([{"path": str(tmp_path / f"{s['id']}.yaml")} for s in specs], "shop")


def _roles_in(tmp_path: Path, *specs: dict) -> list:
    from aidd_indexer import conventions
    (tmp_path / HANDLER).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / HANDLER).write_text("namespace Shop.Infra;\n\n"
                                    "public class PlaceOrderHandler : ICommandHandler<PlaceOrder> { }\n")
    res = R.result(str(tmp_path), files=[R.file(HANDLER)], symbols=[R.symbol("PlaceOrderHandler", HANDLER, line=3)])
    conventions.apply(_load(tmp_path, *specs), res, R.resolved())
    return sorted((v.convention, v.rule, v.line) for v in res.violations)


@pytest.mark.parametrize("first,second", [(LAYOUT, HANDLERS), (ROLES_ONLY, RULE_ONLY)])
def test_roles_in_reads_its_own_layout_whichever_convention_answers_first(tmp_path: Path, first, second):
    """Two conventions that place a file in one layer, in either order; a convention with no roles reads the role
    another one gives."""
    expected = [(second["id"], "handlers-in-core", 3)]
    assert _roles_in(tmp_path, first, second) == _roles_in(tmp_path, second, first) == expected


def test_a_file_outside_the_extraction_is_placed_by_the_layout(tmp_path: Path):
    conv = _load(tmp_path, LAYOUT)[0]
    conv.prepare(R.context(R.result(str(tmp_path))))
    assert conv.layer_of(R.file("src/Shop/Infra/Late.cs"), None) == "infra"
