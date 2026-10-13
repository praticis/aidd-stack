"""The `knowledge` MCP server: project knowledge and process policy for the skills.

Reached through mcp-gateway at http://localhost:3006/mcp. Writes only to the vault
(`<tenant>/knowledge/...`) and to the Qdrant collection of the tenant.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..mcp.server import transport_security
from .service import KnowledgeService
from .vault import KnowledgeError


def _fixed_tenant() -> str | None:
    t = os.getenv("AIDD_TENANT", "").strip()
    if not t:
        raise KnowledgeError("AIDD_TENANT must be set (a tenant name, or 'auto' for multi-tenant mode)")
    return None if t == "auto" else t


def default_service() -> KnowledgeService:
    from qdrant_client import QdrantClient
    from .vectors import FastEmbedder, Mirror
    vault = Path(os.getenv("AIDD_VAULT_DIR", "/vault"))
    if not vault.is_dir():
        raise KnowledgeError(f"vault not found at {vault} (OBSIDIAN_VAULT_PATH mounted at /vault)")
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"), api_key=os.getenv("QDRANT_API_KEY") or None,
                          timeout=15, https=False)
    return KnowledgeService(vault, Mirror(client, FastEmbedder()), _fixed_tenant())


def build_server(service: KnowledgeService | None = None):
    from mcp.server.fastmcp import FastMCP
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    svc = service or default_service()
    mcp = FastMCP(
        "knowledge",
        instructions=(
            "Project knowledge and process policy for the development stages (docs/knowledge-contract.md). "
            "At the start of a stage call policy_for(repo) for what the process requires (coverage, harness "
            "attempts, spec approval, when to ask for an ADR) and insights_for(repo, files/roles/symbols you will "
            "touch) for what went wrong before in that area: `rules` were approved by a person and must be "
            "followed, `context` items are observations to weigh. When a stage learns something non-obvious "
            "(a review rejection and why, the harness giving up, a PR comment, a scanner finding, a fix whose cause "
            "was not obvious) call record_insight with evidence — it decides whether it is new or a repeat. "
            "In multi-tenant mode (AIDD_TENANT=auto) pass `tenant` = the workspace folder right below "
            "WORKSPACE_PATH for the current repo."
        ),
        host=os.getenv("KNOWLEDGE_MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("KNOWLEDGE_MCP_PORT", "3000")),
        stateless_http=True,
        json_response=True,
        transport_security=transport_security("mcp-knowledge", "KNOWLEDGE_ALLOWED_HOSTS"),
    )

    @mcp.tool()
    def policy_for(repo: str, tenant: str | None = None) -> dict[str, Any]:
        """The effective process policy of a repository: `policy` (coverage.min / new_code_min,
        harness.max_attempts, review.spec_approval / adr_when, knowledge.*) and `origin` — the layer each
        value came from (built-in, defaults, tenant, area, repo override). Configured by people in
        ~/.aidd/policy.yaml; read it, never assume it."""
        return svc.policy_for(repo, tenant)

    @mcp.tool()
    def insights_for(repo: str, files: list[str] | None = None, roles: list[str] | None = None,
                     symbols: list[str] | None = None, topic: str | None = None,
                     tenant: str | None = None) -> dict[str, Any]:
        """What was learned about this repository (and tenant-wide insights that apply to it) — mistakes
        from reviews, scanners, incidents, decisions. Pass the `files` (paths), convention `roles` and
        qualified `symbols` you are about to touch to get the ones that bite there (plus general ones);
        none returns everything live. `rules` (status accepted/enforced) were approved by a person: follow
        them. `context` (observed/recurring) are observations: weigh them, do not treat them as rules.
        Each item has `what_to_do` and the `note` path in the vault."""
        return svc.insights_for(repo, tenant, files, roles, symbols, topic)

    @mcp.tool()
    def record_insight(repo: str, topic: str, summary: str, what_happened: str, what_to_do: str,
                       severity: str, evidence: list[dict[str, Any]], applies_to: dict[str, list[str]] | None = None,
                       scope: str = "repo", tenant: str | None = None) -> dict[str, Any]:
        """Record something non-obvious the process learned, so it does not happen again. The service
        decides whether it repeats an existing insight (then it counts one more occurrence and may become
        `recurring`) or is new (a note in the vault, status `observed`). Only a person makes it a rule.
          topic: architecture | review | quality | security | incident | decision | business (+ the
                 tenant's own, see policy_for → knowledge.topics)
          summary: ONE sentence — the problem and what to do instead (≤ 200 chars)
          what_happened: the concrete case (what, where, why it is a problem)
          what_to_do: the rule that avoids it, checkable when possible
          severity: low | medium | high | critical
          evidence: at least one {source, location?, link?, ref?, sha?, tool?, note?}; source is
                    pr-review | review | harness | sarif | sonar | incident | session | scan
          applies_to: {files: [globs], roles: [convention roles], symbols: [qualified names]} — where it bites
          scope: repo (default) or shared (holds for several repos of the tenant)
        Returns `result` (created | updated), the note path, status and occurrences."""
        return svc.record_insight(repo, topic, summary, what_happened, what_to_do, severity, evidence,
                                  applies_to, scope, tenant)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        vault_ok = os.access(svc.layout.root, os.W_OK)
        try:
            svc.mirror.client.get_collections()
            qdrant_ok = True
        except Exception:  # noqa: BLE001
            qdrant_ok = False
        ok = vault_ok and qdrant_ok
        return JSONResponse({"status": "ok" if ok else "degraded", "vault_writable": vault_ok, "qdrant": qdrant_ok},
                            status_code=200 if ok else 503)

    return mcp


def serve(host: str | None = None, port: int | None = None) -> int:
    if host:
        os.environ["KNOWLEDGE_MCP_HOST"] = host
    if port:
        os.environ["KNOWLEDGE_MCP_PORT"] = str(port)
    build_server().run(transport="streamable-http")
    return 0
