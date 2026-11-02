"""TS's module resolution against TypeScript's own, over every TS and JS file the indexer extracts from the repos under
/corpus: for each import, the file the index's `module_target` names against the one TypeScript resolves it to
(`ts_modules.js`, each file read with its `tsconfig.json` or `jsconfig.json`). `same` where both name one file of the
repo, or the index a package and TypeScript none; else the kind of difference, by how TypeScript read the specifier:
the checker's file where the index names a package, none or another file; a file the index does not extract; the
index's file where TypeScript resolves none (an alias a bundler's config declares, a `.vue` file); and, counted apart,
a package a `package.json` of the repo declares, which neither resolves without `node_modules`. The compiler reads the
files; nothing runs.

    ts_modules.py [N]    N samples of each kind (default 5)

In the test image, with the code at /src, the compiler at $AIDD_TYPESCRIPT and the corpus's repos at /corpus."""
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

from aidd_indexer.core.discovery import build_files, discover_modules, list_files
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.languages.base import ResolveContext
from aidd_indexer.languages.typescript.modules import Package, module_target

ORACLE = Path(__file__).with_name("ts_modules.js")
TS = frozenset({"typescript", "tsx", "javascript"})


def context(root: Path) -> tuple[ResolveContext, list[str], set[str]]:
    """The repo's files as the resolver holds them, its TS and JS files, and the packages its `package.json`s name."""
    repo = RepoInfo(tenant="corpus", name=root.name, ref="main", commit_sha="x", root=str(root))
    rels = list_files(root)
    modules, _ = discover_modules(repo, rels)
    files = build_files(repo, rels, modules)
    ctx = ResolveContext(root, {f.path: f for f in files}, {m.path: m for m in modules}, {m.id: m for m in modules},
                         {f.id: f for f in files}, {})
    return ctx, sorted(f.path for f in files if f.language in TS), _workspace(root, rels)


def _workspace(root: Path, rels: list[str]) -> set[str]:
    names = set()
    for rel in (r for r in rels if r.rsplit("/", 1)[-1] == "package.json"):
        try:
            name = json.loads((root / rel).read_text()).get("name")
        except (ValueError, OSError, AttributeError):
            continue
        if isinstance(name, str):
            names.add(name)
    return names


def oracle(root: Path, rels: list[str]) -> list[dict]:
    out = subprocess.run(["node", "--max-old-space-size=8192", str(ORACLE), str(root)], input="\n".join(rels),
                         capture_output=True, text=True, check=True,
                         env={**os.environ, "AIDD_TYPESCRIPT": os.environ.get("AIDD_TYPESCRIPT", "typescript")})
    return [json.loads(line) for line in out.stdout.splitlines()]


def kind_of(mine, row: dict, files: dict, workspace: set[str]) -> str:
    to, via = row["to"], row["via"]
    if to not in (None, "outside"):
        if to not in files:
            return f"a file the index does not extract ({'.d.ts' if to.endswith('.d.ts') else Path(to).suffix})"
        if getattr(mine, "path", None) == to:
            return "same"
        what = "a package" if isinstance(mine, Package) else "none" if mine is None else "another file"
        return f"the checker's file, the index {what} ({via})"
    if mine is not None and not isinstance(mine, Package):
        return f"the index's file, the checker none ({via})"
    if isinstance(mine, Package) and mine.name in workspace:
        return "a package of the repo's workspace"
    return "same"


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 5
    counts, samples = collections.Counter(), collections.defaultdict(list)
    for root in sorted(p for p in Path("/corpus").iterdir() if p.is_dir()):
        ctx, rels, workspace = context(root)
        if not rels:
            continue
        for row in oracle(root, rels):
            mine = module_target(ctx, ctx.files_by_path[row["file"]], row["spec"])
            kind = kind_of(mine, row, ctx.files_by_path, workspace)
            counts[kind] += 1
            if kind != "same" and len(samples[kind]) < n:
                index = mine.name if isinstance(mine, Package) else getattr(mine, "path", None)
                samples[kind].append(f"{root.name}/{row['file']}: {row['spec']!r} -> checker {row['to']}, index {index}")
        print(f"{root.name}: {sum(counts.values())} imports so far", file=sys.stderr, flush=True)
    for key, value in sorted(counts.items()):
        print(f"{key}: {value}")
    for kind, lines in sorted(samples.items()):
        print(f"\n{kind}:\n  " + "\n  ".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
