"""`violations` and `cypher_readonly`: a convention's findings, and raw read-only Cypher."""

from __future__ import annotations

from typing import Any

from .store import FORBIDDEN, MAX_ROWS, AtlasError, Store, _off


def register(mcp, st, the_store: Store) -> None:
    @mcp.tool()
    def violations(repo: str, ref: str | None = None, severity: str | None = None, rule: str | None = None,
                   layer: str | None = None, limit: int = 100, tenant: str | None = None) -> dict[str, Any]:
        """Convention violations recorded for a repository at a ref (default: its default branch):
        which rule, where (file:line, symbol), severity and message — e.g. a domain file importing an
        adapter, a route declared outside the inbound layer. `checked` says whether any convention
        applied to this snapshot (`conventions`): when false, nothing was checked and an empty list
        says nothing about the code — conventions are configured in `atlas.yaml: conventions`.
        Filter by `severity` (error|warning|info), `rule` id or the `layer` of the offending file;
        `summary` counts per rule regardless of `limit`."""
        s = st(tenant)
        ref = s.resolve_ref(repo, ref)
        base = dict(repo=repo, ref=ref, severity=severity, rule=rule, layer=layer)
        where = ("WHERE ($severity IS NULL OR v.severity = $severity) AND ($rule IS NULL OR v.rule = $rule) "
                 "AND ($layer IS NULL OR f.layer = $layer)")
        rows = s.read(f"""
            MATCH (f:File {{tenant: $tenant, repo: $repo, ref: $ref}})-[:HAS_VIOLATION]->(v:Violation)
            {where}
            OPTIONAL MATCH (sy:Symbol)-[:HAS_VIOLATION]->(v)
            RETURN v.convention AS convention, v.rule AS rule, v.severity AS severity, v.message AS message,
                   f.path AS file, f.layer AS layer, v.line AS line, sy.qualified_name AS symbol, v.evidence AS evidence
            ORDER BY CASE v.severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, f.path, v.line
            LIMIT $limit
        """, limit=limit, **base)
        summary = s.read(f"""
            MATCH (f:File {{tenant: $tenant, repo: $repo, ref: $ref}})-[:HAS_VIOLATION]->(v:Violation)
            {where}
            RETURN v.convention AS convention, v.rule AS rule, v.severity AS severity, count(*) AS n
            ORDER BY n DESC
        """, **base)
        applied = s.read("MATCH (sn:Snapshot {tenant: $tenant, repo: $repo, ref: $ref}) RETURN sn.conventions AS c",
                         repo=repo, ref=ref)
        conventions = (applied[0]["c"] if applied else None) or []
        out = {"repo": repo, "ref": ref, "checked": bool(conventions), "conventions": conventions,
               "total": sum(r["n"] for r in summary), "summary": summary, "violations": rows}
        if not conventions:
            out["note"] = ("no convention applies to this repo, so nothing was checked — zero violations does not "
                           "mean the code follows its architecture (configure one in atlas.yaml: conventions)")
        return out

    raw_cypher = the_store.tenant is not None or not _off("ATLAS_RAW_CYPHER")

    @(mcp.tool() if raw_cypher else (lambda f: f))
    def cypher_readonly(query: str, params: dict[str, Any] | None = None, tenant: str | None = None) -> dict[str, Any]:
        """Run a read-only Cypher query against atlas, for what the other tools do not answer.
        `$tenant` is always bound — filter on it: MATCH (s:Symbol {tenant: $tenant, repo: 'x'}) ...
        Writes are refused. At most 200 rows are returned; add LIMIT yourself for big scans.

        Schema (micro nodes carry tenant, repo, ref, commit_sha):
          (:Repo {name, default_ref, stack})-[:HAS_SNAPSHOT]->(:Snapshot {ref, commit_sha, indexed_at,
              ephemeral, architecture, conventions})          default branches: ephemeral = false
          (:Module {name, path, kind, layer})-[:CONTAINS]->(:File {path, language, loc, layer})
              -[:CONTAINS]->(:Symbol)
          (:Symbol {name, qualified_name, kind, signature, doc, visibility, path, line_start, line_end,
              is_entry_point, role})  kind: function|method|struct|interface|class|enum|type|const|var|field
          (:Symbol)-[:CONTAINS]->(:Symbol)                       members
          (:Symbol|File)-[:CALLS {line, strategy, method}]->(:Symbol)    same repo and ref only
          (:File)-[:IMPORTS {spec, line}]->(:File|Module|Package {name, ecosystem, internal})
          (:File|Symbol)-[:HAS_VIOLATION]->(:Violation {convention, rule, severity, message, line})
          (:Symbol|File)-[:MAKES_HTTP_CALL]->(:HttpCall {method, path, path_key, raw_path, line})
          (:Repo)-[:DEPLOYS]->(:Service {name})-[:EXPOSES {ref}]->(:HttpEndpoint {method, path, path_key, app})
          (:HttpEndpoint)-[:HANDLED_BY {ref}]->(:Symbol)
          (:Service)-[:CONSUMES {ref, confidence}]->(:HttpEndpoint)
          (:Service)-[:DEPENDS_ON {ref}]->(:Service)            internal packages (manifests)"""
        if FORBIDDEN.search(query):
            raise AtlasError("refused: only read-only Cypher is allowed through atlas (no CREATE/MERGE/SET/DELETE/CALL{}/apoc writers)")
        s = st(tenant)
        p = dict(params or {})
        p["tenant"] = s.tenant
        rows = s.read(query, **p)
        truncated = len(rows) > MAX_ROWS
        return {"rows": rows[:MAX_ROWS], "row_count": min(len(rows), MAX_ROWS), "truncated": truncated}
