"""Map 1 by whole packages: a worker extracts a directory's files, builds the directory's context, and scans them with
their trees still alive, recording each read with what it saw. The reduce checks each read against the whole repo:
a scan whose reads still hold is final, and only the others are read again in map 2. A directory too large for one
batch is split, and its files take the two-map path."""

from __future__ import annotations

import time

from . import pipeline as P
from .http_base import TEST_FILE, dir_of
from .http_view import RepoView


def _plan(items: list, workers: int) -> tuple[list, int]:
    by_dir: dict[str, list] = {}
    for it in items:
        by_dir.setdefault(dir_of(it[1].path), []).append(it)
    total = sum(f.loc for _, f in items)
    whole_limit, target = max(1, total // (workers * 4)), max(1, total // (workers * 16))
    whole, split = [], []
    for group in by_dir.values():
        size = sum(f.loc for _, f in group)
        if size <= whole_limit:
            whole.append((size, group))
        else:
            split.extend(group)
    tasks, cur, size = [], [], 0
    for s, group in sorted(whole, key=lambda x: -x[0]):
        cur.append(group)
        size += s
        if size >= target:
            tasks.append((size, ("pkg", cur)))
            cur, size = [], 0
    if cur:
        tasks.append((size, ("pkg", cur)))
    tasks += [(sum(f.loc for _, f in b), ("files", b)) for b in P._batches(split, workers)] if split else []
    return [t for _, t in sorted(tasks, key=lambda t: -t[0])], len(split)


def _view() -> RepoView:
    """One view per worker for the repo's structure; each package puts its own context in it."""
    if P._W.get("wview") is None:
        view = RepoView(P._W["repo"], P._W["files"], P._W["modules"], {})
        P._watch(view)
        P._W["wview"] = view
    return P._W["wview"]


def _package(group: list) -> list:
    pairs = [(i, P._extract(f)) for i, f in group]
    kept = [(s, fx) for _, (s, fx) in pairs if s.ok and not s.bundle]
    local = P.contexts([s for s, _ in kept], P._W["patterns"])
    view = _view()
    view.contexts = P._Lookups(local)
    view._classes = None
    for c in local.values():
        c.view = view
    deps = P.Deps(local, view, P._W["files_by_path"])
    for s, fx in kept:
        if not TEST_FILE.search("/" + s.file.path) and P.scanner_of(s.file) is not None:
            t = time.perf_counter()
            delta, reads = P._scan_fx(fx, local[dir_of(s.file.path)])
            s.scan = (delta, [(r, deps.value(r)) for r in reads])
            s.seconds += time.perf_counter() - t
    return [(i, s) for i, (s, _) in pairs]


def _task(t: tuple) -> list:
    kind, body = t
    if kind == "files":
        return P._map1_batch(body)
    return [r for group in body for r in _package(group)]


def map1_packages(files: list, workers: int) -> list:
    tasks, split = _plan(list(enumerate(files)), workers)
    out: list = [None] * len(files)
    if workers <= 1:
        results = [r for t in tasks for r in _task(t)]
    else:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(workers, mp_context=mp.get_context("fork")) as pool:
            results = [r for part in pool.map(_task, tasks) for r in part]
    for i, s in results:
        out[i] = s
    P.STATS.update(map1_hits=0, map1_misses=len(files), map1_cpu=round(sum(s.seconds for s in out), 3),
                   split_files=split, tasks=len(tasks))
    return out
