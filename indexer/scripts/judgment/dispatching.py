"""The dispatch yardsticks of `hierarchy.py`, over its `Repo`: the calls that do not dispatch by what they reach,
Python's `super()` calls its receiver does not decide, the `OVERRIDES` edges against the pairs of one name, and Go's
interface calls with no edge."""
from __future__ import annotations

import collections
from typing import TYPE_CHECKING

from aidd_indexer import languages
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.csharp.overrides import modifiers as csharp_modifiers
from aidd_indexer.languages.go.symbols import _ref as go_ref
from aidd_indexer.languages.python.type_index import qualified as python_qualified
from aidd_indexer.languages.python.type_index import ref as python_ref

if TYPE_CHECKING:
    from hierarchy import Repo

SAMPLES = 3

def not_dispatching(r: Repo, samples: dict) -> collections.Counter:
    out, sites = collections.Counter(), collections.defaultdict(set)
    for c in r.calls:
        if c.virtual:
            continue
        reach = _reach(r, c)
        out[f"{c.strategy} | {reach}"] += 1
        sites[reach].add((c.caller_id, c.line))
        sample(samples, f"not dispatching: {reach}", f"{r.where(c.caller_id, c.line)} -> "
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
        sample(samples, f"super: {why}", r.where(c.caller_id, c.line))
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


def overrides(r: Repo, samples: dict) -> collections.Counter:
    edges = {(e.source_id, e.target_id) for e in r.overrides}
    named = _pairs_by_name(r)
    out = collections.Counter(f"{r.language(m)} | edges" for m, _ in edges)
    for m, o in named - edges:
        why = _left_out(r, m, o)
        out[f"{r.language(m)} | a pair by name left out: {why}"] += 1
        sample(samples, f"overrides left out: {why}", f"{r.sym[m].qualified_name} -> {r.sym[o].qualified_name}")
    for m, o in edges - named:
        out[f"{r.language(m)} | an edge of no pair by name"] += 1
        sample(samples, "overrides of no pair by name", f"{r.sym[m].qualified_name} -> {r.sym[o].qualified_name}")
    callers = collections.defaultdict(set)
    for c in r.calls:
        if c.virtual:
            callers[c.callee_id].add((c.caller_id, c.line))
    out["who_calls adds: (override, caller site)"] = sum(len(callers[o]) for _, o in edges)
    return out


def _pairs_by_name(r: Repo) -> set[tuple[str, str]]:
    members: dict[str, dict[str, list[str]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for s in r.res.symbols:
        if s.kind == "method" and s.parent_id:
            members[s.parent_id][s.name].append(s.id)
    return {(m, o) for t in {e.source_id for e in r.edges} for a in r.ancestors(t)
            for name in members[t].keys() & members[a].keys() for m in members[t][name] for o in members[a][name]}


def _left_out(r: Repo, m: str, o: str) -> str:
    sub, base = r.sym[m], r.sym[o]
    if r.language(m) != "csharp":
        mro = r.rv.ctx.types.of("python").mro(python_ref(r.sym[sub.parent_id].qualified_name))
        return f"no MRO, {mro.reason}" if isinstance(mro, Unknown) else "a definition its class replaces"
    said = csharp_modifiers(sub) | csharp_modifiers(base)
    if sub.arity and base.arity and sub.arity[1] != base.arity[1]:
        return "another number of parameters"
    if "static" in said:
        return "a static method"
    interface = r.sym[base.parent_id].kind == "interface"
    return "an implementation another class gives" if interface else \
        "not `override`" if "override" not in csharp_modifiers(sub) else "past a `new`, or overloads of one number"


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


def sample(samples: dict, key: str, value: str) -> None:
    if len(samples[key]) < SAMPLES:
        samples[key].append(value)
