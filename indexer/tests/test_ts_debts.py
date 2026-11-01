"""TS's and JS's declarations the graph still misses: a base the type index does not reach, and a method that is no
symbol. Each case states the right answer and is a strict xfail with the reason: when the indexer learns it, the case
passes, the xfail fails the suite, and the mark has to go."""

import contextlib
import io

import pytest

PACKAGE = '{"name": "app"}\n'
TSCONFIG_PATHS = {
    "package.json": PACKAGE,
    "tsconfig.json": '{"compilerOptions": {"baseUrl": ".", "paths": {"@core/*": ["lib/core/*"]}}}\n',
    "lib/core/base.ts": "export class Base { run() {} }\n",
    "app/use.ts": 'import { Base } from "@core/base";\nexport class Use extends Base { run() {} }\n',
}
COMMONJS = {
    "package.json": PACKAGE,
    "lib/base.js": "class Base { run() {} }\nmodule.exports = Base;\n",
    "app/use.js": 'const Base = require("../lib/base");\nclass Use extends Base { run() {} }\nmodule.exports = Use;\n',
}
FIELD = {
    "package.json": PACKAGE,
    "app/use.ts": "export class Base { run = () => 1; }\nexport class Use extends Base { run = () => 2; }\n",
}


def case(id, files, edge, why):
    return pytest.param(files, edge, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("an-import-the-repos-tsconfig-paths-map-reaches-its-file", TSCONFIG_PATHS,
         ("app/use:Use", "EXTENDS", "lib/core/base:Base"), "an alias `paths` declares is read as a package's name"),
    case("a-require-of-a-commonjs-export-reaches-its-class", COMMONJS,
         ("app/use:Use", "EXTENDS", "lib/base:Base"), "`module.exports = Base` exports nothing the index reads"),
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
