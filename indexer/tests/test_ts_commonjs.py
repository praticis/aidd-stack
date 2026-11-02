"""A module's own value and the names it assigns, as TypeScript binds them (scripts/checks/ts_heritage.js and
ts_checker.js): a JS file with no `import` or `export` is a CommonJS module, whose last `module.exports = x` is its own
value, each property of an object literal it assigns a name it exports, and each `exports.a = x` or `module.exports.a =
x` a name beside it; a TS module's `export = x` is its own value, and where `x` is a namespace, its export clauses are
the module's names and the class it merges with its own value. A `require`, an `import x = require(..)`, a namespace
import and a default import take the module's own value, even beside a `default` it assigns; a named import and a
destructured `require`, a name of it. Each base a class of the case extends, and each method a call reaches, is the
declaration the checker resolves it to."""

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
FILES = {
    "package.json": '{"name": "app"}\n',
    "lib/base.js": "class Base { run() {} }\nmodule.exports = Base;\n",
    "lib/models.js": "class A { run() {} }\nclass B { run() {} }\nclass D { run() {} }\n"
                     'module.exports = { A, Bee: B, d: new D(), Base: require("./base") };\n',
    "lib/named.js": "class N { run() {} }\nexports.N = N;\n",
    "lib/more.js": "class M { run() {} }\nmodule.exports.M = M;\n",
    "lib/single.js": "class S { run() {} }\nmodule.exports = new S();\n",
    "lib/mixed.js": "class X { run() {} }\nclass Y { run() {} }\nexports.z = 1;\nmodule.exports = X;\n"
                    "module.exports.Y = Y;\n",
    "lib/twice.js": "class First { run() {} }\nclass Second { run() {} }\nmodule.exports = First;\n"
                    "module.exports = Second;\n",
    "lib/esm.js": "class Esm { run() {} }\nexport const unused = 1;\nmodule.exports = Esm;\n",
    "lib/again.js": 'module.exports = require("./base");\n',
    "lib/expr.js": "module.exports = class Expr { run() {} };\n",
    "lib/esdefault.ts": "export default class Ed { run() {} }\n",
    "lib/eq.ts": "class T { run() {} }\nexport = T;\n",
    "lib/inner.ts": "export class L { run() {} }\n",
    "lib/ns.ts": 'import { L } from "./inner";\ndeclare namespace ns { export { L as Lx }; }\nexport = ns;\n',
    "lib/dflt.js": "class P { run() {} }\nclass Q { run() {} }\nmodule.exports = P;\nmodule.exports.default = Q;\n",
    "lib/merged.ts": 'import { L } from "./inner";\nclass Mg { run() {} }\n'
                     "declare namespace Mg { export { L as Lm }; }\nexport = Mg;\n",
    "app/use.js": """const Base = require("../lib/base");
const { A, Bee, Base: Again } = require("../lib/models");
const models = require("../lib/models");
const { N } = require("../lib/named");
const more = require("../lib/more");
const single = require("../lib/single");
const X = require("../lib/mixed");
const { Y } = require("../lib/mixed");
const Twice = require("../lib/twice");
const Esm = require("../lib/esm");
const Expr = require("../lib/expr");
const Again2 = require("../lib/again");
const N2 = require("../lib/named").N;
const Ed = require("../lib/esdefault").default;
const d2 = require("../lib/models").d;
class U1 extends Base { run() {} }
class U2 extends A {}
class U3 extends Bee {}
class U4 extends models.A {}
class U5 extends Again {}
class U6 extends N {}
class U7 extends more.M {}
class U8 extends X {}
class U9 extends Y {}
class U10 extends Twice {}
class U11 extends Esm {}
class U12 extends Expr {}
class U13 extends Again2 {}
class U14 extends N2 {}
class U15 extends Ed {}
single.run();
models.d.run();
new Base().run();
new models.Base().run();
new Ed().run();
d2.run();
module.exports = { U1 };
""",
    "app/main.ts": """import T = require("../lib/eq");
import T2 from "../lib/eq";
import * as T3 from "../lib/eq";
import Base from "../lib/base";
import { A } from "../lib/models";
import { Lx } from "../lib/ns";
import ns = require("../lib/ns");
import Mg = require("../lib/merged");
import { Lm } from "../lib/merged";
import Dd from "../lib/dflt";
export class V1 extends T {}
export class V2 extends T2 {}
export class V3 extends T3 {}
export class V4 extends Base {}
export class V5 extends A {}
export class V6 extends Lx {}
export class V7 extends ns.Lx {}
export class V8 extends Mg {}
export class V9 extends Lm {}
export class V10 extends Dd {}
new T().run();
new Mg().run();
""",
}
BASES = {
    "app/use:U1": "lib/base:Base", "app/use:U2": "lib/models:A", "app/use:U3": "lib/models:B",
    "app/use:U4": "lib/models:A", "app/use:U5": "lib/base:Base", "app/use:U6": "lib/named:N",
    "app/use:U7": "lib/more:M", "app/use:U8": "lib/mixed:X", "app/use:U9": "lib/mixed:Y",
    "app/use:U10": "lib/twice:Second", "app/use:U11": "other", "app/use:U12": "expression",
    "app/use:U13": "lib/base:Base", "app/use:U14": "lib/named:N", "app/use:U15": "lib/esdefault:Ed",
    "app/main:V1": "lib/eq:T", "app/main:V2": "lib/eq:T", "app/main:V3": "lib/eq:T", "app/main:V4": "lib/base:Base",
    "app/main:V5": "lib/models:A", "app/main:V6": "lib/inner:L", "app/main:V7": "lib/inner:L",
    "app/main:V8": "lib/merged:Mg", "app/main:V9": "lib/inner:L", "app/main:V10": "lib/dflt:P",
}
CALLS = {
    ("app/use.js", 31): "lib/single:S.run",
    ("app/use.js", 32): "lib/models:D.run",
    ("app/use.js", 33): "lib/base:Base.run",
    ("app/use.js", 34): "lib/base:Base.run",
    ("app/use.js", 35): "lib/esdefault:Ed.run",
    ("app/use.js", 36): "lib/models:D.run",
    ("app/main.ts", 21): "lib/eq:T.run",
    ("app/main.ts", 22): "lib/merged:Mg.run",
}
NONE = ("other", "expression")


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def _checker(script: str, root: Path) -> list[dict]:
    out = subprocess.run(["node", str(CHECKS / script), str(root)], capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    return [json.loads(line) for line in out.splitlines()]


def test_the_case_is_what_typescript_says(case):
    bases = {f"{module_of(r['file'])}:{r['name']}": r["declared"] for r in _checker("ts_heritage.js", case)}
    calls = {(r["file"], r["line"]): r["declared"] for r in _checker("ts_checker.js", case)}
    assert (bases, calls) == ({k: [v] for k, v in BASES.items()}, {k: [v] for k, v in CALLS.items()})


@pytest.fixture(scope="module")
def indexed(case):
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(case)),
                                   convs=[])


def test_a_class_extends_the_class_the_checker_gives_its_clause(indexed):
    res, rv = indexed
    q = {s.id: s.qualified_name for s in res.symbols}
    extends = {q[e.source_id]: q[e.target_id] for e in rv.hierarchy if e.kind == "EXTENDS"}
    assert {c: extends.get(c) for c in BASES} == {c: None if b in NONE else b for c, b in BASES.items()}


def test_a_call_on_a_value_a_module_exports_reaches_the_checkers_method(case, indexed):
    res, _ = indexed
    reached = {}
    for file in ("app/use.js", "app/main.ts"):
        lang = languages.by_extension("." + file.rsplit(".", 1)[1])
        src = (case / file).read_bytes()
        root = get_parser(lang.grammar).parse(src).root_node
        scopes = TsScopes(root, src)
        for call in (s.named_children[0] for s in root.named_children if s.type == "expression_statement"):
            if call.type == "call_expression":
                receiver = call.child_by_field_name("function").child_by_field_name("object")
                found = receiver_of(receiver, scopes, lang.id == "javascript")
                reached[file, call.start_point[0] + 1] = _method(res.types.of(lang.id), file, found)
    assert reached == CALLS


def _method(types, file: str, found) -> str | None:
    if isinstance(found, Unknown):
        return found.reason
    owner = typed(types, file, *found)
    owner = types.method(owner, "run") if isinstance(owner, TypeRef) else owner
    return f"{qualified(owner)}.run" if isinstance(owner, TypeRef) else getattr(owner, "reason", None)
