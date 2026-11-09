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
own (`workspace_map`) in F2.6.

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

**Obtained (2026-10-03):** ⚠️ answered, with a limit. In the BFF's repo the model took the outbound adapter as the target. The
**across repos** part came right: the route `GET /v1/password-policy` is exposed by `<project-b>` and consumed only by the BFF
(`exact`, no `possible_consumers`), and the route the BFF re-exposes has no indexed consumer. The **within the repo** part showed
the limit of resolution by name: `who_calls` returned only the adapter's 5 tests, because production goes through an interface
and its call has several candidates of one name (the interface method, the concrete one, the tests' fakes), so `unique-name` fails
and no `CALLS` edge exists. The model rebuilt the chain (handler → use case → port → adapter) by reading, and said the graph did
not prove it. That is the metric that triggers SCIP (ADR-002, F1.2).

**2nd round (2026-10-03):** ✅ `impact_of` end to end. The blind spot, a receiver that is a struct field resolved by name only,
led to F0.7.1: the receiver's static type in Go (`receiver-type`), production never resolving to a test, and `impact_of`
separating production callers from test ones. F0.7.3 resolved an interface with a single implementer. Known limit: `CALLS` is
resolved by name (same-file → same-module → unique-name), so in repos with many homonyms the `-ambiguous` paths inflate the
radius: it is SCIP's trigger (ADR-002, F1.2).

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

**Obtained (2026-10-03):** ✅ the tool answered and the model read it right, including the reverse of the expected case: the
indexed branch was **behind** `main` (14 routes against 31), and locally the branch already had `main` merged. `ref_diff`
compares the **indexed** commits (remote refs), not the local checkout, so the tool now returns `snapshots` (each ref's indexed
sha and `indexed_at`) and a `note` about local refs: the lag is in the answer, not in the model's reading. It also listed, on
`main`, 4 calls to `<project-c>`, 3 of them without `linked_to` because of `{param}/{param}`: the recall gap already recorded.

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

## How to run a round

A round checks, on the live install, that a change to the graph, the linker or the MCP left the answers as they should be. The
procedure is `docs/indexer/method.md` §1 (steps 9 and 11), §4.7 (before the merge), §4.8 (after) and §4.9 (the steps of an agent).

- **What it takes:** the install's 3 tenants and 10 snapshots, and the 29 golden calls (27 until the 23rd round), kept in a private
  file, `golden-calls.json`, sealed by `SHA256SUMS` and never regenerated; its shape is `indexer/scripts/live/golden-calls.example.json`.
  The questions are labelled Q1 (`who_consumes`, in lower case and in the code's case), Q2 (`http_map`), Q3 (the map), Q4a and Q4b
  (`impact_of`) and Q5 (`ref_diff`).
- **How:** `validate.sh before`, the author's merge and reinstall, `validate.sh after`; then `indexer/scripts/live/round.py` drafts the
  round and its history line from the in-flight folder, with counts only, never a label or a name. What passes is §4.8's.
- **Where it is recorded:** the history line goes into `docs/history.md`. The round replaces the last one of this file (the final section
  below): its numbers stay in its history line and its text in git (`git show before-golden-questions-condensation:docs/golden-questions.md` holds all 43). The next
  round's "before" is the last round's picture, so the last round stays whole.
- **When it found something:** add a row to "Findings" with what it found and what became of it. A round that found nothing adds nothing.

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

The text of the 5th to the 43rd round is in `git show before-golden-questions-condensation:docs/golden-questions.md`; what they
found is in "Findings" below.

---

## Findings

What a round found, and what became of it. A round that found nothing is not here.

| Round (PR) | What it found | What became of it |
|---|---|---|
| 5th (#5) | The first reinstall gave the TS repo 51 new calls through the app's wrappers, and 34 were wrong: options in a local fell back to the default GET, and a query in parentheses became `{param}`. The corpus did not have those shapes. Also: `python -m aidd_indexer.cli` in an image with `WORKDIR=/app` runs the image's code, not the mounted one | Fixed in increment 12 (`dfbc8d7`), with a fixture case. The comparison dry-run needs `-w` on the mounted code, and the version printed on its first line says which code ran |
| 6th (#7) | `symbol_context` listed a file's imports in an order that could change between two reads: it sorted by type and target, and the imports of one namespace under different specs tied | Fixed: it sorts by the spec too |
| 6th and 7th (#7, #17) | On 4 snapshots a dry-run counted more `CALLS` and `IMPORTS` than the graph holds, because the graph merges an edge by its key | Count by the merge key: a call by its line, an import by its spec. Then they match on every snapshot |
| 11th (#27) | A new judgment found a wrong edge the change added: elsa's `x.GetInput<string>(item)`, in an untyped lambda, went to a method that is not generic. The cause is older than the PR: a call written with type arguments was never checked against the method's type parameters | H5-D18, in a PR of its own |
| 12th (H5-D18) | The calls came from a `golden.py` rebuilt from a transcript, the eleventh round's private file was not read, and loading the script ran the 27 calls once more | The calls file is sealed by `SHA256SUMS` and never regenerated (`docs/indexer/method.md` §4.7) |
| 14th (#47) | The first real run of `validate.sh` copied the whole `indexer/`, and an IDE built a test fixture's C# project in the copy, so its check of the copy failed | It copies only `indexer/aidd_indexer`, the package a dry-run imports (#47) |
| 17th (#53) | Two defects of the live check: `graph_vs_dry.py` compared the graph before the reinstall with head's dry-run, not with `main`'s strategies; and an IDE wrote the `obj/` of the deleted copy's C# projects back, so `dryrun-live.sh` reused two snapshot folders that held only that | Fixed in #53: it takes the before alone, and the snapshots are copied to a folder no earlier run used, each checked against its sha |
| 25th (#63) | A call on an interface that is the single implementer's is listed twice: by `receiver-type-impl` and by the dispatch of the implementer's `OVERRIDES` | TD-036, due in H5 step 6 |
| 28th (#69) | A symbol's signature loses the `>` that closes a type (`Promise<void>` reads `Promise<void`), on 296 TS and 49 C# symbols. Against TypeScript's checker, of 510 heritage clauses the index names the checker's declaration at 274 and neither names one of the repo at 217; of the 19 it does not reach, 7 come through `tsconfig.json` `paths` and 12 name a type a hand-written `.d.ts` declares | TD-040 closed by #70; TD-038 by #72 (`paths`); TD-041 by #79 (declaration files) |
| 29th (#70) | The live tools saw no change of a symbol's property: `dry_sections.py` keys a symbol by its id, the picture lists no signature and `graph_vs_dry.py` compares edges only | Fixed in #71; the 30th round took it |
| 41st (#83) | `repo_map`'s module `loc` is the sum of each file's lines taken once per symbol the file declares, so it grew (731,592 to 734,345) with no file changed: the query counts a file once for each of its symbols | Open: a `fix(mcp)` in its own PR |

---

## Forty-third round: validating PR #85 on a live install (2026-11-08, build `0.2.15+c95fd6e984ba` to `0.2.15+01040a67fd25`)

What changed since the forty-second round: PR #85 is merged, a `fix(typescript)` that has TS's HTTP scanner find a client
by the type its receiver declares (a class of the repo, whose wrappers the call reaches, or a type of a client library
such as `AxiosInstance`), the last PR of TS's step 5. The same 3 tenants and 10 snapshots, and 29 calls.

- **Before the reinstall and the merge, read-only:** the install ran `main`'s code (`09147a4`). The dry-runs of `main`
  and of the PR's head (`55087a2`) on each snapshot, at its sha, are identical in all 10 (0 failed), and the live graph
  held `main`'s dry-run on every snapshot (0 mismatching): 10,711 symbols, 23,440 `CALLS`, 15,961 `IMPORTS`, 404 types'
  and overrides' edges, 351 modules, 0 violations. The corpus, the hold-out and the micro set had given `0 repo(s)
  differ` in CI.
- **After the author's reinstall from `main` (`8748bab`, whose tree is the PR head's):** the 10 snapshots ran since the
  before, all ok, each holds the new build, and `after` passed at the first run.

**The picture of the graph** differs in 2 of its 16 lists, the labels' `IndexRun` counts and the snapshots' build, and in
nothing else: the 14 others, the symbols (10,711), the `CALLS` (23,440), the hierarchy edges (404), the `IMPORTS`
(15,961), the modules (351), the 286 endpoints, the 160 HTTP calls and the 0 violations among them, are the same. The
graph after holds the branch's dry-run on every snapshot (0 mismatching).

**The 29 calls** all reached the MCP. 28 gave no error and `cypher_readonly` still refuses a write. 24 answers are the
same field by field. 5 differ only in their time, build and refresh fields: `atlas_status`, the `ref_diff` of the TS
snapshots and the `repo_map` of the TS, Go and accrual snapshots (the before was taken 908 minutes after the snapshots
were indexed, so the tenants went from stale to fresh); no `repo_map` changes in its symbols, since the PR adds none.

| Q | Result |
|---|---|
| Q1 `who_consumes`, in lower case and in the code's case | ✅ the same |
| Q2 `http_map` | ✅ the same |
| Q3 map | ✅ the same on the 3 tenants |
| Q4a and Q4b `impact_of` | ✅ the same |
| Q5 `ref_diff` | ✅ the same but its time fields |

**What the round shows.** The new rule changes no call and no route of the live repos, as it changed none of the
corpus's: the graph after is the graph before but for the build, so the PR's gain is in the cases it checks against
TypeScript's checker, and what it keeps is the macro graph, the micro graph and what the golden calls ask.
