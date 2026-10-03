"""Linker (ROADMAP F0.5): `HttpCall` × `HttpEndpoint` → `CONSUMES` / `CALLED_FROM`.

Pure functions over rows already in the graph — no Neo4j here, so the rules are unit-testable
(`tests/test_linker.py`). `GraphWriter.link_tenant` reads the rows, calls `link`, writes the edges.

Rules, in order of confidence:

* `exact`  — same tenant, compatible method (equal, or `ANY` on either side), equal `path_key`,
             endpoint exposed by a service other than the caller's.
* `suffix` — only when nothing matches exactly: one `path_key` is a segment-aligned suffix of the
             other (`/v1/orders/{param}` × `/api/v1/orders/{param}` — a base URL with a prefix),
             **and** a hint (`target_hint` / `env_hints`) names the provider. A bare suffix is too
             weak: `/documents/{param}/upload` is the tail of many unrelated routes (seen in the
             first portfolio run), so without corroboration the call stays unmatched.

Second join (F0.5.1): `Snapshot.requires` × `Snapshot.provides` — a manifest dependency whose
package name another repo of the tenant publishes becomes `Service -[:DEPENDS_ON {ref}]-> Service`.
Same stance: exact normalized name, never self, two publishers of the same name → no edge.

When more than one service exposes a candidate, the call's `target_hint` (directory heuristic or a
convention's `targets:`) and `env_hints` (`BILLING_URL`) disambiguate by matching a token of the
service name. Still more than one service → **no edge** (precision before recall, as in the
extractor); the call stays an `HttpCall` and the MCP lists the candidates as "possible".
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

GENERIC_TOKENS = frozenset({"api", "svc", "service", "services", "url", "base", "baseurl", "host", "endpoint", "addr",
                            "http", "https", "client", "gateway", "app", "server", "internal", "v1", "v2", "v3"})


@dataclass(frozen=True)
class EndpointRow:
    id: str
    service: str
    method: str
    path_key: str


@dataclass(frozen=True)
class CallRow:
    id: str
    repo: str                      # the consumer service (1:1 with repo in v0)
    ref: str
    commit_sha: str
    method: str
    path_key: str
    target_hint: str
    env_hints: tuple[str, ...]
    caller_id: str
    evidence: str
    via: str
    line: int


@dataclass(frozen=True)
class LinkEdge:
    call: CallRow
    endpoint: EndpointRow
    confidence: str                # exact | suffix
    hint: str | None               # target_hint | env_hint | None — what broke the tie, if any


@dataclass
class LinkResult:
    edges: list[LinkEdge] = field(default_factory=list)
    unmatched: list[CallRow] = field(default_factory=list)
    ambiguous: dict[str, list[EndpointRow]] = field(default_factory=dict)   # call id -> candidates

    def counts(self) -> dict[str, int]:
        return {
            "linked": len(self.edges),
            "exact": sum(1 for e in self.edges if e.confidence == "exact"),
            "suffix": sum(1 for e in self.edges if e.confidence == "suffix"),
            "by_hint": sum(1 for e in self.edges if e.hint),
            "unmatched": len(self.unmatched),
            "ambiguous": len(self.ambiguous),
        }


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t} - GENERIC_TOKENS


def methods_compatible(a: str, b: str) -> bool:
    return a == b or a == "ANY" or b == "ANY"


def is_segment_suffix(short: str, long: str) -> bool:
    """`/v1/x/{param}` is a suffix of `/api/v1/x/{param}` — path keys start with `/`, so the
    boundary is a whole segment by construction."""
    return len(long) > len(short) and long.endswith(short)


def hint_matches(hint: str, service: str) -> bool:
    h = hint.lower()
    if not h or h in GENERIC_TOKENS:
        return False
    return h in service.lower() or bool(_tokens(h) & _tokens(service))


def hinted_services(call: CallRow, services: set[str]) -> set[str]:
    return {s for s in services if hint_matches(call.target_hint, s) or any(hint_matches(h, s) for h in call.env_hints)}


def _candidates(call: CallRow, endpoints: list[EndpointRow]) -> tuple[list[EndpointRow], str]:
    usable = [e for e in endpoints if e.service != call.repo and methods_compatible(call.method, e.method)]
    exact = [e for e in usable if e.path_key == call.path_key]
    if exact:
        return exact, "exact"
    suffix = [e for e in usable
              if is_segment_suffix(call.path_key, e.path_key) or is_segment_suffix(e.path_key, call.path_key)]
    corroborated = hinted_services(call, {e.service for e in suffix})
    return [e for e in suffix if e.service in corroborated], "suffix"


def _disambiguate(call: CallRow, cands: list[EndpointRow]) -> tuple[list[EndpointRow], str | None]:
    services = {e.service for e in cands}
    if len(services) <= 1:
        return cands, None
    by_target = {s for s in services if hint_matches(call.target_hint, s)}
    if len(by_target) == 1:
        return [e for e in cands if e.service in by_target], "target_hint"
    by_env = {s for s in services if any(hint_matches(h, s) for h in call.env_hints)}
    if len(by_env) == 1:
        return [e for e in cands if e.service in by_env], "env_hint"
    return [], None


def link(calls: list[CallRow], endpoints: list[EndpointRow]) -> LinkResult:
    out = LinkResult()
    for call in calls:
        cands, confidence = _candidates(call, endpoints)
        if not cands:
            out.unmatched.append(call)
            continue
        chosen, hint = _disambiguate(call, cands)
        if not chosen:
            out.ambiguous[call.id] = cands
            continue
        for e in chosen:
            out.edges.append(LinkEdge(call, e, confidence, hint))
    return out


def consumes_rows(result: LinkResult) -> list[dict]:
    """One `CONSUMES {ref}` per (consumer service, endpoint, ref): call sites collapsed."""
    groups: dict[tuple[str, str, str], list[LinkEdge]] = defaultdict(list)
    for e in result.edges:
        groups[(e.call.repo, e.endpoint.id, e.call.ref)].append(e)
    rows = []
    for (repo, endpoint_id, ref), edges in sorted(groups.items()):
        edges.sort(key=lambda e: e.call.evidence)
        rows.append({
            "repo": repo, "endpoint_id": endpoint_id, "ref": ref,
            "commit_sha": edges[0].call.commit_sha,
            "confidence": "suffix" if any(e.confidence == "suffix" for e in edges) else "exact",
            "hint": next((e.hint for e in edges if e.hint), None),
            "call_count": len(edges),
            "methods": sorted({e.call.method for e in edges}),
            "evidence": [e.call.evidence for e in edges[:10]],
        })
    return rows


def called_from_rows(result: LinkResult) -> list[dict]:
    """One `CALLED_FROM {ref, call_id}` per linked call site: endpoint → caller Symbol|File."""
    return [{
        "endpoint_id": e.endpoint.id, "caller_id": e.call.caller_id, "call_id": e.call.id,
        "ref": e.call.ref, "commit_sha": e.call.commit_sha, "line": e.call.line, "method": e.call.method,
        "confidence": e.confidence, "hint": e.hint, "evidence": e.call.evidence, "via": e.call.via,
    } for e in sorted(result.edges, key=lambda e: (e.endpoint.id, e.call.evidence))]


# ---- F0.5.1: manifests → DEPENDS_ON ------------------------------------------------------

@dataclass(frozen=True)
class ProvideRow:
    repo: str
    key: str                       # "<ecosystem>:<normalized name>"


@dataclass(frozen=True)
class DepRow:
    repo: str
    ref: str
    commit_sha: str
    key: str                       # "<ecosystem>:<normalized name>"
    version: str


@dataclass(frozen=True)
class DepEdge:
    dep: DepRow
    provider: str


@dataclass
class DepLinkResult:
    edges: list[DepEdge] = field(default_factory=list)
    ambiguous: dict[str, list[str]] = field(default_factory=dict)   # package key -> publishing repos


def link_deps(requires: list[DepRow], provides: list[ProvideRow]) -> DepLinkResult:
    publishers: dict[str, set[str]] = defaultdict(set)
    for p in provides:
        publishers[p.key].add(p.repo)
    out = DepLinkResult()
    for d in requires:
        repos = publishers.get(d.key, set()) - {d.repo}
        if not repos:
            continue
        if len(repos) > 1:
            out.ambiguous[d.key] = sorted(repos)
            continue
        out.edges.append(DepEdge(d, next(iter(repos))))
    return out


def depends_on_rows(result: DepLinkResult) -> list[dict]:
    """One `DEPENDS_ON {ref}` per (consumer, provider, ref) with the packages that justify it."""
    groups: dict[tuple[str, str, str], list[DepEdge]] = defaultdict(list)
    for e in result.edges:
        groups[(e.dep.repo, e.provider, e.dep.ref)].append(e)
    rows = []
    for (repo, provider, ref), edges in sorted(groups.items()):
        edges = sorted({(e.dep.key, e.dep.version): e for e in edges}.values(), key=lambda e: e.dep.key)
        rows.append({
            "repo": repo, "provider": provider, "ref": ref, "commit_sha": edges[0].dep.commit_sha,
            "packages": [e.dep.key.split(":", 1)[1] for e in edges],
            "versions": [e.dep.version for e in edges],
            "ecosystems": sorted({e.dep.key.split(":", 1)[0] for e in edges}),
        })
    return rows
