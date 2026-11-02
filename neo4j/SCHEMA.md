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

**Micro edges** carry none of `tenant`, `repo`, `ref` or `commit_sha`: both their ends are nodes of one snapshot,
which carry them. Each edge's own properties are in §3.

**Properties of the macro edges** that link a repo's code to a contract (`EXPOSES`, `HANDLED_BY`, `CONSUMES`,
`CALLED_FROM`). `DEPENDS_ON` carries `ref` and `commit_sha` but neither `confidence` nor `evidence`, and `DEPLOYS` none
of them; their own properties are in §3:

| prop | values | description |
|---|---|---|
| `confidence` | `exact` \| `heuristic` \| `llm` | how the link was established |
| `evidence` | string | `repo:path:line` (or spec/manifest) the link came from |
| `ref` | string | ref of the source repo where the evidence was seen |
| `commit_sha` | string | commit of that ref the evidence was seen at |
| `linker_version` | string | linker version that created the edge (planned; not written yet) |

Never store secret values. Environment variables enter by **name only** (`env_var: "ORDERS_API_URL"`).

## 2. Nodes

### Micro

| Label | Specific props | Notes |
|---|---|---|
| `Repo` | `name`, `default_ref`, `stack[]` (`go`,`ts`,`dotnet`,`python`…), `url` | 1 per (tenant, repo) — no `ref` |
| `Snapshot` | `repo`, `ref`, `commit_sha`, `indexed_at`, `indexer_version`, `indexer_build` (`<version>+<fingerprint>` of the code that shapes the graph — a different build makes the next refresh re-index the snapshot), `ephemeral`, `provides[]` (`<ecosystem>:<package>` the manifests publish — go.mod `module`, `PackageId`, package.json `name`, pyproject `name`), `requires[]` (`<ecosystem>:<package>@<version>` direct dependencies), `architecture?` (layout a convention detected, e.g. `split`), `conventions[]` (applied, as `id[layout]`) | 1 per (repo, ref); drives orphan GC (§5); `provides`/`requires` feed `DEPENDS_ON` |
| `Module` | `name`, `path`, `kind` (`go-package`,`npm-workspace`,`csproj`,`py-package`), `layer?` | build/publish unit; `layer` is set by a **convention** when all its files agree, else null |
| `File` | `path`, `language`, `loc`, `layer?`, `last_touched`, `churn_90d`, `authors[]` | `layer` set by a convention's `layers:` globs; git metrics land here (planned) |
| `Symbol` | `name`, `qualified_name`, `kind`, `signature`, `doc`, `visibility`, `path` (of its `File`, so a query needs no join), `line_start`, `line_end`, `scip_symbol?`, `is_entry_point`, `role?` | `signature`: the declaration's first line, cut at the `{` that opens its body, without the `=>`, `=` or `:` that leads into it; `kind` ∈ `class, interface, struct, enum, function, method, field, const, var, type, handler, job` (`var`: package-level only; a TS or JS `method` is each declaration of one, an interface's, an abstract one and each overload signature too); `role` (types only) comes from a convention's `roles:` — what the element is in the pattern (`command-handler`, `repository`…), independent of where it lives |
| `Violation` | `convention`, `rule`, `severity` (`error`,`warning`,`info`), `message`, `line`, `evidence` | a convention rule broken at one place. Micro: per ref, GC'd like `Symbol`. `(File)-[:HAS_VIOLATION]->(Violation)`, `(Symbol)-[:HAS_VIOLATION]->` when attributable |
| `HttpCall` | `method`, `path` (template), `path_key`, `raw_path`, `via` (callee as written), `target_hint` (package/dir: `outbound/<svc>` → `<svc>`), `env_hints[]` (base-URL env var names seen nearby), `line`, `evidence` | **outbound HTTP call site** with a literal/template path — a `CONSUMES` candidate. Micro: per ref, GC'd like `Symbol`. `path_key` = `path` with every placeholder as `{param}` — the join key with `HttpEndpoint.path_key` |

### Macro

| Label | Specific props | Identity |
|---|---|---|
| `Service` | `name`, `env_vars[]`, `base_urls[]` | logical deployable; usually 1:1 with `Repo`, may be N:1 (monorepo) |
| `HttpEndpoint` | `method` (`GET`…`ANY`), `path` (normalized template `/orders/{id}`), `path_key`, `framework`, `app`, `first_seen`, `last_seen`, `openapi_operation_id?` | id = `(service, app, method, path_key)` — placeholders normalized, so `{id}` renamed to `{userId}` on a branch is the same endpoint; `path` keeps the latest spelling written, with the case the code writes (`[controller]` → `/api/Todos`; an ASP.NET route links and is found by `who_consumes` without case). `app` is the repo-relative directory of the module (manifest) that declares the route when the repo's routes come from more than one module, else `""`: the same route in two apps of a monorepo is two endpoints, and a call to it links to both; a route declared in a shared library is one. Which refs expose it lives on the `EXPOSES {ref}` edges |
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
| `IMPORTS` | File→File \| Module \| Package | `spec` (as written), `line`. Go imports target the package `Module`; a TS or JS import, the file TypeScript resolves it to with the importing file's `tsconfig.json` or `jsconfig.json`, else the file a conventional alias names; unresolved specs become external `Package` nodes (`stdlib` flag) |
| `CALLS` | Symbol \| File→Symbol | `line`, `resolved` (bool: SCIP vs. name match), `method` (only for `inherited*`: the method called, which comes from a package base), `virtual` (bool: `false` where the language sends the call to one method by name, C# `base.M()` and Python `super().m()`, so the object's class does not choose it; `true` where it may, a static call included), `receivers` (on a dispatching call to a method others override, when a supertype of the receiver's type declares it: the receiver's types, so the call may run an override only where the override's `receivers` hold one of them; absent where the receiver's type declares the method or is not known, and the call may run any override), `strategy` (`receiver-type`: method of the receiver's static type, or, when none of its methods takes the arguments, the repo's extension method whose `this` takes that type or the nearest base of it (C#); for a Python `super()` whose receiver's type the class's bases do not decide, the method of the first class after the caller's that binds the name in each MRO of the repo's classes that holds it, none past a base outside the repo; a call that does not dispatch goes to no implementation and to no homonym found by name; `receiver-type-impl`: the implementation an interface receiver reaches — its single production implementer, or the one the DI registrations name (C# `AddScoped<I, Impl>()`; in a `Decorate<I, D>()` chain the outermost decorator, and from a decorator the instance it wraps); `dispatch`: a mediator call reaching the handler of the message's type (MediatR built in, an organization's bus declared by its convention); `inherited` / `inherited-impl`: a method the repo does not declare, on a type with a base outside the repo (`repo.CreateAsync()` on `ITodoRepository : IBaseRepository<T>` of a package) — the edge goes to the type and to its single implementer, with `method`; `same-file`, `same-module`, `unique-name`, `*-ambiguous`: name match; `unique-name` is also the only extension method of the repo that takes any value, on a typed receiver none of whose methods takes the arguments); a `File` source means a top-level call. One edge per source, target, `line` and `method`: the calls of one line that reach one target are one edge, whose `strategy` is the strongest of theirs, in the order above and the unambiguous before the `-ambiguous`, which is `virtual` when one of them is, and whose `receivers` are all of theirs, or none when one has none |
| `REFERENCES` | Symbol→Symbol | read/write without a call (types, fields) |
| `IMPLEMENTS` | Symbol→Symbol | a type that is not an interface → an interface of the repo it names as a base (C#); a TS or JS class → what its `implements` clause names, a class too. One edge per type and base: a partial type's parts are one node, and their bases are the type's |
| `EXTENDS` | Symbol→Symbol | a type → any other base of the repo it names: a class's base class, an interface's base interface (C#), a Python class's bases of the repo, what a TS or JS class's or interface's `extends` clause names. A base outside the repo, one the language cannot find in it and a Go embedded type (it promotes its methods and dispatches none) give no edge, and two types of one qualified name (C#'s `IFoo` and `IFoo<T>` in one file) have none, from or to them, since no name a base writes tells them apart |
| `OVERRIDES` | Symbol→Symbol | a method → a method a dispatching call to which may run it instead, on an instance of some type of the repo at or below the target's: what the instance's language looks up. C#: the deepest `override` of a class's method in the instance's class chain, `new` hiding it from the classes below, and an interface's method as the nearest class that names the interface, or a class above it, declares it; matched by name and number of parameters, so overloads of one number are each a target, and a static method has none. Python: what each class's MRO finds first, so a mixin's method overrides a class it does not extend, and only the last definition of a name in a class. TS and JS: what JS looks the name up to on an instance of the class: no method where a class of its `extends` chain declares the name a field, which the instance holds, or where the nearest class whose prototype holds it declares an accessor; else that class's last declaration of the method with a body, after its overload signatures, an abstract method holding nothing; a static method, an accessor and a constructor have none. Go writes none, and two types of one qualified name have none. `receivers`: the qualified names of the types below the target's a receiver of which may hold such an instance, the instance's type or one above it, for a call's `receivers` to pick the overrides it may run |
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
| `CONSUMES` | Service→HttpEndpoint | outbound HTTP call, **materialized by the linker** from `HttpCall × HttpEndpoint`. One edge per `ref` (`{ref}` key) per (consumer, endpoint): `commit_sha`, `confidence` (`exact` = same `path_key`, without case for an ASP.NET route as the framework matches; `suffix` = one path is a segment suffix of the other **and** a hint names the provider), `hint` (`target_hint` \| `env_hint` \| null — what broke a tie between services), `call_count`, `methods[]`, `evidence[]` (≤10 call sites), `linked_at`. Never links a service to itself; when several services expose the path and no hint picks one, **no edge** (the MCP lists them as `possible_consumers`). Rebuilt for the whole tenant on every `aidd link` / end of index·bootstrap·refresh |
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
HttpEndpoint  <tenant>/svc/<name>/http/<METHOD> <path-template>   (<tenant>/svc/<name>/app/<app>/http/... when `app` is set)
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
