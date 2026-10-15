# Code graph schema (v1)

Structural source of truth for the workspace. Two levels live in the same graph: **micro**
(what exists inside one repo) and **macro** (the contracts that connect repos). Storage:
Neo4j (see `docs/adr/ADR-001-graph-db.md`). Vectors in Qdrant point to nodes here by `id`.
Constraints and indexes that enforce this document live in `init/schema.cypher`.

## 1. General rules

**Required properties on every micro node** (`Repo`, `Module`, `File`, `Symbol`):

| prop | type | description |
|---|---|---|
| `id` | string | stable identity (see §4) |
| `tenant` | string | same value as the Qdrant collection (the `scan` skill's tenant) |
| `repo` | string | repository name |
| `ref` | string | indexed branch (`main`, `develop`, `feat/xyz`) |
| `commit_sha` | string | commit at which the node was last observed |
| `indexed_at` | datetime | last write |
| `content_hash` | string | hash of the relevant content (lets the embedder skip unchanged symbols) |

**Macro nodes** (`Service`, `HttpEndpoint`, `GrpcService`, `GrpcMethod`, `Topic`, `EventSchema`,
`Package`, `DbTable`) are **independent of `ref` and `repo`**: they represent the contract, not
the implementation. Who implements/consumes is expressed by edges. They carry `tenant`, `id`,
`first_seen`, `last_seen`.

**Required properties on every macro edge**:

| prop | values | description |
|---|---|---|
| `confidence` | `exact` \| `heuristic` \| `llm` | how the link was established |
| `evidence` | string | `repo:path:line` (or spec/manifest) the link came from |
| `ref` | string | ref of the source repo where the evidence was seen |
| `linker_version` | string | linker version that created the edge (enables re-linking) |

Never store secret values. Environment variables enter by **name only** (`env_var: "ORDERS_API_URL"`).

## 2. Nodes

### Micro

| Label | Specific props | Notes |
|---|---|---|
| `Repo` | `name`, `default_ref`, `stack[]` (`go`,`ts`,`dotnet`,`python`…), `url` | 1 per (tenant, repo) — no `ref` |
| `Snapshot` | `repo`, `ref`, `commit_sha`, `indexed_at`, `indexer_version`, `indexer_build` (`<version>+<fingerprint>` of the code that shapes the graph — a different build makes the next refresh re-index the snapshot), `ephemeral`, `provides[]` (`<ecosystem>:<package>` the manifests publish — go.mod `module`, `PackageId`, package.json `name`, pyproject `name`), `requires[]` (`<ecosystem>:<package>@<version>` direct dependencies), `architecture?` (layout a convention detected, e.g. `split`), `conventions[]` (applied, as `id[layout]`) | 1 per (repo, ref); drives orphan GC (§5); `provides`/`requires` feed `DEPENDS_ON` |
| `Module` | `name`, `path`, `kind` (`go-package`,`npm-workspace`,`csproj`,`py-package`), `layer?` | build/publish unit; `layer` is set by a **convention** when all its files agree, else null |
| `File` | `path`, `language`, `loc`, `layer?`, `last_touched`, `churn_90d`, `authors[]` | `layer` set by a convention's `layers:` globs; git metrics land here (planned) |
| `Symbol` | `name`, `qualified_name`, `kind`, `signature`, `doc`, `visibility`, `path` (of its `File`, so a query needs no join), `line_start`, `line_end`, `scip_symbol?`, `is_entry_point`, `role?` | `kind` ∈ `class, interface, struct, enum, function, method, field, const, var, type, handler, job` (`var`: package-level only); `role` (types only) comes from a convention's `roles:` — what the element is in the pattern (`command-handler`, `repository`…), independent of where it lives |
| `Violation` | `convention`, `rule`, `severity` (`error`,`warning`,`info`), `message`, `line`, `evidence` | a convention rule broken at one place. Micro: per ref, GC'd like `Symbol`. `(File)-[:HAS_VIOLATION]->(Violation)`, `(Symbol)-[:HAS_VIOLATION]->` when attributable |
| `HttpCall` | `method`, `path` (template), `path_key`, `raw_path`, `via` (callee as written), `target_hint` (package/dir: `outbound/<svc>` → `<svc>`), `env_hints[]` (base-URL env var names seen nearby), `line`, `evidence` | **outbound HTTP call site** with a literal/template path — a `CONSUMES` candidate. Micro: per ref, GC'd like `Symbol`. `path_key` = `path` with every placeholder as `{param}` — the join key with `HttpEndpoint.path_key` |

### Macro

| Label | Specific props | Identity |
|---|---|---|
| `Service` | `name`, `env_vars[]`, `base_urls[]` | logical deployable; usually 1:1 with `Repo`, may be N:1 (monorepo) |
| `HttpEndpoint` | `method` (`GET`…`ANY`), `path` (normalized template `/orders/{id}`), `path_key`, `framework`, `first_seen`, `last_seen`, `openapi_operation_id?` | id = `(service, method, path_key)` — placeholders normalized, so `{id}` renamed to `{userId}` on a branch is the same endpoint; `path` keeps the latest spelling written. Which refs expose it lives on the `EXPOSES {ref}` edges |
| `GrpcService` | `name`, `proto_path`, `package` | `package.Service` |
| `GrpcMethod` | `name`, `request_type`, `response_type`, `streaming` | `package.Service/Method` |
| `Topic` | `name`, `broker` (`kafka`,`rabbitmq`,`sqs`,`sns`,`pubsub`), `kind` (`topic`,`queue`,`exchange`) | `(broker, name)` |
| `EventSchema` | `name`, `version`, `schema_ref` | when a registry / explicit schema exists |
| `Package` | `name`, `ecosystem` (`go`,`npm`,`nuget`,`pypi`), `internal` (bool), `version?` | `(ecosystem, name)` |
| `DbTable` | `schema`, `name`, `database` | `(database, schema, name)` |

### Operational

| Label | Props | |
|---|---|---|
| `IndexRun` | `repo`, `ref`, `commit_sha`, `started_at`, `finished_at`, `status`, `counts{}`, `errors[]` | history (`aidd status`) |
| `RefreshState` | `tenant` (unique), `last_started_at`, `last_finished_at`, `last_rc`, `trigger`, `interval_min`, `changed`, `indexer_version` | one per tenant, rewritten by every `refresh` — even one that indexed nothing — so a dead refresher is visible (`atlas_status.refresh.stale`, install-check) |

## 3. Edges

### Micro (inside a repo, same `ref`)

| Edge | From → To | Props |
|---|---|---|
| `CONTAINS` | Repo→Module, Module→File, File→Symbol, Symbol→Symbol (member) | |
| `IMPORTS` | File→File \| Module \| Package | `spec` (as written), `line`. Go imports target the package `Module`; unresolved specs become external `Package` nodes (`stdlib` flag) |
| `CALLS` | Symbol \| File→Symbol | `line`, `resolved` (bool: SCIP vs. name match), `method` (only for `inherited*`: the method called, which comes from a package base), `strategy` (`receiver-type`: method of the receiver's static type; `receiver-type-impl`: the implementation an interface receiver reaches — its single production implementer, or the one the DI registrations name (C# `AddScoped<I, Impl>()`; in a `Decorate<I, D>()` chain the outermost decorator, and from a decorator the instance it wraps); `dispatch`: a mediator call reaching the handler of the message's type (MediatR built in, an organization's bus declared by its convention); `inherited` / `inherited-impl`: a method the repo does not declare, on a type with a base outside the repo (`repo.CreateAsync()` on `ITodoRepository : IBaseRepository<T>` of a package) — the edge goes to the type and to its single implementer, with `method`; `same-file`, `same-module`, `unique-name`, `*-ambiguous`: name match); a `File` source means a top-level call |
| `REFERENCES` | Symbol→Symbol | read/write without a call (types, fields) |
| `IMPLEMENTS` | Symbol→Symbol | class/struct → interface |
| `EXTENDS` | Symbol→Symbol | inheritance |
| `ACCEPTS` / `RETURNS` | Symbol→Symbol | parameter/return types (for data tracing) |
| `IN_SNAPSHOT` | File→Snapshot | membership; enables GC by difference |
| `HAS_SNAPSHOT` | Repo→Snapshot | one per indexed ref |
| `HAS_RUN` | Snapshot→IndexRun | indexing history |
| `HAS_VIOLATION` | File \| Symbol→Violation | a convention rule broken here; rebuilt per commit like the node |
| `MAKES_HTTP_CALL` | Symbol \| File→HttpCall | the call site's enclosing symbol (or the file for top-level code); `File-[:CONTAINS]->HttpCall` also holds |

### Macro (between repo/service and contract)

| Edge | From → To | Meaning |
|---|---|---|
| `DEPLOYS` | Repo→Service | the repo produces the service |
| `EXPOSES` | Service→HttpEndpoint \| GrpcService | implements the contract. **One edge per `ref`** (`{ref}` is the MERGE key) with `commit_sha`, `evidence`, `line`, `raw_pattern`, `confidence`; edges of a ref not refreshed at the current commit are removed, and an endpoint with no `EXPOSES` and no `CONSUMES` is deleted |
| `HANDLED_BY` | HttpEndpoint \| GrpcMethod → Symbol | **macro→micro bridge**: the concrete handler (entry of `trace_flow`). One edge per `ref` (`{ref}` key), same lifecycle as `EXPOSES` |
| `CONSUMES` | Service→HttpEndpoint | outbound HTTP call, **materialized by the linker** from `HttpCall × HttpEndpoint`. One edge per `ref` (`{ref}` key) per (consumer, endpoint): `commit_sha`, `confidence` (`exact` = same `path_key`; `suffix` = one path is a segment suffix of the other **and** a hint names the provider), `hint` (`target_hint` \| `env_hint` \| null — what broke a tie between services), `call_count`, `methods[]`, `evidence[]` (≤10 call sites), `linked_at`. Never links a service to itself; when several services expose the path and no hint picks one, **no edge** (the MCP lists them as `possible_consumers`). Rebuilt for the whole tenant on every `aidd link` / end of index·bootstrap·refresh |
| `CALLS_GRPC` | Service→GrpcMethod | outbound gRPC call |
| `CALLED_FROM` | HttpEndpoint \| GrpcMethod → Symbol \| File | **micro→macro bridge**: one edge per linked call site (`{ref, call_id}` key; target = the `HttpCall`'s caller symbol, or the file for top-level code) with `commit_sha`, `line`, `method`, `confidence`, `hint`, `evidence`, `via`. Same lifecycle as `CONSUMES` |
| `DEFINES_PROTO` | Repo→GrpcService | where the `.proto` lives |
| `PUBLISHES` / `SUBSCRIBES` | Service→Topic | `event_schema?` |
| `PRODUCES` / `CONSUMES_EVENT` | Service→EventSchema | when a schema exists |
| `DEPENDS_ON` | Service→Service | **internal package dependency, materialized by the linker** from `Snapshot.requires × Snapshot.provides` of the tenant: one edge per `ref` (`{ref}` key) per (consumer, provider) with `commit_sha`, `packages[]`, `versions[]`, `ecosystems[]`, `linked_at`. Names are normalized (lower-case; pypi `_`→`-`); never self; a package published by two repos links to **neither** (listed as ambiguous in the `aidd link` log). External packages stay `Package` nodes reached by `IMPORTS` |
| `PROVIDES` | Repo→Package | the repo publishes the internal package |
| `READS` / `WRITES` | Symbol→DbTable | via ORM/migrations/SQL |
| `OWNS_TABLE` | Service→DbTable | inferred: single writer |

The `HANDLED_BY` / `CALLED_FROM` pair is what lets `impact_analysis` cross repos:
`Symbol ←CALLS*← Symbol ←CALLED_FROM← HttpEndpoint ←EXPOSES← Service ←DEPLOYS← Repo`.

## 4. `id` convention

Deterministic, human-readable, no hashes — enables idempotent `MERGE` and debugging in the Browser.

```
Repo          <tenant>/<repo>
Snapshot      <tenant>/<repo>@<ref>
Module        <tenant>/<repo>@<ref>/mod/<path>
File          <tenant>/<repo>@<ref>/file/<path>
Symbol        <tenant>/<repo>@<ref>/sym/<qualified_name>#<kind>   (fallback: <path>:<line> when nameless)
Service       <tenant>/svc/<name>
HttpEndpoint  <tenant>/svc/<name>/http/<METHOD> <path-template>
GrpcService   <tenant>/grpc/<package>.<Service>
GrpcMethod    <tenant>/grpc/<package>.<Service>/<Method>
Topic         <tenant>/topic/<broker>/<name>
Package       <tenant>/pkg/<ecosystem>/<name>
DbTable       <tenant>/db/<database>/<schema>.<name>
IndexRun      <tenant>/<repo>@<ref>/run/<started_at-iso>
RefreshState  (keyed by `tenant`, no `id`)
Violation     <tenant>/<repo>@<ref>/violation/<convention>.<rule>/<path>:<line>
```

`qualified_name` follows the language's native convention (`pkg.Type.Method` in Go,
`Namespace.Class.Method` in .NET, `module/path:Class.method` in TS/Python). When SCIP is
available, `scip_symbol` keeps the original symbol for traceability.

## 5. Refs and lifecycle

- `main` = baseline (production); `develop` = always indexed; feature branches only on demand
  (the `refine-tech` skill) and flagged `ephemeral: true` on the `Snapshot`.
- Re-indexing `(repo, ref)`: the indexer creates/updates the `Snapshot` with the new
  `commit_sha`, `MERGE`s every micro node with the new `commit_sha`, and finally **deletes micro
  nodes of the same `(tenant, repo, ref)` whose `commit_sha` ≠ current** (orphans).
- Macro nodes are never deleted by indexing; the **linker** updates `last_seen` and removes macro
  edges whose `evidence` no longer exists in the corresponding `ref`.
- MCP queries accept an optional `ref`; default = `develop` if it exists, else the `Repo`'s `default_ref`.

## 6. Link to Qdrant

One point per relevant `Symbol` (functions, methods, classes, handlers) and per summary
(`Module`, `Repo`). Minimal payload: `{node_id, tenant, repo, ref, kind, path, content_hash}`.
Same `content_hash` → no re-embedding. Collection = `<tenant>` (same as the `scan` skill).
Hybrid flow: vector search → `MATCH (n {id: $node_id})` → k-hop expansion → answer.

## 7. Reference queries (they validate the schema and become golden questions)

```cypher
// Who consumes an endpoint?
MATCH (e:HttpEndpoint {tenant:$t, method:$m, path:$p})<-[c:CONSUMES]-(s:Service)<-[:DEPLOYS]-(r:Repo)
RETURN r.name, s.name, c.confidence, c.evidence;

// Micro flow from an endpoint (up to 6 hops)
MATCH (e:HttpEndpoint {id:$id})-[:HANDLED_BY]->(h:Symbol)
MATCH p=(h)-[:CALLS*1..6]->(x:Symbol)
WHERE x.ref = h.ref
RETURN p;

// Cross-repo impact of a symbol
MATCH (s:Symbol {id:$id})<-[:CALLS*0..8]-(caller:Symbol)<-[:HANDLED_BY]-(ep)
MATCH (ep)<-[:CONSUMES|CALLS_GRPC]-(svc:Service)<-[:DEPLOYS]-(r:Repo)
RETURN DISTINCT r.name, ep.id;

// Workspace map
MATCH (a:Service)-[x:CONSUMES|CALLS_GRPC|PUBLISHES|SUBSCRIBES]->(c)<-[:EXPOSES|PUBLISHES|SUBSCRIBES]-(b:Service)
WHERE a <> b AND a.tenant = $t
RETURN a.name, type(x), labels(c)[0], c.id, b.name, x.confidence;
```

## 8. Out of scope for v1 (recorded so it is not forgotten)

Intra-procedural dataflow (taint), generic type graphs, contract versioning (OpenAPI v1 vs v2 of
the same endpoint), team ownership (will come from Jira/CODEOWNERS in phase 2).
