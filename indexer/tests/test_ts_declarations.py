"""A declaration file the repo writes is read as TypeScript reads it (scripts/checks/ts_heritage.js, ts_checker.js and
ts_modules.js): its interfaces and classes are symbols, an import resolves to it where no implementation file of the
module exists, and a base it declares is an edge. Beside a JS file, the import stays on the file Node loads and its
values are the JS's; a name the JS cannot declare (an interface, a name of an export assignment's namespace) is the
declaration file's. A module an ambient `declare module` describes is a package's, and a global declaration names no
module."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

from aidd_indexer import languages
from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.typescript.receivers import receiver_of
from aidd_indexer.languages.typescript.scopes import TsScopes
from aidd_indexer.languages.typescript.type_index import module_of, qualified, typed

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
USE = """import Dual = require("../lib/dual");
import { DualShape } from "../lib/dual";
import { Shape } from "../types/shape";
import { Idx } from "../types";
import { Mod } from "../types/mod.mjs";
import { Child } from "../types/child";
import { Remote } from "some-pkg";
import classes from "../types/style.css";
declare const shape: Shape;
export class W1 extends Dual {}
export class W2 implements DualShape {}
export class W3 implements Shape {}
export class W4 implements Idx {}
export class W5 implements Mod {}
export class W6 implements Child {}
export class W7 implements Remote {}
export class W8 extends Window {}
new Dual().run();
shape.area();
"""
FILES = {
    "package.json": '{"name": "app"}\n',
    "types/shape.d.ts": "export interface Shape { area(): number; }\n",
    "types/index.d.ts": "export interface Idx { go(): void; }\n",
    "types/mod.d.mts": "export interface Mod { run(): void; }\n",
    "types/child.d.ts": 'import { Shape } from "./shape";\nexport interface Child extends Shape { sides: number; }\n',
    "types/style.css.d.ts": "declare const classes: { box: string };\nexport default classes;\n",
    "types/ambient.d.ts": 'declare module "some-pkg" { export interface Remote { go(): void; } }\n',
    "types/globals.d.ts": "interface Window { app: string; }\n",
    "lib/dual.js": "class Dual { run() {} }\nmodule.exports = Dual;\n",
    "lib/dual.d.ts": 'import { Shape } from "../types/shape";\ndeclare class Dual { run(): void; }\n'
                     "declare namespace Dual { export { Shape as DualShape }; }\nexport = Dual;\n",
    "app/use.ts": USE,
}
EDGES = {
    ("app/use:W1", "EXTENDS"): "lib/dual.d:Dual", ("app/use:W2", "IMPLEMENTS"): "types/shape.d:Shape",
    ("app/use:W3", "IMPLEMENTS"): "types/shape.d:Shape", ("app/use:W4", "IMPLEMENTS"): "types/index.d:Idx",
    ("app/use:W5", "IMPLEMENTS"): "types/mod.d:Mod", ("app/use:W6", "IMPLEMENTS"): "types/child.d:Child",
    ("types/child.d:Child", "EXTENDS"): "types/shape.d:Shape",
}
AMBIENT = {("app/use:W7", "IMPLEMENTS"): "types/ambient.d:some-pkg.Remote"}
GLOBAL = {("app/use:W8", "EXTENDS"): "types/globals.d:Window"}
DIVERGES = {("app/use:W1", "EXTENDS"): "lib/dual:Dual"}
CALLS = {("app/use.ts", 18): "lib/dual.d:Dual.run", ("app/use.ts", 19): "types/shape.d:Shape.area"}
INDEX_CALLS = {**CALLS, ("app/use.ts", 18): "lib/dual:Dual.run"}
IMPORTS = {
    "../types/shape": "types/shape.d.ts", "../types": "types/index.d.ts", "../types/mod.mjs": "types/mod.d.mts",
    "../types/child": "types/child.d.ts", "../types/style.css": "types/style.css.d.ts",
    "../lib/dual": "lib/dual.d.ts", "some-pkg": None,
}
INDEX_IMPORTS = {**IMPORTS, "../lib/dual": "lib/dual.js"}


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def _checker(script: str, root: Path, stdin: str = "") -> list[dict]:
    env = {**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}
    out = subprocess.run(["node", str(CHECKS / script), str(root)], input=stdin, capture_output=True, text=True,
                         check=True, env=env)
    return [json.loads(line) for line in out.stdout.splitlines()]


def test_the_case_is_what_typescript_says(case):
    clause = {"extends": "EXTENDS", "implements": "IMPLEMENTS"}
    heritage = {(f"{module_of(r['file'])}:{r['name']}", clause[r["clause"]]): r["declared"]
                for r in _checker("ts_heritage.js", case)}
    expected = {k: [v] for k, v in {**EDGES, **AMBIENT}.items()}
    expected |= {k: sorted(["outside", v]) for k, v in GLOBAL.items()}
    assert {k: v for k, v in heritage.items() if k in expected} == expected
    calls = {(r["file"], r["line"]): r["declared"] for r in _checker("ts_checker.js", case)}
    assert calls == {k: [v] for k, v in CALLS.items()}
    imports = {r["spec"]: r["to"] for r in _checker("ts_modules.js", case, "app/use.ts\n")}
    assert imports == IMPORTS


@pytest.fixture(scope="module")
def indexed(case):
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(case)),
                                   convs=[])


def test_a_declaration_files_interface_and_class_are_symbols(indexed):
    res, _ = indexed
    names = {s.qualified_name for s in res.symbols}
    assert {"types/shape.d:Shape", "types/shape.d:Shape.area", "types/index.d:Idx", "types/mod.d:Mod",
            "types/child.d:Child", "lib/dual.d:Dual", "lib/dual.d:Dual.run"} <= names


def test_a_base_a_declaration_file_declares_is_an_edge_as_the_checker_gives_it(indexed):
    res, rv = indexed
    q = {s.id: s.qualified_name for s in res.symbols}
    edges = {(q[e.source_id], e.kind): q[e.target_id] for e in rv.hierarchy if e.kind in ("EXTENDS", "IMPLEMENTS")}
    want = {**EDGES, **DIVERGES}
    assert {k: edges.get(k) for k in (*EDGES, *AMBIENT, *GLOBAL)} == {**want, **dict.fromkeys((*AMBIENT, *GLOBAL))}


def test_a_call_reaches_the_method_of_the_declaration_the_index_holds(case, indexed):
    res, _ = indexed
    lang = languages.by_extension(".ts")
    src = (case / "app/use.ts").read_bytes()
    root = get_parser(lang.grammar).parse(src).root_node
    scopes = TsScopes(root, src)
    reached = {}
    for call in (s.named_children[0] for s in root.named_children if s.type == "expression_statement"):
        receiver = call.child_by_field_name("function").child_by_field_name("object") \
            if call.type == "call_expression" else None
        if receiver is not None:
            found = receiver_of(receiver, scopes, False)
            reached["app/use.ts", call.start_point[0] + 1] = _method(res.types.of(lang.id), "app/use.ts", found,
                                                                    call.child_by_field_name("function")
                                                                    .child_by_field_name("property").text.decode())
    assert reached == INDEX_CALLS


def _method(types, file: str, found, name: str) -> str | None:
    if isinstance(found, Unknown):
        return found.reason
    owner = typed(types, file, *found)
    owner = types.method(owner, name) if isinstance(owner, TypeRef) else owner
    return f"{qualified(owner)}.{name}" if isinstance(owner, TypeRef) else getattr(owner, "reason", None)
