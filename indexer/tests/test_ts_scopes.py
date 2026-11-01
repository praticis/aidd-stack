"""TS's scope index (languages/typescript/scopes.py) against TypeScript's own binder, rule by rule: every name a file
reads binds to the declarations of the file the compiler of the test image binds it to, for what its place means, and
every `this` to the node that binds it. The case table's files are compared too. The same comparison runs over every TS
and JS file of the corpus (scripts/checks/ts_scopes.py)."""

import sys
from pathlib import Path, PurePosixPath

import pytest
from tree_sitter_language_pack import get_parser

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "checks"))
from ts_scopes import compare, oracle  # noqa: E402

from aidd_indexer import languages  # noqa: E402
from aidd_indexer.languages.typescript.scopes import TsScopes  # noqa: E402
from test_ts_types import CASES, CLIENT, MODELS, SCANS  # noqa: E402

RULES = {
    "a-block-shadows-a-name.ts": "const x = new A();\nif (c) { const x = new B(); x.run(); }\nx.run();\n",
    "a-var-is-the-functions.ts": "function f() { x.run(); { var x = 1; } return x; }\nexport {};\n",
    "a-function-in-a-block-of-strict-code.ts": "export function f() { { function k() {} k(); } return k; }\n",
    "a-function-in-a-block-of-a-script.js": "function f() { { function k() {} } return k(); }\n",
    "use-strict-in-a-function.js": "function f() {\n  'use strict';\n  { function k() {} }\n  return k;\n}\n",
    "a-class-is-strict.js": "class C { m() { { function k() {} } return k; } }\n",
    "a-signature-sees-only-parameters.ts":
        "const b = 1;\nexport function f(a = b, c: typeof a = a): typeof a { let b = 2; return b; }\n",
    "a-parameter-and-a-var-of-one-name.js": "function f(options) { var options = options || {}; return options; }\n",
    "a-named-function-expression.ts":
        "export const g = function g(g: number) { return g; };\nexport const h = function h() { return h; };\n",
    "a-class-expressions-name.ts": "export const E = class Named { static m() { return Named; } };\n",
    "a-type-and-a-value-of-one-name.ts":
        "interface X { a: number }\nconst X = 1;\nexport const y: X = { a: X };\n"
        "export function f() { const X = 'v'; const z: X = { a: 1 }; return X + z; }\n",
    "a-type-parameter-shadows-an-import.ts":
        'import { T } from "./t";\nexport function f<T>(x: T): T { return x; }\nexport const t: T = 1;\n'
        "export class K<U> { m(u: U): U { return u; } }\nexport type Alias<V> = V[];\n",
    "catch-and-for-heads.ts":
        "export function f(xs: number[]) {\n  for (const x of xs) { x; }\n  for (let i = 0; i < 1; i++) { i; }\n"
        "  for (var k in xs) { k; }\n  try { } catch ({ message }) { message; }\n  return k;\n}\n",
    "a-switch-shares-one-block.ts":
        "export function f(s: number) {\n  switch (s) { case 1: let z = 2; case 2: return z; }\n}\n",
    "destructuring.ts":
        "export function f({ a, b: [c], d = 1, ...e }: any, [g, ...h]: any[]) {\n  let x, y;\n  [x, y] = [a, c];\n"
        "  ({ x, y } = { x: d, y: e });\n  return [g, h, x, y];\n}\n",
    "decorators-are-read-outside.ts":
        "const Dec = (x?: any) => (..._: any[]) => {};\nconst p = 1;\n@Dec(p) export class D<T> {\n"
        "  @Dec(p) m(@Dec(p) p: T) { return p; }\n  @Dec() f = p;\n}\n",
    "infer-and-mapped-types.ts":
        "export type Cnd<T> = T extends Array<infer U> ? U : never;\nexport type M<T> = { [K in keyof T]: T[K] };\n"
        "export interface I<V> extends Array<V> { m<W>(w: W): V; }\nexport type Fn = (a: number) => typeof a;\n",
    "an-infer-is-its-conditional-types.ts":
        "type U = string;\nexport type A<T> = T extends Array<infer U> ? [U, T] : U;\nexport type B = U;\n"
        "export type C<T> = T extends infer V ? (V extends infer U ? U : never) : U;\n"
        "export type D = U extends infer U ? U : 0;\n",
    "a-generic-constructor-type.ts": "export type S = { I: new <T extends object>(c: T) => Map<T, T> };\n",
    "commonjs.js": "(function (exports, module) {\n  exports.a = 1;\n  module.exports = exports;\n})({}, {});\n"
                   "exports.b = require('./b');\n",
    "a-script.js":"let shared = 1;\nfunction twice() { return shared * 2; }\ntwice();\n",
    "another-script-of-the-same-names.js": "let shared = 2;\nfunction twice() { return shared + shared; }\ntwice();\n",
    "an-enums-members.ts": "export enum E { A = 1, B = A, C = B + 1 }\nexport const e = E.A;\n",
    "a-namespace-of-types-is-no-value.ts":
        "declare global { namespace Cy { interface C { a(): void } } }\nexport const y = Cy.x;\n"
        "module Forms { export const E = 1; }\nexport const e = Forms.E;\n",
    "a-require-in-a-block.js":
        "function f() {\n  try { g(); } catch (e) {\n    const log = require('log');\n    log.error(e);\n  }\n}\n",
    "a-namespace.ts":
        "export namespace N {\n  export const n = 1;\n  const m = n;\n  export function f() { return m; }\n}\n"
        "export const x = N.n;\n",
    "declare-global.ts":
        "declare global { interface Window { w: number } }\nexport const w: Window | null = null;\n",
    "imports-and-exports.ts":
        'import D, { B as Bee, type T } from "./m";\nimport * as ns from "./n";\nimport fs = require("fs");\n'
        "const f = (a: T) => a;\nexport { f as g, Bee };\nexport { a as b } from './m';\nexport default D;\n"
        "export const v: ns.Q = new Bee(fs);\n",
    "jsx.tsx": "import { Comp } from './c';\nclass K { C = Comp; r() { return <this.C />; } }\n"
               "export const a = <Comp.Sub a={K}>{K}</Comp.Sub>;\nexport const d = <div className='x' />;\n"
               "export const e = [1].map((i) => <i key={i} />);\n",
    "this.ts":
        "export class C {\n  x = this;\n  static s = this;\n  static { this.s; }\n  m(a = this) {\n"
        "    const f = () => this;\n    const g = function () { return this; };\n    return [a, f, g];\n  }\n"
        "  [Symbol.iterator]() { return this; }\n  t(): typeof this { return this; }\n}\n"
        "export const o = { m() { return this; }, n: () => this };\nexport function h(this: C) { return this; }\n"
        "export class K {\n  f(): void {}\n  g: typeof this.f = () => {};\n}\n",
    "this-as-a-key-and-in-a-predicate.ts":
        "export class C {\n  is(): this is D { return true; }\n  o() { return { this: 1, t: this }; }\n}\n"
        "class D extends C {}\n",
    "a-tuple-names-its-members.ts": "export function f(key: string): [key: string, v?: number] { return [key]; }\n",
    "a-parameter-named-undefined.js": "(function ($, undefined) { return $ === undefined; })(1);\n",
    "this.js":"function F() { this.x = 1; }\nF.prototype.m = function () { return this.x; };\nconst t = this;\n",
}


def _table() -> dict[str, str]:
    """The case table's files, each case's under a folder of its own."""
    files = {}
    for name, case in CASES.items():
        files |= {f"cases/{name}/app/models.ts": MODELS, f"cases/{name}/app/use.{case.ext}": case.use}
    for name, scan in SCANS.items():
        files |= {f"cases/{name}/app/client.ts": CLIENT, f"cases/{name}/app/use.ts": scan.use}
    return files


FILES = {**{f"rules/{name}": src for name, src in RULES.items()}, **_table()}


@pytest.fixture(scope="module")
def bound(tmp_path_factory) -> dict[str, dict]:
    """The binder's answers for every file, in one run of the compiler."""
    root = tmp_path_factory.mktemp("scopes")
    for rel, src in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(src)
    return {row["file"]: row for row in oracle(root, sorted(FILES))}


@pytest.mark.parametrize("rel", [pytest.param(r, id=r) for r in FILES])
def test_every_name_and_this_bind_as_the_compiler_binds_them(bound, rel):
    grammar = languages.by_extension(PurePosixPath(rel).suffix).grammar
    assert not bound[rel]["broken"]
    found, names, thises = compare(FILES[rel].encode(), grammar, bound[rel])
    assert found == [] and names + thises


def index_of(src: str, grammar: str = "typescript") -> tuple[TsScopes, list]:
    tree = get_parser(grammar).parse(src.encode())
    index = TsScopes(tree.root_node, src.encode())
    return index, sorted(index.names(), key=lambda n: n.start_byte)


def test_a_name_read_after_a_block_binds_to_the_declaration_around_the_block():
    index, names = index_of(RULES["a-block-shadows-a-name.ts"])
    inner, outer = [n for n in names if n.text == b"x"]
    assert [d.start_point for d in index.binding(inner)] == [(1, 15)]
    assert [d.start_point for d in index.binding(outer)] == [(0, 6)]


def test_a_this_in_an_arrow_function_is_bound_by_the_method_around_it():
    index, _ = index_of("class C {\n  m() {\n    return () => this;\n  }\n}\n")
    this, = index.thises()
    assert index.this_of(this).type == "method_definition"


def test_a_name_no_declaration_of_the_file_binds_has_none():
    index, names = index_of("export const a = console;\n")
    assert [index.binding(n) for n in names] == [[]]


def _apart(tmp_path, name: str, src: str) -> list[tuple[str, str, str, str]]:
    (tmp_path / name).write_text(src)
    row, = oracle(tmp_path, [name])
    found, _, _ = compare(src.encode(), languages.by_extension(PurePosixPath(name).suffix).grammar, row)
    return [(d.kind, d.at, d.index, d.compiler) for d in found]


def test_a_require_binds_in_its_block_where_the_binder_binds_it_in_the_function_a_difference_apart(tmp_path):
    catch = "  try { g(); } catch (e) {\n    const log = require('log');\n    log.error(e);\n  }\n"
    assert _apart(tmp_path, "a.js", "function f() {\n" + catch + catch + "}\n") == [("require", "7:4", "6:10", "2:10")]


def test_a_generic_tag_of_a_template_tree_sitter_closes_early_is_a_difference_apart(tmp_path):
    src = "interface Props { a: 1 }\nexport const C = styled.div<Props>`\n  color: red;\n`;\n" \
          "export const asUuid = (id: string) => sql<string>`${id}::uuid`;\n"
    assert _apart(tmp_path, "a.ts", src) == [("misread", "1:28", "", "0:10"), ("misread", "4:52", "", "4:23")]
