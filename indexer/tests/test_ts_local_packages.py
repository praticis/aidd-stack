"""A package the repo holds, but whose entry is a build the clone lacks, is not a package that declares types: its source
is in the repo and only the path to it is missing (a workspace member, or a package a `file:` dependency links). A call
on a value of its types goes by name, as in the version before types, so it reaches the package's own source. A package
whose entry is there is typed, as any class of the repo, and a package of npm declares no method of the repo. A class
that extends such an absent package may take a method from it, so the call goes by name unless the class or a base of
the repo declares the method, whatever other bases it has, and through an `export *` that carries the package; one that
extends a package of npm takes it from there (strategy `inherited`). Every case is checked against the declarations
TypeScript's own checker resolves the call to, with the links a package manager makes (scripts/checks/ts_checker.js)."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "checks" / "ts_checker.js"
PRESENT, ABSENT = "pkgs/present/src/index:Present.run", "pkgs/absent/src/index:Absent.pullAbsent"
LINKED, BUILT = "libs/present/src/index:Linked.run", "libs/absent/src/index:LinkBuilt.pullBuilt"
TYPED_STRATEGIES = ("receiver-type", "receiver-type-impl", "inherited", "inherited-impl")


class Case(NamedTuple):
    use: str                        # the source of the file, which makes one call of `method`
    declared: tuple[str, ...]       # what the checker resolves the call to
    answer: str                     # typed: one edge by the type; by-name: the edges by name reach `source`; external: none
    source: str | None = None       # by-name: the method of the package's source the call reaches
    inherited: str | None = None    # inherited: the type the edge goes to
    method: str = "run"             # a name of the package alone where the call goes by name: a shared one reaches only the
                                    # callers' own module


def _case(file: str, body: str, declared: tuple[str, ...], answer: str, **kw) -> tuple[str, Case]:
    return file, Case(body, declared, answer, **kw)


FILES = {
    "package.json": '{"name": "app", "private": true, "workspaces": ["pkgs/*"]}\n',
    "pkgs/present/package.json": '{"name": "@app/present", "types": "./src/index.ts"}\n',
    "pkgs/present/src/index.ts": "export class Present { run() {} }\n",
    "pkgs/absent/package.json": '{"name": "@app/absent", "main": "./dist/index.js", "types": "./dist/index.d.ts"}\n',
    "pkgs/absent/src/index.ts": "export class Absent { run() {} pullAbsent() {} }\n",
    "libs/present/package.json": '{"name": "@lib/present", "types": "./src/index.ts"}\n',
    "libs/present/src/index.ts": "export class Linked { run() {} }\n",
    "libs/absent/package.json": '{"name": "@lib/absent", "main": "./dist/index.js", "types": "./dist/index.d.ts"}\n',
    "libs/absent/src/index.ts": "export class LinkBuilt { run() {} pullBuilt() {} }\n",
    "tools/package.json": '{"name": "tools", "dependencies": {"@lib/present": "file:../libs/present", '
                          '"@lib/absent": "file:../libs/absent"}}\n',
    "app/other.ts": "export class Other { run() {} }\n",
    "app/npm-base.ts": 'import { Component } from "react";\nexport class V extends Component {}\n',
    "app/barrel.ts": 'export * from "@app/absent";\n',
}
USES = dict([
    _case("app/use-present.ts", 'import { Present } from "@app/present";\nexport function main(x: Present) { return x.run(); }\n',
          (PRESENT,), "typed"),
    _case("app/use-absent.ts", 'import { Absent } from "@app/absent";\nexport function main(x: Absent) { return x.pullAbsent(); }\n',
          (), "by-name", source=ABSENT, method="pullAbsent"),
    _case("tools/use-linked.ts", 'import { Linked } from "@lib/present";\nexport function main(x: Linked) { return x.run(); }\n',
          (LINKED,), "typed"),
    _case("tools/use-built.ts", 'import { LinkBuilt } from "@lib/absent";\nexport function main(x: LinkBuilt) { return x.pullBuilt(); }\n',
          (), "by-name", source=BUILT, method="pullBuilt"),
    _case("app/use-npm.ts", 'import { Thing } from "some-lib";\nexport function main(x: Thing) { return x.run(); }\n',
          (), "external"),
    _case("app/in-subclass.ts", 'import { Absent } from "@app/absent";\n'
          "export class Sub extends Absent {\n  go() { return this.pullAbsent(); }\n}\n", (), "by-name", source=ABSENT,
          method="pullAbsent"),
    _case("app/out-of-subclass.ts", 'import { Sub } from "./in-subclass";\nexport function main(x: Sub) { return x.pullAbsent(); }\n',
          (), "by-name", source=ABSENT, method="pullAbsent"),
    _case("app/own-method.ts", 'import { Absent } from "@app/absent";\n'
          "export class Own extends Absent {\n  run() {}\n  go() { return this.run(); }\n}\n",
          ("app/own-method:Own.run",), "typed"),
    _case("app/out-of-deeper.ts", 'import { Sub } from "./in-subclass";\nexport class Deeper extends Sub {}\n'
          "export function main(x: Deeper) { return x.pullAbsent(); }\n", (), "by-name", source=ABSENT,
          method="pullAbsent"),
    _case("tools/linked-base.ts", 'import { LinkBuilt } from "@lib/absent";\n'
          "export class Sub2 extends LinkBuilt {\n  go() { return this.pullBuilt(); }\n}\n", (), "by-name", source=BUILT,
          method="pullBuilt"),
    _case("app/mixed-bases.ts", 'import { Absent } from "@app/absent";\nimport type { Shape } from "some-lib";\n'
          "export class Mixed extends Absent implements Shape {\n  go() { return this.pullAbsent(); }\n}\n"
          "export function main(x: Mixed) { return x.pullAbsent(); }\n", (), "by-name", source=ABSENT,
          method="pullAbsent"),
    _case("app/through-a-barrel.ts", 'import { Absent } from "./barrel";\nexport class Star extends Absent {}\n'
          "export function main(x: Star) { return x.pullAbsent(); }\n", (), "by-name", source=ABSENT,
          method="pullAbsent"),
    _case("app/out-of-npm-subclass.ts", 'import { V } from "./npm-base";\nexport function main(x: V) { return x.run(); }\n',
          (), "inherited", inherited="app/npm-base:V"),
])


def _write(root: Path) -> None:
    for rel, body in {**FILES, **{f: c.use for f, c in USES.items()}}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    _write(root)
    return root


@pytest.fixture(scope="module")
def checked(repo) -> dict[str, tuple[str, ...]]:
    """What the checker resolves each file's call of its method to."""
    env = {**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}
    out = subprocess.run(["node", str(CHECKER), "--link", str(repo)], capture_output=True, text=True, check=True,
                         env=env).stdout
    rows = map(json.loads, out.splitlines())
    return {r["file"]: tuple(r["declared"]) for r in rows if r["file"] in USES and r["method"] == USES[r["file"]].method}


@pytest.fixture(scope="module")
def edges(repo) -> dict[str, set[tuple[str, str]]]:
    """The targets and strategies of the edges of each file's call of its method."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(repo)),
                                      convs=[])
    sym = {s.id: s for s in res.symbols}
    path = {f.id: f.path for f in res.files}
    out: dict[str, set[tuple[str, str]]] = {file: set() for file in USES}
    for e in rv.calls:
        file = path.get(e.caller_id) or path.get(getattr(sym.get(e.caller_id), "file_id", None))
        if file in out and (e.method or sym[e.callee_id].name) == USES[file].method:
            out[file].add((sym[e.callee_id].qualified_name, e.strategy))
    return out


def _of(answer: str) -> list:
    return [pytest.param(f, id=f) for f, c in USES.items() if c.answer == answer]


@pytest.mark.parametrize("file", list(USES))
def test_the_checker_resolves_the_call_to_the_declarations_the_case_names(checked, file):
    assert checked[file] == USES[file].declared


@pytest.mark.parametrize("file", _of("typed"))
def test_a_value_of_a_package_whose_entry_is_there_reaches_the_declaration_the_checker_names(edges, file):
    assert edges[file] == {(USES[file].declared[0], "receiver-type")}


@pytest.mark.parametrize("file", _of("by-name"))
def test_a_package_whose_entry_is_a_build_the_repo_lacks_is_reached_by_name(edges, file):
    found = edges[file]
    assert USES[file].source in {target for target, _ in found}
    assert not [s for _, s in found if s.removesuffix("-ambiguous") in TYPED_STRATEGIES]


@pytest.mark.parametrize("file", _of("external"))
def test_a_method_of_a_package_of_npm_reaches_no_homonym_of_the_repo(edges, file):
    assert edges[file] == set()


@pytest.mark.parametrize("file", _of("inherited"))
def test_a_class_that_extends_a_package_of_npm_depends_on_it_and_not_on_a_homonym(edges, file):
    assert edges[file] == {(USES[file].inherited, "inherited")}
