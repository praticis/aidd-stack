"""A session on the atlas database, shared by the writer, the linker and the snapshots' bookkeeping: a query in a
write transaction, in auto-commit or in batches, and a read."""

from __future__ import annotations

from typing import Any, Iterable

from neo4j import GraphDatabase, Driver

from .config import Neo4jConfig

BATCH = 1000


def _chunks(rows: list[dict[str, Any]], n: int = BATCH) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


class GraphSession:
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

    def _rows(self, cypher: str, **params) -> list[dict]:
        with self.driver.session(database=self.cfg.database) as s:
            return [dict(r) for r in s.run(cypher, **params)]
