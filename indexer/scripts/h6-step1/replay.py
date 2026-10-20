"""H6 step 1: replay a repo's recent first-parent commits through the prototype pipeline, cold at each commit, and
record per file what each cache policy would need to decide a hit: the file's key, its summary's digest, its scan's
digest, the directories its scan looked up (option D per package) and the context entries it read (option C).
Runs in the indexer image with the prototype's code on PYTHONPATH:

    python /step1/replay.py /hist --name NAME --out /out --commits 40 --workers 4
"""

import argparse
import gzip
import json
import subprocess
import sys
import time
from pathlib import Path

from aidd_indexer import languages
from aidd_indexer.core import pipeline as P
from aidd_indexer.core.deps import collect_manifest_deps
from aidd_indexer.core.discovery import build_files, discover_modules, list_files
from aidd_indexer.core.extract import load_language
from aidd_indexer.core.http_base import TEST_FILE, dir_of
from aidd_indexer.core.http_view import RepoView
from aidd_indexer.core.model import ExtractionResult, RepoInfo
from aidd_indexer.core.resolve import Resolver

DICTS = ("route_consts", "const_parts", "functions_by_name", "segments", "relatives", "passthrough", "verb_lists",
         "file_facts", "classes", "client_bases", "client_classes")
SETS = ("env_hints", "ambiguous", "client_rewritten")


def _key(k):
    return k if isinstance(k, (str, tuple)) else repr(k)


class RecDict(dict):
    def __init__(self, d, attr, data):
        super().__init__(data)
        self._d, self._a = d, attr

    def _rec(self, key):
        if P._W.get("creads") is not None:
            P._W["creads"].add((self._d, self._a, _key(key)))

    def __getitem__(self, key):
        self._rec(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._rec(key)
        return super().get(key, default)

    def __contains__(self, key):
        self._rec(key)
        return super().__contains__(key)

    def __setitem__(self, key, value):
        if P._W.get("creads") is None:          # the route constants' memo is skipped while scanning: a pure cache
            super().__setitem__(key, value)

    def _all(self):
        if P._W.get("creads") is not None:
            P._W["creads"].add((self._d, self._a, "*"))

    def __iter__(self):
        self._all()
        return super().__iter__()

    def items(self):
        self._all()
        return super().items()

    def values(self):
        self._all()
        return super().values()

    def keys(self):
        self._all()
        return super().keys()

    def __len__(self):
        self._all()
        return super().__len__()


class RecSet(set):
    def __init__(self, d, attr, data):
        super().__init__(data)
        self._d, self._a = d, attr

    def __contains__(self, key):
        if P._W.get("creads") is not None:
            P._W["creads"].add((self._d, self._a, _key(key)))
        return super().__contains__(key)

    def __iter__(self):
        if P._W.get("creads") is not None:
            P._W["creads"].add((self._d, self._a, "*"))
        return super().__iter__()

    def __len__(self):
        if P._W.get("creads") is not None:
            P._W["creads"].add((self._d, self._a, "*"))
        return super().__len__()


def track(by_dir) -> None:
    for d, ctx in by_dir.items():
        for a in DICTS:
            setattr(ctx, a, RecDict(d, a, getattr(ctx, a)))
        for a in SETS:
            setattr(ctx, a, RecSet(d, a, getattr(ctx, a)))


def value_of(by_dir, memo, read) -> str:
    """The digest of what a recorded read saw, computed from the contexts as the reduce built them."""
    d, attr, key = read
    if read in memo:
        return memo[read]
    ctx = by_dir.get(d)
    if ctx is None:
        v = "<no dir>"
    else:
        data = P.project(attr, dict(getattr(ctx, attr))) if attr == "functions_by_name" else getattr(ctx, attr)
        if key == "*":
            v = P.digest(set(data) if isinstance(data, set) else dict(data))
        elif isinstance(data, set):
            v = str(key in set(data))
        else:
            v = P.digest(dict.get(data, key, P._MISSING))
    memo[read] = v
    return v


_orig_scan = P._scan


def scan_tracked(f):
    P._W["creads"] = set()
    t = time.perf_counter()
    delta, reads, sec = _orig_scan(f)
    creads, P._W["creads"] = P._W["creads"], None
    return delta, reads, sec, sorted(creads), time.perf_counter() - t


def map2_batch(items):
    return [(i, scan_tracked(f)) for i, f in items]


def analyse(repo: RepoInfo, workers: int, prev: dict) -> dict:
    T = {}
    t = time.perf_counter()
    rel = list_files(Path(repo.root))
    modules, stack = discover_modules(repo, rel)
    repo.stack = sorted(stack)
    files = build_files(repo, rel, modules)
    res = ExtractionResult(repo=repo, modules=modules, files=files)
    res.provides, res.requires = collect_manifest_deps(repo, rel)
    for lang in sorted({f.language for f in files} & languages.parseable()):
        load_language(lang)
    T["discover"] = round(time.perf_counter() - t, 3)
    P._W.update(repo=repo, dispatch=frozenset(), patterns=None, reads=None, creads=None)
    t = time.perf_counter()
    sums = P.map1([f for f in files if f.language in languages.parseable()], workers, None)
    T["map1"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    for s in sums:
        res.symbols.extend(s.symbols)
        res.calls.extend(s.calls)
        res.imports.extend(s.imports)
    kept = [s for s in sums if s.ok and not s.bundle]
    by_dir = P.contexts(kept, None)
    view = RepoView(repo, [s.file for s in kept], modules, by_dir)
    for ctx in by_dir.values():
        ctx.view = view
    T["reduce"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    raw = {d: P.ctx_digest(c, projected=False) for d, c in by_dir.items()}
    proj = {d: P.ctx_digest(c, projected=True) for d, c in by_dir.items()}
    structure = P.structure_digest(repo, kept, modules, rel)
    T["digests"] = round(time.perf_counter() - t, 3)
    view.classes_named("")                          # built once here, so no scan records the whole repo's classes
    track(by_dir)
    P._W.update(by_dir=by_dir, view=view)
    P._watch(view)
    scanned = [s for s in kept if not TEST_FILE.search("/" + s.file.path) and P.scanner_of(s.file) is not None]
    t = time.perf_counter()
    got = dict(P._run(map2_batch, list(enumerate(s.file for s in scanned)), workers))
    T["map2_tracked"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    hr = P._join([(got[i][0], None, None) for i in range(len(scanned))])
    for scanner in dict.fromkeys(P.scanner_of(s.file) for s in scanned):
        scanner.compose(hr, repo, view)
    P._assign_apps(hr, repo, kept, modules)
    P._dedupe(hr)
    res.endpoints, res.http_calls = hr.endpoints, hr.calls
    T["compose"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    rv = Resolver(res, [s for s in sums if s.ok], []).run()
    T["resolve"] = round(time.perf_counter() - t, 3)
    memo: dict = {}
    rid = lambda r: json.dumps([r[0], r[1], r[2] if isinstance(r[2], str) else list(r[2])])
    files_out = {}
    for s in sums:
        files_out[s.file.path] = {"key": P.file_key(s.file), "sum": P.digest((s.ok, s.warnings, s.symbols, s.calls,
                                  s.imports, s.facts, s.namespaces, s.bundle, s.contrib)), "t1": round(s.seconds, 4)}
    names = set(prev.get("names", ()))
    vreads = set(prev.get("vreads", ()))
    reads_now = set(prev.get("reads", ()))
    for i, s in enumerate(scanned):
        delta, reads, sec, creads, _ = got[i]
        names |= {r[1] for r in reads if r[0] == "classes"}
        vreads |= {r for r in reads if r[0] == "view"}
        reads_now |= set(creads)
        files_out[s.file.path].update(
            scan=P.digest((delta.endpoints, delta.calls, delta.warnings, delta.pending, delta.facts)),
            t2=round(sec, 4), dirs=sorted({r[1] for r in reads if r[0] == "ctx"}),
            classes=sorted({r[1] for r in reads if r[0] == "classes"}),
            views=[repr(r) for r in reads if r[0] == "view"],
            c=[rid(r) for r in creads])
    prev["names"] = {r[1] for i in range(len(scanned)) for r in got[i][1] if r[0] == "classes"}
    prev["reads"] = {r for i in range(len(scanned)) for r in got[i][3]}
    prev["vreads"] = {r for i in range(len(scanned)) for r in got[i][1] if r[0] == "view"}
    by_path = {s.file.path: s.file for s in kept}
    P._W["reads"] = None
    sv = {repr(r): P.digest(P.view_answer(view, by_path, r)) for r in vreads}
    cv = {rid(r): value_of(by_dir, memo, r) for r in reads_now}
    classes_val = {n: [d for d, c in by_dir.items() if n in dict.keys(c.classes)] for n in names}
    return {"times": T, "files": files_out, "raw": raw, "proj": proj, "structure": structure,
            "classes": classes_val, "cv": cv, "sv": sv, "endpoints": len(hr.endpoints), "http_calls": len(hr.calls),
            "calls_edges": len(rv.calls), "scanned": len(scanned)}


def typed(repo: RepoInfo, workers: int) -> dict:
    rel = list_files(Path(repo.root))
    modules, stack = discover_modules(repo, rel)
    files = build_files(repo, rel, modules)
    for lang in sorted({f.language for f in files} & languages.parseable()):
        load_language(lang)
    P._W.update(repo=repo, dispatch=frozenset(), patterns=None, reads=None, creads=None)
    sums = P.map1([f for f in files if f.language in languages.parseable()], workers, None)
    by_dir = P.contexts([s for s in sums if s.ok and not s.bundle], None)
    return {"typed": {d: P.ctx_digest(c, projected=True, typed=True) for d, c in by_dir.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hist")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--commits", type=int, default=40)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--typed-only", action="store_true", help="only the contexts' typed digests, beside each record")
    a = ap.parse_args()
    P._map2_batch = map2_batch
    git = ["git", "-c", "safe.directory=*", "-C", a.hist]
    shas = subprocess.run(git + ["rev-list", "--first-parent", f"-n{a.commits}", "replay"], check=True,
                          capture_output=True, text=True).stdout.split()[::-1]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prev: dict = {}
    for k, sha in enumerate(shas):
        dest = out / f"{k:02d}-{sha[:10]}.json.gz"
        if a.typed_only:
            dest = dest.with_name(dest.name.replace(".json.gz", ".typed.json"))
        if dest.exists():
            prev = {}
            continue
        work = Path(f"/tmp/w{k}")
        work.mkdir()
        subprocess.run(f"{' '.join(git)} archive {sha} | tar -x -C {work}", shell=True, check=True)
        repo = RepoInfo(tenant="replay", name=a.name, ref="h6", commit_sha=sha, root=str(work))
        t = time.perf_counter()
        r = typed(repo, a.workers) if a.typed_only else analyse(repo, a.workers, prev)
        r.update(sha=sha, k=k, wall=round(time.perf_counter() - t, 1))
        with (open(dest, "w") if a.typed_only else gzip.open(dest, "wt")) as f:
            json.dump(r, f)
        subprocess.run(["rm", "-rf", str(work)], check=True)
        print(f"{a.name} {k:02d} {sha[:10]} wall={r['wall']}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
