"""What each kind of rule of a declarative convention reports: the message, the place and the symbol of each violation,
in the order of the rules and, within one, of the records it reads."""
from __future__ import annotations

from pathlib import Path

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
