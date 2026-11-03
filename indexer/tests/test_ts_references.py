"""An import that names the output of a project the importing file's config references resolves to the source file that
project builds it from, as TypeScript resolves it where the output is not built (scripts/checks/ts_modules.js and
ts_heritage.js read a program with `useSourceOfProjectReferenceRedirect`, the way an editor does): a package's `types`
or `main` that is a file in the project's `outDir` or `declarationDir`, a subpath, a path below it, a `paths` target, with
the `rootDir` the project writes, or else the folder of its config. A project
the file's config does not reference, and a source its `include` does not hold, leave the import as it is."""

import contextlib
import io
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.languages.typescript.modules import Package, module_target
from aidd_indexer.languages.typescript.type_index import module_of

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
CLASS = "export class {name} {{ run() {{}} }}\n"


def _config(options: dict, **rest) -> str:
    return json.dumps({"compilerOptions": options, **rest}) + "\n"


def _package(name: str, **fields) -> str:
    return json.dumps({"name": name, **fields}) + "\n"


def _named(stem: str) -> str:
    """A source's path: a stem of no extension is a `.ts` file."""
    return stem if re.search(r"\.[mc]?tsx?$", stem) else f"{stem}.ts"


BUILT = {"composite": True, "outDir": "./lib", "rootDir": "./src"}
LIBRARIES = {
    "a": (_package("@x/a", types="./lib/index.d.ts", main="./lib/index.js"), _config(BUILT, include=["src"]),
          ["src/index", "A"], ["src/util", "U"]),
    "m": (_package("@x/m", main="./out/main.js"), _config({**BUILT, "outDir": "./out"}, include=["src"]),
          ["src/main", "M"]),
    "d": (_package("@x/d", types="./types/index.d.ts"),
          _config({**BUILT, "outDir": "./dist", "declarationDir": "./types"}, include=["src"]), ["src/index", "D"]),
    "c": (_package("@x/c", types="./build/index.d.ts"), _config({"composite": True, "outDir": "./build"}),
          ["index", "C"]),
    "e": (_package("@x/e", types="./lib/index.d.ts"), json.dumps({"extends": "./tsconfig.base.json",
                                                                    "include": ["src"]}) + "\n", ["src/index", "E"]),
    "n": (_package("@x/n", types="./lib/src/index.d.ts"), _config({"outDir": "./lib"}, include=["src"]),
          ["src/index", "N"]),
    "n2": (_package("@x/n2", types="./lib/index.d.ts"), _config({"outDir": "./lib"}, include=["src"]),
           ["src/index", "N2"]),
    "b": (_package("@x/b", types="./lib/index.d.ts"), _config(BUILT, include=["src"]), ["src/index", "B"]),
    "mm": (_package("@x/mm", types="./lib/index.d.mts"), _config(BUILT, include=["src"]), ["src/index.mts", "Mm"]),
    "cc": (_package("@x/cc", types="./lib/index.d.cts"), _config(BUILT, include=["src"]), ["src/index.cts", "Cc"]),
    "tx": (_package("@x/tx", types="./lib/index.d.ts"), _config(BUILT, include=["src"]), ["src/index.tsx", "Tx"]),
    "k": (_package("@x/k", types="./lib/index.d.ts"), _config({"outDir": "./lib", "rootDir": "./src"},
                                                                include=["src"]), ["src/index", "K"]),
    "u": (_package("@x/u", types="./lib/index.d.ts"), _config(BUILT, include=["src"]), ["src/index", "Unreferenced"]),
    "x": (_package("@x/x", main="./lib/b.js"), _config(BUILT, include=["src/a.ts"]), ["src/a", "Xa"], ["src/b", "Xb"]),
    "ex": (_package("@x/ex", exports={".": {"types": "./lib/index.d.ts", "default": "./lib/index.js"},
                                      "./sub": "./lib/sub.js"}), _config(BUILT, include=["src"]),
           ["src/index", "Ex"], ["src/sub", "ExSub"]),
    "r": (_package("@x/r", types="./lib/index.d.ts"), _config(BUILT, include=["src"], references=[{"path": "../t"}]),
          ["src/index", "R"]),
    "t": (_package("@x/t", types="./lib/index.d.ts"), _config(BUILT, include=["src"]), ["src/index", "T"]),
}
FILES = {
    "package.json": json.dumps({"name": "app", "private": True, "workspaces": ["libs/*"]}) + "\n",
    "libs/e/tsconfig.base.json": _config(BUILT),
    "app/tsconfig.json": _config(
        {"paths": {"@alias/a": ["../libs/a/lib/index"]}}, include=["src"],
        references=[{"path": f"../libs/{lib}"} for lib in ("a", "m", "d", "c", "e", "n", "n2", "b", "mm", "cc", "tx", "k", "x", "ex", "r")]),
    "app2/tsconfig.json": _config({"baseUrl": "../libs"}, include=["src"], references=[{"path": "../libs/a"}]),
    "other/tsconfig.json": _config({}, include=["src"]),
}
FILES["libs/b/lib/index.d.ts"] = "export declare class Built { run(): void; }\n"
for lib, (package, config, *sources) in LIBRARIES.items():
    FILES[f"libs/{lib}/package.json"] = package
    FILES[f"libs/{lib}/tsconfig.json"] = config
    FILES.update({f"libs/{lib}/{_named(stem)}": CLASS.format(name=name) for stem, name in sources})
IMPORTS = {
    "app/src/use.ts": [
        ("@x/a", "A", "libs/a/src/index"), ("@x/a/lib/util", "U", "libs/a/src/util"),
        ("@x/m", "M", "libs/m/src/main"), ("@x/d", "D", "libs/d/src/index"), ("@x/c", "C", "libs/c/index"),
        ("@x/e", "E", "libs/e/src/index"), ("@x/n", "N", "libs/n/src/index"), ("@x/n2", "N2", None), ("@x/b", "B", "libs/b/src/index"),
        ("@x/mm", "Mm", "libs/mm/src/index.mts"), ("@x/cc", "Cc", "libs/cc/src/index.cts"),
        ("@x/tx", "Tx", "libs/tx/src/index.tsx"),
        ("@x/k", "K", "libs/k/src/index"), ("@x/u", "Unreferenced", None), ("@x/x", "Xb", None),
        ("@x/ex", "Ex", "libs/ex/src/index"), ("@x/ex/sub", "ExSub", "libs/ex/src/sub"),
        ("@x/r", "R", "libs/r/src/index"), ("@x/t", "T", "libs/t/src/index"),
        ("@alias/a", "A", "libs/a/src/index"), ("../../libs/a/lib/util", "U", "libs/a/src/util"),
        ("../../libs/a/lib", "A", "libs/a/src/index"), ("../../libs/a", "A", "libs/a/src/index")],
    "app2/src/use.ts": [("a/lib/util", "U", "libs/a/src/util")],
    "other/src/use.ts": [("@x/a", "A", None)],
}
for file, rows in IMPORTS.items():
    FILES[file] = "".join(f'import {{ {name} as B{i} }} from "{spec}";\nexport class K{i} extends B{i} {{}}\n'
                          for i, (spec, name, _) in enumerate(rows))
WANT = {(file, spec): _named(target) if target else None for file, rows in IMPORTS.items() for spec, _, target in rows}
BASES = {f"{file.removesuffix('.ts')}:K{i}": [f"{re.sub(r'[.][mc]?tsx?$', '', target)}:{name}"] if target else []
         for file, rows in IMPORTS.items() for i, (_, name, target) in enumerate(rows)}


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def _checker(script: str, root: Path, *flags: str, stdin: str = "") -> list[dict]:
    env = {**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}
    out = subprocess.run(["node", str(CHECKS / script), *flags, str(root)], input=stdin, capture_output=True, text=True,
                         check=True, env=env).stdout
    return [json.loads(line) for line in out.splitlines()]


def _imports(root: Path) -> dict[tuple[str, str], str | None]:
    rows = _checker("ts_modules.js", root, "--link", stdin="".join(f"{file}\n" for file in IMPORTS))
    return {(r["file"], r["spec"]): None if r["to"] == "outside" else r["to"] for r in rows}


def _bases(root: Path) -> dict[str, list[str]]:
    rows = _checker("ts_heritage.js", root, "--link")
    return {f"{module_of(r['file'])}:{r['name']}": r["declared"] for r in rows if r["clause"] == "extends"}


def test_the_case_is_what_typescript_says_where_a_project_is_referenced(case):
    assert _imports(case) == WANT
    bases = _bases(case)
    assert {k: bases[k] for k in BASES} == BASES


def _context(root: Path):
    from aidd_indexer.core.discovery import build_files, discover_modules, list_files
    from aidd_indexer.languages.base import ResolveContext
    repo = RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root))
    rels = list_files(root)
    modules, _ = discover_modules(repo, rels)
    files = build_files(repo, rels, modules)
    return ResolveContext(root, {f.path: f for f in files}, {m.path: m for m in modules}, {m.id: m for m in modules},
                          {f.id: f for f in files}, {})


def test_an_import_reaches_the_source_the_referenced_project_builds_it_from(case):
    ctx = _context(case)
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
