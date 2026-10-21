"""`impact_of` and `ref_diff`: the blast radius of one symbol, and what a branch changes."""

from __future__ import annotations

from typing import Any

from ..core.config import is_test_path
from .store import MAX_ROWS, AtlasError
from .tools_http import _collapse_refs
from .tools_symbols import _symbol


def register(mcp, st) -> None:
    @mcp.tool()
    def impact_of(symbol: str, repo: str | None = None, ref: str | None = None, max_depth: int = 6,
                  tenant: str | None = None) -> dict[str, Any]:
        """Blast radius of changing one symbol, across repositories. Walks incoming CALLS inside the
        symbol's repo/ref (up to `max_depth` hops) to the HTTP handlers that reach it, then the
        routes those handlers serve (HANDLED_BY) and the services that consume them (CONSUMES /
        CALLED_FROM, materialized by the linker). Returns: `internal_callers` (symbols in the same
        repo that reach it, with hop distance), `exposed_through` (routes whose handler reaches it),
        `consumers` (other repos: service, route, caller symbol, file:line, confidence). Each internal
        caller carries `test: true|false` (file under a test path) and the counts are split into
        `production_caller_count` / `test_caller_count` — read the production ones first. An empty
        `consumers` with non-empty `exposed_through` means "public route, no indexed caller" — the
        app/front-end is usually the caller. Calls are name-resolved (see who_calls): hops marked
        `-ambiguous` are likely, not proven. On a type (class/interface/struct) the calls to its members
        count too (`members_included`): changing the class affects whoever calls its methods."""
        s = st(tenant)
        sy = _symbol(s, symbol, repo, ref)
        depth = max(1, min(max_depth, 10))
        members = [r["id"] for r in s.read(
            "MATCH (:Symbol {id: $id})-[:CONTAINS]->(m:Symbol) RETURN m.id AS id", id=sy["id"])]
        targets = [sy["id"]] + members
        callers = s.read(f"""
            MATCH (t:Symbol) WHERE t.id IN $targets
            MATCH p = (h:Symbol)-[:CALLS*1..{depth}]->(t)
            WHERE h.ref = $ref AND h.repo = $repo AND NOT h.id IN $targets
            WITH h, min(length(p)) AS hops, collect(DISTINCT [r IN relationships(p) | r.strategy]) AS strategies
            MATCH (f:File)-[:CONTAINS]->(h)
            RETURN h.id AS id, h.qualified_name AS qualified_name, h.kind AS kind, f.path AS file, hops,
                   h.is_entry_point AS entry_point,
                   any(st IN reduce(acc = [], x IN strategies | acc + x) WHERE st ENDS WITH 'ambiguous') AS via_ambiguous
            ORDER BY hops, qualified_name LIMIT $limit
        """, targets=targets, ref=sy["ref"], repo=sy["repo"], limit=MAX_ROWS)
        for c in callers:
            c["test"] = is_test_path(c["file"])
        production = [c for c in callers if not c["test"]]
        reach_ids = targets + [c["id"] for c in callers]
        exposed = s.read("""
            MATCH (e:HttpEndpoint)-[:HANDLED_BY {ref: $ref}]->(h:Symbol)
            WHERE h.id IN $ids
            OPTIONAL MATCH (e)-[cf:CALLED_FROM]->(caller)
            WITH e, h, cf, caller ORDER BY caller.repo, cf.ref, cf.line
            RETURN e.id AS endpoint_id, e.service AS service, e.method AS method, e.path AS path,
                   h.qualified_name AS handler,
                   [x IN collect(CASE WHEN cf IS NULL THEN null ELSE
                        {repo: caller.repo, ref: cf.ref, caller: coalesce(caller.qualified_name, caller.path),
                         evidence: cf.evidence, confidence: cf.confidence, hint: cf.hint} END) WHERE x IS NOT NULL] AS consumers
            ORDER BY path, method
        """, ref=sy["ref"], ids=reach_ids)
        consumers = []
        for e in exposed:
            for c in _collapse_refs(e.pop("consumers")):
                consumers.append({"service": e["service"], "method": e["method"], "path": e["path"], **c})
        return {"symbol": sy, "members_included": len(members), "internal_callers": callers, "internal_caller_count": len(callers),
                "production_caller_count": len(production), "test_caller_count": len(callers) - len(production),
                "exposed_through": exposed, "consumers": consumers,
                "consumer_repos": sorted({c["repo"] for c in consumers})}

    @mcp.tool()
    def ref_diff(repo: str, ref: str, base: str | None = None, limit: int = 100,
                 tenant: str | None = None) -> dict[str, Any]:
        """What a branch adds or removes compared to another indexed ref of the same repo (default:
        the repo's default branch): HTTP routes exposed (`endpoints_added` / `endpoints_removed`),
        entry-point symbols (handlers, controllers, commands — `entry_points_added` / `_removed`, by
        qualified name), outbound HTTP calls (`http_calls_added` / `_removed`, by method+path) and
        every symbol (`symbols_added` / `_removed` / `_changed` — changed = same qualified name, different
        body; struct fields are left out, a field change shows as its struct changing; at most `limit`
        each, `summary` counts them all).
        Useful to review a feature branch's surface before it merges, or to explain why
        `who_consumes` shows a route only in some refs. `snapshots` gives the indexed sha of each
        ref — compare with `git rev-parse` before trusting a diff on a branch you just merged into."""
        s = st(tenant)
        ref = s.resolve_ref(repo, ref)
        base = s.resolve_ref(repo, base)
        if ref == base:
            raise AtlasError(f"ref and base are the same ({ref}) — pass a different `base`")

        def surface(r: str) -> dict[str, Any]:
            eps = s.read("""
                MATCH (:Service {tenant: $tenant, name: $repo})-[x:EXPOSES {ref: $ref}]->(e:HttpEndpoint)
                OPTIONAL MATCH (e)-[:HANDLED_BY {ref: $ref}]->(h:Symbol)
                RETURN e.method + ' ' + e.path AS key, e.method AS method, e.path AS path, h.qualified_name AS handler, x.evidence AS evidence
            """, repo=repo, ref=r)
            syms = s.read("""
                MATCH (sy:Symbol {tenant: $tenant, repo: $repo, ref: $ref, is_entry_point: true})
                MATCH (f:File)-[:CONTAINS]->(sy)
                RETURN sy.qualified_name AS key, sy.kind AS kind, f.path AS file, sy.line_start AS line
            """, repo=repo, ref=r)
            calls = s.read("""
                MATCH (c:HttpCall {tenant: $tenant, repo: $repo, ref: $ref})
                RETURN DISTINCT c.method + ' ' + c.path AS key, c.method AS method, c.path AS path, c.target_hint AS target_hint
            """, repo=repo, ref=r)
            return {"endpoints": {r["key"]: r for r in eps}, "entry_points": {r["key"]: r for r in syms},
                    "http_calls": {r["key"]: r for r in calls}}

        a, b = surface(ref), surface(base)
        snaps = {r["ref"]: r for r in s.read("""
            MATCH (sn:Snapshot {tenant: $tenant, repo: $repo}) WHERE sn.ref IN [$ref, $base]
            RETURN sn.ref AS ref, left(sn.commit_sha, 10) AS sha, toString(sn.indexed_at) AS indexed_at
        """, repo=repo, ref=ref, base=base)}
        out: dict[str, Any] = {"repo": repo, "ref": ref, "base": base,
                               "snapshots": snaps,
                               "note": "compares the INDEXED commits above (remote-tracking refs). A local merge or "
                                       "unpushed commits are not in the graph until they are pushed and refreshed."}
        for kind in ("endpoints", "entry_points", "http_calls"):
            out[f"{kind}_added"] = [a[kind][k] for k in sorted(set(a[kind]) - set(b[kind]))]
            out[f"{kind}_removed"] = [b[kind][k] for k in sorted(set(b[kind]) - set(a[kind]))]
        out["summary"] = {k: len(v) for k, v in out.items() if isinstance(v, list)}

        def symbols(r: str) -> dict[tuple[str, str], dict[str, Any]]:
            by: dict[tuple[str, str], dict[str, Any]] = {}
            for row in s.read("""
                MATCH (sy:Symbol {tenant: $tenant, repo: $repo, ref: $ref}) WHERE sy.kind <> 'field'
                RETURN sy.qualified_name AS qualified_name, sy.kind AS kind, sy.path AS file, sy.line_start AS line,
                       sy.content_hash AS hash
            """, repo=repo, ref=r):
                digest = row.pop("hash")
                key = (row["qualified_name"], row["kind"])
                by.setdefault(key, {"row": row, "hashes": set()})["hashes"].add(digest)   # overloads share a name
            return by

        sa, sb = symbols(ref), symbols(base)
        changes = {"symbols_added": [sa[k]["row"] for k in sorted(set(sa) - set(sb))],
                   "symbols_removed": [sb[k]["row"] for k in sorted(set(sb) - set(sa))],
                   "symbols_changed": [sa[k]["row"] for k in sorted(set(sa) & set(sb)) if sa[k]["hashes"] != sb[k]["hashes"]]}
        for k, v in changes.items():
            out["summary"][k] = len(v)
            out[k] = v[:limit]
        return out
