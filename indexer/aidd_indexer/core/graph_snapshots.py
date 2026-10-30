"""The snapshots' bookkeeping: which (repo, ref) the graph holds and at which sha, the runs that failed, the
refresher's heartbeat, the status, and dropping a snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .. import INDEXER_VERSION
from .build import indexer_build
from . import ids
from .graph_session import GraphSession


def current_sha(sha: str | None, build: str | None) -> str:
    """The snapshot's sha when the running indexer build wrote it, else "" (re-index it)."""
    return (sha or "") if build == indexer_build() else ""


class Snapshots(GraphSession):
    def snapshot_shas(self, tenant: str) -> dict[tuple[str, str], str]:
        """(repo, ref) -> commit_sha currently in the graph — the input of `plan`/`refresh`.
        A snapshot written by another indexer build (version, or the code that shapes the graph —
        core/build.py) reports an empty sha, so the next refresh re-indexes it."""
        with self.driver.session(database=self.cfg.database) as s:
            rows = s.run("MATCH (n:Snapshot {tenant: $tenant}) RETURN n.repo AS repo, n.ref AS ref, n.commit_sha AS sha, "
                         "n.indexer_build AS build", tenant=tenant)
            return {(r["repo"], r["ref"]): current_sha(r["sha"], r["build"]) for r in rows}

    def persistent_snapshots(self, tenant: str) -> set[tuple[str, str]]:
        """(repo, ref) of the snapshots that only a policy change or `aidd wipe` removes
        (`always` / `patterns` refs); ephemeral ones have their own GC."""
        rows = self._rows("""
            MATCH (s:Snapshot {tenant: $tenant}) WHERE coalesce(s.ephemeral, false) = false
            RETURN s.repo AS repo, s.ref AS ref
        """, tenant=tenant)
        return {(r["repo"], r["ref"]) for r in rows}

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

    def heartbeat(self, tenant: str, started: str, finished: str, rc: int, trigger: str,
                  interval_min: int, changed: int) -> None:
        """One `RefreshState` per tenant, rewritten by every refresh — even one that indexed nothing.
        Snapshot ages alone cannot tell "nothing changed" from "the refresher died"; this can
        (`atlas_status.refresh`, install-check)."""
        self._run("""
            MERGE (h:RefreshState {tenant: $tenant})
            SET h.last_started_at = datetime($started), h.last_finished_at = datetime($finished),
                h.last_rc = $rc, h.trigger = $trigger, h.interval_min = $interval, h.changed = $changed,
                h.indexer_version = $ver
        """, tenant=tenant, started=started, finished=finished, rc=rc, trigger=trigger, interval=interval_min,
             changed=changed, ver=INDEXER_VERSION)

    def record_remote_sync(self, tenant: str, results: dict[str, str]) -> None:
        """Whether each repo's last refresh reached its git remote ("ok" or the failure). When it did
        not, the snapshots follow the developer's own fetches and feature branches can lag behind —
        `atlas_status` says so per repo."""
        if not results:
            return
        self._run("""
            UNWIND $rows AS x
            MATCH (r:Repo {tenant: $tenant, name: x.repo})
            SET r.sync_checked_at = datetime(),
                r.sync_note = CASE WHEN x.result = 'ok' THEN null ELSE x.result END,
                r.remote_synced_at = CASE WHEN x.result = 'ok' THEN datetime() ELSE r.remote_synced_at END
        """, tenant=tenant, rows=[{"repo": k, "result": v} for k, v in results.items()])

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
                   duration.inSeconds(s.indexed_at, datetime()).seconds / 60 AS age_min
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
