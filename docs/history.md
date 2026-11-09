# History

> The project's milestones, one per line, with the date and the PR they came in.
>
> - The full text of each entry, as it was written in the ROADMAP's "Where we are" section, is in
>   `git show 1d73bb0:docs/ROADMAP.md` (in Portuguese).
> - The narrative of each corpus increment is in `git show 1d73bb0:docs/corpus-report.md`.
>
> The decisions are in `docs/decisions.md`; the current state, in the ROADMAP.
>
> `#NN` in the docs is `praticis/aidd-stack#NN`; a reference to another repository is written in full.

## Phase 0: the foundation (PR #1, merged on 2026-10-13)

- 2026-09-09: D1, Neo4j Community (no ADR-001 file was written); Neo4j and `neo4j-init` in the compose file; schema v1 in
  `neo4j/SCHEMA.md`.
- 2026-09-10: the compose stack comes up; credentials centralized in `.env`; `install-check.sh` passes; the MCP
  becomes `atlas` (D6).
- 2026-09-10: F0.3, the indexer validated on the real atlas with a Go repo from the portfolio; `AIDD_TENANT` required
  across the whole stack (D7).
- 2026-09-11: a pause to design the indexing process (`docs/indexing-process.md`, D8–D11). Then F0.3.5: `atlas.yaml`,
  `aidd plan/bootstrap/refresh` and refs through `git archive`.
- 2026-09-11: a clean install validated end to end: 6 repos and 22 snapshots in 26 s. The baseline of resolution by
  name is ~40 % of Go call sites, the metric SCIP has to beat.
- 2026-09-11: GC validated; the indexer does its own fetch; D12 (install ≠ update); continuous update validated
  (U1–U3.1).
- 2026-09-11: incident: a build without grammars wrote empty snapshots as a success. The cause was
  `tree-sitter-language-pack` downloading grammars at run time. Fixes:
  - pinned versions;
  - the grammars downloaded at build time;
  - `aidd selftest`;
  - rc=4 when a grammar is missing.
- 2026-09-11: F0.6, the `atlas` MCP v0 (`atlas_status`, `repo_map`, `find_symbol`, `who_calls`, `symbol_context`,
  `cypher_readonly`), validated in Claude Code (F0.6.1).
- 2026-09-11: F0.8, the `scan` skill v2 over the atlas, with an explicit fallback; validated in both cases (F0.8.1).
- 2026-09-12: F0.4, the HTTP integrations extractor v0, with routes and outbound calls in Go, TS, C# and Python and
  the `http_map` and `who_consumes` tools (indexer 0.2.0). Calibrated on a public corpus of 15 repos.
- 2026-09-12: the `docs/indexer-evolution.md` guide and the handoffs H1 (reference apps) and H2 (public corpus).
- 2026-09-14: ADR-002 (tree-sitter as the base, SCIP as an enrichment) and ADR-003 proposed (a core plus
  per-language modules, conventions as extensions).
- 2026-09-15: the first multi-tenant install (`AIDD_TENANT=auto`).
- 2026-09-17: F0.4.1, partial on a multi-tenant .NET environment; F0.4.4, the ADR-003 refactor done, with corpus and
  fixtures identical.
- 2026-09-25: F0.5, the linker materializes `CONSUMES`/`CALLED_FROM` by `path_key` and method, with ties broken by
  hints.
- 2026-09-29: F0.5 validated on the portfolio; F0.5.1 closed; F0.7 (CALLS by receiver type) in progress.
- 2026-10-03: F0.7 closed and **Phase 0 done**: golden questions answered by the graph in Go and in the reference
  .NET pair.
- 2026-10-03: F0.7.2 (C# hooks: `call_receiver`, `implementations`), `DEPENDS_ON` by manifest (F0.5.1), F0.3.6 (ref
  policy) and F0.4.5 (conventions with `route_patterns`, `Violation` in the MCP; indexer 0.2.6).
- 2026-10-03: a GC bug on a re-index of the same commit (0.2.7); a handler in another file of the package; endpoint
  by `path_key` (0.2.8).
- 2026-10-12: more expressive conventions (pattern × architecture); F0.4.2 .NET with the `dotnet-praticis` extension
  and the `csharp-praticis-*` fixtures (0.2.10). The fixtures record the .NET gaps for F0.7.3.
- 2026-10-12: security and operations: exposure closed (gateway, ports on localhost) and the refresher in a container
  with mirrors (D15).
- 2026-10-12: `scan` closed over the foundation (0.2.11); the design of the knowledge track (D16, D17).

## Project knowledge (PR #2, merged on 2026-10-14)

- 2026-10-13: fixes from the first use in code review (0.2.12).
- 2026-10-13: K1 and K1.1 (the vault contract and `policy.yaml`), K2 (the `knowledge` service, `mcp-knowledge` on
  :3006) and K3 (`scan` writes the index through the contract), validated on the real install; the track pauses after
  K3.

## The graph follows dispatch (PR #3, merged on 2026-10-15)

- 2026-10-13: F0.7.3, mediator dispatch and Go interfaces (0.2.13); .NET gaps (3) and (4): a package's base methods,
  container services and closures.
- 2026-10-14: validated on the real install; overloads by argument count and DI registrations with the decorator chain
  (0.2.14); third round of the .NET Q4.
- 2026-10-14: the build fingerprint goes into the snapshot: re-indexing no longer depends on remembering the version.

## H2: the public corpus and the measured extractor (PR #4, merged on 2026-10-18)

- 2026-10-14: F0.4.3a (H2a): the corpus instrument (`http_corpus.py`, `corpus_metrics.py`, expected lists) and
  `docs/corpus-report.md` v1 with 15 repos.
- 2026-10-15: H2b: the cheap fixes; corpus v2 with 39 real-app repos; the cheap defects of v2.
- 2026-10-15/16: the mount graph (within a file, then across files); C# calls and wrappers; NSwag; generated Go servers
  and clients; flask-restx; the cross-file graph in TS/JS; Nest's `setGlobalPrefix`.
- 2026-10-16: outside H2 and found in it: a generic call with a receiver in C#; case-insensitive ASP.NET routes in the
  linker; `.js` imports and aliases in TS. The handoffs H3 (AI dev efficiency) and H4 (public docs and the indexer in
  its own repo) are registered.
- 2026-10-17: custom registrars in TS/JS, generated TS clients and phase 5.
- 2026-10-17: **F0.4.3b closed:** 42 repos, and a hold-out of 16 that showed overfitting (H2-D20). What was missing
  became F1.14.
- 2026-10-17/18: F1.14, increments 1–5, with the shapes the hold-out showed:
  - Go's precision defects;
  - .NET's custom route attributes, OData and FastEndpoints;
  - Go's grpc-gateway and package router;
  - Python's `APIRouter` subclasses;
  - Koa and the client base in TS.

  13 hold-out repos become corpus (55).

## The F1.14 close (PR #5, merged on 2026-10-19)

- 2026-10-18: increments 6–8: FastEndpoints groups; the gRPC custom verb; Go routers by declared type and named
  closures; a global group's own prefix.
- 2026-10-18: increment 9: one endpoint per app in a monorepo (`app` on `HttpEndpoint`, indexer 0.2.15).
- 2026-10-18: increments 10–11: the app's client wrappers in Python and TS/JS; lists of routers in a loop;
  `@fastify/autoload`; Next.js routes. The `corpus.sh` (parallel) and `test.sh` scripts.
- 2026-10-18: the H5 handoff is registered (refactor before SCIP, H5-D1–D5).
- 2026-10-18: **F1.14 closed, and H2 with it.** The new hold-out moves to after H5 (H2-D21).
- 2026-10-19: increment 12: validating the PR on a live install, before the merge, found two TS wrapper defects, and
  they were fixed. Baseline `2026-10-18-v2-baseline-28`. Fifth round of the golden questions.

## Docs (H4 phase 0a, PR #6; H4.1, PR #8)

- 2026-10-19: H4 phase 0a: the working docs recycled (`AGENTS.md`, `history.md` and `decisions.md`), and every doc in
  English (H4-D1).
- 2026-10-19: the H4.1 handoff is registered: the contributor path, its playbooks and an acceptance test by a fresh
  agent.

## The gates in CI (H7 slice 1: PR #10 and PR #11, merged on 2026-10-19; slice 1c, PR #22)

- 2026-10-19: `micro.sh` compares full dry-runs of a base and of the tree record by record on 12 repos (PR #10).
- 2026-10-19: the method's checks become gates on every PR that touches the indexer: the tests, the corpus, the
  hold-out and the micro set against `main`, with the baselines cached by the code's tree (H7-D1, D3, D5). `tests` and
  `gates` are required to merge (PR #11).
- 2026-10-22: H7 slice 1c, from the eighth golden round. The `tests` job runs `mcp-it.sh`: every atlas tool against a
  throwaway Neo4j, and the graph the writer leaves read back against a dry-run of each snapshot, by the writer's merge
  keys (PR #22).

## H5 and H6 (PR #9; the H6 design, PRs #13–#16; H5's first part, PR #7; step 5 in Go, PRs #17 and #20; C#'s refactor, PR #23; its change of behavior and what a name means, PRs #25 and #27; which extension method a call reaches, PR #30; Python's step 5, PRs #42 to #56; F1.16, PRs #57 to #63; TS's step 5, PRs #65 to #85, with step 12's #74 to #78 among them; the process's tools, PRs #86 to #93)

- 2026-10-19: H5's safe steps (0–2, 3a, 4a/b, 7a, 8, 9, 10 in part), with the corpus identical at each one.
- 2026-10-19: the H6 handoff is registered: the extraction as a parallel map, a reduce and a per-file cache
  (H6-D1–D4). H5's steps 3, 5 and 6 are designed with it.
- 2026-10-19: H6 step 0 measures the pipeline phase by phase. What it found:
  - the resolver was quadratic in Go and C#, taking 31–38 min on two repos. The HTTP corpus never runs it;
  - an index built once (PR #9, merged into `main`) brings it to seconds;
  - full dry-runs of `main`, H5 and the fix are identical on 12 repos, and that check joins H5's protocol.
- 2026-10-20: H6 step 1 prototypes the map, the reduce and the cache on a throwaway branch (`h6/step1-proto`):
  - a second map that re-extracts (B), keyed per package (D), gives identical output on the corpus, the micro set and
    6 real pushes, with no scanner changed;
  - 4 workers bring grafana from 132 s to 60 s; memory halves; warm runs of mattermost take 14–23 s;
  - a replay of 78 pushes compares the policies: no key missed a change, and keying by the entries read (C) re-runs
    4 times fewer scans than D at the p90.
- 2026-10-20: H6 step 2: the author decides B keyed per package (H6-D5) and batches by size (H6-D6). The cache store is
  measured, and ADR-004 to ADR-006 are proposed.
- 2026-10-20: H6 step 2 closes. Batches of whole packages, scanned in the worker and checked in the reduce, are
  identical everywhere and take 14–22 % less CPU; the author amends H6-D6 to them. They also find a read the scans did
  not record, which step 1's key missed. ADR-004 to ADR-006 are accepted.
- 2026-10-21: H5's first part merges as PR #7, a checkpoint (H5-D8), after a live install gave the same graph and the
  same answers (the sixth golden round).
- 2026-10-21: a shape ratchet in CI (H5-D9): what is new or grew over a target fails a PR. `gates.py` decides whether a
  PR is a refactor and judges the micro graph.
- 2026-10-21: step 5 goes in two PRs per language (H5-D10). Go's refactor merges as PR #17: the `TypeIndex` API in the
  core, Go's type facts as typed values, and Go's resolver asking `GoTypeIndex`. The corpus, the hold-out and 25 repos'
  dry-runs are identical, and so is the live install (the seventh golden round).
- 2026-10-21: before Go's change of behavior, the docs are checked against the design: H5's identity gets one
  exception, the changes of behavior (H5-D12, amending H2-D21); the hold-out is read only in aggregate in them
  (H5-D13); the micro graph is judged by case (H5-D14).
- 2026-10-21: `symbol_context` lists a file's imports in one order, sorted by their spec too (PR #19), the sixth
  golden round's finding.
- 2026-10-21: Go's change of behavior merges as PR #20. The resolver and the scanner get one answer for a local's
  declared type, with Go's own scoping, and three older gaps of the type service are closed: promoted methods, type
  parameters and a method's declared result (H5-D15). It was judged by case on the corpus (baseline `-29`) and on
  the micro set. On a live install the graph changes only in the two Go snapshots' `CALLS`, as their dry-runs said
  (the eighth golden round).
- 2026-10-22: step 5's C# refactor (PR #23): C#'s type facts as typed values, and C#'s resolver asking
  `CsTypeIndex`, with the indexes it kept in the context inside it. The corpus, the hold-out and 23 repos' dry-runs
  are identical, and so is the live install (the ninth golden round).
- 2026-10-22: C#'s change of behavior merges as PR #25. The resolver and the scanner get one answer for a name's
  declared type, with C#'s own scoping, and four older gaps of the type service are closed: a `partial` type is one
  type, a method's declared result, the repo's extension methods on a typed receiver, and a type written with its
  namespace and type arguments (H5-D16). On a live install the graph is identical, as the dry-runs said (the tenth
  golden round).
- 2026-10-24: what a name means in C# merges as PR #27, a `fix(csharp)` (H5-D17). It was judged by case on the corpus
  (baseline `-29`) and on the micro set, and thirteen gaps stay out, registered as debts on 2026-10-27
  (`docs/tech-debt.md`).
  - On 2026-10-26 the live install showed the graph identical but for the build, as the dry-runs said, and the 27 calls
    gave the same answers (the eleventh golden round). These snapshots hold none of the calls the change reaches, so
    that round checks the install, not the change.
- 2026-10-27: the indexer's validation method, rebuilt from a lost session, merges as PR #28: the cycle of a change, how
  a difference becomes a verdict, a test that a new session can resume from the repository alone, and the local tools
  (`indexer/scripts/`) cut to the 23 in use.
- 2026-10-27: the method's resume test becomes repeatable (`indexer/scripts/protocol/resume-test.sh`, PR #29), and what
  its first three runs found is fixed; a fourth, in a clone, passes all nine criteria.
- 2026-10-27: the fix for the wrong edge PR #27 exposed (H5-D18) is judged. The author accepts the review as the
  judgment, registers the defects the fix leaves as debts (`docs/tech-debt.md`), moves the gaps H5-D16 and H5-D17 left
  out to the same register (TD-007 to TD-022) and decides that the judgment is to be automated (H7-D6).
- 2026-10-27: the fix merges as PR #30 and is validated on a live install (the thirteenth golden round). The dry-runs
  of `main` and of the merge are identical, the graph holds them before and after the reinstall, the picture differs
  only in the build and the `IndexRun` counts, and the 27 calls give the same answers. These snapshots hold none of
  the calls the change reaches, so the round checks the install, not the change. The live validation becomes one
  command, `indexer/scripts/live/validate.sh` (PR #31).
- 2026-10-27: PR #30's merge and live validation are recorded, and its evidence file goes (PR #32).
- 2026-10-27: the register of technical debts is checked in CI against its cases and the ROADMAP (the `debts` job,
  PR #33). On 2026-10-28 the author makes it a required check of `main`.
- 2026-10-28: the expected lists get one tool that edits them and keeps their checked samples true to a corpus run,
  and "expected list" becomes their one name (PR #34).
- 2026-10-28: the new hold-out gets its procedure and tools: a list's first sample, and a guard that keeps a measured
  hold-out unopened (PR #35).
- 2026-10-28: Go's per-site attribution (H5's gap G1) merges as PR #36. On a real change of Go's local typing
  (`52b1e1b` to `1d56070`) it explains all 1,782 changed sites of 7 repos. H5's state is corrected: step 5 is closed
  for C#, and steps 6 and 12 are open in every language.
- 2026-10-28: the fifth resume run, in a clone, passes all nine criteria; what it found is fixed, and the author
  decides H5-D19: Python's step 5 before the `fix(csharp)` PRs, each language's attribution probe first. The sixth
  run, on those fixes, passes too; the author decides H5-D20: step 6 in the portfolio's order, C#, Go, Python, TS.
- 2026-10-28: the per-site attribution gets one probe for every language, read from each tree's own extraction
  (H5-D21), and merges as PR #39. On Go's change of local typing it prints the same output as Go's own probe, which it
  replaces. The seventh resume run, on that merge, passes all nine criteria; what it found is fixed.
- 2026-10-28: the author makes "design a change by its contracts, boundaries and proof" a principle
  (`docs/design.md`): every plan says what already answers its question, where each piece of knowledge belongs and
  what reference proves it. The core's syntax of each language becomes a debt (TD-023). With it, the
  author decides H5-D22: Python's step 5 separates scoping, proven against CPython's `symtable`, from typing.
- 2026-10-28: Python's case table merges as PR #42 (H5-D22): 24 strict xfails and 27 guards, and each of the 31
  cases that can run is run under CPython to show the method it names. An alternative a plan leaves for want of what
  it needs is now tracked in the item that builds it, with a test where one can tell (`docs/design.md` §4). The
  eighth resume run, on #41's merge, passes all nine criteria. What it found is fixed, or decided by the author:
  H5-D23, what the attribution reports for Python's change of behavior, and TD-024, the names of frameworks and
  client libraries in the core.
- 2026-10-28: the per-site attribution reports how a language's `CALLS` are found, and merges as PR #43 (H5-D23): each
  repo's edges by strategy on both sides, and the share found among several homonyms, of the edges and of the sites.
  On `main`, 65.6 % of the edges and 40.4 % of the sites of `dispatch`'s Python files are found so, and 63.1 % and
  38.2 % of `netbox`'s; the shares H5-D22 first quoted mixed two measures.
- 2026-10-28: Python's scope index merges as PR #44, the first of its refactor's two PRs (H5-D24). Of the corpus's
  7,124 Python files, CPython 3.12 compiles 7,114, and the index classifies every name of every scope of them as
  `symtable` does; the other ten are in Python 3.14's syntax. The case table's test that waited for the index is now
  that check, case by case.
- 2026-10-28: Python's types merge as PR #45, the second of its refactor's two PRs (H5-D24), with the graph identical.
  The core builds a language's per-file index once and hands it to the hooks that read the file, a receiver carries why
  it has no type, and a module's members are named apart from a class's. Python's declaration forms, type facts and
  `TypeIndex` answer every case of its table, read by them in the tests, while its `call_receiver` still answers
  nothing; the table's guards count an `inherited` edge as no method's (H5-D25).
- 2026-10-29: an absolute Python import resolves to the same module in every run, PR #46 (`fix(python)`). The roots
  it is looked for under, the root of the importing file's module, the repo's root and `src/`, were a set, ordered by
  the process's hash seed: of eight runs with seeds 0 to 7, two resolved a service's `app.models` to the service's own
  module and six to the repo root's. They are now tried in that order, the module's root first, and the test runs
  those eight seeds. None of the corpus's 42,298 absolute Python imports is found under two roots, so no graph of it
  changes.
- 2026-10-29: Python's change of behavior merges as PR #47, the third of H5-D22's PRs. A call's receiver takes the type
  its declarations give the binding CPython's scopes give its name, and the HTTP scanner asks the same scopes and types
  for its routers. Every xfail of the case table is gained, and the corpus and the hold-out do not change.

  The author keeps a call of a name outside the repo as an instance of it (H5-D26). The edges it loses on a function's
  result are TD-025, due in F1.2.
- 2026-10-29: PR #47 is validated on a live install (the fourteenth golden round), together with #44 to #46: the
  install still ran the package #30 merged, so the author chose one pair for all of them. The dry-runs of the installed
  code and of the branch are identical, the graph holds them before and after the reinstall, the picture differs only
  in the build and the `IndexRun` counts, and the 27 calls give the same answers. These snapshots hold no Python file,
  so the round checks the install, not the change. It is `validate.sh`'s first run: it now copies only the package a
  dry-run imports, since an IDE watching the folder built a test fixture's C# project in its copy.
- 2026-10-30: a Python absolute import is looked for under the directory its file's package runs from, PR #49
  (`fix(python)`, H5-D28). netbox runs from `netbox/`, where its `manage.py` is, and none of its 7,661 absolute imports
  resolved, so the core took its own classes for a package's.
  - Django's model managers, `Model.objects.<method>(..)`, are found by name on more sites: 29,474 edges against
    `main`'s 15,961. The author keeps the change, and that growth is TD-026, due in step 6.
- 2026-10-30: PR #49 is validated on a live install (the fifteenth golden round). The dry-runs of `main` and of the
  branch are identical, the graph holds them before and after the reinstall, the picture differs only in the build and
  the `IndexRun` counts, and the 27 calls give the same answers. These snapshots hold no Python file, so the round
  checks the install, not the change.
- 2026-10-30: a Python star import is followed as CPython binds it, PR #51 (`fix(python)`). `from m import *` binds
  `m`'s `__all__`, or its public names, and a later binding holds a name. In netbox, 9,108 receivers only a star import
  could bind are read: edges found by type go from 4,877 to 8,319, and the share found among several homonyms from
  64.0 % to 60.2 %. The author puts F1.16 before TS's step 5 (H5-D29).
- 2026-10-30: PR #51 is validated on a live install (the sixteenth golden round). The dry-runs of `main` and of the
  branch are identical, the graph holds them before and after the reinstall, the picture differs only in the build and
  the `IndexRun` counts, and the 27 calls give the same answers. These snapshots hold no Python file, so the round
  checks the install, not the change.
- 2026-10-30: one `CALLS` edge per caller, callee, line and method, PR #53 (`fix(graph)`). The resolver now gives one
  edge per key, by the strongest strategy, and the writer creates it. The micro set's dry-runs lose 68,769 repeated
  records and nothing else. The review registers TD-027: that implementation gets no edge of its own, due in a
  `fix(csharp)` PR before F1.2.
- 2026-10-30: PR #53 is validated on a live install (the seventeenth golden round). The graph holds `main`'s dry-run
  before the reinstall and the branch's after, strategies included: 2 edges of one snapshot take the strongest
  strategy, and the picture differs otherwise only in the build and the `IndexRun` counts. The 27 calls give the same
  answers. The round's first two runs showed the two defects of the live check that #53 fixes.
- 2026-10-30: a Python client wrapper's receiver is the class the type index gives it, PR #55 (`fix(python)`). The
  scanner's own classes of a receiver, by the class's name, go: a call reaches the wrapper of the class the index finds
  declaring the method, up the receiver's MRO. Five cases the scanner missed pass on both sides. The corpus, the
  hold-out and the micro set are the same, and so are the outbound calls of the 15 Python repos with both codes; the
  HTTP pass is faster. A class a function holds reaches no wrapper now: TD-028, due in F1.2.
- 2026-10-30: PR #55 is validated on a live install (the eighteenth golden round). The dry-runs of `main` and of the
  branch are identical on the 10 snapshots, the graph holds the branch's after the reinstall, and the 27 calls give the
  same answers. The snapshots hold no Python file, so the round checks the install, not the change.
- 2026-10-30: the per-site attribution reads what the resolver makes of a receiver too, PR #56 (`chore(scripts)`), which
  closes H5's gap G2. Replayed on H5-D28's import roots, it explains all 8,726 changed sites, where `main`'s probe
  explained none, and on the star imports all 4,657, where it explained 792; the `TypeIndex`'s verdict, the reference
  those judgments used, agrees on every site it explains. #47's table is the same.
- 2026-10-30: F1.16 is planned in three PRs (H5-D30), and the first splits the graph writer before F1.16 grows it,
  PR #57 (`refactor(graph)`): its session, the linker's reads and writes and the snapshots' bookkeeping go to modules
  of their own, and the dry-run's payload leaves `cli.py`. `core/graph.py` goes from 462 lines to 235. The corpus,
  the hold-out and the micro set are the same, and the MCP and the writer pass against a throwaway Neo4j.
- 2026-10-30: PR #57 is validated on a live install (the nineteenth golden round). The dry-runs of `main` and of the
  branch are identical on the 10 snapshots, the moved writer writes the same graph, and the 27 calls give the same
  answers.
- 2026-10-30: the resolver's edge records move to `core/edges.py`, PR #58 (`refactor(resolve)`), before F1.16's
  `feat(graph)` grows `core/resolve.py`, which was at 300 lines; it goes to 256.
- 2026-10-31: PR #58 is validated on a live install (the twentieth golden round). The dry-runs of `main` and of the
  PR's head are identical on the 10 snapshots, the resolver with its records moved writes the same graph, and the 27
  calls give the same answers.
- 2026-10-31: the types' bases of the repo are `EXTENDS` and `IMPLEMENTS`, and a `CALLS` edge says whether it may
  dispatch, PR #59 (`feat(graph)`): C# and Python read the bases from their type indexes, Go embeds and writes none, and
  a call on `base` or on `super()` has `virtual: false`. The corpus and the hold-out are the same. Judged at the source,
  the calls that do not dispatch show `main`'s targets of a `base` call on its own override and of a `super()` found by
  name, TD-030 and TD-031, and the change creates TD-032, two C# types of one name in one file taking each other's
  bases; all three are due in a `fix(resolve)` before F1.16's `feat(mcp)` (H5-D31). Go's interface calls are TD-029.
- 2026-10-31: PR #59 is validated on a live install (the twenty-first golden round). The two C# snapshots gain their
  types' edges, 23 and 20, the other 8 are identical, every `CALLS` edge is the same with `virtual` true, the graph
  holds the branch's dry-runs, and the 27 calls give the same answers; the `after` waited for the new build.
- 2026-10-31: a call that does not dispatch reaches no implementation and no homonym found by name, PR #60
  (`fix(resolve)`, H5-D32). TD-030 to TD-032 are closed; the judgment at the source registers TD-033, two C# types of
  one name in one file in a call, and TD-034, a type written with a namespace outside the repo read by its simple name,
  both `main`'s and due in `fix(csharp)` PRs. The corpus and the hold-out are the same.
- 2026-10-31: PR #60 is validated on a live install (the twenty-second round). No live snapshot holds what it touches:
  the dry-runs of `main` and of the PR's head are identical on the 10 snapshots, the graph holds them, and the 27 calls
  give the same answers.
- 2026-10-31: a method a dispatching call may run instead of another `OVERRIDES` it, as the instance's language says,
  PR #61 (`feat(graph)`, H5-D33). C# follows `override`, `new`, `static` and interface implementation, by name and
  number of parameters; Python, what each class's MRO finds first, a mixin's method included, and the last definition of
  a name in a class. CPython's `__mro__` gives the Python fixture's edges exactly. The corpus and the hold-out are the
  same.
- 2026-10-31: PR #61 is validated on a live install (the twenty-third round). The two C# snapshots gain 15 and 17
  `OVERRIDES`, every one method to method, the other 8 are identical, `CALLS` are the same, the graph holds the
  branch's dry-runs, and the 27 calls give the same answers, since no tool reads the edges yet.
- 2026-10-31: a dispatching call keeps its receiver's type, and an override the receivers on which it may run, PR #62
  (`feat(graph)`, H5-D34). F1.16 goes in seven PRs. TD-035 registers an override of a package's method, which no call
  meets until SCIP gives the method a symbol (F1.2). The corpus and the hold-out are the same.
- 2026-10-31: PR #62 is validated on a live install (the twenty-fourth round). The two C# snapshots gain only
  `receivers`, on their 15 and 17 `OVERRIDES` (17 and 22 types) and on one call, the other 8 are identical, the graph
  holds the branch's dry-runs, and the 29 calls give the same answers, since no tool reads the receivers yet.
- 2026-10-31: `who_calls` and `impact_of` follow a dispatch through `OVERRIDES` and the receivers, PR #63 (`feat(mcp)`,
  H5-D34 and H5-D35), which closes F1.16. Of the 82 (site, override) pairs H5-D27 counted on netbox and dispatch,
  `who_calls` reaches 81, the one left TD-035's. The corpus, the hold-out and the micro graph are the same.
- 2026-10-31: PR #63 is validated on a live install (the twenty-fifth round). The graph is the same on the 10
  snapshots and the build too, so no snapshot ran; of the 29 calls, the two on a C# override and `who_calls` on Q4a's
  method gain their dispatching callers, Q4's callers gain `via_dispatch: false`, and the rest are the same.
- 2026-10-31: the live check's `after` takes a change the build does not fingerprint, PR #64 (`chore(scripts)`). The
  refresh then re-indexes nothing, so `after` no longer waits for runs: it refuses a last run since the before that is
  not ok, or a build that moved. F1.16 is closed in the ROADMAP and in H5's Next, whose first step is now TS's. TD-036
  registers a C# call on an interface that reaches its single implementer twice, by its own edge and by the dispatch,
  due in H5's step 6.
- 2026-10-31: TS's step 5 is planned in five PRs, with the TypeScript compiler as its reference (H5-D36), and the
  attribution's probe reads TS's files, PR #65 (`chore(scripts)`). `answers.py` and `attribution.sh` take several
  languages read together (`typescript,tsx,javascript`), and the probe gives TS and JS the node that binds `this` at a
  use and the functions around it. `AGENTS.md`, the ROADMAP and the schema now say that a micro edge carries no
  `tenant`, `repo`, `ref` or `commit_sha`, which its ends carry, and which macro edges carry `confidence` and
  `evidence`.
- 2026-10-31: TS's type cases, each checked against TypeScript's own checker, PR #66 (`test(typescript)`). The test
  image gets Node and `typescript@6.0.3`, the last line with the compiler's JavaScript API, and `ts_checker.js` gives
  the declarations the checker resolves each call to. The table corrects H5-D36's list of what stays `Unknown`: a `let`
  takes its initializer's type, and a parameter injected by token declares its type.
- 2026-10-31: TS's scope index, proven against TypeScript's own binder, PR #67 (`refactor(typescript)`), the first of
  TS's refactor's two PRs (H5-D37), with the graph identical: nothing in the extraction reads it yet. The case table
  gains eight scope cases, six of them typed.
- 2026-11-01: PR #67 is validated on a live install (the twenty-sixth round). The build changes and the 10 snapshots
  are re-indexed, all ok; the graph is the same on each, and of the 29 calls, 5 differ only in their time, build and
  refresh fields.
- 2026-11-01: TS's types, PR #68 (`refactor(typescript)`), the second of TS's refactor's two PRs (H5-D37, H5-D38), with
  the graph identical: TS's `call_receiver` answers nothing yet. TS's facts and one `TypeIndex` for its three ids
  (`LanguageSupport.type_family`); the HTTP scanner takes its class of a `this` from the scope index and its class of a
  `new C()` from the type index, and no site changes on the corpus, the hold-out or the micro set.
- 2026-11-01: PR #68 is validated on a live install (the twenty-seventh round). The build changes and the 10 snapshots
  are re-indexed, all ok; the graph is the same on each, and of the 29 calls, 5 differ only in their time, build and
  refresh fields.
- 2026-11-01: TS's hierarchy, PR #69 (`feat(graph)`), the fifth of TS's step 5 (H5-D39): TS's `EXTENDS`, `IMPLEMENTS`
  and `OVERRIDES`. An abstract method is a method symbol. The proof found TD-038 and TD-039, due before the change of
  behavior, so TS's step 5 is eight PRs.
- 2026-11-01: PR #69 is validated on a live install (the twenty-eighth round). The build changes and the 10
  snapshots are re-indexed, all ok; the TS and JS snapshots gain 285 hierarchy edges and 2 abstract methods, their
  `CALLS` change at 2 sites, and of the 29 calls, 5 differ only in their time, build and refresh fields. The round
  found TD-040, a signature that loses the `>` closing its type.
- 2026-11-01: a symbol's signature, PR #70 (`fix(graph)`), which closes TD-040: the cut that drops what leads into a
  declaration's body, a `=>`, `=` or `:`, dropped any `>` its first line ended with, mostly the one closing a type
  (`Promise<void>` read `Promise<void`), and dropped nothing before a CRLF. On the micro set, 9,906 signatures change
  and nothing else: 9,904 gain their `>` (8,001 TS, 1,905 C#, 15 Go raw strings, a Python `->`), and 2 Python ones
  in CRLF files lose their `:`. Corpus and hold-out: 0 repo(s) differ.
- 2026-11-01: PR #70 is validated on a live install (the twenty-ninth round). The build changes and the 10 snapshots
  are re-indexed, all ok; 345 signatures gain their `>`, which the graph holds as the dry-runs give them, read apart
  since the live tools compare no symbol property; of the 29 calls, 5 differ only in their time, build and refresh
  fields, and `find_symbol`'s scores move with its full-text index.
- 2026-11-01: the live validation compares a symbol's properties, PR #71 (`chore(scripts)`), which #70's live
  validation found it did not: `dry_sections.py` counts the fields that differ on a key both dry-runs keep, the
  graph's picture lists each symbol's properties, its signature and doc percent-encoded, and `graph_vs_dry.py` checks
  that the graph holds each symbol of the dry-run with every property the writer gives it. On #70's pair, the 345
  signatures show where the tools said `identical`.
- 2026-11-01: PR #71 is validated on a live install (the thirtieth round), with its own tools. The graph is the same
  on the 10 snapshots, each symbol's properties compared, and the build too, so no snapshot ran; of the 29 calls, 28
  are the same and `atlas_status` differs only in its time fields.
- 2026-11-01: TS's module resolution, PR #72 (`fix(typescript)`), which closes TD-038 (H5-D40): an import goes to the
  file TypeScript resolves it to with the nearest `tsconfig.json` or `jsconfig.json`, its `extends` and the project a
  config refers to, by `paths` and `baseUrl`, and a conventional alias names a file only where no config maps it. The
  proof found TD-041, a hand-written declaration file discovery skips, and TD-042, a package of the repo's own
  workspace, both due in TS's step 5, which goes in ten PRs; and the call checker, the change of behavior's reference,
  reads each file's config now.
- 2026-11-01: PR #72 is validated on a live install (the thirty-first round). The TS repo gains 21 hierarchy edges,
  the 7 heritage clauses TypeScript's checker resolves through `paths` and 14 `OVERRIDES`, 5 overrides gain the new
  subclasses among their receivers, and 18 `IMPORTS` go from a package to a file; its `CALLS` and the other 9
  snapshots are the same, and the graph holds the dry-runs on all 10. Of the 29 calls, 24 are the same and 5 differ
  only in their time, build and refresh fields.
- 2026-11-01: TS's CommonJS exports, PR #73 (`fix(typescript)`), which closes TD-039 (H5-D41): a module's CommonJS
  exports and a TS module's `export =` are read as TypeScript binds them, and a `require`, a whole module's import and a
  default import take the module's own value. The proof found TD-043, a class a class expression declares that is no
  symbol, due in TS's step 5 with TD-037; TD-039's `export =` of a namespace in a declaration file goes with TD-041.
- 2026-11-02: PR #73 is validated on a live install (the thirty-second round). No class of the live repos extends one a
  module assigns, so the dry-runs of `main` and of the PR are identical on the 10 snapshots, and the graph holds them
  with the new build on each; of the 29 calls, 24 are the same and 5 differ only in their time, build and refresh
  fields.
- 2026-11-02: the declarative conventions in the shape targets, PR #74 (`refactor(conventions)`), H5 step 12's first
  PR: `declarative.py` keeps the YAML's parsing and asks four modules, the layout, a type's declaration, its role and
  one function per kind of rule, and `apply` asks each hook in a step of its own. The graph is identical, and so are
  the micro set's 12 repos with the reference convention and a probe that uses every key of the format, in both
  orders. Its plan found four defects `main` has, TD-044 to TD-047, due in a `fix(conventions)` PR before F1.2
  (H5-D42).
- 2026-11-02: PR #74 is validated on a live install (the thirty-third round). The dry-runs of `main` and of the merge
  are identical on the 10 snapshots, the convention's 104 roles and its layer included, and the graph holds them with
  the new build on each; of the 29 calls, 24 are the same and 5 differ only in their time, build and refresh fields.
- 2026-11-02: the corpus runner measures a repo and sums its totals outside `main`, PR #75 (`refactor(scripts)`): `main`
  goes from complexity 20 to 6 and `report_expected` from 12 to 6, and the totals across repos leave three global
  variables for an accumulator of their own (`corpus_totals.py`). Every path of the runner prints what `main`'s does,
  byte for byte, and the corpus's and the hold-out's dumps are identical. `http_corpus.py` stays at 346 lines, split
  when it must grow (H5-D43). No live validation: nothing in `aidd_indexer/` changes.
- 2026-11-02: the declarative conventions' four debts closed, PR #76 (`fix(conventions)`): a rule that names two kinds
  is refused when its convention loads (TD-044); `roles_in` reads its convention's own layout on every file (TD-046); a
  type's bases are read from the line that declares it, as its language writes them (TD-045); and an id declared more
  than once has the bases of every declaration (TD-047). Three forms the reading still misses (a declaration longer than
  its 15 lines, a Python base with a subscript, a `{` in a call in a TS base list) are a debt, TD-048.
- 2026-11-02: PR #76 is validated on a live install (the thirty-fourth round). The dry-runs of `main` and of the PR's
  head are identical on the 10 snapshots: the convention runs on 2 of them, both C#, and its 104 roles, its layer and
  its entry points are the same. The graph holds them with the new build on each; of the 29 calls, 24 are the same and
  5 differ only in their time, build and refresh fields. What the PR corrects is not in the live repos: the parity of
  the micro set holds it.
- 2026-11-02: the MCP's tools in the shape targets, PR #77 (`refactor(mcp)`): each of `find_symbol`, `who_calls`,
  `symbol_context`, `impact_of` and `ref_diff` keeps in `register` the wrapper its schema comes from (its name,
  parameters, return type and docstring) and calls a function of its module with the tenant's store and every argument
  by name, so both `register` go from complexity 12 to 4 and 3.
- 2026-11-02: PR #77 is validated on a live install (the thirty-fifth round). The dry-runs of `main` and of the PR's
  head are identical on the 10 snapshots, and the graph holds them, with the build unchanged: the tools' code is not in
  its fingerprint. The picture is identical in its 16 lists, and of the 29 calls, 28 are the same field by field and 1,
  the status, differs only in its time, age and refresh fields; the five tools answer as before.
- 2026-11-02: the refresher's modules in the shape targets, PR #78 (`refactor(refresher)`): `load_manifest`,
  `discover_repos`, `plan_refs`, `load_policy`, `sync` and `record_insight` go from complexity 13 or 14 to between 2 and
  7, and the policy's `_validate_layer` from 10 to 6, each split along the seams it already had: a tenant's sources, ref
  policy and conventions; discovery's mirror and fetch loops; the ref policy's three passes; a mirror's creation, its
  copy from the workspace and its fetch from origin; an insight's checks and its repeat. Step 12's remaining code goes
  with the step that changes it (H5-D44): the core's HTTP modules with step 6, and `extract` and `resolve` with step
  12's last PR, after TS's step 5.
- 2026-11-02: PR #78 is validated on a live install (the thirty-sixth round). The dry-runs of `main` and of the PR's
  head are identical on the 10 snapshots, and the graph holds them with the new build on each; the picture is identical
  in its 16 lists but for the build and the `IndexRun` counts, and of the 29 calls, 24 are the same and 5 differ only
  in their time, build and refresh fields. What `aidd plan` and `aidd policy` print for each of the 7 tenants is the
  same, byte for byte, before and after.
- 2026-11-02: TS's declaration files, PR #79 (`fix(typescript)`), which closes TD-041 (H5-D45): discovery reads a
  hand-written `.d.ts`, an import resolves to one by TypeScript's order where no implementation file exists, and beside
  a JS file the import keeps the file Node loads while a name the JS cannot declare is the declaration file's. The proof
  found TD-049, a folder import that ignores the entry its manifest names.
- 2026-11-03: PR #79 is validated on a live install (the thirty-seventh round). The dry-runs of `main` and of the PR's
  head are identical in 7 of the 10 snapshots; in the 3 with declaration files the graph gains 47 symbols, 71 `IMPORTS`
  and 12 `EXTENDS` (classes of the code to types a declaration file declares), all in or to declaration files, and 1
  `CALLS` found by a unique name becomes ambiguous. The graph holds the dry-runs with the new build on each snapshot; of
  the 29 calls, 24 are the same, 4 differ only in their time, build and refresh fields, and the TS snapshot's
  `repo_map` counts the new files and symbols.
- 2026-11-03: TS's workspace packages, PR #80 (`fix(typescript)`), which closes TD-042 (H5-D46): an import of a package
  the repo's own workspace declares resolves to the file TypeScript gives it through the link a package manager makes,
  by the package's `exports` (the conditions `types`, `import`, `default` and the config's `customConditions`), its
  `types`, `typings` or `main`, or its `index`, and a file sees the members of each workspace root above it. Over the
  corpus the index names the checker's file at 14,907 more imports, 13,215 of them grafana's, and at 437 more heritage
  clauses, and none it named changes; 10,614 imports of a package whose entry is a build the clone lacks stay a package,
  TD-050. Micro: grafana, mattermost and ghost differ, by 13,954 `IMPORTS` that go from a package to a file, 471
  hierarchy edges, and 4,816 `CALLS` found by name that the compiler confirms at 208, and an endpoint of grafana whose
  path reads a field an instance fills at run time, TD-051; the corpus and the hold-out as on `main`.
- 2026-11-03: PR #80 is validated on a live install (the thirty-eighth round). The dry-runs of `main` and of the PR's
  head are identical in all 10 snapshots, since no live repo declares a workspace whose packages its code imports. The
  graph after holds the dry-runs on each snapshot (0 mismatching); of the 29 calls, 24 are the same and 5 differ only in
  their time, build and refresh fields.
- 2026-11-03: TS's class members and folder entries, PR #81 (`fix(typescript)`), which closes TD-037, TD-043 and TD-049
  (H5-D47): a class field that holds an arrow or a function is a `method` of its class, and an instance's call of it
  runs what the field holds, the nearest class's winning; a class a module's statement declares by an expression is a
  class, by the binding of a `const`, a `var` or an `export`, or in a JS file by `module.exports =` and `exports.X =`;
  and an import of a folder reads the `types`, `typings` and `main` of its `package.json` before the `index.*`.
- 2026-11-03: PR #81 is validated on a live install (the thirty-ninth round). The dry-runs of `main` and of the PR's
  head are identical in 7 of the 10 snapshots and differ in the 3 TS and JS ones, by 29 symbols, 140 `CALLS` found by
  name and 11 hierarchy edges. The graph after holds the dry-runs on each snapshot (0 mismatching); of the 29 calls, 23
  are the same and 6 differ, in their time, build and refresh fields and in 4 scores of `find_symbol`.
- 2026-11-03: TS's referenced projects, PR #82 (`fix(typescript)`), which narrows TD-050 and opens TD-052 (H5-D48): an
  import that names the output of a project the importing file's config references, directly or through another,
  resolves to the source that project builds it from, as TypeScript reads it with `useSourceOfProjectReferenceRedirect`
  and where the build is there too, by `declarationDir` or `outDir` and `rootDir`.
- 2026-11-03: PR #82 is validated on a live install (the fortieth round). The dry-runs of `main` and of the PR's head are
  identical in all 10 snapshots, since no live repo references a project whose output its code imports. The graph after
  holds the dry-runs on each snapshot (0 mismatching); of the 29 calls, 24 are the same and 5 differ only in their time,
  build and refresh fields.
- 2026-11-03: TS's function members, PR #83 (`fix(typescript)`), which opens TD-053 and TD-054 (H5-D49): a member of an
  interface, of the object type a type alias names, or of an operand of its intersection or union, written as a property
  of a function type (`push: (x: number) => void`) is a `method` of its owner, as a method signature is, and a class
  that implements the interface overrides it.
- 2026-11-07: PR #83 is validated on a live install (the forty-first round). The dry-runs of `main` and of the PR's head
  are identical in 8 of the 10 snapshots and differ in the two of the live install's TS repo, which gain 13 symbols each and 103
  and 97 `CALLS` found by name, and lose 6 and 7. The graph after holds the dry-runs on each snapshot (0 mismatching):
  10,711 symbols and 24,009 `CALLS`, the others as before; of the 29 calls, 24 are the same and 5 differ, 4 only in their
  time, build and refresh fields and the `repo_map` of the TS also in its module's symbols and the `method` count.
- 2026-11-07: TS's resolver reads a receiver's type, PR #84 (`fix(typescript)`), the first PR of the change of behavior
  (H5-D50), which narrows TD-050 and opens TD-056 to TD-061: a call on a receiver whose type the code declares reaches
  the methods of that type and of its bases and no homonym found by name; where the type is not decided, it goes by name
  as before. The corpus and the hold-out do not change, and ghost's dry-run takes 22 % longer (2 % more memory), inside
  what the author accepted.
- 2026-11-07: PR #84 is validated on a live install (the forty-second round). The dry-runs of `main` and of the PR's head
  are identical in 7 of the 10 snapshots and differ in the 3 TS and JS ones, in `CALLS` only: they gain 678, 647 and 46
  edges by the receiver's type and lose 969, 934 and 37 found by name. The graph after holds the dry-runs on each snapshot
  (0 mismatching): 10,711 symbols and 23,440 `CALLS` (-569), the others as before; of the 29 calls, 24 are the same and 5
  differ only in their time, build and refresh fields.
- 2026-11-08: TS's HTTP scanner finds a client by the type its receiver declares, PR #85 (`fix(typescript)`), the last
  PR of the change of behavior and of TS's step 5 (H5-D51), which opens TD-062: a receiver that a class of the repo or a
  client library's type (`AxiosInstance`, not any type of the package) types is a client, like one the name, a `new` or
  an import gives, and the type never takes one away; the method a typed call reaches is the one the class or base that
  declares it holds, under a qualified name, and where name and type give the same client the call its wrapper composes,
  with the client's base, replaces the direct one.
- 2026-11-08: PR #85 is validated on a live install (the forty-third round). The dry-runs of `main` and of the PR's head
  are identical in all 10 snapshots, and the graph after holds them on each snapshot (0 mismatching): its picture is
  the one before but for the build and the `IndexRun` counts (10,711 symbols, 23,440 `CALLS`, 286 endpoints, 160 HTTP
  calls); of the 29 calls, 24 are the same and 5 differ only in their time, build and refresh fields.
- 2026-11-08: the process's notes go into the repo (PR #86): the independent reviewer's handoff (H8) with its three uses (five reviews), and the method's
  notes on mutants, the firing probe, timing a pass over TS files, two agents at once and the recycling of `.local/`.
- 2026-11-08: the independent reviewer is in the repo (`chore(scripts)`, PR #87, H8 slice 1): `indexer/scripts/review/independent-review.js`, called
  by path from any worktree, with each rule of its orchestration pinned by a test with simulated agents.
- 2026-11-08: the research round is in the repo (`chore(scripts)`, PR #88, H8's Tier 2): `indexer/scripts/review/research-round.js`, one read-only
  researcher per open question (at most four, each with a mode and a tool-call budget), a synthesis that decides and a challenge of it,
  with each rule of its orchestration pinned by a test with simulated agents.
- 2026-11-09: one heavy Docker job at a time is held by the scripts themselves (`chore(scripts)`, PR #89): `indexer/scripts/lib/heavy-lock.sh` and a line in
  `corpus.sh`, `micro.sh`, `test.sh` (the whole suite), `mcp-it.sh`, `protocol/`, `attribution.sh`, `live/validate.sh` and `dryrun-live.sh`. A second job ends with
  status 75 and names the holder, or waits; the lock is the holder's process, so it goes when that process ends, however it ends.
- 2026-11-09: the mutants runner is in the repo (`chore(scripts)`, PR #91, which carried #90's commits): `indexer/scripts/checks/mutants.sh` copies the tree, breaks one rule per mutant
  and runs `test.sh` on the copy, printing `DIES` or `SURVIVES`; a survivor ends the run with status 1 unless it is named by `--allow`.
- 2026-11-09: the comparator of TS's edges against TypeScript's checker is in the repo (`chore(scripts)`, PR #91): `indexer/scripts/judgment/ts_vs_checker.py` counts, per verdict, the typed
  edges a change adds and the by-name edges it drops, with a `.d.ts` as the JS beside it, and whether a dropped edge is replaced or lost; on gotify, between the tree before H5-D50
  and the tree after H5-D51, the checker agrees with the 3 typed edges added and with none of the 83 by-name edges dropped.
- 2026-11-09: the cost of a pass in alternating pairs is a script of the repo (`chore(scripts)`, PR #92): `indexer/scripts/protocol/cost-pairs.sh` runs `corpus.sh --jobs 1 --no-expected` on main's tree and the
  branch's, the side that goes first flipping each pair, and prints the change in time per pair, the medians and the change in peak memory; on the saved runs of H5-D51 it gives
  the numbers that PR reported (ghost +9.6, +9.6, +11.8 and +11.0 %, mattermost +3.4, +4.3 and +4.3 %).
- 2026-11-09: the draft of a golden round is a script of the repo (`chore(scripts)`, PR #93): `indexer/scripts/live/round.py` writes the round and its history line from a validated PR's in-flight folder, with counts, snapshot
  numbers, list and tool names and no name the live data holds; on the pair of PR #85 it gives the numbers of the forty-third round, the judgment and the sentence of what changed staying the author's.
- 2026-11-09: TD-057, TD-059 and TD-060, the three TS debts that ask the reading to answer what a type checker answers (a generic's argument an alias gives, a receiver a type guard narrows, an overloaded function's result), move from `fix(typescript)` PRs to F1.2 (H5-D52, `docs:`, PR #94): they explain few of the sites the checker places elsewhere and SCIP gives them from the compiler. Seven TS debts stay due before F1.2.
- 2026-11-09: a review of the docs corrects what had become false, across 24 files (`docs:`, PR #95): the H5 State and Next (TS's step 5 is closed, the debts due before F1.2 by scope), the open questions of H6 (decided in ADR-004), `live-check.sh` (H7, the method; it is `live/validate.sh`), the version-bump rule of the guide (the build is a fingerprint of the code), the commands of `indexing-process.md` (no `aidd sync`), the PR numbers and dates of the process's tools in this log, and the ROADMAP's and `AGENTS.md`'s lists of gates, handoffs and files.
- 2026-11-09: a pull request has a template and a rule (`chore`, PR #96): `indexer/.github/pull_request_template.md`, the body as the long record and each fact written once (`docs/indexer/method.md` §4.17, `docs/decisions.md`), and a check that refuses an attribution line in a pull request's title, body and commit messages, against a list of regexes (`indexer/scripts/checks/pr_text.py`, in the `debts` job).
- 2026-11-09: the files of `docs/` that grow have a ceiling in bytes (`chore(scripts)`, PR #97): `indexer/scripts/checks/docs_size.py` and `docs_ceilings.txt`, in the `debts` job, refuse a PR that passes one; a golden round replaces the last one instead of being added (`docs/indexer/method.md` §4.9, §4.17), and `#NN` in the docs is `praticis/aidd-stack#NN`.
- 2026-11-09: `docs/golden-questions.md` is condensed (`docs:`, PR #98), from 1,592 lines to 287: the five questions, how to run a round, the last round in full and a table of what the rounds found; the text of the 5th to the 43rd round is in git, tag `before-golden-questions-condensation`.
- 2026-11-09: the H5 handoff and the decisions H5-D36 to H5-D51 are condensed by deletion (`docs:`, PR #99): the handoff goes from 2,055 lines and 185 KB to 744 lines and 60 KB (the State, the Steps, the regression protocol, the target architecture, what stays open in each step 5 and the deliverables stay; the per-PR proof of step 5 is in the PR bodies, and what is past and done, the list of merged PRs and the method's recovery, is cut), the sixteen rows go from 43 KB to 22 KB (the rule and the reason stay, no measurement); every line kept is an old line, in order, checked twice, and the old text is the tag `before-h5-condensation`; the ceilings of the golden questions, the H5 handoff and the decisions are lowered to 10 % above what is left; a PR that edits only the ceilings list or the template no longer runs the corpus, the micro set and the tests; `docs/indexer/method.md` §4.4 gains what #84 learned about the checker comparator (read its `no checker site` count first); TD-063 is registered, a TS call on `super` found by name among every class's methods (H5-D39 had left it to a change that did not take it), due in `fix(typescript)`, with its strict xfail.
- 2026-11-09: the ROADMAP, the history and the register of debts are condensed by deletion (`docs:`, PR #100): the ROADMAP goes from 49 KB to 34 KB ("In progress" is the state of H5 and the debts by due, with the sentences `debts.py` reads; Phase 0's exit figures, the compose checklist, the continuous-update and security tracks' done items and the knowledge track's layout are in git), the history from 69 KB to 55 KB (the measures of the longer entries are in the PR bodies; the golden rounds' counts stay), and the register's chronology of how each debt was found is a pointer to git; the old text is the tag `before-roadmap-history-condensation`; the ceilings of the ROADMAP and the history fall to 37 and 60 KB, and the register gets one of 48 KB.
- 2026-11-09: the comparator of TS's edges against TypeScript's checker guards its own reading (`chore(scripts)`, PR #101): each percentage says how many edges it is over, and a line says how many of the TS calls of the two runs are in a file the checker has rows for (97.9 % in `ghost`; 0 with a path compared with its extension to one without it, which hid 11,145 of 15,092 edges in #84), and a site is keyed by the method the edge records, not by its callee's name, which had hidden 1,068 of `ghost`'s 3,045 added typed edges whose callee is the type that owns a member with no symbol; below `--min-keyed` (50 by default) it prints a WARNING, and `--strict` ends in 1. It is not a step of CI: the comparator judges one change's edges against criteria that change declares (`docs/indexer/method.md` §4.4).
