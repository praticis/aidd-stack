"""`atlas` MCP server — intent-level, read-only access to the code graph for the skills.

Design:
  * Every query is scoped to a tenant. Fixed mode (AIDD_TENANT=<name>): server-side, the caller never
    passes one. Multi-tenant mode (AIDD_TENANT=auto, workspace <ws>/<tenant>/<repo>): tools take an
    optional `tenant`; omitted → the only tenant in the graph, or an error listing them.
  * `ref` defaults to the repo's default branch; ephemeral (feature-branch) snapshots
    are searched only when a `ref` is named explicitly.
  * Results are compact JSON, sized for an LLM context (limits everywhere).
  * `cypher_readonly` runs inside a READ transaction — the server rejects writes — and
    additionally refuses obvious mutation keywords before sending anything. Tenant scoping of raw
    Cypher cannot be enforced (a query may simply not filter on `$tenant`): in multi-tenant mode it
    can read every tenant. Offered by default; `ATLAS_RAW_CYPHER=off` withdraws it in multi-tenant mode
    when the tenants must not see each other (e.g. several client organizations on one machine).
  * DNS-rebinding protection: only `Host` values in ATLAS_ALLOWED_HOSTS (default localhost,
    127.0.0.1, [::1] and the compose service name, any port) and browser `Origin`s on those hosts are
    accepted — a web page cannot reach the server through a rebinding domain.

Transport: streamable HTTP, stateless, JSON responses — `POST /mcp` works with a plain
curl `initialize` (install-check.sh) as well as with Claude Code / Cursor / Antigravity.
`GET /healthz` answers 200 when Neo4j is reachable.

Run: `aidd serve [--host 0.0.0.0] [--port 3000]`  (docker-compose service `mcp-atlas`).
"""

from __future__ import annotations

import os

from .. import INDEXER_VERSION
from ..core.config import Neo4jConfig
from . import tools_http, tools_impact, tools_misc, tools_status, tools_symbols
from .store import AtlasError, Store, _tenant, transport_security  # noqa: F401  imported from here by the CLI, tests and `knowledge`
from .tools_http import _collapse_refs  # noqa: F401
from .tools_symbols import _fulltext_query, _word_pattern  # noqa: F401


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
            "http_map / who_consumes for HTTP integrations between repositories, impact_of for the "
            "cross-repo blast radius of a symbol, ref_diff for what a branch adds to a repo's surface, "
            "and cypher_readonly for anything else (schema: neo4j/SCHEMA.md; filter on $tenant). If a repo or ref is "
            "not indexed the tool says so — fall back to reading the source tree. In multi-tenant mode "
            "(AIDD_TENANT=auto) every tool accepts `tenant` = the workspace folder right below WORKSPACE_PATH "
            "for the current repo; omit it when the graph holds a single tenant."
        ),
        host=os.getenv("ATLAS_MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("ATLAS_MCP_PORT", "3000")),
        stateless_http=True,
        json_response=True,
        transport_security=transport_security(),
    )

    def st(tenant: str | None = None) -> Store:
        return the_store.resolve_tenant(tenant)
    # ---- tools, in the order clients list them ------------------------------------------
    tools_status.register(mcp, st, the_store)
    tools_symbols.register(mcp, st)
    tools_http.register(mcp, st)
    tools_impact.register(mcp, st)
    tools_misc.register(mcp, st, the_store)

    # ---- plain HTTP health for docker/compose and install-check ---------------------------
    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        ok = the_store.ping()            # process-wide store: no tenant resolution here (auto → tenant null)
        return JSONResponse({"status": "ok" if ok else "degraded", "neo4j": ok, "tenant": the_store.tenant,
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
