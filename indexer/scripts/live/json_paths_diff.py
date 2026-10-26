"""Leaf paths that differ between two JSON answers, with list items keyed by position. Values are shown only for
numbers and for keys named in SHOW, so names in the answers stay out of the output.

usage: json_paths_diff.py A B"""
import json
import sys

SHOW = {"indexer_build", "indexed_at", "started_at", "finished_at", "build", "strategy", "outdated", "status"}


def leaves(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from leaves(v, f"{path}[{i}]")
    else:
        yield path, x


a, b = (dict(leaves(json.load(open(p)))) for p in sys.argv[1:3])
for p in sorted(set(a) | set(b)):
    if a.get(p) != b.get(p):
        key = p.rsplit(".", 1)[-1].split("[")[0]
        show = key in SHOW or all(isinstance(v, (int, float)) or v is None for v in (a.get(p), b.get(p)))
        print(f"  {p}: {a.get(p) if show else '…'} -> {b.get(p) if show else '…'}")
