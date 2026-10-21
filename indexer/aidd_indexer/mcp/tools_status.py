"""`atlas_status` and `repo_map`: what atlas knows, and the overview of one repository."""

from __future__ import annotations

from typing import Any

from .. import INDEXER_VERSION
from ..core.build import indexer_build
from .store import NO_REFRESH, Store


def _collapse_dependents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One line per dependent service: packages (union over refs) and the refs that declare them."""
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        e = by.setdefault(r["service"], {"service": r["service"], "packages": set(), "refs": set()})
        e["packages"].update(r["packages"] or ())
        e["refs"].update(r["refs"] or ())
    return [{"service": k, "packages": sorted(v["packages"]), "refs": sorted(v["refs"])} for k, v in sorted(by.items())]


def register(mcp, st, the_store: Store) -> None:
    @mcp.tool()
    def atlas_status(tenant: str | None = None) -> dict[str, Any]:
        """What atlas knows: indexed repositories, their refs (default branch + active feature
        branches), commit and freshness. Call first; a repo missing here means 'not indexed'.
        `refresh` is the tenant's last automatic update: when `stale` is true the refresher has not run
        for over two intervals and the graph may lag behind the remotes — say so in your answer
        (`stale: null` = no automatic run recorded yet, e.g. a tenant just indexed on demand).
        `remote` per repo: whether the last refresh reached its git remote. `ok: false` means the
        snapshots follow the developer's own `git fetch` (the service token cannot read that remote —
        `note` says why), so a feature branch or PR can lag behind what was pushed: say so, and after a
        `git fetch` run `~/.aidd/aidd refresh --tenant <tenant> --repos <repo>` to catch up.
        `outdated: true` on a snapshot: an older indexer build wrote it, so links the running indexer
        makes (newer resolution) are missing until the refresh re-indexes it — say so instead of
        concluding atlas cannot see them; the same `refresh` command catches up at once.
        In multi-tenant mode (AIDD_TENANT=auto) omit `tenant` to list every tenant's repos, or pass
        the tenant (the workspace folder right below WORKSPACE_PATH) to scope the answer."""
        if the_store.tenant is None and not tenant:
            return {"mode": "multi-tenant", "indexer_version": INDEXER_VERSION, "indexer_build": indexer_build(),
                    "tenants": [{"tenant": t, "refresh": the_store.scoped(t).refresh_state() or NO_REFRESH,
                                 "repos": the_store.scoped(t).repos()} for t in the_store.tenants()]}
        s = st(tenant)
        return {"mode": "fixed" if the_store.tenant else "multi-tenant", "tenant": s.tenant,
                "indexer_version": INDEXER_VERSION, "indexer_build": indexer_build(), "refresh": s.refresh_state() or NO_REFRESH,
                "repos": s.repos()}

    @mcp.tool()
    def repo_map(repo: str, ref: str | None = None, max_entry_points: int = 40, tenant: str | None = None) -> dict[str, Any]:
        """Overview of one repository at a ref (default: its default branch): stack, modules with
        file/symbol counts, entry points (HTTP handlers, controllers, commands), the external
        packages it imports, `layers` (files per architectural layer when a convention is configured,
        with their violation count — see `violations`), and `depends_on` / `depended_by`: other services
        of the workspace linked through internal packages declared in manifests (go.mod, .csproj,
        package.json, pyproject). With a convention configured: `architecture` (the layout it detected,
        e.g. `split`), `conventions` applied, and `roles` — what each type is in the pattern
        (`command-handler`, `validator`, `repository`...), with counts and examples; `find_symbol(role=...)`
        lists every element of a role. Use it before reading files — it tells where things live."""
        s = st(tenant)
        ref = s.resolve_ref(repo, ref)
        base = dict(repo=repo, ref=ref)
        head = s.read("""
            MATCH (r:Repo {tenant: $tenant, name: $repo})-[:HAS_SNAPSHOT]->(snap:Snapshot {ref: $ref})
            RETURN r.stack AS stack, r.area AS area, r.default_ref AS default_ref, r.url AS url,
                   left(snap.commit_sha, 10) AS sha, toString(snap.indexed_at) AS indexed_at, snap.ephemeral AS ephemeral,
                   snap.architecture AS architecture, coalesce(snap.conventions, []) AS conventions
        """, **base)
        head = head[0] if head else {}
        modules = s.read("""
            MATCH (m:Module {tenant: $tenant, repo: $repo, ref: $ref})
            OPTIONAL MATCH (m)-[:CONTAINS]->(f:File)
            OPTIONAL MATCH (f)-[:CONTAINS]->(sy:Symbol)
            RETURN m.name AS name, m.path AS path, m.kind AS kind, count(DISTINCT f) AS files,
                   count(DISTINCT sy) AS symbols, sum(f.loc) AS loc
            ORDER BY files DESC, path
        """, **base)
        entry_points = s.read("""
            MATCH (f:File {tenant: $tenant, repo: $repo, ref: $ref})-[:CONTAINS]->(sy:Symbol {is_entry_point: true})
            RETURN sy.id AS id, sy.qualified_name AS qualified_name, sy.kind AS kind, f.path AS file,
                   sy.line_start AS line, sy.signature AS signature
            ORDER BY file, line LIMIT $limit
        """, limit=max_entry_points, **base)
        packages = s.read("""
            MATCH (f:File {tenant: $tenant, repo: $repo, ref: $ref})-[:IMPORTS]->(p:Package)
            WHERE coalesce(p.stdlib, false) = false
            RETURN p.name AS name, p.ecosystem AS ecosystem, count(DISTINCT f) AS files
            ORDER BY files DESC, name LIMIT 40
        """, **base)
        kinds = s.read("""
            MATCH (sy:Symbol {tenant: $tenant, repo: $repo, ref: $ref})
            RETURN sy.kind AS kind, count(*) AS n ORDER BY n DESC
        """, **base)
        roles = s.read("""
            MATCH (sy:Symbol {tenant: $tenant, repo: $repo, ref: $ref}) WHERE sy.role IS NOT NULL
            WITH sy ORDER BY sy.name
            RETURN sy.role AS role, count(*) AS count, collect(sy.name)[..5] AS examples
            ORDER BY count DESC, role
        """, **base)
        layers = s.read("""
            MATCH (f:File {tenant: $tenant, repo: $repo, ref: $ref}) WHERE f.layer IS NOT NULL
            OPTIONAL MATCH (f)-[:HAS_VIOLATION]->(v:Violation)
            RETURN f.layer AS layer, count(DISTINCT f) AS files, count(DISTINCT v) AS violations
            ORDER BY layer
        """, **base)
        depends_on = s.read("""
            MATCH (:Service {tenant: $tenant, name: $repo})-[d:DEPENDS_ON {ref: $ref}]->(b:Service)
            RETURN b.name AS service, d.packages AS packages, d.versions AS versions, d.ecosystems AS ecosystems
            ORDER BY service
        """, **base)
        depended_by = s.read("""
            MATCH (a:Service)-[d:DEPENDS_ON]->(:Service {tenant: $tenant, name: $repo})
            RETURN a.name AS service, d.packages AS packages, collect(DISTINCT d.ref) AS refs
            ORDER BY service
        """, **base)
        return {**base, **head, "symbol_kinds": {k["kind"]: k["n"] for k in kinds},
                "modules": modules, "entry_points": entry_points, "external_packages": packages,
                "roles": roles, "layers": layers, "depends_on": depends_on, "depended_by": _collapse_dependents(depended_by)}
