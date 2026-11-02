"""TS's and JS's imports resolve to the file TypeScript's own module resolution gives them (scripts/checks/ts_modules.js),
each file read with its config: a `paths` pattern, the exact one first and else the longest prefix, each target in
turn, relative to `baseUrl` or to the config that writes them, and none below `baseUrl` after a pattern that
matches and names no file; a name below `baseUrl`; a config's `extends`; the
project a config that only refers to others holds the file in; a `jsconfig.json`; the repo's root, and a folder
written with a trailing `/`. A conventional alias no config maps still names the file a bundler's config would."""

import json
import os
import subprocess
from pathlib import Path

import pytest

CHECKS = Path(__file__).resolve().parents[1] / "scripts" / "checks"
FILES = {
    "package.json": '{"name": "app"}\n',
    "index.js": "module.exports = {};\n",
    "tsconfig.json": """{
  // the app's own names
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@core/*": ["lib/core/*"],
      "@core/special/*": ["lib/special/*"],
      "@app": ["app/main.ts"],
      "@multi/*": ["missing/*", "lib/multi/*"], /* the first target names no file */
      "@gone/*": ["missing/*"],
    },
  },
}
""",
    "lib/core/base.ts": "export class Base {}\n",
    "lib/core/special/y.ts": "export const y = 1;\n",
    "lib/special/y.ts": "export const y = 2;\n",
    "lib/multi/m.ts": "export const m = 1;\n",
    "lib/flat.ts": "export const flat = 1;\n",
    "@gone/x.ts": "export const x = 1;\n",
    "app/main.ts": "export const main = 1;\n",
    "app/sub.ts": "export const sub = 1;\n",
    "app/sub/index.ts": "export const sub = 2;\n",
    "app/use.ts": """import { Base } from "@core/base";
import { y } from "@core/special/y";
import { main } from "@app";
import { m } from "@multi/m";
import { flat } from "lib/flat";
import { x } from "@gone/x";
import { sub } from "./sub/";
import { sub as file } from "./sub";
import React from "react";
""",
    "configs/tsconfig.web.json": '{"compilerOptions": {"paths": {"@web/*": ["../packages/web/src/*"]}}}\n',
    "packages/web/package.json": '{"name": "web"}\n',
    "configs/tsconfig.strict.json": '{"compilerOptions": {"strict": true}}\n',
    "packages/web/tsconfig.json": '{"extends": ["../../configs/tsconfig.web.json", "../../configs/tsconfig.strict"], '
                                  '"include": ["src"]}\n',
    "packages/web/src/a.ts": 'import { b } from "@web/b";\n',
    "packages/web/src/b.ts": "export const b = 1;\n",
    "packages/vite/package.json": '{"name": "vite-app"}\n',
    "packages/vite/tsconfig.json": '{"files": [], "references": [{"path": "./tsconfig.app.json"}, '
                                   '{"path": "./tsconfig.node.json"}]}\n',
    "packages/vite/tsconfig.app.json": '{"compilerOptions": {"paths": {"@/*": ["./lib/*"]}}, "include": ["src"]}\n',
    "packages/vite/tsconfig.node.json": '{"compilerOptions": {"paths": {"@/*": ["./other/*"]}}, '
                                        '"include": ["vite.config.ts"]}\n',
    "packages/vite/src/x.ts": 'import { y } from "@/y";\n',
    "packages/vite/vite.config.ts": 'import { y } from "@/y";\n',
    "packages/vite/src/y.ts": "export const y = 1;\n",
    "packages/vite/lib/y.ts": "export const y = 2;\n",
    "packages/vite/other/y.ts": "export const y = 3;\n",
    "js/package.json": '{"name": "js"}\n',
    "js/jsconfig.json": '{"compilerOptions": {"baseUrl": "./web", "paths": {"~/*": ["./*"]}}}\n',
    "js/app.js": 'import { z } from "~/z";\n',
    "js/z.js": "export const z = 1;\n",
    "js/web/z.js": "export const z = 2;\n",
    "nuxt/package.json": '{"name": "nuxt"}\n',
    "nuxt/pages/p.ts": 'import { c } from "~/components/c";\n',
    "nuxt/components/c.ts": "export const c = 1;\n",
    "examples/demo/run.js": 'const app = require("../..");\n',
}
CHECKER = {
    ("app/use.ts", "@core/base"): "lib/core/base.ts",
    ("app/use.ts", "@core/special/y"): "lib/special/y.ts",
    ("app/use.ts", "@app"): "app/main.ts",
    ("app/use.ts", "@multi/m"): "lib/multi/m.ts",
    ("app/use.ts", "lib/flat"): "lib/flat.ts",
    ("app/use.ts", "@gone/x"): None,
    ("app/use.ts", "./sub/"): "app/sub/index.ts",
    ("app/use.ts", "./sub"): "app/sub.ts",
    ("app/use.ts", "react"): None,
    ("packages/web/src/a.ts", "@web/b"): "packages/web/src/b.ts",
    ("packages/vite/src/x.ts", "@/y"): "packages/vite/lib/y.ts",
    ("packages/vite/vite.config.ts", "@/y"): "packages/vite/other/y.ts",
    ("js/app.js", "~/z"): "js/web/z.js",
    ("nuxt/pages/p.ts", "~/components/c"): None,
    ("examples/demo/run.js", "../.."): "index.js",
}
ALIASED = {("nuxt/pages/p.ts", "~/components/c"): "nuxt/components/c.ts"}
PACKAGES = {("app/use.ts", "react"): "react", ("app/use.ts", "@gone/x"): "@gone/x"}


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("repo")
    for rel, body in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def _checker(root: Path) -> dict[tuple[str, str], str | None]:
    files = sorted(rel for rel in FILES if rel.endswith((".ts", ".js")))
    out = subprocess.run(["node", str(CHECKS / "ts_modules.js"), str(root)], input="\n".join(files),
                         capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")}).stdout
    rows = [json.loads(line) for line in out.splitlines()]
    return {(r["file"], r["spec"]): (None if r["to"] == "outside" else r["to"]) for r in rows}


def _index(root: Path, imports) -> dict[tuple[str, str], str | None]:
    from aidd_indexer.core.discovery import build_files, discover_modules, list_files
    from aidd_indexer.core.model import RepoInfo
    from aidd_indexer.languages.base import ResolveContext
    from aidd_indexer.languages.typescript.modules import Package, module_target
    repo = RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root))
    rels = list_files(root)
    modules, _ = discover_modules(repo, rels)
    files = build_files(repo, rels, modules)
    ctx = ResolveContext(root, {f.path: f for f in files}, {m.path: m for m in modules}, {m.id: m for m in modules},
                         {f.id: f for f in files}, {})
    out = {}
    for file, spec in imports:
        found = module_target(ctx, ctx.files_by_path[file], spec)
        out[file, spec] = found.name if isinstance(found, Package) else getattr(found, "path", None)
    return out


def test_the_case_resolves_as_typescript_says(case):
    assert _checker(case) == CHECKER


def test_an_import_reaches_the_file_typescript_resolves_it_to(case):
    expected = {k: ALIASED.get(k) or PACKAGES.get(k) or v for k, v in _checker(case).items()}
    assert _index(case, expected) == expected
