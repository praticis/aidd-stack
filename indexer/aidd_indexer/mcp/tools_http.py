"""`http_map` and `who_consumes`: one repository's HTTP surface, and who calls a route."""

from __future__ import annotations

import re
from typing import Any

from ..core.linker import CASE_INSENSITIVE


def _collapse_refs(consumers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (repo, caller) with the refs it appears in — a call site indexed on 13 branches
    is one consumer, not thirteen. `evidence` is taken from the first ref in sorted order (the
    default branch sorts first in practice: 'main' < 'feature/...' is not guaranteed, so refs are listed)."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for c in consumers:
        key = (c["repo"], c.get("caller") or "")
        g = groups.setdefault(key, {**{k: v for k, v in c.items() if k != "ref"}, "refs": []})
        g["refs"].append(c["ref"])
    out = []
    for g in groups.values():
        g["refs"] = sorted(set(g["refs"]), key=lambda r: (r not in ("main", "master", "develop"), r))
        g["ref_count"] = len(g["refs"])
        out.append(g)
    return sorted(out, key=lambda g: (g["repo"], g.get("caller") or ""))


def register(mcp, st) -> None:
    @mcp.tool()
    def http_map(repo: str, ref: str | None = None, tenant: str | None = None) -> dict[str, Any]:
        """HTTP surface of one repository at a ref: the routes it EXPOSES (method, path template,
        framework, handler symbol; `app`, the module that declares the route when the repo holds
        several apps, else empty) and the outbound HTTP calls it makes with a literal path
        (method, path template, where in the code, which package/env var hints at the target
        service, and `linked_to`: the endpoint of another service the linker matched it to, or
        null). Extracted deterministically from the source — no runtime data."""
        s = st(tenant)
        ref = s.resolve_ref(repo, ref)
        base = dict(repo=repo, ref=ref)
        exposes = s.read("""
            MATCH (:Service {tenant: $tenant, name: $repo})-[x:EXPOSES {ref: $ref}]->(e:HttpEndpoint)
            OPTIONAL MATCH (e)-[:HANDLED_BY {ref: $ref}]->(h:Symbol)
            OPTIONAL MATCH (consumer:Service)-[:CONSUMES]->(e)
            RETURN e.id AS id, e.method AS method, e.path AS path, e.framework AS framework, coalesce(e.app, '') AS app,
                   h.id AS handler_id, h.qualified_name AS handler, x.evidence AS evidence,
                   collect(DISTINCT consumer.name) AS consumer_repos
            ORDER BY path, method
        """, **base)
        calls = s.read("""
            MATCH (c:HttpCall {tenant: $tenant, repo: $repo, ref: $ref})
            OPTIONAL MATCH (caller)-[:MAKES_HTTP_CALL]->(c)
            OPTIONAL MATCH (target:HttpEndpoint)-[cf:CALLED_FROM {call_id: c.id}]->()
            WITH c, caller, collect(DISTINCT CASE WHEN target IS NULL THEN null ELSE
                 {service: target.service, app: coalesce(target.app, ''), method: target.method, path: target.path,
                  confidence: cf.confidence, hint: cf.hint}
                 END) AS targets
            RETURN c.id AS id, c.method AS method, c.path AS path, c.via AS via, c.target_hint AS target_hint,
                   c.env_hints AS env_hints, coalesce(caller.qualified_name, caller.path) AS caller, c.evidence AS evidence,
                   [t IN targets WHERE t IS NOT NULL] AS targets
            ORDER BY target_hint, path, method
        """, **base)
        for c in calls:                          # one row per call site; a call linked to several endpoints lists them all
            targets = c.pop("targets") or []
            c["linked_to"] = targets[0] if targets else None
            if len(targets) > 1:
                c["also_linked_to"] = targets[1:]
        by_target: dict[str, int] = {}
        for c in calls:
            by_target[c["target_hint"] or "?"] = by_target.get(c["target_hint"] or "?", 0) + 1
        linked = sum(1 for c in calls if c["linked_to"])
        return {**base, "exposes": exposes, "outbound_calls": calls, "outbound_by_target_hint": by_target,
                "outbound_linked": linked, "outbound_unlinked": len(calls) - linked}

    @mcp.tool()
    def who_consumes(path: str, method: str | None = None, repo: str | None = None, tenant: str | None = None) -> dict[str, Any]:
        """Which repositories call an HTTP route, and from where. `path` is a route template as
        exposed ('/v1/users/{id}' — placeholder names do not matter) or a prefix; `repo` narrows
        to the service exposing it. Returns each matching endpoint (with its `app` when the repo
        holds several apps, as the same route can be exposed by each) with its handler, its
        `consumers` (materialized CONSUMES/CALLED_FROM edges, one per repo × caller symbol with the
        `refs` where the call site exists, file:line evidence, confidence exact|suffix and which
        hint broke a tie) and `possible_consumers`: outbound
        calls with the same path that the linker did NOT link — usually because several services
        expose that path and nothing (target_hint, env var name, convention `targets:`) picks one.
        An ASP.NET route matches without case, as the framework (and the linker) match it.
        Consumers come from outbound calls with a literal/template path in the consumer's code;
        URLs assembled dynamically are invisible."""
        s = st(tenant)
        key = re.sub(r"\{[^}]*\}", "{param}", path.rstrip("/") or "/")
        rows = s.read("""
            MATCH (svc:Service {tenant: $tenant})-[:EXPOSES]->(e:HttpEndpoint)
            WHERE ($repo IS NULL OR svc.name = $repo)
              AND ($method IS NULL OR e.method = toUpper($method) OR e.method = 'ANY')
            WITH svc, e, coalesce(e.framework IN $nocase, false) AS nocase
            WITH svc, e, nocase, CASE WHEN nocase THEN toLower(e.path_key) ELSE e.path_key END AS ekey,
                 CASE WHEN nocase THEN toLower($key) ELSE $key END AS qkey
            WHERE ekey = qkey OR ekey STARTS WITH qkey + '/'
            WITH DISTINCT svc, e, nocase
            OPTIONAL MATCH (e)-[:HANDLED_BY]->(h:Symbol)
            WITH svc, e, nocase, collect(DISTINCT {ref: h.ref, symbol: h.qualified_name})[0..3] AS handlers
            OPTIONAL MATCH (e)-[cf:CALLED_FROM]->(caller)
            WITH svc, e, nocase, handlers, cf, caller ORDER BY caller.repo, cf.ref, cf.line
            WITH svc, e, nocase, handlers,
                 [x IN collect(CASE WHEN cf IS NULL THEN null ELSE
                    {repo: caller.repo, ref: cf.ref, method: cf.method, caller: coalesce(caller.qualified_name, caller.path),
                     evidence: cf.evidence, confidence: cf.confidence, hint: cf.hint} END) WHERE x IS NOT NULL] AS consumers
            OPTIONAL MATCH (c:HttpCall {tenant: $tenant})
            WHERE (c.path_key = e.path_key OR nocase AND toLower(c.path_key) = toLower(e.path_key))
              AND (c.method = e.method OR e.method = 'ANY' OR c.method = 'ANY') AND c.repo <> svc.name
              AND NOT EXISTS { MATCH (e)-[x:CALLED_FROM]->() WHERE x.call_id = c.id }
            OPTIONAL MATCH (pc)-[:MAKES_HTTP_CALL]->(c)
            WITH svc, e, handlers, consumers, c, pc ORDER BY c.repo, c.ref, c.line
            RETURN svc.name AS service, coalesce(e.app, '') AS app, e.id AS endpoint_id, e.method AS method, e.path AS path,
                   handlers, consumers,
                   [x IN collect(CASE WHEN c IS NULL THEN null ELSE
                        {repo: c.repo, ref: c.ref, method: c.method, path: c.path,
                         caller: coalesce(pc.qualified_name, pc.path), evidence: c.evidence,
                         target_hint: c.target_hint, env_hints: c.env_hints} END) WHERE x IS NOT NULL][0..20] AS possible_consumers
            ORDER BY service, path, method LIMIT 50
        """, key=key, method=method, repo=repo, nocase=sorted(CASE_INSENSITIVE))
        for r in rows:
            r["consumers"] = _collapse_refs(r["consumers"])
            r["consumer_repos"] = sorted({c["repo"] for c in r["consumers"]})
        return {"query": {"path": path, "method": method, "repo": repo}, "endpoints": rows}
