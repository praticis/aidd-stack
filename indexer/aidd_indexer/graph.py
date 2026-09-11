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

from . import INDEXER_VERSION, ids
from .config import Neo4jConfig
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
              area: str | None = None) -> dict[str, int]:
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
                n.name = m.name, n.path = m.path, n.kind = m.kind, n.content_hash = m.kind + ':' + m.path
            WITH n
            MATCH (r:Repo {id: $repo_id})
            MERGE (r)-[:CONTAINS]->(n)
        """, [m.__dict__ for m in res.modules], repo_id=ids.repo(repo.tenant, repo.name), **common)

        counts["files"] = self._batched("""
            UNWIND $rows AS f
            MERGE (n:File {id: f.id})
            SET n.tenant = $tenant, n.repo = $repo, n.ref = $ref, n.commit_sha = $sha, n.indexed_at = datetime($now),
                n.path = f.path, n.language = f.language, n.loc = f.loc, n.content_hash = f.content_hash
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

        # Orphan GC: micro nodes of this (tenant, repo, ref) not seen at this commit.
        rec = self._run_autocommit("""
            MATCH (n:File|Symbol|Module {tenant: $tenant, repo: $repo, ref: $ref})
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
                r.status = 'ok', r.counts = $counts_json, r.errors = $errors, r.indexer_version = $ver
            MERGE (s)-[:HAS_RUN]->(r)
        """, id=ids.index_run(repo.tenant, repo.name, repo.ref, started.isoformat()),
             snap_id=ids.snapshot(repo.tenant, repo.name, repo.ref), started=started.isoformat(),
             finished=finished.isoformat(), counts_json=json.dumps(counts), errors=res.warnings[:50],
             ver=INDEXER_VERSION, **common)
        return counts

    # ------------------------------------------------------------------------------
    def snapshot_shas(self, tenant: str) -> dict[tuple[str, str], str]:
        """(repo, ref) -> commit_sha currently in the graph — the input of `plan`/`refresh`."""
        with self.driver.session(database=self.cfg.database) as s:
            rows = s.run("MATCH (n:Snapshot {tenant: $tenant}) RETURN n.repo AS repo, n.ref AS ref, n.commit_sha AS sha", tenant=tenant)
            return {(r["repo"], r["ref"]): r["sha"] for r in rows}

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
                   last.status AS status, s.ephemeral AS ephemeral
            ORDER BY tenant, repo, ref
        """
        with self.driver.session(database=self.cfg.database) as s:
            return [dict(r) for r in s.run(q, tenant=tenant)]

    def wipe(self, tenant: str, repo: str, ref: str | None) -> int:
        q = """
            MATCH (n:File|Symbol|Module|Snapshot|IndexRun {tenant: $tenant, repo: $repo})
            WHERE $ref IS NULL OR n.ref = $ref
            CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 1000 ROWS
        """
        rec = self._run_autocommit(q, tenant=tenant, repo=repo, ref=ref)
        return rec.counters.nodes_deleted if rec else 0
