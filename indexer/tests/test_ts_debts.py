"""TS's and JS's declarations the graph still misses: a base in a package whose entry is a build the repo lacks. Each
case states the right answer and is a strict xfail with the reason: when the indexer learns it, the case passes, the
xfail fails the suite, and the mark has to go."""

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


def case(id, files, edge, why):
    return pytest.param(files, edge, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("an-import-of-a-package-whose-entry-is-a-build-the-repo-lacks-reaches-its-source", BUILD_ENTRY,
         ("packages/web/src/use:Use", "EXTENDS", "packages/core/src/index:Base"),
         "the entry of a package is a build the repo lacks, and nothing in its config says where its source is"),
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
