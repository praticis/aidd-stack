"""TS's and JS's declarations the graph still misses: a base the type index does not reach, in a declaration file or in
a package of the repo's workspace, and a method or a class that is no symbol. Each case states the right answer and is
a strict xfail with the reason: when the indexer learns it, the case passes, the xfail fails the suite, and the mark has
to go."""

import contextlib
import io

import pytest

PACKAGE = '{"name": "app"}\n'
DECLARATION = {
    "package.json": PACKAGE,
    "types/base.d.ts": "export interface Base { run(): void; }\n",
    "app/use.ts": 'import { Base } from "../types/base";\nexport class Use implements Base { run() {} }\n',
}
WORKSPACE = {
    "package.json": '{"name": "app", "workspaces": ["packages/*"]}\n',
    "packages/core/package.json": '{"name": "@app/core", "types": "src/index.ts"}\n',
    "packages/core/src/index.ts": "export class Base { run() {} }\n",
    "packages/web/package.json": '{"name": "@app/web", "dependencies": {"@app/core": "*"}}\n',
    "packages/web/src/use.ts": 'import { Base } from "@app/core";\nexport class Use extends Base { run() {} }\n',
}
COMMONJS = {
    "package.json": PACKAGE,
    "lib/base.js": "class Base { run() {} }\nmodule.exports = Base;\n",
    "app/use.js": 'const Base = require("../lib/base");\nclass Use extends Base { run() {} }\nmodule.exports = Use;\n',
}
CLASS_EXPRESSION = {
    "package.json": PACKAGE,
    "lib/base.js": "class Base { run() {} }\nmodule.exports = Base;\n",
    "app/use.js": 'const Base = require("../lib/base");\nmodule.exports = class Use extends Base { run() {} };\n',
}
FIELD = {
    "package.json": PACKAGE,
    "app/use.ts": "export class Base { run = () => 1; }\nexport class Use extends Base { run = () => 2; }\n",
}


def case(id, files, edge, why):
    return pytest.param(files, edge, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-type-a-hand-written-declaration-file-declares-is-a-base", DECLARATION,
         ("app/use:Use", "IMPLEMENTS", "types/base.d:Base"), "discovery skips every `.d.ts` as generated"),
    case("an-import-of-a-package-of-the-repos-workspace-reaches-its-class", WORKSPACE,
         ("packages/web/src/use:Use", "EXTENDS", "packages/core/src/index:Base"),
         "a package the repo's workspace declares is read as an npm package"),
    case("a-require-of-a-commonjs-export-reaches-its-class", COMMONJS,
         ("app/use:Use", "EXTENDS", "lib/base:Base"), "`module.exports = Base` exports nothing the index reads"),
    case("a-class-a-class-expression-declares-extends-its-base", CLASS_EXPRESSION,
         ("app/use:Use", "EXTENDS", "lib/base:Base"), "a class expression is no symbol"),
    case("a-function-a-class-field-holds-is-a-method-of-its-class", FIELD,
         ("app/use:Use.run", "OVERRIDES", "app/use:Base.run"), "a class field that holds a function is no symbol"),
]


@pytest.mark.parametrize("files, edge", CASES)
def test_a_base_and_an_override_the_declarations_give_are_edges(tmp_path, files, edge):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(tmp_path)),
                                      convs=[])
    q = {s.id: s.qualified_name for s in res.symbols}
    assert edge in {(q[e.source_id], e.kind, q[e.target_id]) for e in rv.hierarchy}
