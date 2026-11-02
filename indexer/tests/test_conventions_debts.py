"""The declarative conventions' known defects. Each case states the right answer and is a strict xfail with the reason:
when the code reaches it, the case passes, the xfail fails the suite, and the mark has to go."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def case(id, *values, why):
    return pytest.param(*values, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


LONG = {"src/Shop/Shop.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
        "src/Shop/Builder.cs": "namespace Shop;\n\npublic class Builder\n    : BuilderBase,\n"
                               + "".join(f"        IWith{i},\n" for i in range(16)) + "        Base\n{\n}\n"}
SUBSCRIPT = {"pyproject.toml": "[project]\nname = 'shop'\n", "shop/__init__.py": "",
             "shop/lookups.py": "class Base:\n    pass\n\n\nclass IntLookup(Base[int]):\n    pass\n"}
CALL = {"package.json": '{"name": "shop"}\n',
        "src/options.ts": "export class Base {}\n\nclass Options\n  extends Record({\n    a: 1,\n  })\n"
                          "  implements Base\n{\n}\n\nexport default Options;\n"}


@pytest.mark.parametrize("files,name", [
    case("a-declaration-longer-than-the-window-gives-its-last-bases", LONG, "Builder",
         why="the reading takes 15 lines from the line that declares the type, and the base list goes on past them"),
    case("a-python-base-with-a-subscript-gives-its-name", SUBSCRIPT, "IntLookup",
         why="the subscript stays on the name, which is then no identifier"),
    case("a-brace-in-a-call-in-a-base-list-hides-no-base", CALL, "Options",
         why="the `{` of the call's argument ends the declaration before its `implements`"),
])
def test_a_type_takes_the_role_of_a_base_its_declaration_writes(tmp_path: Path, files, name):
    from aidd_indexer import conventions
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "shop"
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    (tmp_path / "convention.yaml").write_text(yaml.safe_dump({"id": "x", "roles": {"entity": {"extends": ["Base"]}}}))
    convs = conventions.load([{"path": str(tmp_path / "convention.yaml")}], "shop")
    repo = RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=str(root))
    res, _ = extract_and_resolve(repo, convs=convs)
    assert {s.name: s.role for s in res.symbols}[name] == "entity"
