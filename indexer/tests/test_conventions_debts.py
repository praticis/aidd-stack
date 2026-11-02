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


def _partial(base_in: str) -> dict[str, str]:
    """A partial class declared in two files, one of which names its base."""
    other = "B" if base_in == "A" else "A"
    return {"src/Shop/Shop.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
            f"src/Shop/{base_in}/Order.cs": "namespace Shop;\n\npublic partial class Order : IEntity { }\n",
            f"src/Shop/{other}/Order.cs": "namespace Shop;\n\npublic partial class Order { }\n"}


@pytest.mark.parametrize("base", [
    case("a-partial-class-takes-the-role-of-a-base-any-of-its-declarations-names", "IEntity",
         why="a partial class's declarations share one id, and the bases read are the last one's in path order"),
])
def test_a_partial_class_has_the_bases_of_all_its_declarations(tmp_path, base):
    from aidd_indexer.cli import extract_and_resolve
    convs = _load(tmp_path, "convention", {"id": "x", "roles": {"entity": {"extends": [base]}}})
    roles = {}
    for base_in in ("A", "B"):
        res, _ = extract_and_resolve(_write(tmp_path / base_in / "shop", _partial(base_in)), convs=convs)
        roles[base_in] = {s.role for s in res.symbols if s.name == "Order"}
    assert roles == {"A": {"entity"}, "B": {"entity"}}
