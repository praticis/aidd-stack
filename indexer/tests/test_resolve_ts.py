"""TypeScript import resolution: the ESM `.js` specifier of a `.ts` file and a package's own `src/*` alias."""
from __future__ import annotations

import contextlib
import io


def test_js_specifiers_and_package_aliases_resolve_to_ts_files(tmp_path):
    """`import { X } from '../enum.js'` names enum.ts (TS with `moduleResolution: nodenext`); `src/x.js` in a package
    below the repo root (immich's server/, `paths: {"src/*": ["./src/*"]}`) is that package's src/x.ts. A package from
    npm stays a package."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "app"
    src = root / "server" / "src"
    (src / "controllers").mkdir(parents=True)
    (root / "server" / "package.json").write_text('{"name": "server"}')
    (src / "enum.ts").write_text("export enum RouteKey { Asset = 'assets' }\n")
    (src / "constants.ts").write_text("export const excludePaths = ['/custom.css'];\n")
    (src / "controllers" / "asset.controller.ts").write_text(
        "import { RouteKey } from '../enum.js';\nimport { excludePaths } from 'src/constants.js';\n"
        "import { Controller } from '@nestjs/common';\n")
    repo = RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    files = {f.id: f.path for f in res.files}
    got = {(e.spec, files.get(e.target_id, e.target_label)) for e in rv.imports}
    assert ("../enum.js", "server/src/enum.ts") in got
    assert ("src/constants.js", "server/src/constants.ts") in got
    assert ("@nestjs/common", "Package") in got
