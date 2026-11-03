"""TS's and JS's declarations the graph still misses: a base in a package whose entry is a build the repo lacks, and one
whose source a condition a tool of the repo enables names; a member of an interface whose type is a function the code
does not write in place, and a function an object literal holds, both of them the declaration TypeScript's checker
resolves a call of the member to (scripts/checks/ts_checker.js). Each case states the right answer and is a strict
xfail with the reason: when the indexer learns it, the case passes, the xfail fails the suite, and the mark has to
go."""

import contextlib
import io

import pytest

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
         "the entry of a package is a build the repo lacks, and no project its config references says where its source is"),
    case("an-import-of-a-package-whose-source-a-condition-of-a-tool-names-reaches-it", CONDITION_OF_A_TOOL,
         ("packages/web/src/use:Use", "EXTENDS", "packages/core/src/index:Base"),
         "the condition that leads to the source is one the bundler's config enables, which TypeScript does not read"),
]

NOT_WRITTEN_IN_PLACE = ("a member's type is a function only a name, `typeof` or a union gives, which the syntax does "
                        "not decide")
THEME = 'import {{ Theme }} from "./models";\nexport function main(t: Theme) {{ return t.{}(1); }}\n'
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
]


def _indexed(root, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in {"package.json": '{"name": "app"}\n', **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


@pytest.mark.parametrize("files, edge", CASES)
def test_a_base_and_an_override_the_declarations_give_are_edges(tmp_path, files, edge):
    res, rv = _indexed(tmp_path, files)
    q = {s.id: s.qualified_name for s in res.symbols}
    assert edge in {(q[e.source_id], e.kind, q[e.target_id]) for e in rv.hierarchy}


@pytest.mark.parametrize("files, member", MEMBERS)
def test_the_member_a_call_reaches_is_a_symbol(tmp_path, files, member):
    res, _ = _indexed(tmp_path, files)
    assert member in {s.qualified_name for s in res.symbols}
