"""A prototype of the extraction as a map over files, a reduce per repo and a per-file cache.

Map 1 extracts each file in a worker and returns its summary: symbols, calls, imports, facts and what the file adds to
its directory's HTTP context. The reduce joins the contexts in file order. Map 2 re-extracts each file a scanner reads
and scans it with its directory's context (the second read, option B). Map 2's result is kept under a key made of the
digests of what the scan can read (option D): its directory's context, the repo's structure, and the other
directories' contexts it looked up, recorded as it ran.
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import pickle
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path

from .. import languages
from .build import indexer_build
from .extract import extract_file
from .http_base import TEST_FILE, HttpResult, PackageContext, collect_constants, dir_of
from .http_view import RepoView
from .integrations import _assign_apps, _dedupe, built_bundle
from .model import ExtractionResult, FileInfo, RepoInfo

STATS: dict = {}
_W: dict = {}
_MISSING = ("<missing>",)


@dataclass
class Summary:
    file: FileInfo
    ok: bool
    warnings: list
    symbols: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    imports: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    namespaces: list = field(default_factory=list)
    bundle: bool = False
    contrib: dict | None = None
    seconds: float = 0.0


class _Recorder(PackageContext):
    """One file's additions to its directory's context, replayed in file order by the reduce."""

    def __init__(self, patterns) -> None:
        super().__init__(patterns)
        self.log: list = []

    def define(self, *a, **k) -> None:
        self.log.append((a, k))
        super().define(*a, **k)

    def contribution(self) -> dict:
        return {"define": self.log, "verb_lists": self.verb_lists, "passthrough": self.passthrough,
                "classes": self.classes, "client_bases": self.client_bases, "client_classes": self.client_classes,
                "client_rewritten": self.client_rewritten, "env_hints": self.env_hints}


def _merge(ctx: PackageContext, c: dict) -> None:
    for a, k in c["define"]:
        ctx.define(*a, **k)
    ctx.verb_lists.update(c["verb_lists"])
    for attr in ("passthrough", "classes", "client_classes"):
        d = getattr(ctx, attr)
        for k, v in c[attr].items():
            d[k] = v if d.get(k, v) == v else None
    ctx.client_bases.update(c["client_bases"])
    ctx.client_rewritten |= c["client_rewritten"]
    ctx.env_hints |= c["env_hints"]


# -- canonical digests ------------------------------------------------------------------------------------------

def canon(o):
    if isinstance(o, dict):
        return ("d", tuple((canon(k), canon(v)) for k, v in o.items()))
    if isinstance(o, (set, frozenset)):
        return ("s", tuple(sorted((canon(v) for v in o), key=repr)))
    if isinstance(o, (list, tuple)):
        return tuple(canon(v) for v in o)
    if is_dataclass(o) and not isinstance(o, type):
        return (type(o).__name__, tuple(canon(getattr(o, f.name)) for f in fields(o)))
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o if type(o) in (str, int, float, bool) or o is None else (type(o).__name__, str(o))
    if hasattr(o, "_asdict"):
        return (type(o).__name__, canon(tuple(o)))
    return (type(o).__name__, repr(o))


def digest(o) -> str:
    """Over `repr`, not pickle: pickle shares equal objects by identity, so equal values can give different bytes."""
    return hashlib.sha256(repr(canon(o)).encode()).hexdigest()[:32]


CTX_FIELDS = ("route_consts", "const_parts", "env_hints", "segments", "relatives", "ambiguous", "passthrough",
              "verb_lists", "file_facts", "classes", "client_bases", "client_classes", "client_rewritten", "_values")


def project(attr: str, value):
    """What a scanner reads of an entry: a function's name and id, not its lines or its hash."""
    if attr == "functions_by_name":
        return {k: [(s.name, s.id, s.kind) for s in v] for k, v in value.items()}
    return value


def ctx_digest(ctx: PackageContext, projected: bool, typed: bool = False) -> str:
    """`typed`: the files' facts cut to what a scanner reads of them, the struct fields."""
    parts = [canon({p: f.get("structs", {}) for p, f in ctx.file_facts.items()}) if typed and a == "file_facts"
             else canon(getattr(ctx, a)) for a in CTX_FIELDS]
    fbn = project("functions_by_name", ctx.functions_by_name) if projected else ctx.functions_by_name
    return digest((parts, canon(fbn)))


# -- the cache ----------------------------------------------------------------------------------------------------

class Cache:
    """Content-addressed entries, written once through a temporary file and a rename; a read that fails is a miss."""

    def __init__(self, root: str, repo: RepoInfo, patterns, dispatch_calls) -> None:
        ns = digest((indexer_build(), canon(patterns), sorted(dispatch_calls), repo.tenant, repo.name, repo.ref))
        self.root = Path(root) / ns[:16]
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, kind: str, key: str) -> Path:
        return self.root / kind / key[:2] / key

    def get(self, kind: str, key: str):
        try:
            return pickle.loads(zlib.decompress(self._path(kind, key).read_bytes()))
        except Exception:  # noqa: BLE001 — a missing or broken entry is a miss
            return None

    def put(self, kind: str, key: str, value) -> int:
        p = self._path(kind, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        blob = zlib.compress(pickle.dumps(value, protocol=5), 1)
        tmp = p.with_name(f".{p.name}.{os.getpid()}")
        tmp.write_bytes(blob)
        os.replace(tmp, p)
        return len(blob)


def file_key(f: FileInfo) -> str:
    return digest((f.id, f.path, f.language, f.content_hash, f.module_id))


# -- the pool -------------------------------------------------------------------------------------------------------

def _batches(items: list, workers: int) -> list[list]:
    """Largest first, cut by size in lines: a cut by count put the largest files in one batch, and the run waited on
    it."""
    items = sorted(items, key=lambda it: -it[1].loc)
    target = max(1, sum(f.loc for _, f in items) // (workers * 16))
    out, cur, size = [], [], 0
    for it in items:
        cur.append(it)
        size += it[1].loc
        if size >= target or len(cur) >= 256:
            out.append(cur)
            cur, size = [], 0
    return out + [cur] if cur else out


def _run(fn, items: list, workers: int) -> list:
    """`items` are (index, FileInfo); the results come back as (index, result), in any order."""
    if workers <= 1 or len(items) < 2:
        return fn(items)
    out: list = []
    with ProcessPoolExecutor(workers, mp_context=mp.get_context("fork")) as pool:
        for part in pool.map(fn, _batches(items, workers)):
            out.extend(part)
    return out


# -- map 1 --------------------------------------------------------------------------------------------------------

def _summarize(f: FileInfo) -> Summary:
    t = time.perf_counter()
    fx, warns = extract_file(_W["repo"], f, _W["dispatch"])
    if fx is None:
        return Summary(f, False, warns, seconds=time.perf_counter() - t)
    s = Summary(f, True, warns, fx.symbols, fx.calls, fx.imports, fx.facts, fx.namespaces,
                bundle=built_bundle(f.path, fx.src))
    if not s.bundle:
        rec = _Recorder(_W["patterns"])
        collect_constants(fx, rec)
        s.contrib = rec.contribution()
    s.seconds = time.perf_counter() - t
    return s


def _map1_batch(items: list) -> list:
    return [(i, _summarize(f)) for i, f in items]


def map1(files: list[FileInfo], workers: int, cache: Cache | None) -> list[Summary]:
    out: list = [None] * len(files)
    todo = []
    for i, f in enumerate(files):
        hit = cache.get("sum", file_key(f)) if cache else None
        if hit is not None:
            out[i] = hit
        else:
            todo.append((i, f))
    for i, s in _run(_map1_batch, todo, workers):
        out[i] = s
        if cache:
            STATS["sum_bytes"] = STATS.get("sum_bytes", 0) + cache.put("sum", file_key(files[i]), s)
    STATS.update(map1_hits=len(files) - len(todo), map1_misses=len(todo),
                 map1_cpu=round(sum(out[i].seconds for i, _ in todo), 3))
    return out


# -- the reduce ---------------------------------------------------------------------------------------------------

def contexts(kept: list[Summary], patterns) -> dict[str, PackageContext]:
    by_dir: dict[str, PackageContext] = {}
    for s in kept:
        ctx = by_dir.setdefault(dir_of(s.file.path), PackageContext(patterns))
        _merge(ctx, s.contrib)
        ctx.file_facts[s.file.path] = s.facts
        if not TEST_FILE.search("/" + s.file.path):
            for sym in s.symbols:
                if sym.kind in ("function", "method"):
                    ctx.functions_by_name.setdefault(sym.name, []).append(sym)
    return by_dir


def structure_digest(repo: RepoInfo, kept: list[Summary], modules, rel_files: list[str]) -> str:
    """What `RepoView` reads besides the contexts: the files, the modules and the manifests' text."""
    names = {n for lang in languages.all() for n in lang.manifests}
    manifests = []
    for r in rel_files:
        if r.rsplit("/", 1)[-1] in names:
            manifests.append((r, hashlib.sha1((Path(repo.root) / r).read_bytes()).hexdigest()))
    files = [(s.file.path, s.file.language, s.file.module_id) for s in kept]
    return digest((files, canon(modules or []), manifests))


def scanner_of(f: FileInfo):
    lang = languages.by_id(f.language)
    return lang.http_scanner if lang is not None else None


# -- map 2 --------------------------------------------------------------------------------------------------------

class _Lookups(dict):
    """The view's directory contexts, recording which ones a scan looks up."""

    def _rec(self, key) -> None:
        if _W.get("reads") is not None:
            _W["reads"].add(("ctx", key))

    def get(self, key, default=None):
        self._rec(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._rec(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self._rec(key)
        return super().__contains__(key)


def _watch(view: RepoView) -> None:
    """Records what a scan reads of the rest of the repo: the contexts it looks up, the classes it names, and each
    question it asks of the repo's structure, with the question's arguments, so the answer can be asked again."""
    view.contexts = _Lookups(view.contexts)
    dirs = {id(c): d for d, c in view.contexts.items()}
    orig = view.classes_named

    def classes_named(name: str):
        found = orig(name)
        if _W.get("reads") is not None:
            _W["reads"].add(("classes", name))
            _W["reads"].update(("ctx", dirs[id(c)]) for c in found)
        return found
    view.classes_named = classes_named
    view.unwatched = {m: getattr(view, m) for m in ("resolve", "manifest_dir", "files_under", "constants")}
    for m, fn in view.unwatched.items():
        setattr(view, m, _asked(m, fn))


def _asked(method: str, fn):
    def call(*a):
        if _W.get("reads") is not None:
            _W["reads"].add(("view", method, *(x.path if isinstance(x, FileInfo) else tuple(x) if isinstance(x, list)
                                               else x for x in a)))
        return fn(*a)
    return call


def view_answer(view: RepoView, files: dict[str, FileInfo], read: tuple):
    """A recorded question asked again of `view`; what a context lookup chose is its directory's key."""
    method, args = read[1], list(read[2:])
    if method in ("resolve", "manifest_dir"):
        if args[0] not in files:
            return _MISSING
        args[0] = files[args[0]]
    if method == "files_under":
        args[0] = list(args[0])
    got = view.unwatched[method](*args)
    if method == "constants":
        return next((d for d, c in view.contexts.items() if c is got), None)
    return got


def _scan(f: FileInfo):
    t = time.perf_counter()
    fx, _ = extract_file(_W["repo"], f, _W["dispatch"])
    delta = HttpResult()
    _W["reads"] = set()
    try:
        scanner_of(f)(_W["repo"], fx, _W["by_dir"][dir_of(f.path)], delta).scan()
    except Exception as e:  # noqa: BLE001 — a weird file must not stop the repo
        delta.warnings.append(f"{f.path}: http candidates skipped ({type(e).__name__}: {e})")
    reads, _W["reads"] = _W["reads"], None
    return delta, sorted(reads, key=repr), time.perf_counter() - t


def _map2_batch(items: list) -> list:
    return [(i, _scan(f)) for i, f in items]


class Deps:
    """The digests map 2's keys are made of, computed once per run, before any scan."""

    def __init__(self, by_dir: dict[str, PackageContext], view: RepoView, files: list[FileInfo]) -> None:
        self.by_dir, self.view = by_dir, view
        self.files = {f.path: f for f in files}
        self.ctx = {d: ctx_digest(c, projected=True) for d, c in by_dir.items()}
        self.memo: dict = {}

    def base(self, s: Summary) -> str:
        return digest((file_key(s.file), self.ctx[dir_of(s.file.path)]))

    def value(self, read: tuple):
        if read[0] == "ctx":
            return self.ctx.get(read[1], _MISSING)
        if read[0] == "classes":
            return tuple(d for d, c in self.by_dir.items() if read[1] in c.classes)
        if read not in self.memo:
            self.memo[read] = digest(view_answer(self.view, self.files, read))
        return self.memo[read]

    def valid(self, deps: list) -> bool:
        return all(self.value(r) == v for r, v in deps)


def map2(scanned: list[Summary], workers: int, cache: Cache | None, deps: Deps | None) -> list:
    out: list = [None] * len(scanned)
    todo = []
    for i, s in enumerate(scanned):
        hit = cache.get("scan", deps.base(s)) if cache else None
        if hit is not None and deps.valid(hit[0]):
            out[i] = (hit[1], [r for r, _ in hit[0]], 0.0)
        else:
            todo.append((i, s.file))
    for i, (delta, reads, sec) in _run(_map2_batch, todo, workers):
        out[i] = (delta, reads, sec)
        if cache:
            STATS["scan_bytes"] = STATS.get("scan_bytes", 0) + cache.put(
                "scan", deps.base(scanned[i]), ([(r, deps.value(r)) for r in reads], delta))
    STATS.update(map2_hits=len(scanned) - len(todo), map2_misses=len(todo),
                 map2_cpu=round(sum(out[i][2] for i, _ in todo), 3),
                 map2_foreign=sum(1 for s, o in zip(scanned, out)
                                  if any(r[0] == "classes" or r[0] == "ctx" and r[1] != dir_of(s.file.path)
                                         for r in o[1])))
    return out


# -- the whole extraction -----------------------------------------------------------------------------------------

def _join(deltas: list) -> HttpResult:
    out = HttpResult()
    for delta, _, _ in deltas:
        out.endpoints.extend(delta.endpoints)
        out.calls.extend(delta.calls)
        out.warnings.extend(delta.warnings)
        out.pending.extend(delta.pending)
        for kind, names in delta.facts.items():
            k = out.facts.setdefault(kind, {})
            for name, facts in names.items():
                k.setdefault(name, []).extend(facts)
    return out


def _timed(name: str, t0: float) -> float:
    t = time.perf_counter()
    STATS[name] = round(t - t0, 3)
    return t


def run(repo: RepoInfo, res: ExtractionResult, files: list[FileInfo], rel_files: list[str], patterns,
        dispatch_calls: frozenset[str]) -> tuple[ExtractionResult, list[Summary]]:
    STATS.clear()
    workers = int(os.getenv("AIDD_WORKERS", "2"))
    cache = Cache(os.environ["AIDD_CACHE"], repo, patterns, dispatch_calls) if os.getenv("AIDD_CACHE") else None
    _W.update(repo=repo, dispatch=dispatch_calls, patterns=patterns, reads=None)
    t = time.perf_counter()
    sums = map1([f for f in files if f.language in languages.parseable()], workers, cache)
    t = _timed("map1", t)
    for s in sums:
        res.warnings.extend(s.warnings)
        res.symbols.extend(s.symbols)
        res.calls.extend(s.calls)
        res.imports.extend(s.imports)
    kept = [s for s in sums if s.ok and not s.bundle]
    by_dir = contexts(kept, patterns)
    view = RepoView(repo, [s.file for s in kept], res.modules, by_dir)
    for ctx in by_dir.values():
        ctx.view = view
    _W.update(by_dir=by_dir, view=view)
    t = _timed("reduce", t)
    _watch(view)
    deps = Deps(by_dir, view, [s.file for s in kept]) if cache else None
    t = _timed("digests", t)
    scanned = [s for s in kept if not TEST_FILE.search("/" + s.file.path) and scanner_of(s.file) is not None]
    deltas = map2(scanned, workers, cache, deps)
    t = _timed("map2", t)
    hr = _join(deltas)
    for scanner in dict.fromkeys(scanner_of(s.file) for s in scanned):
        try:
            scanner.compose(hr, repo, view)
        except Exception as e:  # noqa: BLE001
            hr.warnings.append(f"{scanner.__name__}: cross-file composition skipped ({type(e).__name__}: {e})")
    _assign_apps(hr, repo, kept, res.modules)
    _dedupe(hr)
    _timed("compose", t)
    res.endpoints, res.http_calls = hr.endpoints, hr.calls
    res.warnings.extend(hr.warnings)
    res.http = hr
    print(f"[pipeline] workers={workers} " + " ".join(f"{k}={v}" for k, v in STATS.items()), file=sys.stderr)
    return res, [s for s in sums if s.ok]
