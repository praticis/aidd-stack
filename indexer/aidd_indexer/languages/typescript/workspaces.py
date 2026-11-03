"""The packages the repo's own workspaces declare: a `package.json`'s `workspaces` (a list, or `{packages}`) and a
`pnpm-workspace.yaml`'s `packages`, with their globs, at any depth. A package is the folder of a `package.json` that
one of them matches and that names itself. A file sees the packages of each workspace that holds it, the deepest first,
as the walk up the `node_modules` of its folders does, since a package manager links a workspace's packages there."""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path

import yaml

from ..base import ResolveContext

_KEY = "ts_workspaces"


def workspaces(ctx: ResolveContext) -> Workspaces:
    """The repo's workspaces, read once for each context that resolves an import."""
    found = ctx.extra.get(_KEY)
    if found is None:
        found = ctx.extra[_KEY] = Workspaces(ctx.root, _folders(ctx.files_by_path))
    return found


def _folders(paths) -> set[str]:
    """Every folder that holds a file, and every one above: a manifest shares its folder's module with the first the
    folder has, so the modules do not list them all."""
    return {folder for path in paths for folder in _above(path)}


def _above(path: str):
    folder = posixpath.dirname(path)
    while folder:
        yield folder
        folder = posixpath.dirname(folder)
    yield ""


def package_name(spec: str) -> tuple[str, str]:
    """The package a bare specifier names, and the subpath of it: `@a/b/c` is (`@a/b`, `c`)."""
    parts = spec.split("/")
    size = 2 if spec.startswith("@") else 1
    return "/".join(parts[:size]), "/".join(parts[size:])


class Workspaces:
    def __init__(self, root: Path, folders: set[str]):
        self.packages = {f: p for f in sorted(folders) if isinstance(p := _json(root / f / "package.json"), dict)}
        roots = [(f, _members(f, self.packages, _globs(root, f, p))) for f, p in self.packages.items()]
        self._roots = sorted((r for r in roots if r[1]), key=lambda r: -len(r[0]))

    def member(self, file: str, name: str) -> str | None:
        """The folder of the package `name` that the file at path `file` sees; None where it sees none."""
        return next((m[name] for root, m in self._roots if name in m and (not root or file.startswith(f"{root}/"))),
                    None)


def _globs(root: Path, folder: str, package: dict) -> list[str]:
    declared = package.get("workspaces")
    listed = declared.get("packages") if isinstance(declared, dict) else declared
    out = [g for g in listed if isinstance(g, str)] if isinstance(listed, list) else []
    try:
        pnpm = yaml.safe_load((root / folder / "pnpm-workspace.yaml").read_text(errors="replace"))
    except (OSError, yaml.YAMLError):
        return out
    more = pnpm.get("packages") if isinstance(pnpm, dict) else None
    return out + [g for g in more if isinstance(g, str)] if isinstance(more, list) else out


def _members(root: str, packages: dict[str, dict], globs: list[str]) -> dict[str, str]:
    """`name -> folder` of the packages below `root` that the globs match and `!` globs do not."""
    include = [_glob(g) for g in globs if not g.startswith("!")]
    exclude = [_glob(g[1:]) for g in globs if g.startswith("!")]
    prefix = f"{root}/" if root else ""
    found: dict[str, str] = {}
    for folder, package in packages.items():
        below = folder.removeprefix(prefix)
        if folder and folder != root and folder.startswith(prefix) and isinstance(package.get("name"), str) \
                and any(g.fullmatch(below) for g in include) and not any(g.fullmatch(below) for g in exclude):
            found.setdefault(package["name"], folder)
    return found


def _glob(written: str) -> re.Pattern:
    """A workspace glob: `**` any folders, `*` within one name, a leading `./` and a trailing `/` ignored."""
    written = written.strip().removeprefix("./").strip("/")
    return re.compile(re.escape(written).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*"))


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError):
        return None
