"""The graph the writer leaves holds what a dry-run of the same checkout computes, field by field, with the records
counted by their keys in the graph: a call by its caller, callee, line and method, an import by its file, target and
spec, a type's base or a method's override by its two ends and the edge's kind. The corpus and the micro set compare dry-runs only, so a writer that drops a record or a field passes them; this
reads the graph back. Run by `scripts/mcp-it.sh`, which indexes the repositories under tests/mcp_it, writes one of them
again without a file and once more at the same commit, as the refresher does after an upgrade, and leaves a dry-run of
each snapshot in AIDD_IT_DRY; skipped without them."""

import json
import os
from collections import Counter
from pathlib import Path

import pytest

DRY = Path(os.getenv("AIDD_IT_DRY", "/nonexistent"))
pytestmark = pytest.mark.skipif(not (os.getenv("NEO4J_URI") and DRY.is_dir()),
                                reason="needs the Neo4j and the dry-runs that scripts/mcp-it.sh leaves")

AT = "{tenant: $tenant, repo: $repo, ref: $ref}"

# each section of a dry-run: the query that reads its records back, under the dry-run's own field names, and the
# record's key in the graph
SECTIONS = {
    "modules": (f"""
        MATCH (n:Module {AT})
        RETURN n.id AS id, n.name AS name, n.path AS path, n.kind AS kind, n.layer AS layer""", ("id",)),
    "files": (f"""
        MATCH (m:Module)-[:CONTAINS]->(n:File {AT})-[:IN_SNAPSHOT]->(:Snapshot {AT})
        RETURN n.id AS id, n.path AS path, n.language AS language, n.loc AS loc, n.content_hash AS content_hash,
               n.layer AS layer, m.id AS module_id""", ("id",)),
    "symbols": (f"""
        MATCH (f:File)-[:CONTAINS]->(n:Symbol {AT})
        OPTIONAL MATCH (p:Symbol)-[:CONTAINS]->(n)
        RETURN n.id AS id, f.id AS file_id, n.name AS name, n.qualified_name AS qualified_name, n.kind AS kind,
               n.signature AS signature, n.doc AS doc, n.visibility AS visibility, n.line_start AS line_start,
               n.line_end AS line_end, n.content_hash AS content_hash, n.is_entry_point AS is_entry_point,
               n.role AS role, p.id AS parent_id""", ("id",)),
    "calls": (f"""
        MATCH (a:Symbol|File {AT})-[e:CALLS]->(b)
        RETURN a.id AS caller_id, b.id AS callee_id, e.line AS line, e.strategy AS strategy, e.method AS method,
               e.virtual AS virtual""",
              ("caller_id", "callee_id", "line", "method")),
    "hierarchy": (f"""
        MATCH (a:Symbol {AT})-[e:EXTENDS|IMPLEMENTS|OVERRIDES]->(b:Symbol)
        RETURN a.id AS source_id, b.id AS target_id, type(e) AS kind""", ("source_id", "target_id", "kind")),
    "imports": (f"""
        MATCH (f:File {AT})-[e:IMPORTS]->(t)
        RETURN f.id AS file_id, t.id AS target_id, e.spec AS spec, e.line AS line,
               [x IN labels(t) WHERE x IN ['File', 'Module', 'Package']][0] AS target_label""",
                ("file_id", "target_id", "spec")),
    "endpoints": ("""
        MATCH (:Service {tenant: $tenant, name: $repo})-[x:EXPOSES {ref: $ref}]->(n:HttpEndpoint)
        OPTIONAL MATCH (n)-[:HANDLED_BY {ref: $ref}]->(h:Symbol)
        RETURN n.id AS id, n.method AS method, n.path AS path, n.framework AS framework, n.app AS app,
               x.evidence AS evidence, x.line AS line, x.raw_pattern AS raw_pattern, h.id AS handler_id""", ("id",)),
    "http_calls": (f"""
        MATCH (c)-[:MAKES_HTTP_CALL]->(n:HttpCall {AT})<-[:CONTAINS]-(f:File)
        RETURN n.id AS id, n.method AS method, n.path AS path, n.raw_path AS raw_path, n.via AS via,
               n.target_hint AS target_hint, n.env_hints AS env_hints, n.line AS line, n.evidence AS evidence,
               c.id AS caller_id, f.id AS file_id""", ("id",)),
    "violations": (f"""
        MATCH (f:File)-[:HAS_VIOLATION]->(n:Violation {AT})
        OPTIONAL MATCH (s:Symbol)-[:HAS_VIOLATION]->(n)
        RETURN n.id AS id, n.convention AS convention, n.rule AS rule, n.severity AS severity, n.message AS message,
               n.line AS line, n.evidence AS evidence, f.id AS file_id, s.id AS symbol_id""", ("id",)),
}

RUNS = sorted(DRY.glob("*.json")) if DRY.is_dir() else []


@pytest.fixture(scope="module")
def store():
    from aidd_indexer.core.config import Neo4jConfig
    from aidd_indexer.mcp.server import Store
    s = Store(Neo4jConfig.from_env(), None)
    yield s
    s.close()


def by_key(rows: list[dict], key: tuple[str, ...]) -> dict[tuple, dict]:
    """The records by their key in the graph, the last one written winning where the writer merges them."""
    return {tuple(r[k] for k in key): r for r in rows}


def differences(dry: dict[tuple, dict], graph: dict[tuple, dict]) -> list[str]:
    missing = [f"not in the graph: {k}" for k in dry.keys() - graph.keys()]
    extra = [f"only in the graph: {k}" for k in graph.keys() - dry.keys()]
    changed = [f"{k}: {f} is {graph[k][f]!r} in the graph, {dry[k][f]!r} in the dry-run"
               for k in dry.keys() & graph.keys() for f in graph[k] if graph[k][f] != dry[k][f]]
    return sorted(missing)[:5] + sorted(extra)[:5] + sorted(changed)[:5]


@pytest.mark.parametrize("section", SECTIONS)
@pytest.mark.parametrize("run", RUNS, ids=lambda p: p.stem)
def test_the_graph_holds_the_dry_run(store, run, section):
    payload = json.loads(run.read_text())
    repo = payload["repo"]
    query, key = SECTIONS[section]
    graph = by_key(store.read(query, tenant=repo["tenant"], repo=repo["name"], ref=repo["ref"]), key)
    fields = next(iter(graph.values()), {}).keys()
    dry = by_key([{f: r.get(f) for f in fields} | {k: r[k] for k in key} for r in payload[section]], key)
    assert not differences(dry, graph), differences(dry, graph)
    assert len(graph) == len(dry)


@pytest.mark.parametrize("run", RUNS, ids=lambda p: p.stem)
def test_a_call_is_one_edge(store, run):
    """The writer creates an edge per call, so a call the dry-run repeated would be two edges."""
    payload = json.loads(run.read_text())
    repo = payload["repo"]
    query, key = SECTIONS["calls"]
    keys = [tuple(r[k] for k in key) for r in payload["calls"]]
    assert len(set(keys)) == len(keys) == len(store.read(query, tenant=repo["tenant"], repo=repo["name"],
                                                         ref=repo["ref"]))


def test_the_dry_runs_hold_every_kind_of_record_but_violations():
    """A section empty in every run would pass while checking nothing, and so would calls of which no two of one line
    reach one target, for two methods."""
    payloads = [json.loads(p.read_text()) for p in RUNS]
    assert {s for s in SECTIONS if any(p[s] for p in payloads)} == set(SECTIONS) - {"violations"}
    assert max(Counter((c["caller_id"], c["callee_id"], c["line"]) for p in payloads for c in p["calls"]).values()) > 1
    assert {(p["repo"]["tenant"], p["repo"]["ref"]) for p in payloads} == \
        {("it", "main"), ("it", "feature/items"), ("it-writer", "main")}
