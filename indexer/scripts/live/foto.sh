#!/usr/bin/env bash
# Read-only picture of the live graph: counts per snapshot and the sorted lists the before/after diff compares.
#   foto.sh OUT_DIR
set -euo pipefail
out="$1"; mkdir -p "$out"

q() {  # q NAME CYPHER
  docker exec -i aidd-core-neo4j sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#*/}" --format plain' <<<"$2" \
    | tail -n +2 | LC_ALL=C sort > "$out/$1.txt"
  echo "$1: $(wc -l < "$out/$1.txt" | tr -d ' ') rows"
}

q snapshots 'MATCH (s:Snapshot) RETURN s.tenant, s.repo, s.ref, s.commit_sha, s.indexer_build, s.ephemeral, s.conventions, s.architecture;'
q labels 'MATCH (n) WITH labels(n)[0] AS l, n.tenant AS t RETURN t, l, count(*);'
q counts_micro '
MATCH (sn:Snapshot) WITH sn.tenant AS t, sn.repo AS r, sn.ref AS ref
CALL { WITH t, r, ref MATCH (f:File {tenant: t, repo: r, ref: ref}) RETURN count(f) AS files }
CALL { WITH t, r, ref MATCH (s:Symbol {tenant: t, repo: r, ref: ref}) RETURN count(s) AS symbols }
CALL { WITH t, r, ref MATCH (a {tenant: t, repo: r, ref: ref})-[c:CALLS]->() RETURN count(c) AS calls }
CALL { WITH t, r, ref MATCH (f:File {tenant: t, repo: r, ref: ref})-[i:IMPORTS]->() RETURN count(i) AS imports }
CALL { WITH t, r, ref MATCH (v:Violation {tenant: t, repo: r, ref: ref}) RETURN count(v) AS violations }
CALL { WITH t, r, ref MATCH (h:HttpCall {tenant: t, repo: r, ref: ref}) RETURN count(h) AS http_calls }
RETURN t, r, ref, files, symbols, calls, imports, violations, http_calls;'
q counts_macro '
MATCH (s:Service)-[x:EXPOSES]->(e:HttpEndpoint) RETURN "EXPOSES" AS k, s.tenant AS t, s.name AS r, x.ref AS ref, count(*) AS n
UNION ALL MATCH (e:HttpEndpoint)-[h:HANDLED_BY]->(:Symbol) RETURN "HANDLED_BY" AS k, e.tenant AS t, e.service AS r, h.ref AS ref, count(*) AS n
UNION ALL MATCH (s:Service)-[c:CONSUMES]->(:HttpEndpoint) RETURN "CONSUMES" AS k, s.tenant AS t, s.name AS r, c.ref AS ref, count(*) AS n
UNION ALL MATCH (e:HttpEndpoint)-[c:CALLED_FROM]->() RETURN "CALLED_FROM" AS k, e.tenant AS t, e.service AS r, c.ref AS ref, count(*) AS n
UNION ALL MATCH (s:Service)-[d:DEPENDS_ON]->(:Service) RETURN "DEPENDS_ON" AS k, s.tenant AS t, s.name AS r, d.ref AS ref, count(*) AS n;'
q endpoints '
MATCH (s:Service)-[x:EXPOSES]->(e:HttpEndpoint)
OPTIONAL MATCH (e)-[h:HANDLED_BY {ref: x.ref}]->(sym:Symbol)
RETURN s.tenant, s.name, x.ref, e.method, e.path_key, e.path, coalesce(e.app, "<null>"), e.framework, x.evidence, sym.qualified_name;'
q endpoint_nodes 'MATCH (e:HttpEndpoint) RETURN e.tenant, e.service, e.id, coalesce(e.app, "<null>"), EXISTS { (:Service)-[:EXPOSES]->(e) } AS exposed, EXISTS { (:Service)-[:CONSUMES]->(e) } AS consumed;'
q http_calls 'MATCH (c:HttpCall) OPTIONAL MATCH (caller)-[:MAKES_HTTP_CALL]->(c) RETURN c.tenant, c.repo, c.ref, c.method, c.path_key, c.raw_path, c.via, c.target_hint, c.evidence, coalesce(caller.qualified_name, caller.path);'
q consumes 'MATCH (s:Service)-[c:CONSUMES]->(e:HttpEndpoint) RETURN s.tenant, s.name, c.ref, e.service, coalesce(e.app, "<null>"), e.method, e.path_key, c.confidence, c.hint, c.call_count, c.methods;'
q called_from 'MATCH (e:HttpEndpoint)-[c:CALLED_FROM]->(t) RETURN e.tenant, e.service, coalesce(e.app, "<null>"), e.method, e.path_key, c.ref, c.evidence, c.confidence, c.hint, c.via, coalesce(t.qualified_name, t.path);'
q depends_on 'MATCH (a:Service)-[d:DEPENDS_ON]->(b:Service) RETURN a.tenant, a.name, d.ref, b.name, d.packages;'
q symbols 'MATCH (s:Symbol) RETURN s.id, s.kind, s.line_start, s.line_end, s.role, s.is_entry_point;'
q calls_edges 'MATCH (a)-[c:CALLS]->(b) RETURN a.id, b.id, c.line, c.strategy, c.resolved, c.method;'
q imports_edges 'MATCH (a:File)-[i:IMPORTS]->(b) RETURN a.id, b.id, i.spec, i.line;'
q violations 'MATCH (v:Violation) RETURN v.id, v.severity, v.message;'
q modules 'MATCH (m:Module) RETURN m.id, m.kind, m.layer;'
