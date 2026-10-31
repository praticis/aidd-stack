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
- `overrides`: the methods a type's method of the same name overrides through the edges, and the calls that reach one;
- `go interfaces`: Go's calls on an interface of the repo with no edge of the method's name, and how many of them are
  on an interface of two implementers or more;
- `seconds`: the resolver's calls and the hierarchy.

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
from aidd_indexer.core.hierarchy import type_edges
from aidd_indexer.core.model import RepoInfo, SymbolInfo
from aidd_indexer.core.resolve import TYPE_KINDS, Resolver
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.go.symbols import _ref as go_ref
from aidd_indexer.languages.python.type_index import qualified as python_qualified
from aidd_indexer.languages.python.type_index import ref as python_ref

SAMPLES = 3


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
            self.seconds = {"calls": round(t1 - t0, 2), "hierarchy": round(time.perf_counter() - t1, 3)}
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
        _sample(samples, verdict, q)
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
        _sample(samples, "one name", q)
    return out


def not_dispatching(r: Repo, samples: dict) -> collections.Counter:
    out, sites = collections.Counter(), collections.defaultdict(set)
    for c in r.calls:
        if c.virtual:
            continue
        reach = _reach(r, c)
        out[f"{c.strategy} | {reach}"] += 1
        sites[reach].add((c.caller_id, c.line))
        _sample(samples, f"not dispatching: {reach}", f"{r.where(c.caller_id, c.line)} -> "
                f"{r.sym[c.callee_id].qualified_name} ({c.strategy})")
    out.update({f"sites | {k}": len(v) for k, v in sites.items()})
    return out


def _reach(r: Repo, c) -> str:
    caller, callee = r.sym.get(c.caller_id), r.sym[c.callee_id]
    if caller is None:
        return "from a file"
    owner = r.sym.get(caller.parent_id) if caller.parent_id else None
    target = r.sym[callee.parent_id] if callee.parent_id else callee
    if callee.id == caller.id:
        return "the caller itself"
    if owner is None:
        return "no ancestor"
    if target.id == owner.id:
        return "the caller's class"
    if {owner.qualified_name, target.qualified_name} & r.shared:
        return "a name two types share"
    if target.qualified_name in r.ancestry(owner):
        return "an ancestor"
    return "after it in an MRO" if target.qualified_name in r.after(owner.qualified_name) else "no ancestor"


def super_calls(r: Repo, samples: dict) -> collections.Counter:
    py, out = languages.by_id("python"), collections.Counter()
    reached = collections.Counter((c.caller_id, c.line) for c in r.calls if not c.virtual)
    for c in r.res.calls:
        f = r.rv.files_by_id.get(c.file_id)
        if f is None or f.language != "python" or py.dispatches(c) \
                or c.receiver_type and py.resolve_receiver(r.rv.ctx, f, c.receiver_type, c.receiver_path):
            continue
        n = reached[(c.caller_id, c.line)]
        why = f"{min(n, 3)}{'+' if n > 2 else ''} edge(s)" if n else _no_edge(r, f.path, c)
        out[why] += 1
        _sample(samples, f"super: {why}", r.where(c.caller_id, c.line))
    return out


def _no_edge(r: Repo, path: str, c) -> str:
    if not (c.receiver_type or "").startswith("super:"):
        return "none: super() given arguments"
    found = r.rv.ctx.types.of("python").value(c.receiver_type.removeprefix("super:"), path)
    rests = r.rests.get(python_qualified(found), ()) if isinstance(found, TypeRef) else ()
    if not rests:
        return "none: no MRO the index computes holds its class"
    binds = r.rv.ctx.types.of("python").binds
    firsts = [next((t for t in rest if not isinstance(t, TypeRef) or binds(t, c.callee_name)), None) for rest in rests]
    if any(isinstance(t, TypeRef) for t in firsts):
        return "none: what binds the name is no method the call may reach"
    return "none: a base outside the repo comes first" if any(firsts) else "none: no class after it binds the name"


def overrides(r: Repo) -> collections.Counter:
    members: dict[str, dict[str, list[str]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for s in r.res.symbols:
        if s.kind == "method" and s.parent_id:
            members[s.parent_id][s.name].append(s.id)
    overridden: dict[str, set[str]] = collections.defaultdict(set)
    for t in {e.source_id for e in r.edges}:
        for a in r.ancestors(t):
            for name in members[t].keys() & members[a].keys():
                for o in members[a][name]:
                    overridden[o].update(members[t][name])
    out = collections.Counter({"methods overridden": len(overridden),
                               "override pairs": sum(len(v) for v in overridden.values())})
    for c in r.calls:
        if c.callee_id in overridden:
            out[f"calls to one, {'may dispatch' if c.virtual else 'do not dispatch'}"] += 1
    return out


def go_interfaces(r: Repo) -> collections.Counter:
    go, out = languages.by_id("go"), collections.Counter()
    at: dict[tuple[str, int], set[str]] = collections.defaultdict(set)
    for c in r.calls:
        at[(c.caller_id, c.line)].add(r.sym[c.callee_id].name)
    interfaces = {t.qualified_name for t in r.types if t.kind == "interface"}
    for c in r.res.calls:
        f = r.rv.files_by_id.get(c.file_id)
        if f is None or f.language != "go" or not c.receiver_type:
            continue
        q = go.resolve_receiver(r.rv.ctx, f, c.receiver_type, c.receiver_path)
        if q not in interfaces or c.callee_name in at[(c.caller_id, c.line)]:
            continue
        out["calls with no edge of the method's name"] += 1
        implementers = r.rv.ctx.types.of("go").implementers(go_ref(q))
        out["of them on 2+ implementers"] += not isinstance(implementers, Unknown) and len(implementers) > 1
    return out


def _sample(samples: dict, key: str, value: str) -> None:
    if len(samples[key]) < SAMPLES:
        samples[key].append(value)


def report(root: str, name: str) -> dict:
    r, samples = Repo(root, name), collections.defaultdict(list)
    return {"repo": name, "seconds": r.seconds, "edges": edges(r), "consistency": consistency(r, samples),
            "one name": one_name(r, samples), "not dispatching": not_dispatching(r, samples),
            "super": super_calls(r, samples),
            "overrides": overrides(r), "go interfaces": go_interfaces(r), "samples": samples}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    for name in argv[2:]:
        print(json.dumps(report(argv[1], name)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
