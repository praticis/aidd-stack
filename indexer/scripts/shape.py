#!/usr/bin/env python3
"""The code's shape against its targets: functions above the complexity limit (ruff C901) and modules above the line
limit, counted over the whole file as `wc -l` counts. A report: it exits 0 unless `--strict` is given.

    python indexer/scripts/shape.py [--complexity 9] [--lines 300] [--strict] [--json FILE] [path ...]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "aidd_indexer"


def complex_functions(paths: list[Path], limit: int) -> list[dict] | None:
    """(file, line, function, complexity) above `limit`, or None when ruff is not installed."""
    ruff = shutil.which("ruff")
    if ruff is None:
        return None
    cmd = [ruff, "check", "--no-cache", "--isolated", "--select", "C901", "--output-format", "json",
           "--config", f"lint.mccabe.max-complexity = {limit}", *map(str, paths)]
    found = json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout or "[]")
    out = []
    for f in found:
        name, _, rest = f["message"].partition("` is too complex (")
        out.append({"file": os.path.relpath(f["filename"]), "line": f["location"]["row"], "function": name.strip("`"),
                    "complexity": int(rest.split(" ")[0])})
    return sorted(out, key=lambda x: -x["complexity"])


def long_modules(paths: list[Path], limit: int) -> list[dict]:
    files = [f for p in paths for f in (sorted(p.rglob("*.py")) if p.is_dir() else [p])]
    sizes = [{"file": str(f), "lines": len(f.read_bytes().splitlines())} for f in files]
    return sorted((s for s in sizes if s["lines"] > limit), key=lambda x: -x["lines"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*", type=Path, default=[PACKAGE])
    ap.add_argument("--complexity", type=int, default=9)
    ap.add_argument("--lines", type=int, default=300)
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is over a target")
    ap.add_argument("--json", type=Path, help="also write the report here")
    args = ap.parse_args()
    funcs = complex_functions(args.paths, args.complexity)
    mods = long_modules(args.paths, args.lines)
    if funcs is None:
        print("ruff not installed: complexity not measured", file=sys.stderr)
    else:
        print(f"functions above complexity {args.complexity}: {len(funcs)}")
        for f in funcs:
            print(f"  {f['complexity']:4}  {f['file']}:{f['line']} {f['function']}")
    print(f"modules above {args.lines} lines: {len(mods)}")
    for m in mods:
        print(f"  {m['lines']:5}  {m['file']}")
    if args.json:
        args.json.write_text(json.dumps({"functions": funcs, "modules": mods}, indent=1))
    over = bool(mods) or bool(funcs)
    return 1 if args.strict and over else 0


if __name__ == "__main__":
    sys.exit(main())
