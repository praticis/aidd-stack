"""What a type's declaration gives its roles: the line that declares the type by its name, past its attributes and
decorators; the bases each language writes there; and every declaration of an id."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import convention_records as R

ROLES = {"id": "x", "roles": {"entity": {"extends": ["Base"]}, "repository": {"extends": ["BaseRepo"]},
                              "controller": {"extends": ["ControllerBase"]}, "client": {"declares": ["(HttpClient "]},
                              "go-struct": {"declares": [" struct {"]}}}
PYPROJECT = {"pyproject.toml": "[project]\nname = 'shop'\n", "shop/__init__.py": ""}
PACKAGE = {"package.json": '{"name": "shop"}\n'}
GO = "module example.com/shop\n\ngo 1.22\n"
NEIGHBOUR = "\ntype Neighbour struct {\n\tID string\n}\n"
CSPROJ = {"src/Shop/Shop.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n'}
LONG_DECORATOR = "@Component({\n" + "".join(f"  option{i}: {i},\n" for i in range(18)) + "})\n"

CASES = [
    ("a Python class with a body", PYPROJECT | {
        "shop/models.py": "class Base:\n    pass\n\n\nclass Order(Base):\n    def total(self):\n        return 0\n"},
     "Order", "entity"),
    ("a Python class of one line", PYPROJECT | {"shop/models.py": "class Base: pass\nclass One(Base): pass\n"},
     "One", "entity"),
    ("a Python decorator with a brace", PYPROJECT | {
        "shop/models.py": 'class Base:\n    pass\n\n\n@register({"kind": 1})\nclass Order(Base):\n    x = 1\n'},
     "Order", "entity"),
    ("a constrained type parameter", PACKAGE | {
        "src/repo.ts": "export class BaseRepo<T> {}\n\nexport class OrderRepo<T extends object> extends BaseRepo<T> {\n"
                       "  find() {}\n}\n"},
     "OrderRepo", "repository"),
    ("an arrow in a constraint", PACKAGE | {
        "src/repo.ts": "export class BaseRepo<T> {}\n\n"
                       "export class Mapper<T extends (a: string) => number> extends BaseRepo<T> {\n}\n"},
     "Mapper", "repository"),
    ("a type parameter with no constraint", PACKAGE | {
        "src/repo.ts": "export class BaseRepo<T> {}\n\nexport class Plain<T> extends BaseRepo<T> {\n}\n"},
     "Plain", "repository"),
    ("a decorator with a brace", PACKAGE | {
        "src/models.ts": 'export class Base {}\n\n@Table({ tableName: "orders" })\nclass Order extends Base {\n'
                         "  total() {}\n}\n\nexport default Order;\n"},
     "Order", "entity"),
    ("a decorator longer than the window", PACKAGE | {
        "src/models.ts": "export class Base {}\n\n" + LONG_DECORATOR
                         + "class Big extends Base {\n}\n\nexport default Big;\n"},
     "Big", "entity"),
    ("a name another declares as its prefix", PACKAGE | {
        "src/models.ts": 'export class Base {}\n\n@Doc({ text: "class OrderLine" })\nclass Order extends Base {\n}\n\n'
                         "export default Order;\n"},
     "Order", "entity"),
    ("a line separator in a string above", PACKAGE | {
        "src/models.ts": 'export class Base {}\nconst s = "a\u2028b\u0085c";\nconst r = 1;\rconst q = 2;\n'
                         "export class Order extends Base {}\n"},
     "Order", "entity"),
    ("a brace in a type parameter's default", PACKAGE | {
        "src/repo.ts": "export class BaseRepo<T> {}\n\nexport class Panel<\n  T = any,\n  U extends object = {},\n"
                       "> extends BaseRepo<T> {\n}\n"},
     "Panel", "repository"),
    ("an arrow in a base's type argument", PACKAGE | {
        "src/sidebar.tsx": "export class Base<P> {}\n\n"
                           "class Pin extends Base<{ pinned: boolean; onCommit: () => void }> {\n}\n"},
     "Pin", "entity"),
    ("a comment in a Python base list", PYPROJECT | {
        "shop/models.py": "class Base:\n    pass\n\n\n"
                          "class Order(\n    # the base (no other) comes next\n    Base,\n):\n    pass\n"},
     "Order", "entity"),
    ("a C# record that ends with a semicolon", CSPROJ | {
        "src/Shop/Order.cs": "namespace Shop;\n\npublic record Order(string Id) : Base;\n"},
     "Order", "entity"),
    ("a C# directive and a comment before the body", CSPROJ | {
        "src/Shop/Order.cs": "namespace Shop;\n\n#pragma warning disable CS0618\n"
                             "public class Order : Base // a comment\n#pragma warning restore CS0618\n{\n}\n"},
     "Order", "entity"),
    ("a Go type with no body", {"go.mod": GO, "shop.go": "package shop\n\ntype Members []Member\n" + NEIGHBOUR},
     "Members", None),
    ("a Go function type", {"go.mod": GO, "shop.go": "package shop\n\ntype F = func(id string) error\n" + NEIGHBOUR},
     "F", None),
    ("a Go function type over lines", {"go.mod": GO, "shop.go": "package shop\n\ntype G func(\n\tid string,\n"
                                                                 "\tn int,\n) error\n" + NEIGHBOUR},
     "G", None),
    ("a Go channel type", {"go.mod": GO, "shop.go": "package shop\n\ntype C <-chan Message\n" + NEIGHBOUR},
     "C", None),
    ("a Go generic struct", {"go.mod": GO, "shop.go": "package shop\n\ntype Box[T any] struct {\n\tv T\n}\n"},
     "Box", "go-struct"),
    ("a Go type in a group", {"go.mod": GO, "shop.go": "package shop\n\ntype (\n\tIDs []string\n\tPair struct {\n"
                                                       "\t\ta, b int\n\t}\n)\n"},
     "IDs", None),
    ("a brace in a C# attribute", CSPROJ | {
        "src/Shop/Api/OrdersController.cs": 'namespace Shop.Api;\n\n[ApiController]\n'
                                            '[Route("api/v{version:apiVersion}/[controller]")]\n'
                                            "public class OrdersController : ControllerBase\n{\n}\n"},
     "OrdersController", "controller"),
    ("a C# line that ends with the colon", CSPROJ | {
        "src/Shop/Spread.cs": "namespace Shop;\n\npublic class Spread :\n    Base\n{\n}\n"},
     "Spread", "entity"),
]


def _roles(tmp_path: Path, files: dict[str, str]) -> dict[str, str | None]:
    """Each type's role after a real extraction of `files`."""
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "shop"
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    (tmp_path / "convention.yaml").write_text(yaml.safe_dump(ROLES))
    convs = conventions.load([{"path": str(tmp_path / "convention.yaml")}], "shop")
    repo = RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=str(root))
    res, _ = extract_and_resolve(repo, convs=convs)
    return {s.name: s.role for s in res.symbols}


@pytest.mark.parametrize("files,name,role", [pytest.param(*c[1:], id=c[0]) for c in CASES])
def test_a_type_takes_the_role_of_a_base_its_declaration_names(tmp_path, files, name, role):
    assert _roles(tmp_path, files)[name] == role


def _prepared(tmp_path: Path, text: str, symbols: list) -> object:
    from aidd_indexer.conventions.declarative import DeclarativeConvention
    (tmp_path / "Types.cs").write_text(text)
    (tmp_path / "convention.yaml").write_text(yaml.safe_dump(
        {"id": "x", "roles": {"first": {"extends": ["Base1"]}, "second": {"extends": ["Base2"]}}}))
    conv = DeclarativeConvention(tmp_path / "convention.yaml")
    conv.prepare(R.context(R.result(str(tmp_path), files=[R.file("Types.cs")], symbols=symbols)))
    return conv


def test_a_type_no_line_declares_by_its_name_is_read_from_its_first_line(tmp_path: Path):
    """Its name on the line after the keyword: the declaration is read from the symbol's first line, and the search
    stays within the symbol's lines, so another type of that name further down is not taken for it."""
    split = R.symbol("Order", "Types.cs", line=1)
    split.line_end = 2
    conv = _prepared(tmp_path, "public class\n    Order : Base1 { }\n\npublic class Order : Base2 { }\n", [split])
    assert conv.role_of(split, None) == "first"


@pytest.mark.parametrize("partial", ["partial ", ""], ids=["partial", "one id, no partial"])
@pytest.mark.parametrize("named_in", ["A", "B"])
@pytest.mark.parametrize("named,role", [(" : Base", "entity"), ("(HttpClient http)", "client")],
                         ids=["base", "declares"])
def test_every_declaration_of_an_id_counts_whichever_file_comes_first(tmp_path, partial, named_in, named, role):
    """A C# partial class, or one class two projects declare in one namespace: one id, the bases of all its
    declarations and the text of each."""
    other = "B" if named_in == "A" else "A"
    files = CSPROJ | {
        f"src/Shop/{named_in}/Order.cs": f"namespace Shop;\n\npublic {partial}class Order{named} {{ }}\n",
        f"src/Shop/{other}/Order.cs": f"namespace Shop;\n\npublic {partial}class Order {{ }}\n"}
    assert _roles(tmp_path, files)["Order"] == role


def test_a_lattice_of_bases_is_walked_once_per_type(tmp_path: Path):
    """Thirty diamonds deep, a walk by path would take hours."""
    from aidd_indexer.conventions.declarative import DeclarativeConvention
    types = [R.symbol("L0", "models.py", signature="class L0")]
    for i in range(1, 31):
        types += [R.symbol(f"A{i}", "models.py", signature=f"class A{i}(L{i - 1})"),
                  R.symbol(f"B{i}", "models.py", signature=f"class B{i}(L{i - 1})"),
                  R.symbol(f"L{i}", "models.py", signature=f"class L{i}(A{i}, B{i})")]
    (tmp_path / "convention.yaml").write_text(yaml.safe_dump({"id": "x", "roles": {"entity": {"extends": ["L0"]}}}))
    conv = DeclarativeConvention(tmp_path / "convention.yaml")
    conv.prepare(R.context(R.result(str(tmp_path), files=[R.file("models.py", language="python")], symbols=types)))
    assert {t.name for t in types if conv.role_of(t, None) == "entity"} == {t.name for t in types} - {"L0"}


def _cycle(a_file: str, b_file: str) -> dict[str, str]:
    """A and B name each other, B names Base above them, and C extends A."""
    return PYPROJECT | {f"shop/{a_file}.py": "class A(B):\n    pass\n",
                        f"shop/{b_file}.py": "class B(A, Base):\n    pass\n", "shop/c.py": "class C(A):\n    pass\n"}


HOMONYMS = PYPROJECT | {f"shop/migrations/m{i}.py": "from django.db import migrations\n\n\n"
                        f"class Migration(migrations.Migration{', Base' if i == 2 else ''}):\n    pass\n"
                        for i in range(3)} | {"shop/other.py": "class Other(Migration):\n    pass\n"}


@pytest.mark.parametrize("files,name", [
    pytest.param(_cycle("a", "b"), "C", id="a cycle of names, its first file first"),
    pytest.param(_cycle("z", "b"), "C", id="a cycle of names, its first file last"),
    pytest.param(HOMONYMS, "Other", id="a group of homonyms"),
])
def test_the_names_above_a_cycle_or_a_group_of_homonyms(tmp_path, files, name):
    """A guard of the names above a type worked out once a name, against walking each type: around a cycle of names,
    and through a group of homonyms (Django's `Migration`). It passes before that change and after it: it proves the
    two the same, not a fix."""
    assert _roles(tmp_path, files)[name] == "entity"
