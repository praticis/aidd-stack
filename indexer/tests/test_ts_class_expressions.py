"""A class a module declares by an expression is a class of the graph, with the name that gives it one (the checker's
declaration of a heritage clause, scripts/checks/ts_heritage.js): the binding of `const X = class {..}`, the own name of
`module.exports = class X {..}`, the property of `exports.X = class {..}`. It has the symbol of a declaration, its
bases, the methods that override, and it is the value its module exports; one with no such name, or one a function
holds, is no symbol and no base."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
FILES = {
    "package.json": '{"name": "app"}\n',
    "lib/base.ts": "export class Base { run() {} }\n",
    "lib/root.js": "module.exports = class Root { go() {} };\n",
    "lib/decl.ts": """import { Base } from "./base";
export const Declared = class extends Base { run() {} };
export const Named = class Inner extends Base {};
const Local = class extends Base {};
export { Local };
export var Old = class extends Base {};
var Plain = class extends Base {};
export { Plain };
export interface Shape { size(): number; }
export const Shaped = class implements Shape { size() { return 1; } };
""",
    "lib/own.js": """const Root = require("./root");
module.exports = class Own extends Root { go() {} };
""",
    "lib/props.js": """const Root = require("./root");
exports.A = class extends Root { go() {} };
module.exports.B = class Wrapped extends Root {};
""",
    "lib/anon.js": """const Root = require("./root");
module.exports = class extends Root {};
""",
    "lib/esm.js": """import { Base } from "./base";
export const Js1 = class extends Base {};
const Js2 = class extends Base {};
var Js3 = class extends Base {};
export var Js4 = class extends Base {};
export { Js2, Js3 };
""",
    "lib/hidden.js": """import { Base } from "./base";
export function make() { const L = class extends Base {}; return L; }
""",
    "lib/hidden.ts": """import { Base } from "./base";
export function make() { return class extends Base {}; }
function inner() { const Local = class extends Base {}; return Local; }
""",
    "app/use.ts": """import { Declared, Named, Local, Old, Shaped } from "../lib/decl";
export class U1 extends Declared {}
export class U2 extends Named {}
export class U3 extends Local {}
export class U4 extends Old {}
export class U5 extends Shaped {}
""",
    "app/cjs.js": """const Own = require("../lib/own");
const { A, B } = require("../lib/props");
const Anon = require("../lib/anon");
class V1 extends Own {}
class V2 extends A {}
class V3 extends B {}
class V4 extends Anon {}
module.exports = { V1, V2, V3, V4 };
""",
}
UNNAMED = ("lib/anon:", "lib/hidden:")
DECLARED = ("Js1", "Js2", "Js3", "Js4")


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


@pytest.fixture(scope="module")
def indexed(case):
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(case)),
                                   convs=[])


def _checker(root: Path) -> list[dict]:
    out = subprocess.run(["node", str(CHECKS / "ts_heritage.js"), str(root)], capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    return [json.loads(line) for line in out.splitlines()]


def _module(file: str) -> str:
    return str(Path(file).with_suffix(""))


def test_the_checker_names_the_class_each_clause_reaches(case):
    edges = {(f"{_module(r['file'])}:{r['name']}", "IMPLEMENTS" if r["clause"] == "implements" else "EXTENDS", d)
             for r in _checker(case) for d in r["declared"]}
    assert edges >= {
        ("lib/decl:Declared", "EXTENDS", "lib/base:Base"), ("lib/decl:Named", "EXTENDS", "lib/base:Base"),
        ("lib/decl:Local", "EXTENDS", "lib/base:Base"), ("lib/decl:Old", "EXTENDS", "lib/base:Base"),
        ("lib/decl:Shaped", "IMPLEMENTS", "lib/decl:Shape"), ("lib/own:Own", "EXTENDS", "lib/root:Root"),
        ("lib/props:A", "EXTENDS", "lib/root:Root"), ("lib/props:B", "EXTENDS", "lib/root:Root"),
        ("app/use:U1", "EXTENDS", "lib/decl:Declared"), ("app/use:U2", "EXTENDS", "lib/decl:Named"),
        ("app/use:U3", "EXTENDS", "lib/decl:Local"), ("app/use:U4", "EXTENDS", "lib/decl:Old"),
        ("app/cjs:V1", "EXTENDS", "lib/own:Own"), ("app/cjs:V2", "EXTENDS", "lib/props:A"),
        ("app/cjs:V3", "EXTENDS", "lib/props:B"), ("app/cjs:V4", "EXTENDS", "expression"),
    }


def test_a_named_class_expression_has_the_edges_the_checker_gives_it(case, indexed):
    res, rv = indexed
    q = {s.id: s.qualified_name for s in res.symbols}
    mine = {(q[e.source_id], e.kind, q[e.target_id]) for e in rv.hierarchy if e.kind != "OVERRIDES"}
    checker = {(f"{_module(r['file'])}:{r['name']}", "IMPLEMENTS" if r["clause"] == "implements" else "EXTENDS", d)
               for r in _checker(case) for d in r["declared"] if d not in ("outside", "other", "expression")}
    assert mine == checker


def test_a_js_module_declares_class_expressions_as_a_ts_one_does(case, indexed):
    res, rv = indexed
    q = {s.id: s.qualified_name for s in res.symbols}
    mine = {q[e.source_id] for e in rv.hierarchy if e.kind == "EXTENDS"}
    assert {f"lib/esm:{n}" for n in DECLARED} <= mine
    assert {f"lib/decl:{n}" for n in ("Plain",)} <= mine


def test_a_class_expression_is_a_class_with_its_methods(indexed):
    res, rv = indexed
    kinds = {s.qualified_name: s.kind for s in res.symbols}
    assert [kinds.get(n) for n in ("lib/decl:Declared", "lib/decl:Declared.run", "lib/own:Own", "lib/own:Own.go",
                                   "lib/props:A", "lib/props:B", "lib/decl:Shaped.size")] \
        == ["class", "method", "class", "method", "class", "class", "method"]
    assert not [n for n in kinds if n.startswith(UNNAMED) and kinds[n] in ("class", "method")]
    assert "lib/hidden:make" in kinds
    q = {s.id: s.qualified_name for s in res.symbols}
    overrides = {(q[e.source_id], q[e.target_id]) for e in rv.hierarchy if e.kind == "OVERRIDES"}
    assert {("lib/decl:Declared.run", "lib/base:Base.run"), ("lib/own:Own.go", "lib/root:Root.go"),
            ("lib/props:A.go", "lib/root:Root.go"), ("lib/decl:Shaped.size", "lib/decl:Shape.size")} <= overrides


def test_a_module_whose_class_has_no_name_holds_no_class():
    from tree_sitter_language_pack import get_parser

    from aidd_indexer.languages.typescript.type_facts import type_facts
    src = (FILES["lib/anon.js"]).encode()
    facts = type_facts(get_parser("javascript").parse(src).root_node, js=True)
    assert not facts.owners and "=" not in facts.members
