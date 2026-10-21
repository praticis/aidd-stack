#!/usr/bin/env python3
"""The code's shape against its targets: functions above the complexity limit (ruff C901) and modules above the line
limit, counted over the whole file as `wc -l` counts. It exits 0, unless `--strict` finds anything over a target, or
`--against REF` finds a function or a module over a target that is new or worse than at REF.

    python indexer/scripts/shape.py [--complexity 9] [--lines 300] [--strict] [--against REF] [--json FILE] [path ...]

By default it reads the indexer's code: the package, the scripts and the tests, but not the tests' fixture repos,
which copy the shape of other projects' code.

`--against` is a ratchet: what is already over a target may stay while it does not grow, and nothing joins it. A
function is matched by its file and name, or by its name alone when it moved to another file.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

INDEXER = Path(__file__).resolve().parent.parent
ROOT = INDEXER.parent                           # a report's paths are relative to it, on both sides of `--against`
CODE = [INDEXER / "aidd_indexer", INDEXER / "scripts", INDEXER / "tests"]
FIXTURES = ("indexer/tests/fixtures", "indexer/tests/mcp_it")


def _fixture(rel: str) -> bool:
    return any(rel == f or rel.startswith(f + "/") for f in FIXTURES)


def complex_functions(paths: list[Path], limit: int, root: Path = ROOT) -> list[dict] | None:
    """(file, line, function, complexity) above `limit`, or None when ruff is not installed."""
    ruff = shutil.which("ruff")
    if ruff is None:
        return None
    cmd = [ruff, "check", "--no-cache", "--isolated", "--select", "C901", "--output-format", "json",
           "--config", f"lint.mccabe.max-complexity = {limit}", "--extend-exclude", ",".join(FIXTURES),
           *map(str, paths)]
    found = json.loads(subprocess.run(cmd, capture_output=True, text=True, cwd=root).stdout or "[]")
    out = []
    for f in found:
        name, _, rest = f["message"].partition("` is too complex (")
        out.append({"file": os.path.relpath(f["filename"], root), "line": f["location"]["row"],
                    "function": name.strip("`"), "complexity": int(rest.split(" ")[0])})
    return sorted(out, key=lambda x: -x["complexity"])


def long_modules(paths: list[Path], limit: int, root: Path = ROOT) -> list[dict]:
    files = [f for p in paths for f in (sorted(p.rglob("*.py")) if p.is_dir() else [p])]
    sizes = [{"file": rel, "lines": len(f.read_bytes().splitlines())}
             for f in files if not _fixture(rel := os.path.relpath(f, root))]
    return sorted((s for s in sizes if s["lines"] > limit), key=lambda x: -x["lines"])


def report(paths: list[Path], args, root: Path = ROOT) -> dict:
    return {"functions": complex_functions(paths, args.complexity, root),
            "modules": long_modules(paths, args.lines, root)}


def at_ref(ref: str, paths: list[Path], args) -> dict:
    """The report of `paths` as the git ref `ref` holds them."""
    rels = [os.path.relpath(p.resolve(), ROOT) for p in paths]
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", ref, *rels], capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        archive.extractall(tmp, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        return report([Path(tmp) / r for r in rels], args, Path(tmp))


def worse_modules(base: list[dict], head: list[dict]) -> list[str]:
    was = {m["file"]: m["lines"] for m in base}
    return [f"{m['file']}: {m['lines']} lines, " + (f"was {was[m['file']]}" if m["file"] in was else "new over the limit")
            for m in head if m["lines"] > was.get(m["file"], 0)]


def _pool(functions: list[dict], key) -> dict:
    pool: dict = {}
    for f in sorted(functions, key=lambda f: -f["complexity"]):
        pool.setdefault(key(f), []).append(f["complexity"])
    return pool


def _pair(functions: list[dict], pool: dict, key) -> tuple[list[str], list[dict]]:
    """Each function against the largest complexity left under its key in `pool`, largest first, so of two functions
    with one name the worse one shows: those that grew, and those with nothing to pair with."""
    worse, alone = [], []
    for f in functions:
        left = pool.get(key(f))
        if not left:
            alone.append(f)
            continue
        was = left.pop(0)
        if f["complexity"] > was:
            worse.append(f"{f['file']}:{f['line']} {f['function']}: complexity {f['complexity']}, was {was}")
    return worse, alone


def _at_file(f: dict) -> tuple[str, str]:
    return f["file"], f["function"]


def worse_functions(base: list[dict], head: list[dict]) -> list[str]:
    head = sorted(head, key=lambda f: -f["complexity"])
    pool = _pool(base, _at_file)
    worse, moved = _pair(head, pool, _at_file)
    left = [{"function": name, "complexity": c} for (_, name), cs in pool.items() for c in cs]
    grew, new = _pair(moved, _pool(left, lambda f: f["function"]), lambda f: f["function"])
    return worse + grew + [f"{f['file']}:{f['line']} {f['function']}: complexity {f['complexity']}, new over the limit"
                           for f in new]


def against(ref: str, head: dict, args) -> list[str]:
    base = at_ref(ref, args.paths, args)
    worse = worse_functions(base["functions"], head["functions"]) + worse_modules(base["modules"], head["modules"])
    print(f"\nagainst {ref}: {len(worse)} new or worse over a target")
    for w in worse:
        print(f"  {w}")
    return worse


def show(rep: dict, args) -> None:
    if rep["functions"] is None:
        print("ruff not installed: complexity not measured", file=sys.stderr)
    else:
        print(f"functions above complexity {args.complexity}: {len(rep['functions'])}")
        for f in rep["functions"]:
            print(f"  {f['complexity']:4}  {f['file']}:{f['line']} {f['function']}")
    print(f"modules above {args.lines} lines: {len(rep['modules'])}")
    for m in rep["modules"]:
        print(f"  {m['lines']:5}  {m['file']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*", type=Path, default=CODE)
    ap.add_argument("--complexity", type=int, default=9)
    ap.add_argument("--lines", type=int, default=300)
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is over a target")
    ap.add_argument("--against", metavar="REF", help="exit 1 when anything over a target is new or worse than at REF")
    ap.add_argument("--json", type=Path, help="also write the report here")
    args = ap.parse_args()
    rep = report(args.paths, args)
    show(rep, args)
    if args.json:
        args.json.write_text(json.dumps(rep, indent=1))
    if args.against and rep["functions"] is None:
        return 2                                # a ratchet that cannot measure must not pass
    worse = against(args.against, rep, args) if args.against else []
    over = bool(rep["modules"]) or bool(rep["functions"])
    return 1 if worse or (args.strict and over) else 0


if __name__ == "__main__":
    sys.exit(main())
