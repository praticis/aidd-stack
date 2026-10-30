"""Neo4j writer — idempotent MERGE by id, snapshot bookkeeping, orphan GC.

Every micro node carries tenant/repo/ref/commit_sha/indexed_at (SCHEMA.md §1).
Re-indexing the same (repo, ref) updates nodes in place and finally deletes
micro nodes whose commit_sha is not the current one (§5).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .. import INDEXER_VERSION
from .build import indexer_build
from . import ids
from .graph_links import TenantLinks
from .graph_snapshots import Snapshots
from .paths import path_key
from .model import ExtractionResult
from .resolve import Resolved


class GraphWriter(TenantLinks, Snapshots):
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
                s.indexed_at = datetime($now), s.indexer_version = $ver, s.indexer_build = $build, s.ephemeral = $ephemeral,
                s.provides = $provides, s.requires = $requires,
                s.conventions = $conventions, s.architecture = $architecture
            MERGE (r)-[:HAS_SNAPSHOT]->(s)
        """, id=ids.snapshot(repo.tenant, repo.name, repo.ref), repo_id=ids.repo(repo.tenant, repo.name),
             ver=INDEXER_VERSION, build=indexer_build(), ephemeral=ephemeral, conventions=res.conventions, architecture=res.architecture,
             provides=sorted({p.key() for p in res.provides}),
             requires=sorted({f"{d.key()}@{d.version}" for d in res.requires}), **common)
        counts["provides"], counts["requires"] = len(res.provides), len(res.requires)

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
                n.content_hash = s.content_hash, n.is_entry_point = s.is_entry_point, n.role = s.role
            WITH n, s
            MATCH (f:File {id: s.file_id})
            MERGE (f)-[:CONTAINS]->(n)
            SET n.path = f.path
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

        # the resolver gives one row per edge, and the snapshot's edges are gone: a MERGE would key on a null `method`
        counts["calls"] = self._batched("""
            UNWIND $rows AS c
            MATCH (a:Symbol|File {id: c.caller_id}), (b:Symbol {id: c.callee_id})
            CREATE (a)-[:CALLS {line: c.line, resolved: false, strategy: c.strategy, method: c.method}]->(b)
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

        # Endpoint ids are keyed by `path_key` since 0.2.8, and by the app in a repo whose routes span modules
        # since 0.2.15; a node written by an older indexer would survive on EXPOSES edges of refs not reindexed
        # in this run (ephemeral branches waiting for their GC) and the linker would link calls to both. Drop
        # them: a node without `app` predates 0.2.15.
        self._run("""
            MATCH (e:HttpEndpoint {tenant: $tenant, service: $repo})
            WHERE e.app IS NULL OR e.id <> $tenant + '/svc/' + $repo + CASE WHEN e.app = '' THEN '' ELSE '/app/' + e.app END
                                           + '/http/' + e.method + ' ' + coalesce(e.path_key, e.path)
            DETACH DELETE e
        """, **common)

        counts["endpoints"] = self._batched("""
            UNWIND $rows AS e
            MERGE (n:HttpEndpoint {id: e.id})
            SET n.tenant = $tenant, n.service = $repo, n.method = e.method, n.path = e.path, n.path_key = e.path_key,
                n.framework = e.framework, n.app = e.app, n.last_seen = datetime($now)
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
              SET hb.commit_sha = $sha, hb.evidence = e.evidence, hb.confidence = 'exact', hb.last_seen = datetime($now))
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
        # "Refreshed" = touched by *this* run (`last_seen`), not "same commit": a reindex of the same sha
        # (indexer upgrade) must also drop what the new extractor no longer sees.
        self._run("""
            MATCH (:Service {id: $svc_id})-[x:EXPOSES {ref: $ref}]->(e:HttpEndpoint)
            WHERE x.last_seen IS NULL OR x.last_seen <> datetime($now)
            DELETE x
        """, svc_id=svc_id, **common)
        self._run("""
            MATCH (e:HttpEndpoint {tenant: $tenant, service: $repo})-[hb:HANDLED_BY {ref: $ref}]->()
            WHERE hb.last_seen IS NULL OR hb.last_seen <> datetime($now)
            DELETE hb
        """, **common)
        self._run("""
            MATCH (e:HttpEndpoint {tenant: $tenant, service: $repo})
            WHERE NOT (e)<-[:EXPOSES]-() AND NOT (e)<-[:CONSUMES]-()
            DETACH DELETE e
        """, **common)

        # Orphan GC: micro nodes of this (tenant, repo, ref) not written by this run (same rule as above:
        # a commit can be reindexed by a newer extractor and lose nodes).
        rec = self._run_autocommit("""
            MATCH (n:File|Symbol|Module|HttpCall|Violation {tenant: $tenant, repo: $repo, ref: $ref})
            WHERE n.indexed_at IS NULL OR n.indexed_at <> datetime($now)
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
