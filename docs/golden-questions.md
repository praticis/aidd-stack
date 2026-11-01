# Golden questions (F0.7)

> A living document. Each question has **the MCP tool that answers it**, **the Cypher that checks the answer directly
> on the graph** and **the result obtained on the pilot pair** — `<project-a>` (BFF) → `<project-b>` (auth service)
> and `<project-c>` (onboarding service), a fixed tenant, 6 Go repos. Real names never go in here (an open source
> repo); the result is described in shape, not in content.
>
> A question only counts as answered when the MCP's answer and the Cypher's agree **and** a sample was checked at the
> source (the `evidence` points to `repo:file:line`). Regression: repeat all five after any change to what the graph
> holds (the extractor's output, such as the `CALLS` Q4 reads, included), to the graph writer (`core/graph*.py`), to
> `linker.py` or to the MCP (`mcp/`).

## Why these five

They cover the three axes the atlas exists to answer and that reading the repository alone does not give: **within a
repo** (Q2), **across repos** (Q1, Q3, Q4) and **across refs** (Q5). Q1–Q3 are the everyday questions of the `scan`
skill and of `refine-business`; Q4 is the one that justifies the graph (impact crossing repositories, which no `grep`
answers); Q5 is the one continuous `refresh` enables (the branch is indexed before the merge).

---

## Q1 — Who consumes this route?

**Question:** "Who calls `<project-b>`'s `POST /v1/password-reset/start`, and from where?"

**MCP:** `who_consumes(path="/v1/password-reset/start", method="POST")` — without `repo`, because the same route may
be exposed by more than one service (the BFF re-exposes the service's routes).

**Cypher:**

```cypher
MATCH (svc:Service {tenant: $t})-[:EXPOSES]->(e:HttpEndpoint {method: 'POST', path_key: '/v1/password-reset/start'})
OPTIONAL MATCH (e)-[cf:CALLED_FROM]->(caller)
RETURN svc.name AS provider, caller.repo AS consumer, caller.qualified_name AS symbol,
       collect(DISTINCT cf.ref) AS refs, cf.evidence AS evidence, cf.confidence AS confidence
ORDER BY provider, consumer;
```

**Expected:** two routes — `<project-b>`'s with one consumer (`<project-a>`, the outbound adapter's symbol,
`file:line`, `confidence: exact`, a list of `refs`) and the one re-exposed by `<project-a>` with no consumer (whoever
calls the BFF is the app, which is not indexed). `possible_consumers` empty.

**Obtained (2026-09-29):** ✅ exactly that. The model told the two routes apart without being instructed and
explained why the BFF has no consumer. Before the fix, `consumers` came with one line per ref (13 branches = 13
"consumers"); now it is one line per repo × symbol with `refs[]`.

---

## Q2 — What does this repository call, and where does it go?

**Question:** "Which outbound HTTP calls does `<project-a>` make on `main`, and which service/route does each one
hit?"

**MCP:** `http_map(repo="<project-a>")` — look at `outbound_calls[].linked_to`, `outbound_unlinked`.

**Cypher:**

```cypher
MATCH (c:HttpCall {tenant: $t, repo: '<project-a>', ref: 'main'})
OPTIONAL MATCH (target:HttpEndpoint)-[cf:CALLED_FROM {call_id: c.id}]->()
RETURN c.method, c.path, c.target_hint, c.evidence, target.service AS linked_service, target.path AS linked_path, cf.confidence
ORDER BY c.path;
```

**Expected:** every call with a literal path shows up; the ones that match a route of another workspace repo have
`linked_to` (`exact`); the external ones (anti-fraud, e-mail, WhatsApp) and the ones with a literal segment passed
through a variable stay `linked_to: null`.

**Obtained (2026-09-29):** ✅ 5 calls on `main`, 5 linked to `<project-b>`, `outbound_unlinked: 0`. The model
pointed out, from the repo's `AGENTS.md`, calls that do not show up on the map (2FA, `users/me`, balance/statement) —
its hypothesis (a dynamic path, or only on a branch) is right in both cases and is the recall gap recorded for H1
(`docs/handoffs/H1-reference-apps.md`).

---

## Q3 — Service map: who talks to whom in the workspace?

**Question:** "Draw the HTTP integrations between this tenant's repositories."

**MCP:** `cypher_readonly` with the query below (it is the "workspace map" of `SCHEMA.md` §7; absent on a
multi-tenant atlas with `ATLAS_RAW_CYPHER=off`); or `http_map` per repo and add them up. A candidate for a tool of its
own (`workspace_map`) in F1.

**Cypher:**

```cypher
MATCH (a:Service {tenant: $t})-[c:CONSUMES]->(e:HttpEndpoint)<-[:EXPOSES]-(b:Service)
WITH DISTINCT a, b, e, c.confidence AS conf
RETURN a.name AS consumer, b.name AS provider, count(e) AS routes, collect(DISTINCT conf) AS confidence
ORDER BY consumer, provider;
```

Careful: `CONSUMES` and `EXPOSES` are **per ref** — without the `DISTINCT` the query multiplies rows per snapshot
(496 rows for 6 pairs in the first round).

**Expected:** one pair per (consumer, provider) with the number of routes; only `exact` after the suffix rule with
corroboration.

**Obtained (2026-09-29):** ✅ `<project-a>` → `<project-b>` (5 routes) and `<project-a>` → `<project-c>` (1 route).
The `<project-c>` → `<project-a>` pair that showed up by suffix was a false positive and led to the "suffix only with
a hint" rule (`core/linker.py`).

---

## Q4 — The impact of changing a symbol, across repositories

**Question:** "If I change `<the auth service symbol that validates the password policy>`, what is affected — within
the repo and in the others?"

**MCP:** `impact_of(symbol="<qualified_name>", repo="<project-b>")` → `internal_callers` (with `hops`),
`exposed_through` (routes whose handler reaches the symbol), `consumers` (other repos: service, route, calling
symbol, `file:line`, `confidence`).

**Cypher:**

```cypher
MATCH (s:Symbol {id: $id})
MATCH p = (h:Symbol)-[:CALLS*1..6]->(s) WHERE h.ref = s.ref AND h.repo = s.repo
WITH s, h, min(length(p)) AS hops
OPTIONAL MATCH (e:HttpEndpoint)-[:HANDLED_BY {ref: s.ref}]->(h)
OPTIONAL MATCH (e)-[cf:CALLED_FROM]->(caller)
RETURN h.qualified_name AS reaches_via, hops, e.method + ' ' + e.path AS route,
       caller.repo AS consumer, caller.qualified_name AS consumer_symbol, cf.evidence
ORDER BY hops, route;
```

**Expected:** the internal callers up to the HTTP handler (growing `hops`; `via_ambiguous: true` when every path from
the caller has a `*-ambiguous` `CALLS` edge; at each hop a method is also reached by a dispatching call to a method it
`OVERRIDES`, on a receiver that may hold an instance which runs it, which the Cypher above does not follow, and
`via_dispatch: true` when every path goes through one), the route `GET /v1/password-policy` in `exposed_through`, and
`<project-a>` in `consumers` with the outbound adapter and the line. If no handler reaches the symbol, an empty
`exposed_through` = a change internal to the service.

**Obtained (2026-10-03):** ⚠️ answered, with an important limit. The question was asked in the BFF's repo
(`<project-a>`), and the model picked the outbound adapter (`Client.GetPasswordPolicy`) as the target. The **across
repos** part came right from the graph: the route `GET /v1/password-policy` is exposed by `<project-b>`, consumed only
by the BFF (`exact`, no `possible_consumers`), and the route re-exposed by the BFF has no indexed consumer (the app).
The **within the repo** part exposed the limit of resolution by name: `who_calls` returned only the adapter's 5
tests; production use goes through an **interface** (`ports.PasswordPolicyGetter`), and the call
`getter.GetPasswordPolicy()` has several candidates with the same name (the interface method, the concrete method, the
tests' fakes) in different modules → `unique-name` fails → no `CALLS` edge exists. The model rebuilt the right chain
(handler → use case → port → adapter) through `find_symbol` + reading, and said the graph did not prove it. That is
exactly the metric that triggers SCIP (ADR-002, F1.2). A cheap fix before that: when resolving calls from production
code, discard candidates defined in test files (`TEST_FILE`) — that removes the fakes from the contest, and many cases
become `unique-name` again (F0.7.1).

**2nd round (2026-10-03):** ✅ `impact_of` was used end to end in `<project-b>`'s repo. The blind spot was a receiver
that is a struct field and resolved by name only. It led to F0.7.1, which brought three things:

- the receiver's static type in Go (`receiver-type`);
- production never resolves to a test;
- `impact_of` separating production callers from test ones.

Interfaces were left to SCIP or to a convention, and F0.7.3 resolved an interface with a single implementer.

Known limit: `CALLS` is resolved by name (same-file → same-module → unique-name); in repos with many homonyms the
`-ambiguous` paths inflate the radius. It is SCIP's trigger (ADR-002, F1.2).

---

## Q5 — What does this branch add to the service's surface?

**Question:** "Which routes, entry points and outbound calls does `<project-a>`'s branch `<feature/x>` have that
`main` does not (and vice versa)?"

**MCP:** `ref_diff(repo="<project-a>", ref="<feature/x>")` (base = the default branch; `base=` to compare two
features).

**Cypher:**

```cypher
MATCH (:Service {tenant: $t, name: '<project-a>'})-[x:EXPOSES]->(e:HttpEndpoint)
WITH e.method + ' ' + e.path AS route, collect(DISTINCT x.ref) AS refs
WHERE '<feature/x>' IN refs XOR 'main' IN refs
RETURN route, refs ORDER BY route;
```

**Expected:** the onboarding routes that exist only on the feature branches show up in `endpoints_added` with a
handler and `evidence`; `entry_points_added` lists the new handlers by `qualified_name`; `http_calls_added` the new
calls (by method+path); `*_removed` empty for a branch that only adds. `summary` with the counts.

**Obtained (2026-10-03):** ✅ the tool answered and the model read it right — including the reverse of the expected
case: the indexed branch was **behind** `main` (14 routes × 31; `main` had just received onboarding, 17 routes in
`endpoints_removed` from the branch's point of view), and locally the branch already had `main` merged. The model
explained that `ref_diff` compares the **indexed** commits (remote refs), not the local checkout, and proposed
`git diff main...<branch>` for the local code. It also listed, on `main`, the 4 calls to `<project-c>` with 3 without
`linked_to` because of `{param}/{param}` — the recall gap already recorded. A fix made in the tool: `ref_diff` now
returns `snapshots` (each ref's indexed sha and `indexed_at`) and a `note` about local refs, so that the lag is
explicit in the answer itself instead of depending on the model's reading.

---

## How to use this document

- A new question = a new block with the four fields (question, MCP, Cypher, expected) **before** implementing the
  tool; the "obtained" comes later, with a date.
- An answer that needed `cypher_readonly` is a sign of a missing tool (Q3 today).
- A right answer that the graph **does not prove** (Q4: a chain rebuilt by reading because `CALLS` does not cross an
  interface) is F1.2's metric — note how often it happens before deciding on SCIP.
- When the model answers right but with noise (Q1 and the refs), the fix is in the MCP, not in the prompt.
- Each `[WARN]`/gap noted here has an owner: extractor → the rules table in `indexer-evolution.md` §3 and the
  handoffs; linker → `core/linker.py` + `tests/test_linker.py`; MCP → `tests/test_mcp_protocol.py`.

---

## Earlier rounds

The full text of each round is in `git show 1d73bb0:docs/golden-questions.md` (in Portuguese).

- **1st (2026-09-29 and 2026-10-03), pilot Go tenant:**
  - Q1–Q3 and Q5 ✅;
  - Q4 ⚠️, because the chain through an interface was not in the graph. That led to F0.7.1–F0.7.2b.
- **2nd (2026-10-03), the reference .NET pair:**
  - Q1–Q3 ✅;
  - Q4a ⚠️ (7 false internal callers, from resolution by name in C#) and Q4b ❌ (the interface without the handler).
    That led to F0.7.2: the receiver's type and the single implementer in C#.
- **3rd (2026-10-14, indexer 0.2.14):** the .NET Q4 after F0.7.3, with mediator dispatch, DI and package bases.
  - Q4a: 1 caller, the route and the consumer;
  - Q4b: 5 callers and 2 routes.
- **4th (2026-10-18, build `0.2.14+8553d8007527`):** Q1, Q2 and the .NET Q4 after H2, with the ASP.NET route in the
  code's case.
  - What it caught: `who_consumes` compared `path_key` case-sensitively, and that was fixed in `98b8368`.
  - The lesson: every reader of a join key needs the linker's same rule.

## Fifth round: validating PR #5 on a live install (2026-10-19, build `0.2.15+0377dbb62b98`)

What changed since the fourth round: F1.14 (`feature/f114-close`, PR #5). It brought:

- one endpoint per app in a monorepo, with `app` on the node and in the id (indexer 0.2.15);
- the app's client wrappers in Python and in TS/JS;
- Go routes by declared type.

The round was part of a two-phase validation before the merge:

- **offline:** corpus and hold-out of `main` against the branch, the chain of baselines, the expected lists and the
  tests;
- **on the install:** 3 tenants and 10 snapshots.

The questions and one call of each of the 11 tools were recorded as JSON, through the MCP's HTTP, before and after the
reinstall. The comparison leaves out only the time and build fields.

| Q | Result | Note |
|---|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` | the endpoint gains `app: ""` |
| Q2 `http_map` | ✅ the same | `linked_to` also carries the `app` |
| Q3 map | ✅ the same on the 3 tenants | one pair, `<svc-accrual>` → `<svc-transaction>`, `exact` |
| Q4a and Q4b `impact_of` | ✅ the same | — |
| Q5 `ref_diff` (a TS repo, `develop` against `master`) | ✅ now with the 7 calls only `develop` makes, with the right verb | before, 0: the app's client wrappers hid the calls |

**What the round caught.** On the first reinstall, the TS repo gained 51 calls through the app's wrappers, and 34 were
wrong because of two defects:

- options in a local fell back to the default GET;
- a query in parentheses became `{param}`.

The fix is increment 12 (`dfbc8d7`), with a fixture case. On the second reinstall, the 109 new calls (51 and 58 on
the two refs) match the dry-run and are right. The corpus did not have those shapes. Only real code showed them.

**The rest of the graph.**

- Outside HTTP, these stayed identical before and after: symbols, `CALLS`, `IMPORTS`, modules, violations,
  `DEPENDS_ON`, `CONSUMES` and `CALLED_FROM`.
- In the sample Go monorepo, 3 routes that 3 services with their own `go.mod` declare became one endpoint per service:
  8 endpoints, where there were 3.
- The orphan node of the old lower-case route of the .NET pair was removed.

**An operations lesson.** `python -m aidd_indexer.cli` in an image with `WORKDIR=/app` runs the image's code, not the
code mounted through `PYTHONPATH`, because the working directory comes first in `sys.path`.

- The comparison dry-run needs `-w` pointing at the mounted code.
- The version printed on the first line confirms which code ran.

## Sixth round: validating PR #7 on a live install (2026-10-21, build `0.2.15+5ce9b1e9898a`)

What changed since the fifth round: H5's first part (PR #7). It is a refactor that must change nothing in the graph,
and it also splits the MCP into one module per tool group, with `who_consumes` normalizing the path it is asked for.

The validation had the same two phases as the fifth round, on 3 tenants and 10 snapshots:

- **before the reinstall, read-only:** dry-runs of `main` and of the branch on each snapshot, at its sha. They are
  identical in every section, HTTP included;
- **after the reinstall from the branch:** the refresher re-indexed each snapshot once, with no error, and the next
  refresh re-indexed none.

**The picture of the graph** is identical before and after. It covers the counts per snapshot and the sorted lists of
symbols, `CALLS`, `IMPORTS`, modules, endpoints, HTTP calls, `CONSUMES`, `CALLED_FROM`, `DEPENDS_ON` and violations.
Only the build and the `IndexRun` nodes changed: one more run per snapshot.

**The golden questions and one call of each of the 11 tools** (27 calls, recorded as JSON through the MCP's HTTP) give
the same answers, leaving out the time and build fields. `cypher_readonly` still refuses a write.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

**What the round found.**

- `symbol_context` lists a file's imports in an order that can change between two reads of the same graph. It sorts
  them by type and target, and the imports of one namespace under different specs tie. The set is the same; sorting by
  the spec too fixes the order.
- On 4 snapshots, a dry-run counts more `CALLS` and `IMPORTS` than the graph holds, as in the fifth round. The graph
  merges an edge by its key (a call by its line, an import by its spec), and counted by those keys the dry-run matches
  the graph on every snapshot.

## Seventh round: validating PR #17 on a live install (2026-10-21, build `0.2.15+20b9ed33bf9a`)

What changed since the sixth round: step 5's Go refactor (PR #17), the type service with Go on it. It is a refactor
that must change nothing in the graph. The validation had the sixth round's two phases, on the same 3 tenants and 10
snapshots:

- **before the reinstall, read-only:** dry-runs of `main` and of the branch on each snapshot, at its sha, are identical
  in every section: files, symbols, `CALLS`, `IMPORTS`, violations, endpoints, HTTP calls and warnings;
- **after the reinstall from the branch:** the refresher re-indexed the 10 snapshots with no error, and the next
  refresh re-indexed none.

**The picture of the graph** is identical before and after, in the same counts and sorted lists as the sixth round.
Only the build and the `IndexRun` nodes changed, one more run per snapshot.

**The 27 calls** give the same answers. 21 are byte for byte the same; the other 6 differ in their time and build
fields, and `symbol_context` also in the order of its imports, the sixth round's finding, still open.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

On the same 4 snapshots as before, a dry-run counts more `CALLS` and `IMPORTS` than the graph holds; counted by the
graph's merge keys, a call by its line and an import by its spec, they match on every snapshot.

## Eighth round: validating PR #20 on a live install (2026-10-21, build `0.2.15+a3e96d849f09`)

What changed since the seventh round: Go's change of behavior (PR #20). The resolver and the scanner get one answer
for a local's declared type, with Go's own scoping, and three older gaps of the type service are closed: promoted
methods, type parameters and a method's declared result (H5-D15). The graph changes on purpose, in Go's `CALLS` only.
The validation had the seventh round's two phases, on the same 3 tenants and 10 snapshots:

- **before the merge, read-only:** dry-runs of `main` and of the branch on each snapshot, at its sha. The 8 snapshots
  in other languages are identical in every section. The 2 Go ones, both public repos, differ only in `CALLS`, and
  each difference was judged at the source;
- **after the merge and a reinstall from `main`:** the refresher re-indexed the 10 snapshots with no error, and the
  next refresh re-indexed none.

**The picture of the graph** is the same before and after, except for the two Go snapshots' `CALLS`, the build and
one more `IndexRun` per snapshot. Counted by the graph's merge key (the caller, the callee and the line), the graph
before holds `main`'s dry-run and the graph after holds the branch's, on every snapshot, so what changed in the graph
is exactly what the dry-runs judged:

- **go-food-delivery-microservices** (4,327 → 4,402 calls):
  - 80 added: 44 `receiver-type` (among them methods embedded structs promote, as `Entity.Id`, and the configurators
    typed by the result `Build()` declares), 27 `receiver-type-impl` (an interface's single implementation, as
    `mongoProductRepository.GetAllProducts`) and 9 by name (values of a type parameter, found as untyped ones are);
  - 26 keep their target and are now typed, from `same-module` or `unique-name`;
  - 5 removed: three `app.Run()` calls that pointed at the method making them, and two calls on an interface, left
    out by rule (H5-D15). `app.ResolveFunc` comes from the `contracts.Application` the configurator embeds, and
    `rabbitmqProducer.PublishMessage` from the `producer.Producer` that `CreateProducer` declares. Each interface has
    more than one implementation.
- **go-vertical-slice-template** (528 calls on both sides): `app.Run()` and `app.RunTest()` pointed at the methods
  making them, and now reach `application.Application`'s, the type `Build()` declares. Four calls on a logger keep
  their target and become `receiver-type-impl`.

**The 27 calls** give the same answers: 22 are byte for byte the same, and the other 5 differ only in their time and
build fields. `symbol_context` now gives its imports in one order (PR #19), which closes the sixth round's finding.
None of the 27 reads Go's `CALLS`, so the change was also read through the MCP: `who_calls` on go-vertical-slice's
`Application.Run` answers `App.Run`, line 23, `receiver-type`.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

## Ninth round: validating PR #23 on a live install (2026-10-22, build `0.2.15+5b97077d4996`)

What changed since the eighth round: step 5's C# refactor (PR #23). C#'s type facts became typed values and C#'s
resolver asks `CsTypeIndex`. It is a refactor that must change nothing in the graph. The validation had the seventh
round's two phases, on the same 3 tenants and 10 snapshots:

- **before the merge, read-only:** dry-runs of `main` and of the branch on each snapshot, at its sha, are identical
  in every section, HTTP included. Counted by the writer's merge keys, the live graph holds `main`'s dry-run on every
  snapshot;
- **after the merge and a reinstall from `main`:** the refresher re-indexed the 10 snapshots with no error, and the
  next refresh re-indexed none.

**The picture of the graph** is identical before and after, in the same counts and sorted lists as the eighth round.
Only the build and the `IndexRun` nodes changed, one more run per snapshot.

**The 27 calls** give the same answers: 22 are byte for byte the same, and the other 5 differ only in their time and
build fields. `symbol_context` keeps its imports in one order.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

## Tenth round: validating PR #25 on a live install (2026-10-22, build `0.2.15+e3a6590925af`)

What changed since the ninth round: C#'s change of behavior (PR #25). The resolver and the scanner get one answer for
a name's declared type, with C#'s own scoping, and four older gaps of the type service are closed: a `partial` type is
one type, a method's declared result, the repo's extension methods on a typed receiver, and a type written with its
namespace and type arguments (H5-D16). The graph may change on purpose, in C#'s `CALLS` only. The validation had the
seventh round's two phases, on the same 3 tenants and 10 snapshots:

- **before the merge, read-only:** dry-runs of `main` and of the branch on each snapshot, at its sha, are identical
  in every section, the C# snapshots included: their code has none of the calls the change reaches. Counted by the
  writer's merge keys, the live graph holds `main`'s dry-run on every snapshot;
- **after the merge and a reinstall from `main`:** the refresher re-indexed the 10 snapshots with no error, and the
  next refresh re-indexed none.

**The picture of the graph** is identical before and after, in the same counts and sorted lists as the ninth round.
Only the build and the `IndexRun` nodes changed, one more run per snapshot.

**The 27 calls** give the same answers: 22 are byte for byte the same, and the other 5 differ only in their time and
build fields. `who_calls`, `symbol_context` and `impact_of` on the C# repo answer as before, as the dry-runs said.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

## Eleventh round: validating PR #27 on a live install (2026-10-26, build `0.2.15+ccc54d86dbc7`)

What changed since the tenth round: what a name means in C# (PR #27, H5-D17), a `fix(csharp)`. A type's simple name
is looked up as C# does, and a capitalized member, a nested type, a `global using`, a type parameter's constraint and
type argument, an array and an extension block are read as C# reads them. The graph may change on purpose, in C#'s
`CALLS` only. The validation had the tenth round's two phases, on the same 3 tenants and 10 snapshots:

- **before the merge, read-only (2026-10-23):** dry-runs of `main` and of the branch on each snapshot, at its sha,
  are identical in every section, and on 2026-10-26 they were found identical record by record in every list.
  Counted by the writer's merge keys, the live graph holds `main`'s dry-run on every snapshot;
- **after the merge and a reinstall from `main` (2026-10-24):** the refresher re-indexed the 10 snapshots with no
  error. The after side was taken on 2026-10-26, after the install's Neo4j container was recreated.

**The picture of the graph** is identical before and after, in the same counts and sorted lists as the tenth round.
Only the build and the `IndexRun` nodes changed, one more run per snapshot. Counted by the merge keys, the graph after
holds the branch's dry-run on every snapshot.

**The 27 calls** give the same answers: 22 are byte for byte the same, and the other 5 differ only in their time and
build fields. `cypher_readonly` still refuses a write, and no snapshot is `outdated`.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same consumer, `exact` |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

**What the round does not show.** As in the tenth round, these snapshots hold none of the calls the change reaches, so
the round checks the install, not the change. The change was judged on the corpus. A new judgment on 2026-10-26 found
one wrong edge it added there: elsa's `x.GetInput<string>(item)`, in a lambda without a type, went to a method that is
not generic. The cause is older than the PR, since a call written with type arguments was never checked against the
method's type parameters. The fix is H5-D18, in a PR of its own.

## Twelfth round: H5-D18 before its merge, on a live install (2026-10-26, build `0.2.15+ccc54d86dbc7`)

What changed since the eleventh round: nothing in the install. H5-D18 is in a working tree, not merged: which
extension method a C# call reaches when only one can serve it. The graph may change on purpose, in C#'s `CALLS` only.
This round is the read-only side before a merge, on the same 3 tenants and 10 snapshots:

- **the dry-runs** of `main` and of the branch on each snapshot, at its sha, are identical record by record in all 12
  lists;
- **the graph** holds `main`'s dry-run on every snapshot, counted by the writer's merge keys;
- **the picture of the graph** equals the eleventh round's after picture in all 15 lists, by the digests kept with that round's private evidence.

**The 27 calls.** This round is the planned run inside `pre-merge.sh`.

- **Where the calls came from.** The eleventh round's private calls file was not read, by the author's instruction.
  The 27 calls came from the original `golden.py` that the recovery rebuilt from a transcript. Their labels are the 27
  the documents name, but the list was not compared with the eleventh round's file.
- **An earlier, unplanned run.** Loading that recovered script to read its calls also ran them, a few minutes before
  the planned run: the same 27 calls, with the same write refused. It is not a round of its own. It only shows that
  the answers are stable: 26 are byte for byte the planned run's, and `atlas_status` differs only in its time fields,
  since a refresher cycle ran in between.
- **The planned run:** all 27 reached the MCP. 26 gave no error, `cypher_readonly` still refuses a write, and no
  snapshot is `outdated`.
- **Against the eleventh round:** the 5 answers that hold time fields are the five of the eleventh round. The eleventh round's answers are kept privately and were not read for this round, so the other 22 were
  **not** compared with them file by file. They are inferred the same, since the graph and the build are.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ one route, one consumer, `exact`; no `possible_consumers` |
| Q2 `http_map` | ✅ the outbound call linked; the other repo calls out to none |
| Q3 map | ✅ one `CONSUMES` on one tenant, none on the other two |
| Q4a and Q4b `impact_of` | ✅ answered, with consumers and callers |
| Q5 `ref_diff` | ✅ answered |

**What the round does not show.** As in the tenth and eleventh rounds, these snapshots hold none of the calls the change
reaches, so the round checks the install, not the change. The change was judged on the corpus and by an independent review (H5-D18 in [the decisions](decisions.md)). The after
side is the thirteenth round.

## Thirteenth round: validating PR #30 on a live install (2026-10-27, build `0.2.15+ccc54d86dbc7` to `0.2.15+2aa181ba2eec`)

What changed since the twelfth round: H5-D18 is merged (PR #30): which extension method a C# call reaches when only one
can serve it. The graph may change on purpose, in C#'s `CALLS` only. The same 3 tenants and 10 snapshots.

- **Before the reinstall, read-only:** the dry-runs of `main` (`82032e8`) and of the merge (`2aa26b0`) on each snapshot,
  at its sha, are identical section by section in all 10. The live graph holds `main`'s dry-run on every snapshot,
  counted by the writer's merge keys (0 mismatching). The "before" was taken afresh, not copied from an earlier round:
  10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules, 0 violations.
- **After the author's reinstall from `main`:** the refresher re-indexed the 10 snapshots, one run each, `ok` and with
  no error, and no snapshot is `outdated`.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round does not show.** As in the tenth to twelfth rounds, these snapshots hold none of the calls the change
reaches, so the round checks the install, not the change. The change was judged on the corpus and by an independent
review of a seeded sample (H5-D18 in [the decisions](decisions.md)).

**How it was taken.** The steps of `docs/indexer/method.md` §4.7 and §4.8, by hand. `indexer/scripts/live/validate.sh`
(PR #31) gave the same counts for the after side on a copy of the folder.

## Fourteenth round: validating PR #47 on a live install (2026-10-29, build `0.2.15+2aa181ba2eec` to `0.2.15+665c35e2b90b`)

What changed since the thirteenth round: Python's step 5 is merged (PRs #42, #44, #45 and #47, with the `fix(python)`
#46). The graph may change on purpose, in Python's `CALLS` and the routes its scanner finds. The same 3 tenants and 10
snapshots.

- **The install was behind `main`.** It still ran the package PR #30 merged: #44, #45 and #46 changed it and were not
  reinstalled, so none had a round of its own. The author chose one pair for all of them: the installed code
  (`ed80de7`, #43's merge, whose package is #30's) against the branch (`de3de69`).
- **Before the reinstall, read-only:** the dry-runs of the installed code and of the branch on each snapshot, at its
  sha, are identical section by section in all 10. The live graph holds the installed code's dry-run on every snapshot
  (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`9a7a585`):** the refresher re-indexed the 10 snapshots, `ok` and with no
  error.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round does not show.** These snapshots hold no Python file, so the round checks the install, not the change,
for all four PRs. They were judged on the corpus, the micro set with its per-site attribution, and by an independent
review of seeded samples (H5-D22 to H5-D27 in [the decisions](decisions.md)).

**How it was taken.** `indexer/scripts/live/validate.sh`, on its first real run. It copied the whole `indexer/`, and an
IDE watching the folder built a test fixture's C# project in the copy, so its check of the copy failed; it now copies
only `indexer/aidd_indexer`, the package a dry-run imports (in #47).

## Fifteenth round: validating PR #49 on a live install (2026-10-30, build `0.2.15+665c35e2b90b` to `0.2.15+6d3486cc3a3b`)

What changed since the fourteenth round: H5-D28 is merged (PR #49). A Python absolute import is looked for under the
directory its file's package runs from, and a method a class of the repo declares past a base outside it is found by
name. The graph may change on purpose, in Python's `IMPORTS` and `CALLS` only. The same 3 tenants and 10 snapshots.

- **Before the reinstall, read-only:** the install ran `main`'s code (`c4f1b8d`). The dry-runs of `main` and of the
  branch (`69f5faf`) on each snapshot, at its sha, are identical section by section in all 10. The live graph holds
  `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules,
  0 violations.
- **After the author's reinstall from `main` (`b233676`):** the refresher re-indexed the 10 snapshots, `ok` and with no
  error.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round does not show.** These snapshots hold no Python file, so the round checks the install, not the change.
The change was judged on the corpus, the micro set and an independent review of seeded samples (H5-D28 in
[the decisions](decisions.md)).

## Sixteenth round: validating PR #51 on a live install (2026-10-30, build `0.2.15+6d3486cc3a3b` to `0.2.15+bad2ba9c1832`)

What changed since the fifteenth round: PR #51 is merged. A Python star import binds what CPython binds: the module's
`__all__`, or its public names, with a later binding holding a name. The graph may change on purpose, in Python's
`CALLS` only. The same 3 tenants and 10 snapshots.

- **Before the reinstall, read-only:** the install ran `main`'s code (`b61488a`). The dry-runs of `main` and of the
  branch (`6abfa81`) on each snapshot, at its sha, are identical section by section in all 10. The live graph holds
  `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules,
  0 violations.
- **After the author's reinstall from `main` (`71d6185`):** the refresher re-indexed the 10 snapshots, `ok` and with no
  error.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round does not show.** These snapshots hold no Python file, so the round checks the install, not the change.
The change was judged on the corpus, the micro set and an independent review of seeded samples (the star imports'
section of `docs/handoffs/H5-indexer-refactor.md`).

## Seventeenth round: validating PR #53 on a live install (2026-10-30, build `0.2.15+bad2ba9c1832` to `0.2.15+cd952c66db8a`)

What changed since the sixteenth round: PR #53 is merged. The resolver gives one `CALLS` edge per caller, callee, line
and method, with the strongest strategy of the calls that give it, and the writer creates each edge. The graph may
change on purpose, in `CALLS` only. The same 3 tenants and 10 snapshots.

- **Before the reinstall, read-only:** the install ran `main`'s code (`c1ca087`). The branch's dry-runs (`1e2eda2`) lose
  142 repeated records in 4 snapshots, and in one of them 2 edges take a stronger strategy; every other section is the
  same as `main`'s. The live graph holds `main`'s dry-run on every snapshot, strategies included (0 mismatching):
  10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`5586326`):** the refresher re-indexed the 10 snapshots, `ok` and with no
  error.

**The picture of the graph** is identical in 12 of its 15 lists. Two differ only in the build, on all 10 snapshots, and
in the `IndexRun` counts. The third, `CALLS`, differs in the 2 edges the change gives the strongest strategy: a
`same-module` and a `unique-name` become `receiver-type-impl`. The count of edges is the same, since no live line
reaches one target for two methods. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** Unlike the two before it, it checks the change itself: the 2 live edges that showed a weaker
strategy are the ones the branch's dry-run corrects. The edges the old writer lost, two methods of one line, have no
live case; they were judged on the micro set.

**How it was taken.** The before was sealed on its third run, and the two runs that failed showed two defects of the
live check, which #53 fixes:
- `graph_vs_dry.py` compared the graph before the reinstall with head's dry-run, not with `main`'s strategies, so it
  failed on the 2 edges above. It now takes the before alone.
- An IDE that had loaded the C# projects of the deleted copy wrote their `obj/` back to its paths, and `dryrun-live.sh`
  reused two snapshot folders that held only that output: their dry-runs had no file, which the graph check caught. The
  snapshots are now copied to a folder no earlier run used, and each copy is checked against its sha.

## Eighteenth round: validating PR #55 on a live install (2026-10-30, build `0.2.15+cd952c66db8a` to `0.2.15+0afc39c36d2f`)

What changed since the seventeenth round: PR #55 is merged. A call on a receiver reaches the wrapper of the class the
type index finds declaring the method, up the receiver's MRO, and Python's scanner keeps no classes of its own. The
graph may change on purpose, in Python's outbound HTTP calls only. The same 3 tenants and 10 snapshots.

- **Before the reinstall, read-only:** the install ran `main`'s code (`a7e631a`). The dry-runs of `main` and of the
  branch (`f4b4a42`) on each snapshot, at its sha, are identical section by section in all 10. The live graph holds
  `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules,
  0 violations, the same picture as the seventeenth round's after.
- **After the author's reinstall from `main` (`167f3d4`):** the refresher re-indexed the 10 snapshots, `ok` and with no
  error.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round does not show.** These snapshots hold no Python file, so the round checks the install, not the change.
The change was judged on five cases checked on both sides, the corpus, the micro set and an oracle over the 15 Python
repos (the client wrappers' section of `docs/handoffs/H5-indexer-refactor.md`).

## Nineteenth round: validating PR #57 on a live install (2026-10-30, build `0.2.15+0afc39c36d2f` to `0.2.15+3940c91fecfd`)

What changed since the eighteenth round: PR #57 is merged. The graph writer's session, the linker's reads and writes
and the snapshots' bookkeeping move to modules of their own, and the dry-run's payload leaves `cli.py`: a refactor,
so the graph may not change. The same 3 tenants and 10 snapshots.

- **Before the reinstall, read-only:** the install ran `main`'s code (`c1b355d`). The dry-runs of `main` and of the
  branch (`29a91cd`) on each snapshot, at its sha, are identical section by section in all 10. The live graph holds
  `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules,
  0 violations.
- **After the author's reinstall from `main` (`93a4de1`):** the refresher re-indexed the 10 snapshots with the moved
  writer, `ok` and with no error.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching),
strategies included.

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** The moved writer writes the same graph: every node and edge it writes, read back against
the dry-runs, and the answers the MCP gives from them.

## Twentieth round: validating PR #58 on a live install (2026-10-31, build `0.2.15+3940c91fecfd` to `0.2.15+98ca8774b8e7`)

What changed since the nineteenth round: PR #58 is merged. The resolver's edge records move to a module of their own:
a refactor, so the graph may not change. The same 3 tenants and 10 snapshots.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`93a4de1`). The dry-runs of `main`
  and of the PR's head (`fae0687`) on each snapshot, at its sha, are identical section by section in all 10. The live
  graph holds `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`,
  351 modules, 0 violations.
- **After the author's reinstall from `main` (`e30c118`, whose package is the PR head's):** the refresher re-indexed
  the 10 snapshots with the moved records, `ok` and with no error, all of them after the reinstall.

**The picture of the graph** is identical in 13 of its 15 lists. The other two differ only in the build, on all 10
snapshots, and in the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching),
strategies included.

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** The resolver with its records moved writes the same graph, and the MCP gives the same
answers from it. A first reinstall did not reach the install, and the `after` refused it, since the installed code was
still `main`'s; a second one did. The `after` accepts an `ok` run of each snapshot since the `before`, which a refresh
before the reinstall would also give: here every run came after it.

## Twenty-first round: validating PR #59 on a live install (2026-10-31, build `0.2.15+98ca8774b8e7` to `0.2.15+48b1542d7ce8`)

What changed since the twentieth round: PR #59 is merged. The types' bases of the repo are `EXTENDS` and `IMPLEMENTS`,
and a `CALLS` edge says whether it may dispatch (`virtual`): a change of the graph. The same 3 tenants and 10 snapshots.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`e30c118`). The dry-runs of `main`
  and of the PR's head (`247b4de`) on each snapshot, at its sha, are identical section by section in 8. The two C#
  snapshots gain only their types' edges, 23 and 20 (18 and 14 of them `IMPLEMENTS`); their `CALLS` are the same, and
  none is a call on `base` or `super`, so every one may dispatch. The live graph holds `main`'s dry-run on every
  snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 351 modules, 0 violations, no type edge.
- **After the author's reinstall from `main` (`7884cbb`, whose package is the PR head's):** the refresher re-indexed
  the 10 snapshots with the new build, `ok` and with no error. The `after` now waits for it: it refuses until every
  snapshot holds a build other than the `before`'s, and here none held the old one.

**The picture of the graph** is identical in 12 of its 16 lists. `CALLS` are the same 23,682 edges, whose `virtual`
goes from unset to true; the types' edges go from 0 to 43 (32 `IMPLEMENTS`, 11 `EXTENDS`), on the two C# snapshots;
the snapshots and the labels differ only in the build and the `IndexRun` counts. The graph after holds the branch's
dry-run on every snapshot (0 mismatching), strategies, `virtual` and the types' edges included.

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** The writer writes the types' edges and `virtual` as the dry-runs give them, and the MCP's
answers do not change, since no tool reads them before F1.16's `feat(mcp)`. The live snapshots make no call on `base`
or `super`, so the calls that do not dispatch are proven on the micro set.

## Twenty-second round: validating PR #60 on a live install (2026-10-31, build `0.2.15+48b1542d7ce8` to `0.2.15+e19400dc64a7`)

What changed since the twenty-first round: PR #60 is merged. A call that does not dispatch reaches no implementation
and no homonym, a Python `super()` reaches what follows the caller's class in each MRO, and two types of one name in
one file get no types' edges: a change of the graph. The same 3 tenants and 10 snapshots.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`7884cbb`). The dry-runs of `main`
  and of the PR's head (`5d2943b`) on each snapshot, at its sha, are identical section by section in all 10: no live
  snapshot makes a call on `base` or `super`, or declares two types of one name in a file. The live graph holds
  `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 43 types'
  edges, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`8fa9bf8`, whose package is the PR head's):** the refresher re-indexed
  the 10 snapshots with the new build, `ok` and with no error.

**The picture of the graph** is identical in 14 of its 16 lists; the snapshots and the labels differ only in the build
and the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** The install takes the new build and writes the same graph, since the live snapshots hold
none of what the change touches: the change is proven on the micro set and against CPython.

## Twenty-third round: validating PR #61 on a live install (2026-10-31, build `0.2.15+e19400dc64a7` to `0.2.15+b202477c2793`)

What changed since the twenty-second round: PR #61 is merged. A method a dispatching call may run instead of another
`OVERRIDES` it, as the instance's language says: a change of the graph. The same 3 tenants and 10 snapshots.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`8fa9bf8`). The dry-runs of `main`
  and of the PR's head (`668bbc0`) on each snapshot, at its sha, are identical section by section in 8. The two C#
  snapshots gain only `OVERRIDES` in their `hierarchy`, 15 and 17, every one from a method to a method; their `CALLS`
  are the same. The live graph holds `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682
  `CALLS`, 15,890 `IMPORTS`, 43 types' edges, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`1873a8d`, whose package is the PR head's):** the refresher re-indexed
  the 10 snapshots with the new build, `ok` and with no error.

**The picture of the graph** is identical in 13 of its 16 lists. The hierarchy goes from 43 edges to 75, the 32
`OVERRIDES` the dry-runs gave, and nothing else in it changes; the snapshots and the labels differ only in the build
and the `IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 27 calls** all reached the MCP. 26 gave no error and `cypher_readonly` still refuses a write. 22 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** The writer writes `OVERRIDES` as the dry-runs give them, and the MCP's answers do not change,
since no tool reads the edges before F1.16's `feat(mcp)`. Two calls join the list for it: `who_calls` and `impact_of` on
a C# method that implements an interface method, with no caller of its own and three dispatching calls to the
interface's.

## Twenty-fourth round: validating PR #62 on a live install (2026-10-31, build `0.2.15+b202477c2793` to `0.2.15+27df2af8e1ef`)

What changed since the twenty-third round: PR #62 is merged. A dispatching call to a method others override keeps its
receiver's type when a supertype declares the method, and an override the receivers on which it may run: a change of
the graph. The same 3 tenants and 10 snapshots, and 29 calls: the two the last round added ask `who_calls` and
`impact_of` about a C# method that implements an interface's, which F1.16's `feat(mcp)` changes.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`1873a8d`). The dry-runs of `main`
  and of the PR's head (`acc6822`) on each snapshot, at its sha, are identical section by section in 8. The two C#
  snapshots gain only `receivers`: on their 15 and 17 `OVERRIDES` (17 and 22 types), and on one call of the first.
  Without the field, their `calls` and `hierarchy` are the same. The live graph holds `main`'s dry-run on every
  snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 75 types' and overrides' edges, 351
  modules, 0 violations.
- **After the author's reinstall from `main` (`0c66ae0`, whose package is the PR head's):** the refresher re-indexed
  the 10 snapshots with the new build, `ok` and with no error.

**The picture of the graph** is identical in 12 of its 16 lists. `CALLS` and the hierarchy hold the same edges, the 32
`OVERRIDES` and one call now with their `receivers`; the snapshots and the labels differ only in the build and the
`IndexRun` counts. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 29 calls** all reached the MCP. 28 gave no error and `cypher_readonly` still refuses a write. 24 answers are the
same field by field, and the other 5 differ only in their time, build and refresh fields.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same, but for the snapshots' `indexed_at` |

**What the round shows.** The writer writes the receivers as the dry-runs give them, and the MCP's answers do not
change, since no tool reads them before F1.16's `feat(mcp)`.

## Twenty-fifth round: validating PR #63 on a live install (2026-10-31, build `0.2.15+27df2af8e1ef`, unchanged)

What changed since the twenty-fourth round: PR #63 is merged, and closes F1.16. `who_calls` lists a method's
dispatching callers and what it overrides, and `impact_of` follows a dispatch at any hop and marks a caller
`via_ambiguous` only when every chain from it has a hop resolved by name among several. Only the MCP changes, which the
build does not fingerprint. The same 3 tenants and 10 snapshots, and 29 calls.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`0c66ae0`). The dry-runs of `main`
  and of the PR's head (`1a0a2d7`) on each snapshot, at its sha, are identical in all 10. The live graph holds `main`'s
  dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 75 types' and
  overrides' edges, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`3bf8859`, whose package is the PR head's):** the build is the same, so
  the refresher re-indexed nothing, and `main`'s `validate.sh after` waited for runs that never come. It ran with the
  branch's, which takes this case (PR #64): no snapshot ran since the before, and the 10 hold the before's build.

**The picture of the graph** is identical in all 16 of its lists, and the graph holds the branch's dry-run on every
snapshot (0 mismatching).

**The 29 calls** all reached the MCP. 28 gave no error and `cypher_readonly` still refuses a write. 23 answers are the
same field by field, `atlas_status` differs only in its time fields, and 5 differ as the PR says:

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same callers, hops and `via_ambiguous`; each of the 1 and 5 callers gains `via_dispatch: false` |
| Q5 `ref_diff` | ✅ the same |

- **`who_calls` on Q4a's method**, which implements an interface's method, gains one dispatching caller and the
  interface's method in `overrides`. The dispatching call is its one caller's: a call on the interface, which also
  reaches the method directly, since it is the interface's only implementer (`receiver-type-impl`): the site is listed
  twice, which TD-036 registers.
- **`who_calls` on the C# method with no caller of its own** gains 3 dispatching callers and the interface's method in
  `overrides`. One of them is the method itself: a call in its body on the interface may run it again.
- **`impact_of` on that method** goes from 0 internal callers to 3, each `via_dispatch: true`: the other two
  dispatching callers at hop 1, and a caller of them at hop 2. It leaves the method itself out, as it leaves out every
  target. No route reaches them.

**What the round shows.** The MCP reads the dispatch the graph has held since #61 and #62, and the graph does not
change. A change the build does not fingerprint leaves no run to wait for, which the live check now knows.

## Twenty-sixth round: validating PR #67 on a live install (2026-11-01, build `0.2.15+27df2af8e1ef` to `0.2.15+87152c41d4e2`)

What changed since the twenty-fifth round: PR #67 is merged, TS's scope index. Nothing in the extraction reads it yet,
so the graph does not change; its modules are under `languages/`, which the build fingerprints, so the build changes
and the refresher re-indexes every snapshot. The same 3 tenants and 10 snapshots, and 29 calls.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`2279bd0`). The dry-runs of `main`
  and of the PR's head (`c031257`) on each snapshot, at its sha, are identical in all 10. The live graph holds `main`'s
  dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 75 types' and
  overrides' edges, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`f7208c5`, whose package is the PR head's):** the 10 snapshots ran since
  the before, all ok, and each holds the new build.

**The picture of the graph:** 14 of its 16 lists are identical, and the other 2 differ only in the build and the index
runs' counts. The graph holds the dry-run on every snapshot (0 mismatching).

**The 29 calls** all reached the MCP. 28 gave no error and `cypher_readonly` still refuses a write. 24 answers are the
same field by field, and 5 differ only in their time, build and refresh fields:

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

**What the round shows.** A refactor that adds code the build fingerprints changes the build and every snapshot's
time, and nothing of the graph.

## Twenty-seventh round: validating PR #68 on a live install (2026-11-01, build `0.2.15+87152c41d4e2` to `0.2.15+ccfcfcc426f3`)

What changed since the twenty-sixth round: PR #68 is merged, TS's type facts and one `TypeIndex` for its three ids.
TS's `call_receiver` answers nothing yet, so the resolver asks none of the type hooks; the HTTP scanner asks the scope
and type indexes what it answered alone, and no site changes. Its modules are under `languages/`, which the build
fingerprints, so the build changes and the refresher re-indexes every snapshot. The same 3 tenants and 10 snapshots,
and 29 calls.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`f7208c5`). The dry-runs of `main`
  and of the PR's head (`05e9bb5`) on each snapshot, at its sha, are identical in all 10. The live graph holds `main`'s
  dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890 `IMPORTS`, 75 types' and
  overrides' edges, 351 modules, 0 violations.
- **After the author's reinstall from `main` (`b06cbfb`, whose tree is the PR head's):** the 10 snapshots ran since the
  before, all ok, and each holds the new build.

**The picture of the graph:** 14 of its 16 lists are identical, and the other 2 differ only in the build and the index
runs' counts. The graph holds the dry-run on every snapshot (0 mismatching).

**The 29 calls** all reached the MCP. 28 gave no error and `cypher_readonly` still refuses a write. 24 answers are the
same field by field, and 5 differ only in their time, build and refresh fields:

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

**What the round shows.** The HTTP scanner's answers read through TS's scope and type indexes keep every live site, as
they keep the corpus's, the hold-out's and the micro set's.

## Twenty-eighth round: validating PR #69 on a live install (2026-11-01, build `0.2.15+ccfcfcc426f3` to `0.2.15+474c5668f80c`)

What changed since the twenty-seventh round: PR #69 is merged, TS's `EXTENDS`, `IMPLEMENTS` and `OVERRIDES`, and an
abstract method as a method symbol: a change of the graph. The same 3 tenants and 10 snapshots, and 29 calls.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`b06cbfb`). The dry-runs of `main`
  and of the PR's head (`e7e24b1`) on each snapshot, at its sha, are identical section by section in 7, the ones with
  no TS or JS. The two refs of a JS and TS repo gain only hierarchy edges, 131 and 130: 102 `IMPLEMENTS` from a class
  to an interface, and 29 and 28 `EXTENDS` from a class to a class. The TS repo gains its 2 abstract methods, 24
  hierarchy edges (9 `EXTENDS`, 4 `IMPLEMENTS`, 11 `OVERRIDES`, one of them to an abstract method), and its `CALLS`
  change at 2 sites:
  - a call on `this` in a base class, which reached a subclass's method as the only one of its name, reaches the base's
    abstract method, the declaration TypeScript's checker names;
  - a call on `this`, which reached the only method of its name, the checker's, reaches none: the abstract method it
    implements is a second one, and the caller's class extends it through a name the repo's `tsconfig.json` `paths`
    map, which the type index does not read (TD-038). It comes back with TD-038 and TS's change of behavior.

  The live graph holds `main`'s dry-run on every snapshot (0 mismatching): 10,607 symbols, 23,682 `CALLS`, 15,890
  `IMPORTS`, 75 types' and overrides' edges, 351 modules, 0 violations.
- **Against TypeScript's checker** (`checks/ts_heritage.py` on the 3 TS snapshots, read and typed, nothing run): of
  their 510 heritage clauses, the index names the checker's declaration at 274, every new type edge, and another at
  none; neither names one of the repo at 217. Of the checker's 19 the index does not reach, 7 come through
  `tsconfig.json` `paths` (TD-038), and 12 name a type a hand-written `.d.ts` declares, which discovery skips as
  generated: TD-038's text puts that file after a `.js`, where it is not read at all.
- **After the author's reinstall from `main` (`4c57394`, whose tree is the PR head's):** the 10 snapshots ran since the
  before, all ok, and each holds the new build.

**The picture of the graph** is identical in 10 of its 16 lists. The symbols go from 10,607 to 10,609, the 2 abstract
methods; `CALLS` from 23,682 to 23,681, the TS repo's 2 sites; the hierarchy from 75 edges to 360, the 285 the dry-runs
gave. The counts per snapshot change with them, the labels with them and the `IndexRun` counts, and the snapshots
only in the build. The graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 29 calls** all reached the MCP. 28 gave no error and `cypher_readonly` still refuses a write. 24 answers are the
same field by field, and 5 differ only in their time, build and refresh fields:

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same |

**What the round shows.** The writer writes TS's hierarchy as the dry-runs give it, and each type edge is the
declaration TypeScript's checker resolves its clause to. It also found TD-040: a symbol's signature loses the `>` that
closes a type at its end (`Promise<void>` reads `Promise<void`), on 296 TS and 49 C# symbols of the live graph,
which `main` has.
