#!/usr/bin/env python3
"""What a tree's types' bases give each repo, and the yardsticks of the work they open, one JSON line per repo:

- `edges`: the `EXTENDS` and `IMPLEMENTS` edges, by language, kind and the kinds of their ends;
- `consistency`: whether each type's ancestors through them are the ancestry the resolver walks for a call: in C#, the
  same names; in Python, the resolver's supertypes among them, and why the others are not. A name two types share has
  no edge, and the types past it say so;
- `one name`: the qualified names several type symbols of one file share, and the edges that touch them;
- `not dispatching`: the `CALLS` that do not dispatch, by strategy and by what they reach from the caller: itself, its
  own class, a class of a name two types share, an ancestor of its class, a class after it in an MRO of the repo
  (Python) or none, and their sites;
- `super`: Python's `super()` calls whose receiver's type the type index does not decide: how many edges each has, or
  why it has none;
- `overrides`: the `OVERRIDES` edges by language, against the methods of one name a type and an ancestor through the
  type edges declare: a pair the edges leave out, by why, and an edge no such pair gives (a class after another in an
  MRO); and the dispatching calls each adds to `who_calls`;
- `receivers`: for each dispatching call to a method others override, the overrides its `receivers` keep, and whether
  they are what the language runs on an instance at or below the receiver's type;
- `go interfaces`: Go's calls on an interface of the repo with no edge of the method's name, and how many of them are
  on an interface of two implementers or more;
- `seconds`: the resolver's calls, the types' edges and the overrides.

It reads and parses the repos and never runs their code. In the indexer's image, with the tree's `indexer/` on
PYTHONPATH, as root (the grammar cache is root's):

    hierarchy.py REPOS_DIR REPO... > HIERARCHY.jsonl
"""
from __future__ import annotations

import collections
import contextlib
import io
import json
import sys
import time

from aidd_indexer import languages
from aidd_indexer.cli import extract_tree
from aidd_indexer.core.hierarchy import override_edges, type_edges
from aidd_indexer.core.model import RepoInfo, SymbolInfo
from aidd_indexer.core.resolve import TYPE_KINDS, Resolver
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.python.type_index import qualified as python_qualified
from aidd_indexer.languages.python.type_index import ref as python_ref
from dispatching import SAMPLES, go_interfaces, not_dispatching, overrides, receivers, sample, super_calls


class Repo:
    """One repo's extraction, its resolver and what the resolver gives, as the yardsticks read them."""

    def __init__(self, root: str, name: str) -> None:
        repo = RepoInfo(tenant="p", name=name, ref="p", commit_sha="p", root=f"{root}/{name}")
        with contextlib.redirect_stderr(io.StringIO()):
            self.res, extractors = extract_tree(repo)
            self.rv = Resolver(self.res, extractors)
            for lang in languages.all():
                lang.link_symbols(self.res.symbols, self.rv.files_by_id)
            self.rv.resolve_imports()
            t0 = time.perf_counter()
            self.calls, _ = self.rv.resolve_calls()
            t1 = time.perf_counter()
            self.types = [s for s in self.res.symbols if s.kind in TYPE_KINDS]
            self.edges = type_edges(self.types, self.rv.files_by_id, self.rv.ctx)
            t2 = time.perf_counter()
            methods = [s for s in self.res.symbols if s.kind == "method"]
            self.overrides = override_edges(self.types, methods, self.edges, self.rv.files_by_id, self.rv.ctx)
            self.seconds = {"calls": round(t1 - t0, 2), "hierarchy": round(t2 - t1, 3),
                            "overrides": round(time.perf_counter() - t2, 3)}
        self.sym = {s.id: s for s in self.res.symbols}
        self.up: dict[str, set[str]] = collections.defaultdict(set)
        for e in self.edges:
            self.up[e.source_id].add(e.target_id)
        names: dict[str, set[str]] = collections.defaultdict(set)
        for t in self.types:
            names[t.qualified_name].add(t.id)
        self.shared = {q for q, found in names.items() if len(found) > 1}
        self.rests: dict[str, set[tuple]] = collections.defaultdict(set)    # Python: what follows a class in an MRO
        index = self.rv.ctx.types.of("python")
        for d in index.classes():
            found = index.mro(d)
            for i, t in enumerate(found if not isinstance(found, Unknown) else ()):
                if isinstance(t, TypeRef):
                    self.rests[python_qualified(t)].add(tuple(found[i + 1:]))

    def language(self, symbol_id: str) -> str:
        return self.rv.files_by_id[self.sym[symbol_id].file_id].language

    def ancestors(self, type_id: str) -> set[str]:
        seen, todo = set(), list(self.up.get(type_id, ()))
        while todo:
            t = todo.pop()
            if t not in seen:
                seen.add(t)
                todo += self.up.get(t, ())
        return seen

    def ancestry(self, t: SymbolInfo) -> set[str]:
        """A type's ancestors by name: through the edges, or as the resolver walks them."""
        walked = languages.by_id(self.language(t.id)).supertypes(self.rv.ctx, t.qualified_name)
        return {self.sym[a].qualified_name for a in self.ancestors(t.id)} | set(walked)

    def after(self, q: str) -> set[str]:
        return {python_qualified(t) for rest in self.rests.get(q, ()) for t in rest if isinstance(t, TypeRef)}

    def where(self, caller_id: str, line: int) -> str:
        caller = self.sym.get(caller_id)
        return f"{self.rv.files_by_id[caller.file_id].path}:{line}" if caller else f"{caller_id}:{line}"


def edges(r: Repo) -> collections.Counter:
    return collections.Counter(f"{r.language(e.source_id)} | {e.kind} | {r.sym[e.source_id].kind} -> "
                               f"{r.sym[e.target_id].kind}" for e in r.edges)


def consistency(r: Repo, samples: dict) -> collections.Counter:
    names: dict[str, set[str]] = collections.defaultdict(set)
    for t in r.types:
        names[t.qualified_name].add(t.id)
    out = collections.Counter()
    for q, ids in sorted(names.items()):
        lang = r.language(next(iter(ids)))
        if lang not in ("csharp", "python"):
            continue
        closure = {r.sym[a].qualified_name for i in ids for a in r.ancestors(i)} - {q}
        verdict = _verdict(r, lang, q, set(languages.by_id(lang).supertypes(r.rv.ctx, q)), closure)
        out[f"{lang} | {verdict}"] += 1
        sample(samples, verdict, q)
    return out


def _verdict(r: Repo, lang: str, q: str, walked: set[str], closure: set[str]) -> str:
    shared = bool(({q} | walked) & r.shared)                # a name two types share has no edge
    if lang == "csharp":
        return _csharp_verdict(walked, closure, shared)
    if not walked <= closure:
        return "supertypes outside the closure" + (": through a name two types share" if shared else "")
    if closure == walked:
        return "closure = supertypes"
    mro = r.rv.ctx.types.of("python").mro(python_ref(q))
    if isinstance(mro, Unknown):
        return f"closure > supertypes: no MRO, {mro.reason}"
    if any(not isinstance(t, TypeRef) for t in mro):
        return "closure > supertypes: a base outside the repo ahead in the MRO"
    return "closure > supertypes: unexplained"


def _csharp_verdict(walked: set[str], closure: set[str], shared: bool) -> str:
    if closure == walked:
        return "closure = ancestry"
    return "closure < ancestry: through a name two types share" if closure < walked and shared else "closure != ancestry"


def one_name(r: Repo, samples: dict) -> collections.Counter:
    shared = r.shared
    out = collections.Counter({"names": len(shared)})
    for e in r.edges:
        source, target = r.sym[e.source_id].qualified_name, r.sym[e.target_id].qualified_name
        if source == target:
            out["edges between two of one name"] += 1
        elif target in shared:
            out["edges into one of them"] += 1
    for q in sorted(shared)[:SAMPLES]:
        sample(samples, "one name", q)
    return out


def report(root: str, name: str) -> dict:
    r, samples = Repo(root, name), collections.defaultdict(list)
    return {"repo": name, "seconds": r.seconds, "edges": edges(r), "consistency": consistency(r, samples),
            "one name": one_name(r, samples), "not dispatching": not_dispatching(r, samples),
            "super": super_calls(r, samples),
            "overrides": overrides(r, samples), "receivers": receivers(r, samples), "go interfaces": go_interfaces(r),
            "samples": samples}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    for name in argv[2:]:
        print(json.dumps(report(argv[1], name)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
