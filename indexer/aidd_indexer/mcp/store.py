"""The read-only Neo4j accessor of the `atlas` MCP server, its tenant resolution and its transport security."""

from __future__ import annotations

import os
import re
from typing import Any

from neo4j import GraphDatabase

from ..core.build import indexer_build
from ..core.config import ConfigError, Neo4jConfig

MAX_ROWS = 200
NO_REFRESH = {"stale": None, "note": "no automatic refresh recorded for this tenant yet (indexed on demand, or the "
                                     "refresher is not running — `aidd schedule status`)"}
FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL\s+\{|LOAD\s+CSV|FOREACH|"
    r"apoc\.(create|merge|refactor|periodic|load|export|import|trigger|cypher\.)|"
    r"db\.(create|drop|index\.fulltext\.(create|drop))|dbms\.)",
    re.IGNORECASE,
)
LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')


class AtlasError(RuntimeError):
    """Raised for user-facing errors (unknown repo/ref, refused query). Surfaces as a tool error."""


def _off(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("0", "off", "false", "no")


def transport_security(service: str = "mcp-atlas", env: str = "ATLAS_ALLOWED_HOSTS"):
    """Host/Origin allowlist (DNS-rebinding protection): localhost, plus the service's compose name."""
    from mcp.server.transport_security import TransportSecuritySettings
    hosts = [h.strip() for h in os.getenv(env, "").split(",") if h.strip()] or \
        ["localhost", "127.0.0.1", "[::1]", service]
    with_port = [h if ":" in h.replace("[::1]", "") else f"{h}:*" for h in hosts]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(set(hosts + with_port)),
        allowed_origins=sorted({f"{scheme}://{h}" for h in with_port for scheme in ("http", "https")}),
    )


def _tenant() -> str | None:
    """Fixed tenant from AIDD_TENANT, or None for multi-tenant mode (`AIDD_TENANT=auto`: the
    workspace is laid out as <workspace>/<tenant>/<repo> and the graph may hold several tenants;
    tools then take an optional `tenant` argument, resolved by the skill from the repo path)."""
    t = os.getenv("AIDD_TENANT", "").strip()
    if not t:
        raise ConfigError("AIDD_TENANT must be set (a tenant name, or 'auto' for multi-tenant mode)")
    return None if t == "auto" else t


class Store:
    """Thin read-only Neo4j accessor. One driver per server process; `scoped(tenant)` returns a
    view bound to one tenant (every query is parameterized with `$tenant`)."""

    def __init__(self, cfg: Neo4jConfig, tenant: str | None, driver=None):
        self.cfg = cfg
        self.tenant = tenant                     # None = multi-tenant mode, resolve per call
        self.driver = driver or GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password), notifications_min_severity="OFF")

    def close(self) -> None:
        self.driver.close()

    def scoped(self, tenant: str) -> "Store":
        view = Store.__new__(Store)
        view.cfg, view.tenant, view.driver = self.cfg, tenant, self.driver
        return view

    def read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        if self.tenant is not None:
            params.setdefault("tenant", self.tenant)
        with self.driver.session(database=self.cfg.database, default_access_mode="READ") as s:
            return s.execute_read(lambda tx: [r.data() for r in tx.run(query, **params)])

    def tenants(self) -> list[str]:
        return [r["t"] for r in self.read("MATCH (r:Repo) RETURN DISTINCT r.tenant AS t ORDER BY t")]

    def resolve_tenant(self, tenant: str | None) -> "Store":
        """Fixed mode: the server's tenant wins (a different explicit one is an error, not silently
        ignored). Multi-tenant mode: the argument, or the only tenant in the graph, or an error listing them."""
        if self.tenant is not None:
            if tenant and tenant != self.tenant:
                raise AtlasError(f"this atlas serves tenant '{self.tenant}' only (AIDD_TENANT); got '{tenant}'")
            return self
        if tenant:
            known = self.tenants()
            if tenant not in known:
                raise AtlasError(f"tenant '{tenant}' is not in atlas. Indexed tenants: {', '.join(known) or '(none)'}")
            return self.scoped(tenant)
        known = self.tenants()
        if len(known) == 1:
            return self.scoped(known[0])
        raise AtlasError("multi-tenant atlas (AIDD_TENANT=auto): pass `tenant` — the workspace folder right below "
                         f"WORKSPACE_PATH for this repo. Indexed tenants: {', '.join(known) or '(none)'}")

    def refresh_state(self) -> dict[str, Any] | None:
        """Last refresh of this tenant (written by every `aidd refresh`, even when nothing changed).
        `stale`: no refresh within 2 intervals — the graph may lag behind the remotes."""
        rows = self.read("""
            MATCH (h:RefreshState {tenant: $tenant})
            RETURN toString(h.last_finished_at) AS last_finished_at, h.last_rc AS last_rc, h.trigger AS trigger,
                   h.interval_min AS interval_min, h.changed AS changed,
                   duration.inSeconds(h.last_finished_at, datetime()).seconds / 60 AS age_min
        """)
        if not rows:
            return None
        r = rows[0]
        r["stale"] = r["age_min"] is not None and r["age_min"] > 2 * int(r["interval_min"] or 15)
        return r

    def ping(self) -> bool:
        try:
            self.read("RETURN 1 AS ok")
            return True
        except Exception:  # noqa: BLE001
            return False

    # -- helpers -------------------------------------------------------------------------
    def repos(self) -> list[dict[str, Any]]:
        """Repos and their snapshots; `outdated: true` on a snapshot an older indexer build wrote — the graph
        lacks what the running indexer would add (wait for the refresh, or run it), not a limit of atlas."""
        rows = self.read("""
            MATCH (r:Repo {tenant: $tenant})
            OPTIONAL MATCH (r)-[:HAS_SNAPSHOT]->(s:Snapshot)
            RETURN r.name AS repo, r.default_ref AS default_ref, r.stack AS stack, r.area AS area,
                   CASE WHEN r.sync_checked_at IS NULL THEN null ELSE {
                       ok: r.sync_note IS NULL, note: r.sync_note,
                       last_success_at: toString(r.remote_synced_at),
                       success_age_min: duration.inSeconds(r.remote_synced_at, datetime()).seconds / 60
                   } END AS remote,
                   collect({ref: s.ref, sha: left(s.commit_sha, 10), ephemeral: s.ephemeral,
                            indexed_at: toString(s.indexed_at), build: s.indexer_build,
                            age_min: duration.inSeconds(s.indexed_at, datetime()).seconds / 60}) AS snapshots
            ORDER BY repo
        """)
        build = indexer_build()
        for r in rows:
            for snap in r.get("snapshots") or []:
                if snap.get("ref") is not None:
                    snap["outdated"] = snap.pop("build", None) != build
        return rows

    def resolve_ref(self, repo: str, ref: str | None) -> str:
        rows = self.read("""
            MATCH (r:Repo {tenant: $tenant, name: $repo})
            OPTIONAL MATCH (r)-[:HAS_SNAPSHOT]->(s:Snapshot)
            RETURN r.default_ref AS default_ref, collect(s.ref) AS refs
        """, repo=repo)
        if not rows:
            known = [r["repo"] for r in self.repos()]
            raise AtlasError(f"repo '{repo}' is not in atlas. Indexed repos: {', '.join(known) or '(none)'}")
        default_ref, refs = rows[0]["default_ref"], rows[0]["refs"]
        chosen = ref or default_ref
        if chosen not in refs:
            raise AtlasError(f"ref '{chosen}' of '{repo}' is not indexed. Available: {', '.join(sorted(refs))}")
        return chosen
