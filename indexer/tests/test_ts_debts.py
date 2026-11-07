"""TS's and JS's declarations the graph still misses: a base in a package whose entry is a build the repo lacks, and one
whose source a condition a tool of the repo enables names; a member of an interface whose type is a function the code
does not write in place, a function an object literal holds, a member of an object type no declaration names, and one
of an alias's wrappers the query does not reach, each the declaration TypeScript's checker resolves a call of the member
to (scripts/checks/ts_checker.js, which a test of the case checks). Each case states the right answer and is a strict
xfail with the reason: when the indexer learns it, the case passes, the xfail fails the suite, and the mark has to
go."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "checks" / "ts_checker.js"

BUILD_ENTRY = {
    "package.json": '{"name": "app", "workspaces": ["packages/*"]}\n',
    "packages/core/package.json": '{"name": "@app/core", "main": "./dist/index.js"}\n',
    "packages/core/src/index.ts": "export class Base { run() {} }\n",
    "packages/web/package.json": '{"name": "@app/web"}\n',
    "packages/web/src/use.ts": 'import { Base } from "@app/core";\nexport class Use extends Base { run() {} }\n',
}
CONDITION_OF_A_TOOL = {
    "package.json": '{"name": "app", "workspaces": ["packages/*"]}\n',
    "packages/core/package.json": '{"name": "@app/core", "exports": {".": {"source": "./src/index.ts", '
                                  '"default": "./dist/index.js"}}}\n',
    "packages/core/src/index.ts": "export class Base { run() {} }\n",
    "packages/web/package.json": '{"name": "@app/web"}\n',
    "packages/web/vite.config.ts": "export default { resolve: { conditions: ['source'] } };\n",
    "packages/web/src/use.ts": 'import { Base } from "@app/core";\nexport class Use extends Base { run() {} }\n',
}


def case(id, files, want, why):
    return pytest.param(files, want, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("an-import-of-a-package-whose-entry-is-a-build-the-repo-lacks-reaches-its-source", BUILD_ENTRY,
         ("packages/web/src/use:Use", "EXTENDS", "packages/core/src/index:Base"),
         "the entry of a package is a build the repo lacks, and no project its config references says where its source "
         "is"),
    case("an-import-of-a-package-whose-source-a-condition-of-a-tool-names-reaches-it", CONDITION_OF_A_TOOL,
         ("packages/web/src/use:Use", "EXTENDS", "packages/core/src/index:Base"),
         "the condition that leads to the source is one the bundler's config enables, which TypeScript does not read"),
]

NOT_WRITTEN_IN_PLACE = ("a member's type is a function only a name, `typeof` or a union gives, which the syntax does "
                        "not decide")
THEME = 'import {{ Theme }} from "./models";\nexport function main(t: Theme) {{ return t.{}(1); }}\n'
NOT_IN_REACH = ("the alias's object type is below more wrappers than the query reaches, or a mix of them or a pair of "
                "parentheses, where a method signature is a member of the alias")
MEMBERS = [
    case("a-member-whose-type-an-alias-of-a-function-type-gives-is-the-method-its-call-reaches",
         {"app/models.ts": "export type Spacing = (n: number) => string;\n"
                           "export interface Theme { spacing: Spacing; }\n",
          "app/use.ts": THEME.format("spacing")},
         "app/models:Theme.spacing", NOT_WRITTEN_IN_PLACE),
    case("a-member-whose-type-typeof-a-function-gives-is-the-method-its-call-reaches",
         {"app/models.ts": "export function format(n: number) { return String(n); }\n"
                           "export interface Theme { format: typeof format; }\n",
          "app/use.ts": THEME.format("format")},
         "app/models:Theme.format", NOT_WRITTEN_IN_PLACE),
    case("a-member-whose-type-is-a-function-or-undefined-is-the-method-its-call-reaches",
         {"app/models.ts": "export interface Theme { pick: ((n: number) => string) | undefined; }\n",
          "app/use.ts": 'import { Theme } from "./models";\nexport function main(t: Theme) { return t.pick?.(1); }\n'},
         "app/models:Theme.pick", NOT_WRITTEN_IN_PLACE),
    case("a-function-an-object-literal-a-constant-holds-is-the-symbol-its-call-reaches",
         {"app/keys.ts": 'export const QUERY_KEYS = {\n  list: () => ["list"],\n};\n',
          "app/use.ts": 'import { QUERY_KEYS } from "./keys";\nexport function main() { return QUERY_KEYS.list(); }\n'},
         "app/keys:QUERY_KEYS.list",
         "an object literal's member has no symbol: neither the constant that holds it nor a property is one"),
    case("a-member-of-an-object-type-no-declaration-names-is-the-method-its-call-reaches",
         {"app/models.ts": "export function take(o: { go(): void }) { return o.go(); }\n"},
         "app/models:take.o.go",
         "a method signature in an object type no declaration names sits under the function around it, with no "
         "name for the parameter that holds the type"),
]


WRAPPED = [
    case("a-member-of-a-union-of-four-object-types-is-the-method-its-call-reaches",
         {"app/models.ts": "export type Four =\n"
                           "  { a: () => void } | { b: () => void } | { c: () => void } | { d: () => void };\n"
                           'export function main(f: Four) { if ("a" in f) { f.a(); } }\n'},
         "app/models:Four.a", NOT_IN_REACH),
    case("a-member-of-an-object-type-three-intersections-down-is-the-method-its-call-reaches",
         {"app/models.ts": "export interface Api { push(): void }\n"
                           "export type Deep = { deep: () => void } & Api & Api & Api;\n"
                           "export function main(d: Deep) { d.deep(); }\n"},
         "app/models:Deep.deep", NOT_IN_REACH),
    case("a-member-of-a-parenthesized-object-type-is-the-method-its-call-reaches",
         {"app/models.ts": "export interface Api { push(): void }\n"
                           "export type Paren = Api & ({ pm: () => void });\n"
                           "export function main(p: Paren) { p.pm(); }\n"},
         "app/models:Paren.pm", NOT_IN_REACH),
    case("a-member-of-a-parenthesized-union-in-an-intersection-is-the-method-its-call-reaches",
         {"app/models.ts": "export interface Api { push(): void }\n"
                           "export type Mixed = Api & ({ mixed: () => void } | { other: () => void });\n"
                           'export function main(m: Mixed) { if ("mixed" in m) { m.mixed(); } }\n'},
         "app/models:Mixed.mixed", NOT_IN_REACH),
    case("a-member-of-a-union-of-an-intersection-is-the-method-its-call-reaches",
         {"app/models.ts": "export interface Api { push(): void }\n"
                           "export type Mix = { um: () => void } & Api | Api;\n"
                           'export function main(m: Mix) { if ("um" in m) { m.um(); } }\n'},
         "app/models:Mix.um", NOT_IN_REACH),
]
MEMBERS += WRAPPED


def _write(root, files):
    for rel, body in {"package.json": '{"name": "app"}\n', **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)


def _indexed(root, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    _write(root, files)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


@pytest.mark.parametrize("files, edge", CASES)
def test_a_base_and_an_override_the_declarations_give_are_edges(tmp_path, files, edge):
    res, rv = _indexed(tmp_path, files)
    q = {s.id: s.qualified_name for s in res.symbols}
    assert edge in {(q[e.source_id], e.kind, q[e.target_id]) for e in rv.hierarchy}


@pytest.mark.parametrize("files, member", [pytest.param(p.values[0], p.values[1], id=p.id) for p in MEMBERS])
def test_the_checker_resolves_the_call_to_the_member_the_case_names(tmp_path, files, member):
    _write(tmp_path, files)
    out = subprocess.run(["node", str(CHECKER), str(tmp_path)], capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    assert member in {d for r in map(json.loads, out.splitlines()) for d in r["declared"]}


@pytest.mark.parametrize("files, member", MEMBERS)
def test_the_member_a_call_reaches_is_a_symbol(tmp_path, files, member):
    res, _ = _indexed(tmp_path, files)
    assert member in {s.qualified_name for s in res.symbols}
