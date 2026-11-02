"""The declarative conventions' known defects. Each case states the right answer and is a strict xfail with the reason:
when the code reaches it, the case passes, the xfail fails the suite, and the mark has to go."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def case(id, *values, why):
    return pytest.param(*values, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


def _write(root: Path, files: dict[str, str]):
    from aidd_indexer.core.model import RepoInfo
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))


def _load(tmp_path: Path, name: str, spec: dict) -> list:
    from aidd_indexer import conventions
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(spec))
    return conventions.load([{"path": str(path)}], "shop")


@pytest.mark.parametrize("rule", [
    case("a-rule-with-two-kinds-is-a-config-error",
         {"id": "two", "endpoints_only_in": ["api"], "http_calls_only_in": ["infra"]},
         why="a rule's first kind in the order the check reads them runs, and the others are ignored"),
])
def test_a_rule_has_one_kind(tmp_path, rule):
    from aidd_indexer.core.config import ConfigError
    with pytest.raises(ConfigError, match="rule #1"):
        _load(tmp_path, "convention", {"id": "x", "rules": [rule]})


PYTHON = {
    "pyproject.toml": "[project]\nname = 'shop'\n",
    "shop/__init__.py": "",
    "shop/models.py": "class Base:\n    pass\n\n\nclass Order(Base):\n    def total(self):\n        return 0\n",
}

CONSTRAINED = {
    "package.json": '{"name": "shop"}\n',
    "src/repo.ts": "export class BaseRepo<T> {}\n\nexport class OrderRepo<T extends object> extends BaseRepo<T> {\n"
                   "  find() {}\n}\n",
}


@pytest.mark.parametrize("files,name,role", [
    case("a-python-class-with-a-body-takes-the-role-of-its-base", PYTHON, "Order", "entity",
         why="a Python class's header has no `{` or `;` to end it, so the lines of its body are read as its bases"),
    case("a-class-with-a-constrained-type-parameter-takes-the-role-of-its-base", CONSTRAINED, "OrderRepo",
         "repository", why="the constraint's `extends` is taken for the class's, and no base is read"),
])
def test_a_type_takes_the_role_of_a_base_its_declaration_names(tmp_path, files, name, role):
    from aidd_indexer.cli import extract_and_resolve
    convs = _load(tmp_path, "convention", {"id": "x", "roles": {"entity": {"extends": ["Base"]},
                                                                "repository": {"extends": ["BaseRepo"]}}})
    res, _ = extract_and_resolve(_write(tmp_path / "shop", files), convs=convs)
    assert {s.name: s.role for s in res.symbols}[name] == role


HANDLER = {
    "src/Shop/Shop.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
    "src/Shop/Infra/PlaceOrderHandler.cs": (
        "namespace Shop.Infra;\n\npublic class PlaceOrderHandler : ICommandHandler<PlaceOrder> { }\n"),
}

# Both place the handler's file in `infra`; only the second has a rule on where a handler lives.
LAYOUT = {"id": "layout", "layers": {"infra": ["src/*/Infra/**"]}}
HANDLERS = {"id": "handlers", "layers": {"infra": ["src/*/Infra/**"]},
            "roles": {"command-handler": {"extends": ["ICommandHandler"]}},
            "rules": [{"id": "handlers-in-core", "roles_in": {"command-handler": ["core"]}}]}


@pytest.mark.parametrize("first,second", [
    case("roles-in-gives-the-same-violations-in-either-order", LAYOUT, HANDLERS,
         why="`roles_in` reads only the files its convention was asked the layer of, so a convention that answers "
             "first hides them"),
])
def test_a_conventions_rules_do_not_depend_on_the_order_of_the_conventions(tmp_path, first, second):
    from aidd_indexer.cli import extract_and_resolve
    repo = _write(tmp_path / "shop", HANDLER)
    a, b = _load(tmp_path, "first", first), _load(tmp_path, "second", second)

    def violations(convs):
        res, _ = extract_and_resolve(repo, convs=convs)
        return sorted((v.convention, v.rule, v.line) for v in res.violations)

    assert violations(a + b) == violations(b + a)
