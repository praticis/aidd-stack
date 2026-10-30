"""The tenant's links in the graph: what the linker reads (every `HttpCall` and `HttpEndpoint`, every snapshot's
requires and provides) and the edges it writes (`CONSUMES`, `CALLED_FROM`, `DEPENDS_ON`)."""

from __future__ import annotations

from datetime import datetime, timezone

from .graph_session import GraphSession
from .linker import CallRow, DepRow, EndpointRow, ProvideRow, called_from_rows, consumes_rows, depends_on_rows, link, link_deps


class TenantLinks(GraphSession):
    def link_tenant(self, tenant: str) -> dict[str, int]:
        """Rebuild every CONSUMES / CALLED_FROM edge of the tenant from what is in the graph now.
        Cross-repo by nature (a call in A matches a route of B), so it runs after the snapshots
        are written — at the end of index/bootstrap/refresh, or `aidd link`. Idempotent."""
        endpoints = [EndpointRow(r["id"], r["service"], r["method"], r["path_key"], r["framework"] or "") for r in self._rows("""
            MATCH (s:Service {tenant: $tenant})-[:EXPOSES]->(e:HttpEndpoint)
            RETURN DISTINCT e.id AS id, s.name AS service, e.method AS method, e.path_key AS path_key, e.framework AS framework
        """, tenant=tenant)]
        calls = [CallRow(r["id"], r["repo"], r["ref"], r["sha"], r["method"], r["path_key"], r["target_hint"] or "",
                         tuple(r["env_hints"] or ()), r["caller_id"], r["evidence"], r["via"] or "", r["line"])
                 for r in self._rows("""
            MATCH (caller)-[:MAKES_HTTP_CALL]->(c:HttpCall {tenant: $tenant})
            RETURN c.id AS id, c.repo AS repo, c.ref AS ref, c.commit_sha AS sha, c.method AS method,
                   c.path_key AS path_key, c.target_hint AS target_hint, c.env_hints AS env_hints,
                   caller.id AS caller_id, c.evidence AS evidence, c.via AS via, c.line AS line
        """, tenant=tenant)]
        result = link(calls, endpoints)
        now = datetime.now(timezone.utc).isoformat()
        self._run("MATCH (:Service {tenant: $tenant})-[c:CONSUMES]->() DELETE c", tenant=tenant)
        self._run("MATCH (:HttpEndpoint {tenant: $tenant})-[c:CALLED_FROM]->() DELETE c", tenant=tenant)
        self._batched("""
            UNWIND $rows AS r
            MATCH (s:Service {tenant: $tenant, name: r.repo}), (e:HttpEndpoint {id: r.endpoint_id})
            MERGE (s)-[c:CONSUMES {ref: r.ref}]->(e)
            SET c.commit_sha = r.commit_sha, c.confidence = r.confidence, c.hint = r.hint, c.call_count = r.call_count,
                c.methods = r.methods, c.evidence = r.evidence, c.linked_at = datetime($now)
        """, consumes_rows(result), tenant=tenant, now=now)
        self._batched("""
            UNWIND $rows AS r
            MATCH (e:HttpEndpoint {id: r.endpoint_id}), (caller:Symbol|File {id: r.caller_id})
            MERGE (e)-[c:CALLED_FROM {ref: r.ref, call_id: r.call_id}]->(caller)
            SET c.commit_sha = r.commit_sha, c.line = r.line, c.method = r.method, c.confidence = r.confidence,
                c.hint = r.hint, c.evidence = r.evidence, c.via = r.via, c.linked_at = datetime($now)
        """, called_from_rows(result), tenant=tenant, now=now)
        deps = self._link_deps(tenant, now)
        return {"endpoints": len(endpoints), "calls": len(calls)} | result.counts() | deps

    def _link_deps(self, tenant: str, now: str) -> dict[str, int]:
        """`Snapshot.requires` × `Snapshot.provides` → `Service -[:DEPENDS_ON {ref}]-> Service`.
        What a repo publishes is the union over its refs; what it requires is per ref."""
        snaps = self._rows("""
            MATCH (s:Snapshot {tenant: $tenant})
            RETURN s.repo AS repo, s.ref AS ref, s.commit_sha AS sha, s.provides AS provides, s.requires AS requires
        """, tenant=tenant)
        provides = [ProvideRow(r["repo"], key) for r in snaps for key in (r["provides"] or ())]
        requires = []
        for r in snaps:
            for item in r["requires"] or ():
                key, _, version = item.rpartition("@")
                requires.append(DepRow(r["repo"], r["ref"], r["sha"] or "", key, version))
        result = link_deps(requires, provides)
        self._run("MATCH (:Service {tenant: $tenant})-[d:DEPENDS_ON]->() DELETE d", tenant=tenant)
        rows = depends_on_rows(result)
        self._batched("""
            UNWIND $rows AS r
            MATCH (a:Service {tenant: $tenant, name: r.repo}), (b:Service {tenant: $tenant, name: r.provider})
            MERGE (a)-[d:DEPENDS_ON {ref: r.ref}]->(b)
            SET d.commit_sha = r.commit_sha, d.packages = r.packages, d.versions = r.versions,
                d.ecosystems = r.ecosystems, d.linked_at = datetime($now)
        """, rows, tenant=tenant, now=now)
        return {"depends_on": len(rows), "deps_packages": len(result.edges), "deps_ambiguous": len(result.ambiguous)}
