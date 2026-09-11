"""`atlas` MCP server — intent-level, read-only access to the code graph for the skills.

Design (ROADMAP F0.6):
  * Every query is scoped to AIDD_TENANT; the caller never passes a tenant.
  * `ref` defaults to the repo's default branch; ephemeral (feature-branch) snapshots
    are searched only when a `ref` is named explicitly.
  * Results are compact JSON, sized for an LLM context (limits everywhere).
  * `cypher_readonly` runs inside a READ transaction — the server rejects writes — and
    additionally refuses obvious mutation keywords before sending anything.

Transport: streamable HTTP, stateless, JSON responses — `POST /mcp` works with a plain
curl `initialize` (install-check.sh) as well as with Claude Code / Cursor / Antigravity.
`GET /healthz` answers 200 when Neo4j is reachable.

Run: `aidd serve [--host 0.0.0.0] [--port 3000]`  (docker-compose service `mcp-atlas`).
"""

from __future__ import annotations

import os
import re
from typing import Any

from neo4j import GraphDatabase

from . import INDEXER_VERSION
from .config import ConfigError, Neo4jConfig

MAX_ROWS = 200
FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL\s+\{|LOAD\s+CSV|FOREACH|"
    r"apoc\.(create|merge|refactor|periodic|load|export|import|trigger|cypher\.run(Write|Many|Schema))|"
    r"db\.(create|drop|index\.fulltext\.(create|drop))|dbms\.)",
    re.IGNORECASE,
)
LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')


class AtlasError(RuntimeError):
    """Raised for user-facing errors (unknown repo/ref, refused query). Surfaces as a tool error."""


def _tenant() -> str:
    t = os.getenv("AIDD_TENANT", "").strip()
    if not t or t == "auto":
        raise ConfigError("AIDD_TENANT must be set to a concrete tenant for the atlas MCP (not 'auto')")
    return t


class Store:
    """Thin read-only Neo4j accessor. One instance per server process."""

    def __init__(self, cfg: Neo4jConfig, tenant: str):
        self.cfg = cfg
        self.tenant = tenant
        self.driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password), notifications_min_severity="OFF")

    def close(self) -> None:
        self.driver.close()

    def read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        params.setdefault("tenant", self.tenant)
        with self.driver.session(database=self.cfg.database, default_access_mode="READ") as s:
            return s.execute_read(lambda tx: [r.data() for r in tx.run(query, **params)])

    def ping(self) -> bool:
        try:
            self.read("RETURN 1 AS ok")
            return True
        except Exception:  # noqa: BLE001
            return False

    # -- helpers -------------------------------------------------------------------------
    def repos(self) -> list[dict[str, Any]]:
        return self.read("""
            MATCH (r:Repo {tenant: $tenant})
            OPTIONAL MATCH (r)-[:HAS_SNAPSHOT]->(s:Snapshot)
            RETURN r.name AS repo, r.default_ref AS default_ref, r.stack AS stack, r.area AS area,
                   collect({ref: s.ref, sha: left(s.commit_sha, 10), ephemeral: s.ephemeral,
                            indexed_at: toString(s.indexed_at),
                            age_min: duration.between(s.indexed_at, datetime()).minutes}) AS snapshots
            ORDER BY repo
        """)

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


def _fulltext_query(text: str) -> str:
    """Lucene query for `symbol_fulltext`: exact term OR prefix, special chars escaped."""
    terms = [LUCENE_SPECIAL.sub(r"\\\1", t) for t in text.split() if t]
    if not terms:
        raise AtlasError("empty query")
    parts = []
    for t in terms:
        parts.append(f"{t}")
        parts.append(f"{t}*")
    return " OR ".join(parts)


# ------------------------------------------------------------------------------------------
def build_server(store: Store | None = None):
    from mcp.server.fastmcp import FastMCP
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    # One driver for the process lifetime. (FastMCP's `lifespan` is entered per session — per
    # request in stateless mode — so it is the wrong place for a connection pool.)
    the_store = store or Store(Neo4jConfig.from_env(), _tenant())

    mcp = FastMCP(
        "atlas",
        instructions=(
            "Read-only access to the aidd code graph (micro level: repos, modules, files, symbols, "
            "calls, imports). Start with atlas_status to see what is indexed; use repo_map for an "
            "overview of one repository, find_symbol / who_calls / symbol_context to navigate code, "
            "and cypher_readonly for anything else (schema: neo4j/SCHEMA.md). If a repo or ref is "
            "not indexed the tool says so — fall back to reading the source tree."
        ),
        host=os.getenv("ATLAS_MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("ATLAS_MCP_PORT", "3000")),
        stateless_http=True,
        json_response=True,
    )

    def st() -> Store:
        return the_store

    # ---- tools ---------------------------------------------------------------------------
    @mcp.tool()
    def atlas_status() -> dict[str, Any]:
        """What atlas knows: indexed repositories, their refs (default branch + active feature
        branches), commit and freshness. Call first; a repo missing here means 'not indexed'."""
        s = st()
        return {"tenant": s.tenant, "indexer_version": INDEXER_VERSION, "repos": s.repos()}

    @mcp.tool()
    def repo_map(repo: str, ref: str | None = None, max_entry_points: int = 40) -> dict[str, Any]:
        """Overview of one repository at a ref (default: its default branch): stack, modules with
        file/symbol counts, entry points (HTTP handlers, controllers, commands) and the external
        packages it depends on. Use it before reading files — it tells where things live."""
        s = st()
        ref = s.resolve_ref(repo, ref)
        base = dict(repo=repo, ref=ref)
        head = s.read("""
            MATCH (r:Repo {tenant: $tenant, name: $repo})-[:HAS_SNAPSHOT]->(snap:Snapshot {ref: $ref})
            RETURN r.stack AS stack, r.area AS area, r.default_ref AS default_ref, r.url AS url,
                   left(snap.commit_sha, 10) AS sha, toString(snap.indexed_at) AS indexed_at, snap.ephemeral AS ephemeral
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
        return {**base, **head, "symbol_kinds": {k["kind"]: k["n"] for k in kinds},
                "modules": modules, "entry_points": entry_points, "external_packages": packages}

    @mcp.tool()
    def find_symbol(query: str, repo: str | None = None, ref: str | None = None,
                    kind: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search over symbol names, qualified names, signatures and docstrings
        (functions, methods, classes, structs, interfaces...), topped up with substring matches on
        the name ('Handler' finds 'Handler', 'HandlerFunc' and 'AuthHandler'). Without `ref`, only default branches are
        searched; name a `ref` to search a feature branch. `kind` filters e.g. function|method|class|struct|interface."""
        s = st()
        if repo:
            ref = s.resolve_ref(repo, ref)
        rows = s.read("""
            CALL db.index.fulltext.queryNodes('symbol_fulltext', $q) YIELD node AS sy, score
            WHERE sy.tenant = $tenant
              AND ($repo IS NULL OR sy.repo = $repo)
              AND ($kind IS NULL OR sy.kind = $kind)
            MATCH (snap:Snapshot {tenant: $tenant, repo: sy.repo, ref: sy.ref})
            WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
            MATCH (f:File)-[:CONTAINS]->(sy)
            RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                   sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line,
                   sy.signature AS signature, sy.is_entry_point AS entry_point, round(score, 2) AS score
            ORDER BY score DESC LIMIT $limit
        """, q=_fulltext_query(query), repo=repo, ref=ref, kind=kind, limit=min(limit, MAX_ROWS))
        # Lucene matches whole terms and prefixes ('Handler' → 'Handler', 'HandlerFunc'), not
        # suffixes ('AuthHandler'). Top up with a case-insensitive substring pass on the name.
        if len(rows) < limit and " " not in query.strip():
            seen = {r["id"] for r in rows}
            extra = s.read("""
                MATCH (sy:Symbol {tenant: $tenant})
                WHERE toLower(sy.name) CONTAINS toLower($text)
                  AND ($repo IS NULL OR sy.repo = $repo)
                  AND ($kind IS NULL OR sy.kind = $kind)
                MATCH (snap:Snapshot {tenant: $tenant, repo: sy.repo, ref: sy.ref})
                WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
                MATCH (f:File)-[:CONTAINS]->(sy)
                RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                       sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line,
                       sy.signature AS signature, sy.is_entry_point AS entry_point, 0.0 AS score
                ORDER BY size(sy.name), sy.name LIMIT $limit
            """, text=query.strip(), repo=repo, ref=ref, kind=kind, limit=min(limit, MAX_ROWS))
            rows += [r for r in extra if r["id"] not in seen][: limit - len(rows)]
        return rows

    def _symbol(s: Store, symbol: str, repo: str | None, ref: str | None) -> dict[str, Any]:
        """Resolve `symbol` (id, qualified_name or bare name) to exactly one Symbol node."""
        if repo:
            ref = s.resolve_ref(repo, ref)
        rows = s.read("""
            MATCH (sy:Symbol {tenant: $tenant})
            WHERE (sy.id = $symbol OR sy.qualified_name = $symbol OR sy.name = $symbol)
              AND ($repo IS NULL OR sy.repo = $repo)
            MATCH (snap:Snapshot {tenant: $tenant, repo: sy.repo, ref: sy.ref})
            WHERE ($ref IS NOT NULL AND sy.ref = $ref) OR ($ref IS NULL AND coalesce(snap.ephemeral, false) = false)
            MATCH (f:File)-[:CONTAINS]->(sy)
            RETURN sy.id AS id, sy.repo AS repo, sy.ref AS ref, sy.kind AS kind, sy.name AS name,
                   sy.qualified_name AS qualified_name, f.path AS file, sy.line_start AS line_start,
                   sy.line_end AS line_end, sy.signature AS signature, sy.doc AS doc,
                   sy.visibility AS visibility, sy.is_entry_point AS entry_point
            LIMIT 6
        """, symbol=symbol, repo=repo, ref=ref)
        if not rows:
            raise AtlasError(f"symbol '{symbol}' not found" + (f" in {repo}@{ref}" if repo else "") +
                             " — try find_symbol first, or name the repo/ref")
        if len(rows) > 1:
            opts = "; ".join(f"{r['id']}" for r in rows)
            raise AtlasError(f"'{symbol}' is ambiguous ({len(rows)} matches). Use one of the ids: {opts}")
        return rows[0]

    @mcp.tool()
    def who_calls(symbol: str, repo: str | None = None, ref: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Incoming calls: which symbols (and files) call `symbol`. `symbol` may be a symbol id from
        find_symbol, a qualified name (pkg.Type.Method) or a bare name when unambiguous. Calls are
        resolved by name within the repo (strategy on each edge) — treat cross-package hits as likely, not proven."""
        s = st()
        target = _symbol(s, symbol, repo, ref)
        callers = s.read("""
            MATCH (caller)-[c:CALLS]->(:Symbol {id: $id})
            OPTIONAL MATCH (f:File)-[:CONTAINS]->(caller)
            RETURN caller.id AS id, labels(caller)[0] AS type, coalesce(caller.qualified_name, caller.path) AS qualified_name,
                   caller.kind AS kind, coalesce(f.path, caller.path) AS file, c.line AS line, c.strategy AS strategy
            ORDER BY file, line LIMIT $limit
        """, id=target["id"], limit=min(limit, MAX_ROWS))
        return {"symbol": target, "callers": callers, "caller_count": len(callers)}

    @mcp.tool()
    def symbol_context(symbol: str, repo: str | None = None, ref: str | None = None, limit: int = 30) -> dict[str, Any]:
        """Everything the graph knows around one symbol: definition (file, lines, signature, doc),
        its container (class/struct) and members, what it calls, who calls it, and what its file
        imports. The right tool before editing a function or estimating impact."""
        s = st()
        sy = _symbol(s, symbol, repo, ref)
        base = dict(id=sy["id"], limit=min(limit, MAX_ROWS))
        parent = s.read("MATCH (p:Symbol)-[:CONTAINS]->(:Symbol {id: $id}) RETURN p.id AS id, p.kind AS kind, p.qualified_name AS qualified_name", **base)
        members = s.read("MATCH (:Symbol {id: $id})-[:CONTAINS]->(m:Symbol) RETURN m.id AS id, m.kind AS kind, m.name AS name, m.signature AS signature ORDER BY m.line_start LIMIT $limit", **base)
        callees = s.read("""
            MATCH (:Symbol {id: $id})-[c:CALLS]->(t:Symbol)
            MATCH (f:File)-[:CONTAINS]->(t)
            RETURN t.id AS id, t.kind AS kind, t.qualified_name AS qualified_name, f.path AS file, c.line AS line, c.strategy AS strategy
            ORDER BY line LIMIT $limit
        """, **base)
        callers = s.read("""
            MATCH (caller)-[c:CALLS]->(:Symbol {id: $id})
            OPTIONAL MATCH (f:File)-[:CONTAINS]->(caller)
            RETURN caller.id AS id, labels(caller)[0] AS type, coalesce(caller.qualified_name, caller.path) AS qualified_name,
                   coalesce(f.path, caller.path) AS file, c.line AS line, c.strategy AS strategy
            ORDER BY file, line LIMIT $limit
        """, **base)
        imports = s.read("""
            MATCH (f:File)-[:CONTAINS]->(:Symbol {id: $id})
            MATCH (f)-[i:IMPORTS]->(t)
            RETURN labels(t)[0] AS type, coalesce(t.name, t.path) AS target, i.spec AS spec
            ORDER BY type, target LIMIT $limit
        """, **base)
        return {"symbol": sy, "parent": parent[0] if parent else None, "members": members,
                "calls": callees, "called_by": callers, "file_imports": imports}

    @mcp.tool()
    def cypher_readonly(query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a read-only Cypher query against atlas (schema in neo4j/SCHEMA.md: Repo, Snapshot,
        Module, File, Symbol, Package; edges HAS_SNAPSHOT, CONTAINS, IN_SNAPSHOT, CALLS, IMPORTS).
        `$tenant` is always bound — filter on it: MATCH (s:Symbol {tenant: $tenant, repo: 'x'}) ...
        Writes are refused. At most 200 rows are returned; add LIMIT yourself for big scans."""
        if FORBIDDEN.search(query):
            raise AtlasError("refused: only read-only Cypher is allowed through atlas (no CREATE/MERGE/SET/DELETE/CALL{}/apoc writers)")
        s = st()
        p = dict(params or {})
        p["tenant"] = s.tenant
        rows = s.read(query, **p)
        truncated = len(rows) > MAX_ROWS
        return {"rows": rows[:MAX_ROWS], "row_count": min(len(rows), MAX_ROWS), "truncated": truncated}

    # ---- plain HTTP health for docker/compose and install-check ---------------------------
    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        s = st()
        ok = s.ping()
        return JSONResponse({"status": "ok" if ok else "degraded", "neo4j": ok, "tenant": s.tenant,
                             "version": INDEXER_VERSION}, status_code=200 if ok else 503)

    return mcp


def serve(host: str | None = None, port: int | None = None) -> int:
    if host:
        os.environ["ATLAS_MCP_HOST"] = host
    if port:
        os.environ["ATLAS_MCP_PORT"] = str(port)
    # fail fast on a broken contract instead of serving 500s
    Neo4jConfig.from_env()
    _tenant()
    mcp = build_server()
    mcp.run(transport="streamable-http")
    return 0
