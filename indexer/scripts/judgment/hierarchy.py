#!/usr/bin/env python3
"""What a tree's types' bases give each repo, and the yardsticks of the work they open, one JSON line per repo:

- `edges`: the `EXTENDS` and `IMPLEMENTS` edges, by language, kind and the kinds of their ends;
- `consistency`: whether each type's ancestors through them are the ancestry the resolver walks for a call: in C#, the
  same names; in Python, the resolver's supertypes among them, and why the others are not;
- `one name`: the qualified names several type symbols of one file share, and the edges that touch them;
- `not dispatching`: the `CALLS` that do not dispatch, by strategy and by what they reach from the caller: itself, its
  own class, an ancestor of its class or none, and their sites;
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
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.core.resolve import TYPE_KINDS, Resolver
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.go.symbols import _ref as go_ref
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
    if lang == "csharp":
        return "closure = ancestry" if closure == walked else "closure != ancestry"
    if not walked <= closure:
        return "supertypes outside the closure"
    if closure == walked:
        return "closure = supertypes"
    mro = r.rv.ctx.types.of("python").mro(python_ref(q))
    if isinstance(mro, Unknown):
        return f"closure > supertypes: no MRO, {mro.reason}"
    if any(not isinstance(t, TypeRef) for t in mro):
        return "closure > supertypes: a base outside the repo ahead in the MRO"
    return "closure > supertypes: unexplained"


def one_name(r: Repo, samples: dict) -> collections.Counter:
    ids: dict[str, set[str]] = collections.defaultdict(set)
    for t in r.types:
        ids[t.qualified_name].add(t.id)
    shared = {q for q, v in ids.items() if len(v) > 1}
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
    owner = caller.parent_id if caller else None
    target = callee.parent_id or callee.id
    if caller is None:
        return "from a file"
    if callee.id == caller.id:
        return "the caller itself"
    if target == owner:
        return "the caller's class"
    return "an ancestor" if owner and target in r.ancestors(owner) else "no ancestor"


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
