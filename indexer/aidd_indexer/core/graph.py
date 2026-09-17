"""Neo4j writer — idempotent MERGE by id, snapshot bookkeeping, orphan GC.

Every micro node carries tenant/repo/ref/commit_sha/indexed_at (SCHEMA.md §1).
Re-indexing the same (repo, ref) updates nodes in place and finally deletes
micro nodes whose commit_sha is not the current one (§5).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from neo4j import GraphDatabase, Driver

from .. import INDEXER_VERSION
from . import ids
from .config import Neo4jConfig
from .paths import path_key
from .model import ExtractionResult
from .resolve import Resolved

BATCH = 1000


def _chunks(rows: list[dict[str, Any]], n: int = BATCH) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


class GraphWriter:
    def __init__(self, cfg: Neo4jConfig):
        self.cfg = cfg
        # Server notifications ("property key does not exist" on an empty graph, deprecations)
        # are noise for a CLI; failures still surface as exceptions.
        self.driver: Driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password),
                                                   notifications_min_severity="OFF")

    def close(self) -> None:
        self.driver.close()

    def verify(self) -> None:
        self.driver.verify_connectivity()
        with self.driver.session(database=self.cfg.database) as s:
            s.run("RETURN 1").consume()

    def _run(self, query: str, **params: Any) -> Any:
        with self.driver.session(database=self.cfg.database) as s:
            return s.execute_write(lambda tx: tx.run(query, **params).consume())

    def _run_autocommit(self, query: str, **params: Any) -> Any:
        """`CALL (...) {...} IN TRANSACTIONS` (Neo4j >= 5.23 syntax) only runs in auto-commit mode."""
        with self.driver.session(database=self.cfg.database) as s:
            return s.run(query, **params).consume()

    def _batched(self, query: str, rows: list[dict[str, Any]], **extra: Any) -> int:
        n = 0
        for chunk in _chunks(rows):
            self._run(query, rows=chunk, **extra)
            n += len(chunk)
        return n

    # ------------------------------------------------------------------------------
    def write(self, res: ExtractionResult, rv: Resolved, started: datetime, ephemeral: bool,
              area: str | None = None, trigger: str = "manual") -> dict[str, int]:
        repo = res.repo
        now = datetime.now(timezone.utc).isoformat()
        common = dict(tenant=repo.tenant, repo=repo.name, ref=repo.ref, sha=repo.commit_sha, now=now)
        counts: dict[str, int] = {}

        self._run("""
            MERGE (r:Repo {id: $id})
            SET r.tenant = $tenant, r.name = $repo, r.default_ref = $default_ref,
                r.stack = $stack, r.url = $url, r.indexed_at = datetime($now),
                r.area = coalesce($area, r.area)
        """, id=ids.repo(repo.tenant, repo.name), default_ref=repo.default_ref, stack=sorted(repo.stack), url=repo.url,
             area=area, **common)

        self._run("""
            MATCH (r:Repo {id: $repo_id})
            MERGE (s:Snapshot {id: $id})
            SET s.tenant = $tenant, s.repo = $repo, s.ref = $ref, s.commit_sha = $sha,
                s.indexed_at = datetime($now), s.indexer_version = $ver, s.ephemeral = $ephemeral
            MERGE (r)-[:HAS_SNAPSHOT]->(s)
        """, id=ids.snapshot(repo.tenant, repo.name, repo.ref), repo_id=ids.repo(repo.tenant, repo.name),
             ver=INDEXER_VERSION, ephemeral=ephemeral, **common)

        counts["modules"] = self._batched("""
            UNWIND $rows AS m
            MERGE (n:Module {id: m.id})
            SET n.tenant = $tenant, n.repo = $repo, n.ref = $ref, n.commit_sha = $sha, n.indexed_at = datetime($now),
                n.name = m.name, n.path = m.path, n.kind = m.kind, n.layer = m.layer, n.content_hash = m.kind + ':' + m.path
            WITH n
            MATCH (r:Repo {id: $repo_id})
            MERGE (r)-[:CONTAINS]->(n)
        """, [m.__dict__ for m in res.modules], repo_id=ids.repo(repo.tenant, repo.name), **common)

        counts["files"] = self._batched("""
            UNWIND $rows AS f
            MERGE (n:File {id: f.id})
            SET n.tenant = $tenant, n.repo = $repo, n.ref = $ref, n.commit_sha = $sha, n.indexed_at = datetime($now),
                n.path = f.path, n.language = f.language, n.loc = f.loc, n.layer = f.layer, n.content_hash = f.content_hash
            WITH n, f
            MATCH (m:Module {id: f.module_id})
            MERGE (m)-[:CONTAINS]->(n)
            WITH n
            MATCH (s:Snapshot {id: $snap_id})
            MERGE (n)-[:IN_SNAPSHOT]->(s)
        """, [f.__dict__ for f in res.files], snap_id=ids.snapshot(repo.tenant, repo.name, repo.ref), **common)

        counts["symbols"] = self._batched("""
            UNWIND $rows AS s
            MERGE (n:Symbol {id: s.id})
            SET n.tenant = $tenant, n.repo = $repo, n.ref = $ref, n.commit_sha = $sha, n.indexed_at = datetime($now),
                n.name = s.name, n.qualified_name = s.qualified_name, n.kind = s.kind, n.signature = s.signature,
                n.doc = s.doc, n.visibility = s.visibility, n.line_start = s.line_start, n.line_end = s.line_end,
                n.content_hash = s.content_hash, n.is_entry_point = s.is_entry_point
            WITH n, s
            MATCH (f:File {id: s.file_id})
            MERGE (f)-[:CONTAINS]->(n)
        """, [s.__dict__ for s in res.symbols], **common)

        members = [{"child": s.id, "parent": s.parent_id} for s in res.symbols if s.parent_id]
        counts["members"] = self._batched("""
            UNWIND $rows AS r
            MATCH (p:Symbol {id: r.parent}), (c:Symbol {id: r.child})
            MERGE (p)-[:CONTAINS]->(c)
        """, members)

        # Edges are rebuilt from scratch for this snapshot: drop, then recreate.
        self._run_autocommit("""
            MATCH (a:Symbol|File {tenant: $tenant, repo: $repo, ref: $ref})-[e:CALLS|IMPORTS]->()
            CALL (e) { DELETE e } IN TRANSACTIONS OF 5000 ROWS
        """, **common)

        counts["calls"] = self._batched("""
            UNWIND $rows AS c
            MATCH (a:Symbol|File {id: c.caller_id}), (b:Symbol {id: c.callee_id})
            MERGE (a)-[e:CALLS {line: c.line}]->(b)
            SET e.resolved = false, e.strategy = c.strategy
        """, [c.__dict__ for c in rv.calls])

        counts["packages"] = self._batched("""
            UNWIND $rows AS p
            MERGE (n:Package {id: p.id})
            SET n.tenant = $tenant, n.name = p.name, n.ecosystem = p.ecosystem, n.stdlib = p.stdlib,
                n.internal = coalesce(n.internal, false), n.last_seen = datetime($now)
            SET n.first_seen = coalesce(n.first_seen, datetime($now))
        """, [p.__dict__ for p in rv.packages.values()], **common)

        counts["imports"] = self._batched("""
            UNWIND $rows AS i
            MATCH (f:File {id: i.file_id}), (t:File|Module|Package {id: i.target_id})
            MERGE (f)-[e:IMPORTS {spec: i.spec}]->(t)
            SET e.line = i.line
        """, [i.__dict__ for i in rv.imports])

        # ---- integration candidates (SCHEMA.md §3/§7) -------------------------------------
        # Service is 1:1 with the repo in v0 (monorepos split it later).
        svc_id = ids.service(repo.tenant, repo.name)
        self._run("""
            MATCH (r:Repo {id: $repo_id})
            MERGE (s:Service {id: $id})
            SET s.tenant = $tenant, s.name = $repo, s.repo = $repo, s.last_seen = datetime($now)
            MERGE (r)-[:DEPLOYS]->(s)
        """, id=svc_id, repo_id=ids.repo(repo.tenant, repo.name), **common)

        counts["endpoints"] = self._batched("""
            UNWIND $rows AS e
            MERGE (n:HttpEndpoint {id: e.id})
            SET n.tenant = $tenant, n.service = $repo, n.method = e.method, n.path = e.path, n.path_key = e.path_key,
                n.framework = e.framework, n.last_seen = datetime($now)
            SET n.first_seen = coalesce(n.first_seen, datetime($now))
            WITH n, e
            MATCH (s:Service {id: $svc_id})
            MERGE (s)-[x:EXPOSES {ref: $ref}]->(n)
            SET x.commit_sha = $sha, x.evidence = e.evidence, x.line = e.line, x.raw_pattern = e.raw_pattern,
                x.confidence = 'exact', x.last_seen = datetime($now)
            WITH n, e
            OPTIONAL MATCH (h:Symbol {id: e.handler_id})
            FOREACH (_ IN CASE WHEN h IS NULL THEN [] ELSE [1] END |
              MERGE (n)-[hb:HANDLED_BY {ref: $ref}]->(h)
              SET hb.commit_sha = $sha, hb.evidence = e.evidence, hb.confidence = 'exact')
        """, [e.__dict__ | {"path_key": path_key(e.path)} for e in res.endpoints], svc_id=svc_id, **common)

        counts["http_calls"] = self._batched("""
            UNWIND $rows AS c
            MERGE (n:HttpCall {id: c.id})
            SET n.tenant = $tenant, n.repo = $repo, n.ref = $ref, n.commit_sha = $sha, n.indexed_at = datetime($now),
                n.method = c.method, n.path = c.path, n.path_key = c.path_key, n.raw_path = c.raw_path, n.via = c.via,
                n.target_hint = c.target_hint, n.env_hints = c.env_hints, n.line = c.line, n.evidence = c.evidence,
                n.content_hash = c.method + ' ' + c.path + '@' + c.evidence
            WITH n, c
            MATCH (caller:Symbol|File {id: c.caller_id})
            MERGE (caller)-[:MAKES_HTTP_CALL]->(n)
            WITH n, c
            MATCH (f:File {id: c.file_id})
            MERGE (f)-[:CONTAINS]->(n)
        """, [c.__dict__ | {"path_key": path_key(c.path)} for c in res.http_calls], **common)

        # ---- convention violations (conventions/) — micro, GC'd like Symbol -------------------
        counts["violations"] = self._batched("""
            UNWIND $rows AS v
            MERGE (n:Violation {id: v.id})
            SET n.tenant = $tenant, n.repo = $repo, n.ref = $ref, n.commit_sha = $sha, n.indexed_at = datetime($now),
                n.convention = v.convention, n.rule = v.rule, n.severity = v.severity, n.message = v.message,
                n.line = v.line, n.evidence = v.evidence, n.content_hash = v.rule + '@' + v.evidence
            WITH n, v
            MATCH (f:File {id: v.file_id})
            MERGE (f)-[:HAS_VIOLATION]->(n)
            WITH n, v
            OPTIONAL MATCH (s:Symbol {id: v.symbol_id})
            FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END | MERGE (s)-[:HAS_VIOLATION]->(n))
        """, [v.__dict__ for v in res.violations], **common)

        # EXPOSES / HANDLED_BY edges of this ref that were not refreshed at this commit are stale
        # (route removed or moved); endpoints left without any exposer and consumer are dropped.
        self._run("""
            MATCH (:Service {id: $svc_id})-[x:EXPOSES {ref: $ref}]->(e:HttpEndpoint)
            WHERE x.commit_sha <> $sha
            DELETE x
            WITH e
            OPTIONAL MATCH (e)-[hb:HANDLED_BY {ref: $ref}]->()
            DELETE hb
        """, svc_id=svc_id, **common)
        self._run("""
            MATCH (e:HttpEndpoint {tenant: $tenant, service: $repo})
            WHERE NOT (e)<-[:EXPOSES]-() AND NOT (e)<-[:CONSUMES]-()
            DETACH DELETE e
        """, **common)

        # Orphan GC: micro nodes of this (tenant, repo, ref) not seen at this commit.
        rec = self._run_autocommit("""
            MATCH (n:File|Symbol|Module|HttpCall|Violation {tenant: $tenant, repo: $repo, ref: $ref})
            WHERE n.commit_sha <> $sha
            CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 1000 ROWS
        """, **common)
        counts["orphans_deleted"] = rec.counters.nodes_deleted if rec else 0

        finished = datetime.now(timezone.utc)
        self._run("""
            MATCH (s:Snapshot {id: $snap_id})
            MERGE (r:IndexRun {id: $id})
            SET r.tenant = $tenant, r.repo = $repo, r.ref = $ref, r.commit_sha = $sha,
                r.started_at = datetime($started), r.finished_at = datetime($finished),
                r.status = 'ok', r.counts = $counts_json, r.errors = $errors, r.indexer_version = $ver,
                r.trigger = $trigger
            MERGE (s)-[:HAS_RUN]->(r)
        """, id=ids.index_run(repo.tenant, repo.name, repo.ref, started.isoformat()), trigger=trigger,
             snap_id=ids.snapshot(repo.tenant, repo.name, repo.ref), started=started.isoformat(),
             finished=finished.isoformat(), counts_json=json.dumps(counts), errors=res.warnings[:50],
             ver=INDEXER_VERSION, **common)
        return counts

    # ------------------------------------------------------------------------------
    def snapshot_shas(self, tenant: str) -> dict[tuple[str, str], str]:
        """(repo, ref) -> commit_sha currently in the graph — the input of `plan`/`refresh`.
        A snapshot written by an older indexer reports an empty sha, so the next refresh
        re-indexes it (new extractors → new nodes, e.g. HttpEndpoint/HttpCall in 0.2.0)."""
        with self.driver.session(database=self.cfg.database) as s:
            rows = s.run("MATCH (n:Snapshot {tenant: $tenant}) RETURN n.repo AS repo, n.ref AS ref, n.commit_sha AS sha, n.indexer_version AS ver", tenant=tenant)
            return {(r["repo"], r["ref"]): (r["sha"] if r["ver"] == INDEXER_VERSION else "") for r in rows}

    def gc_ephemeral(self, tenant: str, older_than_days: int, keep: set[tuple[str, str]]) -> int:
        """Drop ephemeral snapshots that the current plan no longer lists and that were not
        refreshed in `older_than_days`. Returns number of snapshots removed."""
        with self.driver.session(database=self.cfg.database) as s:
            rows = s.run("""
                MATCH (n:Snapshot {tenant: $tenant, ephemeral: true})
                WHERE n.indexed_at < datetime() - duration({days: $days})
                RETURN n.repo AS repo, n.ref AS ref
            """, tenant=tenant, days=older_than_days)
            victims = [(r["repo"], r["ref"]) for r in rows if (r["repo"], r["ref"]) not in keep]
        for repo, ref in victims:
            self.wipe(tenant, repo, ref)
        return len(victims)

    def record_failure(self, tenant: str, repo: str, ref: str, sha: str, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._run("""
            MERGE (r:IndexRun {id: $id})
            SET r.tenant = $tenant, r.repo = $repo, r.ref = $ref, r.commit_sha = $sha,
                r.started_at = datetime($now), r.finished_at = datetime($now),
                r.status = 'failed', r.errors = [$error], r.indexer_version = $ver
        """, id=ids.index_run(tenant, repo, ref, now), tenant=tenant, repo=repo, ref=ref, sha=sha,
             now=now, error=error[:2000], ver=INDEXER_VERSION)

    def status(self, tenant: str | None) -> list[dict[str, Any]]:
        q = """
            MATCH (s:Snapshot)
            WHERE $tenant IS NULL OR s.tenant = $tenant
            OPTIONAL MATCH (s)-[:HAS_RUN]->(r:IndexRun)
            WITH s, r ORDER BY r.finished_at DESC
            WITH s, collect(r)[0] AS last
            OPTIONAL MATCH (f:File)-[:IN_SNAPSHOT]->(s)
            RETURN s.tenant AS tenant, s.repo AS repo, s.ref AS ref, left(s.commit_sha, 10) AS sha,
                   toString(s.indexed_at) AS indexed_at, count(f) AS files, last.counts AS counts,
                   last.status AS status, s.ephemeral AS ephemeral, last.trigger AS trigger,
                   duration.between(s.indexed_at, datetime()).minutes AS age_min
            ORDER BY tenant, repo, ref
        """
        with self.driver.session(database=self.cfg.database) as s:
            return [dict(r) for r in s.run(q, tenant=tenant)]

    def wipe(self, tenant: str, repo: str, ref: str | None) -> int:
        q = """
            MATCH (n:File|Symbol|Module|Snapshot|IndexRun|HttpCall|Violation {tenant: $tenant, repo: $repo})
            WHERE $ref IS NULL OR n.ref = $ref
            CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 1000 ROWS
        """
        rec = self._run_autocommit(q, tenant=tenant, repo=repo, ref=ref)
        n = rec.counters.nodes_deleted if rec else 0
        # macro side: this ref no longer exposes anything; drop endpoints nobody references
        self._run("""
            MATCH (:Service {tenant: $tenant, name: $repo})-[x:EXPOSES]->(e:HttpEndpoint)
            WHERE $ref IS NULL OR x.ref = $ref
            DELETE x
            WITH e
            OPTIONAL MATCH (e)-[hb:HANDLED_BY]->() WHERE $ref IS NULL OR hb.ref = $ref
            DELETE hb
        """, tenant=tenant, repo=repo, ref=ref)
        self._run("""
            MATCH (e:HttpEndpoint {tenant: $tenant, service: $repo})
            WHERE NOT (e)<-[:EXPOSES]-() AND NOT (e)<-[:CONSUMES]-()
            DETACH DELETE e
        """, tenant=tenant, repo=repo)
        if ref is None:
            self._run("MATCH (s:Service {tenant: $tenant, name: $repo}) WHERE NOT (s)-[:EXPOSES|CONSUMES]->() DETACH DELETE s", tenant=tenant, repo=repo)
        return n
