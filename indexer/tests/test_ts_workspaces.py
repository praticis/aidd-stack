"""An import of a package the repo's own workspace declares resolves to the file TypeScript resolves it to through the
link a package manager makes (scripts/checks/ts_modules.js and ts_heritage.js, with real links in the case, and the host
that emulates them where a clone has none): the entry its `exports` names by the conditions TypeScript matches and the
config's `customConditions`, its `types` or `main`, a subpath its `exports` maps, or its folder. A member is one a
`workspaces` or a `pnpm-workspace.yaml` declares, and a file sees those of each workspace that holds it, the deepest
first, as the walk up the `node_modules` of its folders does. So is a package a `file:`, `link:` or `portal:`
dependency of a `package.json` names, under the dependency's own name, for the files below that manifest. An entry that
is a build the clone lacks leaves a package."""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.languages.typescript.modules import Package, module_target
from aidd_indexer.languages.typescript.type_index import module_of
from aidd_indexer.languages.typescript.workspaces import Workspaces

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
CLASS = "export class {name} {{ run() {{}} }}\n"
CORE = ('{"name": "@app/core", "exports": {".": {"types": "./src/index.ts", "import": "./dist/index.js"}, '
        '"./util": "./src/util.ts", "./feature/*": "./src/feature/*.ts", "./feature/deep/*": "./src/deep/*.ts"}}')
PACKAGES = {
    "packages/core": (CORE, ["src/index", "Core"], ["src/util", "Util"], ["src/feature/a", "FeatureA"],
                      ["src/deep/b", "Deep"]),
    "packages/typed": ('{"name": "@app/typed", "types": "./src/index.ts", "main": "./dist/index.js"}',
                       ["src/index", "Typed"]),
    "packages/mainonly": ('{"name": "mainonly", "main": "./src/index.js"}', ["src/index", "Main"]),
    "packages/plain": ('{"name": "@app/plain"}', ["index", "Plain"], ["util", "PlainUtil"]),
    "packages/built": ('{"name": "@app/built", "main": "./dist/index.js", "types": "./dist/index.d.ts"}',
                       ["src/index", "Built"]),
    "packages/cond": ('{"name": "@app/cond", "exports": {".": {"source": "./src/index.ts", "default": '
                      '"./dist/index.js"}}}', ["src/index", "Cond"]),
    "packages/gated": ('{"name": "@app/gated", "exports": {".": "./src/index.ts"}}', ["src/index", "Gated"],
                       ["src/internal", "Internal"]),
    "packages/esm": ('{"name": "@app/esm", "exports": {".": {"require": "./src/cjs.ts", "import": "./src/index.ts"}}}',
                     ["src/index", "Esm"], ["src/cjs", "Cjs"]),
    "packages/dflt": ('{"name": "@app/dflt", "exports": {".": {"worker": "./src/worker.ts", "default": '
                      '"./src/index.ts"}}}', ["src/index", "Dflt"], ["src/worker", "Worker"]),
    "packages/fall": ('{"name": "@app/fall", "exports": {".": {"types": "./dist/index.d.ts", "default": '
                      '"./src/index.ts"}}}', ["src/index", "Fall"]),
    "packages/str": ('{"name": "@app/str", "exports": "./src/index.ts"}', ["src/index", "Str"], ["src/other", "Other"]),
    "packages/typ": ('{"name": "@app/typ", "typings": "./src/index.ts"}', ["src/index", "Typ"]),
    "packages/over": ('{"name": "@app/over", "types": "./src/index.ts"}', ["src/index", "Over"], ["alt", "OverAlt"]),
    "packages/excluded": ('{"name": "@app/excluded"}', ["index", "Excluded"]),
    "packages/unnamed": ("{}", ["index", "Unnamed"]),
    "packages/core/inner": ('{"name": "@app/inner"}', ["index", "Inner"]),
    "web/lib/ui": ('{"name": "@web/ui", "types": "./index.ts"}', ["index", "Ui"]),
    "web/lib/core": ('{"name": "@app/core", "types": "./index.ts"}', ["index", "WebCore"]),
    "pn/libs/one": ('{"name": "@pn/one", "types": "./index.ts"}', ["index", "One"]),
    "sample": ('{"name": "fastify"}', ["index", "Sample"]),
    "libs/linked": ('{"name": "@lib/linked", "types": "./src/index.ts"}', ["src/index", "Linked"]),
    "libs/built": ('{"name": "@lib/built", "main": "./dist/index.js", "types": "./dist/index.d.ts"}',
                   ["src/index", "LinkBuilt"]),
    "libs/looked": ('{"name": "@lib/looked", "types": "./index.ts"}', ["index", "Looked"]),
    "libs/ported": ('{"name": "@lib/ported", "types": "./index.ts"}', ["index", "Ported"]),
    "libs/origin": ('{"name": "@lib/origin", "types": "./index.ts"}', ["index", "Origin"]),
    "tools": ('{"name": "tools", "dependencies": {"@lib/linked": "file:../libs/linked", "@lib/built": '
              '"file:../libs/built", "@lib/alias": "file:../libs/origin", "@lib/tarball": "file:../vendor/x.tgz", '
              '"@lib/gone": "file:../libs/gone"}, "devDependencies": {"@lib/looked": "link:../libs/looked"}, '
              '"optionalDependencies": {"@lib/ported": "portal:../libs/ported"}}',),
    "tools/inner": ('{"name": "inner-tool", "dependencies": {"@lib/linked": "file:../../libs/looked"}}',),
}
FILES = {
    "go.mod": "module app\n",
    "package.json": '{"name": "app", "private": true, "workspaces": ["./packages/*", "!./packages/excluded"]}\n',
    "tsconfig.json": '{"extends": "./tsconfig.base.json", "compilerOptions": {"paths": {"@app/over": '
                     '["packages/over/alt.ts"]}}}\n',
    "tsconfig.base.json": '{"compilerOptions": {"customConditions": ["source"]}}\n',
    "web/package.json": '{"name": "web", "workspaces": {"packages": ["lib/*"]}}\n',
    "pn/package.json": '{"name": "pn"}\n',
    "pn/pnpm-workspace.yaml": "packages:\n  - libs/*\n",
}
for folder, (manifest, *sources) in PACKAGES.items():
    FILES[f"{folder}/package.json"] = manifest + "\n"
    FILES.update({f"{folder}/{stem}.ts": CLASS.format(name=name) for stem, name in sources})
LINKS = {f"{root}node_modules/{name}": folder for root, name, folder in (
    ("", "@app/core", "packages/core"), ("", "@app/typed", "packages/typed"), ("", "mainonly", "packages/mainonly"),
    ("", "@app/plain", "packages/plain"), ("", "@app/built", "packages/built"), ("", "@app/cond", "packages/cond"),
    ("", "@app/gated", "packages/gated"), ("", "@app/esm", "packages/esm"), ("", "@app/dflt", "packages/dflt"),
    ("", "@app/fall", "packages/fall"), ("", "@app/str", "packages/str"), ("", "@app/typ", "packages/typ"),
    ("", "@app/over", "packages/over"), ("web/", "@web/ui", "web/lib/ui"), ("web/", "@app/core", "web/lib/core"),
    ("pn/", "@pn/one", "pn/libs/one"), ("tools/", "@lib/linked", "libs/linked"), ("tools/", "@lib/built", "libs/built"),
    ("tools/", "@lib/alias", "libs/origin"), ("tools/", "@lib/looked", "libs/looked"),
    ("tools/", "@lib/ported", "libs/ported"), ("tools/inner/", "@lib/linked", "libs/looked"))}
IMPORTS = {
    "app/use.ts": [
        ("@app/core", "Core", "packages/core/src/index"), ("@app/core/util", "Util", "packages/core/src/util"),
        ("@app/core/feature/a", "FeatureA", "packages/core/src/feature/a"),
        ("@app/core/feature/deep/b", "Deep", "packages/core/src/deep/b"),
        ("@app/typed", "Typed", "packages/typed/src/index"), ("mainonly", "Main", "packages/mainonly/src/index"),
        ("@app/plain", "Plain", "packages/plain/index"), ("@app/plain/util", "PlainUtil", "packages/plain/util"),
        ("@app/built", "Built", None), ("@app/cond", "Cond", "packages/cond/src/index"),
        ("@app/gated", "Gated", "packages/gated/src/index"), ("@app/gated/internal", "Internal", None),
        ("@app/esm", "Esm", "packages/esm/src/index"), ("@app/dflt", "Dflt", "packages/dflt/src/index"),
        ("@app/fall", "Fall", "packages/fall/src/index"), ("@app/str", "Str", "packages/str/src/index"),
        ("@app/str/other", "Other", None), ("@app/typ", "Typ", "packages/typ/src/index"),
        ("@app/over", "OverAlt", "packages/over/alt"), ("@app/excluded", "Excluded", None),
        ("@app/inner", "Inner", None), ("@web/ui", "Ui", None), ("fastify", "Sample", None),
        ("@lib/linked", "Linked", None)],
    "web/app/page.ts": [("@web/ui", "Ui", "web/lib/ui/index"), ("@app/core", "WebCore", "web/lib/core/index"),
                        ("@app/typed", "Typed", "packages/typed/src/index")],
    "web2/use.ts": [("@web/ui", "Ui", None)],
    "pn/app/x.ts": [("@pn/one", "One", "pn/libs/one/index")],
    "tools/use.ts": [("@lib/linked", "Linked", "libs/linked/src/index"), ("@lib/built", "LinkBuilt", None),
                     ("@lib/looked", "Looked", "libs/looked/index"), ("@lib/ported", "Ported", "libs/ported/index"),
                     ("@lib/alias", "Origin", "libs/origin/index"), ("@lib/tarball", "Tarball", None),
                     ("@lib/gone", "Gone", None)],
    "tools/inner/use.ts": [("@lib/linked", "Looked", "libs/looked/index")],
}
for file, rows in IMPORTS.items():
    FILES[file] = "".join(f'import {{ {name} as B{i} }} from "{spec}";\nexport class K{i} extends B{i} {{}}\n'
                          for i, (spec, name, _) in enumerate(rows))
WANT = {(file, spec): f"{target}.ts" if target else None for file, rows in IMPORTS.items() for spec, _, target in rows}
BASES = {f"{file.removesuffix('.ts')}:K{i}": [f"{target}:{name}"] if target else []
         for file, rows in IMPORTS.items() for i, (_, name, target) in enumerate(rows)}


def _write(root: Path) -> Path:
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    return _write(tmp_path_factory.mktemp("repo"))


@pytest.fixture(scope="module")
def linked(tmp_path_factory) -> Path:
    root = _write(tmp_path_factory.mktemp("installed"))
    for link, target in LINKS.items():
        (root / link).parent.mkdir(parents=True, exist_ok=True)
        (root / link).symlink_to(os.path.relpath(root / target, (root / link).parent))
    return root


def _checker(script: str, root: Path, *flags: str, stdin: str = "") -> list[dict]:
    env = {**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}
    out = subprocess.run(["node", str(CHECKS / script), *flags, str(root)], input=stdin, capture_output=True, text=True,
                         check=True, env=env).stdout
    return [json.loads(line) for line in out.splitlines()]


def _imports(root: Path, *flags: str) -> dict[tuple[str, str], str | None]:
    rows = _checker("ts_modules.js", root, *flags, stdin="".join(f"{file}\n" for file in IMPORTS))
    return {(r["file"], r["spec"]): None if r["to"] == "outside" else r["to"] for r in rows}


def _bases(root: Path, *flags: str) -> dict[str, list[str]]:
    rows = _checker("ts_heritage.js", root, *flags)
    return {f"{module_of(r['file'])}:{r['name']}": r["declared"] for r in rows if r["clause"] == "extends"}


def test_the_case_is_what_typescript_says_with_the_links_made(linked):
    assert _imports(linked) == WANT
    bases = _bases(linked)
    assert {k: bases[k] for k in BASES} == BASES


def test_the_emulated_link_resolves_what_the_made_one_does(case):
    assert _imports(case, "--link") == WANT
    bases = _bases(case, "--link")
    assert {k: bases[k] for k in BASES} == BASES


def test_an_import_reaches_the_file_typescript_resolves_it_to(case):
    from aidd_indexer.core.discovery import build_files, discover_modules, list_files
    from aidd_indexer.languages.base import ResolveContext
    repo = RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(case))
    rels = list_files(case)
    modules, _ = discover_modules(repo, rels)
    files = build_files(repo, rels, modules)
    ctx = ResolveContext(case, {f.path: f for f in files}, {m.path: m for m in modules}, {m.id: m for m in modules},
                         {f.id: f for f in files}, {})
    got = {}
    for file, spec in WANT:
        found = module_target(ctx, ctx.files_by_path[file], spec)
        got[file, spec] = None if isinstance(found, Package) else getattr(found, "path", None)
    assert got == WANT


@pytest.fixture(scope="module")
def indexed(case):
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(case)),
                                   convs=[])


def test_a_class_extends_the_class_the_checker_gives_its_clause(indexed):
    res, rv = indexed
    q = {s.id: s.qualified_name for s in res.symbols}
    extends = {q[e.source_id]: q[e.target_id] for e in rv.hierarchy if e.kind == "EXTENDS"}
    assert {c: extends.get(c) for c in BASES} == {c: (b[0] if b else None) for c, b in BASES.items()}


def test_an_import_is_an_edge_to_the_file_or_to_the_package_where_none_resolves(indexed):
    res, rv = indexed
    paths = {f.id: f.path for f in res.files}
    got = {(paths[e.file_id], e.spec): (e.target_label, paths.get(e.target_id)) for e in rv.imports
           if (paths.get(e.file_id), e.spec) in WANT}
    assert got == {k: ("File", v) if v else ("Package", None) for k, v in WANT.items()}


def test_a_member_of_the_workspace_outranks_a_dependency_of_its_name_in_the_same_manifest(tmp_path):
    """The package managers leave this undefined, so no checker decides it: the member the manifest's own `workspaces`
    declares is the choice."""
    manifests = {"package.json": '{"name": "a", "workspaces": ["pkgs/*"], "dependencies": {"dup": "file:libs/dup"}}',
                 "pkgs/dup/package.json": '{"name": "dup"}', "libs/dup/package.json": '{"name": "dup"}'}
    for rel, body in manifests.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    assert Workspaces(tmp_path, {"", "pkgs/dup", "libs/dup"}).member("app/x.ts", "dup") == "pkgs/dup"
