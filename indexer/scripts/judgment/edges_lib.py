"""A micro dry-run's CALLS edges per call site, shared by the judgment scripts: a site is its caller's file and the
call's line, and its edges are (callee's qualified name, strategy)."""
import collections
import gzip
import json
import random
import sys


def load(d, repo):
    return json.load(gzip.open(f"{d}/{repo}.json.gz", "rt"))


def edges(run):
    files = {f["id"]: f["path"] for f in run["files"]}
    sym = {s["id"]: s for s in run["symbols"]}
    out = {}
    for c in run["calls"]:
        caller = sym.get(c["caller_id"])
        f = files.get(caller["file_id"]) if caller else None
        if f is None:                                  # a call from a file, not from a symbol
            f = files.get(c["caller_id"], "?")
        callee = sym.get(c["callee_id"], {}).get("qualified_name", c["callee_id"])
        out.setdefault((f, c["line"]), set()).add((callee, c["strategy"]))
    return out

