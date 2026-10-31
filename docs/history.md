# History

> The project's milestones, one per line, with the date and the PR they came in.
>
> - The full text of each entry, as it was written in the ROADMAP's "Where we are" section, is in
>   `git show 1d73bb0:docs/ROADMAP.md` (in Portuguese).
> - The narrative of each corpus increment is in `git show 1d73bb0:docs/corpus-report.md`.
>
> The decisions are in `docs/decisions.md`; the current state, in the ROADMAP.

## Phase 0: the foundation (PR #1, merged on 2026-10-13)

- 2026-09-09: D1, Neo4j Community (ADR-001); Neo4j and `neo4j-init` in the compose file; schema v1 in
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

## H5 and H6 (PR #9; the H6 design, PRs #13–#16; H5's first part, PR #7; step 5 in Go, PRs #17 and #20; C#'s refactor, PR #23; its change of behavior and what a name means, PRs #25 and #27; which extension method a call reaches, PR #30; Python's step 5, PRs #42 to #51)

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
  namespace and type arguments (H5-D16). It was judged by case on the corpus (baseline `-29`) and on the micro set;
  two more gaps of what a name means in C# go in a `fix(csharp)` (H5-D17). On a live install the graph is identical,
  as the dry-runs said (the tenth golden round).
- 2026-10-24: what a name means in C# merges as PR #27, a `fix(csharp)` (H5-D17). A type's simple name is looked up
  as C# does, and a capitalized member, a nested type, a `global using`, a type parameter's constraint and type
  argument, an array and an extension block are read as C# reads them. It was judged by case on the corpus (baseline
  `-29`) and on the micro set, and thirteen gaps stay out, registered as debts on 2026-10-27 (`docs/tech-debt.md`).
  - Its validation after the merge was left open when the session that ran it stopped. Its method was recovered into
    `docs/indexer/`.
  - On 2026-10-26 the live install showed the graph identical but for the build, as the dry-runs said, and the 27
    calls gave the same answers (the eleventh golden round). These snapshots hold none of the calls the change
    reaches, so that round checks the install, not the change.
  - A new judgment on the corpus that day found one wrong edge the PR added: elsa's `x.GetInput<string>(item)` went
    to a method that is not generic. Its cause is older than the PR, and its fix is H5-D18.
- 2026-10-27: the indexer's validation method, rebuilt from a lost session, merges as PR #28: the cycle of a change, how
  a difference becomes a verdict, a test that a new session can resume from the repository alone, and the local tools
  (`indexer/scripts/`) cut to the 23 in use.
- 2026-10-27: the method's resume test becomes repeatable (`indexer/scripts/protocol/resume-test.sh`, PR #29), and what
  its first three runs found is fixed; a fourth, in a clone, passes all nine criteria.
- 2026-10-27: the fix for the wrong edge PR #27 exposed (H5-D18) is judged. The corpus and the hold-out are unchanged,
  the micro graph differs on 6 C# repos (−815 and +97 edges), an independent review of 189 items finds no wrong changed
  edge, and the live check before the merge is identical, though its snapshots hold none of the calls the change
  reaches. The author accepts the review as the judgment, registers the defects the fix leaves as debts
  (`docs/tech-debt.md`), moves the gaps H5-D16 and H5-D17 left out to the same register (TD-007 to TD-022) and decides
  that the judgment is to be automated (H7-D6).
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
  The core builds a language's per-file index once and hands it to the hooks that read the file, a receiver carries
  why it has no type, and a module's members are named apart from a class's. Python's declaration forms, type facts
  and `TypeIndex` answer every case of its table, read by them in the tests, while its `call_receiver` still answers
  nothing; the table's guards count an `inherited` edge as no method's (H5-D25). The facts of the corpus's 7,124
  Python files are values, the same in two runs. Building them costs netbox's extraction 2.2 s (5.8 to 8.0) and
  14 MiB of peak memory; the index, kept beside the tree, cost it about 270 MiB more, so it lives only while its file
  is extracted.
- 2026-10-29: an absolute Python import resolves to the same module in every run, PR #46 (`fix(python)`). The roots
  it is looked for under, the root of the importing file's module, the repo's root and `src/`, were a set, ordered by
  the process's hash seed: of eight runs with seeds 0 to 7, two resolved a service's `app.models` to the service's own
  module and six to the repo root's. They are now tried in that order, the module's root first, and the test runs
  those eight seeds. None of the corpus's 42,298 absolute Python imports is found under two roots, so no graph of it
  changes.
- 2026-10-29: Python's change of behavior merges as PR #47, the third of H5-D22's PRs. A call's receiver takes the
  type its declarations give the binding CPython's scopes give its name, and the HTTP scanner asks the same scopes and
  types for its routers. Every xfail of the case table is gained, and the corpus and the hold-out do not change.

  The per-site attribution explains all 4,188 changed sites of the micro set's four Python repos. dispatch's share of
  edges found among several homonyms falls from 65.6 % to 53.0 %.

  Its judgment found three answers of "outside the repo" the index had not proven: an import under a root it does not
  try, a module with a star import, and a class attribute a descriptor may read. The review of an agent that did not
  write the change (H7-D6) found five more:
  - a mixin's method only a subclass gives;
  - `super()` that a class of several bases may reorder;
  - `typing.Any` and a `TypeVar`;
  - a re-exported function;
  - a router class a function imports.

  Each became `Unknown`, so the call goes by name as on `main`.

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
  resolved, so the core took its own classes for a package's. The rule resolves 4,054 more of the corpus's 42,155
  absolute Python imports and changes none, and CPython's `FileFinder` finds the indexer's file for every one it
  resolves. The corpus and the hold-out do not change. netbox's edges found by type go from 2,024 to 4,877.

  Its judgment found two more things:
  - a method a class of the repo declares past a base outside it got no edge; it goes by name again, as an `Unknown`
    does;
  - Django's model managers, `Model.objects.<method>(..)`, are found by name on more sites: 29,474 edges against
    `main`'s 15,961. The author keeps the change, and that growth is TD-026, due in step 6.
- 2026-10-30: PR #49 is validated on a live install (the fifteenth golden round). The dry-runs of `main` and of the
  branch are identical, the graph holds them before and after the reinstall, the picture differs only in the build and
  the `IndexRun` counts, and the 27 calls give the same answers. These snapshots hold no Python file, so the round
  checks the install, not the change.
- 2026-10-30: a Python star import is followed as CPython binds it, PR #51 (`fix(python)`). `from m import *` binds
  `m`'s `__all__`, or its public names, and a later binding holds a name. All 703 star imports of the corpus name a
  module of the repo whose chain is seen whole. In netbox, 9,108 receivers only a star import could bind are read:
  edges found by type go from 4,877 to 8,319, and the share found among several homonyms from 64.0 % to 60.2 %. An
  independent review of 43 seeded rows found none wrong. The module an import names is now found once per file and
  import, and netbox's dry-run is faster than `main`'s. The author puts F1.16 before TS's step 5 (H5-D29).
- 2026-10-30: PR #51 is validated on a live install (the sixteenth golden round). The dry-runs of `main` and of the
  branch are identical, the graph holds them before and after the reinstall, the picture differs only in the build and
  the `IndexRun` counts, and the 27 calls give the same answers. These snapshots hold no Python file, so the round
  checks the install, not the change.
- 2026-10-30: one `CALLS` edge per caller, callee, line and method, PR #53 (`fix(graph)`). The writer merged the edges of
  one line to one target, the last row winning: 161 edges of the micro set lost their `method`, and 2,910 showed a
  weaker strategy than the strongest, mostly an interface's method found again through an implementation that does not
  declare it. The resolver now gives one edge per key, by the strongest strategy, and the writer creates it. The micro
  set's dry-runs lose 68,769 repeated records and nothing else. The review registers TD-027: that implementation gets no
  edge of its own, due in a `fix(csharp)` PR before F1.2.
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
- 2026-10-30: the per-site attribution reads what the resolver makes of a receiver too, PR #56 (`chore(scripts)`),
  which closes H5's gap G2. `answers.py` records, beside the extraction's type, the resolver's answer: a builtin, a
  name an import binds to a package, the repo's type, a type outside the repo, or none. Replayed on H5-D28's import
  roots, it explains all 8,726 changed sites, where `main`'s probe explained none, and on the star imports all 4,657,
  where it explained 792; the `TypeIndex`'s verdict, the reference those judgments used, agrees on every site it
  explains. #47's table is the same.
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
  a call on `base` or on `super()` has `virtual: false`. On the micro set, `CALLS` are the same once `virtual` is left
  out, and the six C# and Python repos gain 159 to 5,888 edges each; each type's ancestors through them are the ancestry
  the resolver walks in C#, and hold its supertypes in Python, the rest explained. The hierarchy costs 0.06 s of
  umbraco's 5.8 s of calls. The corpus and the hold-out are the same. Judged at the source, the calls that do not
  dispatch show `main`'s targets of a `base` call on its own override and of a `super()` found by name, TD-030 and
  TD-031, and the change creates TD-032, two C# types of one name in one file taking each other's bases; all three are
  due in a `fix(resolve)` before F1.16's `feat(mcp)` (H5-D31). Go's interface calls are TD-029. The probe that measures
  them is versioned (`judgment/hierarchy.py`), and the live `after` now waits for the new build.
- 2026-10-31: PR #59 is validated on a live install (the twenty-first golden round). The two C# snapshots gain their
  types' edges, 23 and 20, the other 8 are identical, every `CALLS` edge is the same with `virtual` true, the graph
  holds the branch's dry-runs, and the 27 calls give the same answers; the `after` waited for the new build.
- 2026-10-31: a call that does not dispatch reaches no implementation and no homonym found by name, PR #60
  (`fix(resolve)`, H5-D32). A Python `super()` its receiver does not decide reaches the first class after the caller's
  that binds the name in each MRO of the repo's classes, as CPython looks it up: on netbox, 490 of 841 sites get an
  edge, 466 to one method, and `main`'s 1,754 edges found by name go; the other 351 sites have a base outside the repo
  ahead of the method, or an MRO the index cannot compute. C#'s 18 edges from `base.M()` to the caller's own override
  go, and two types of one qualified name in one file get no `EXTENDS` or `IMPLEMENTS`: 703 edges of the micro set,
  each touching such a name. TD-030 to TD-032 are closed; the judgment at the source registers TD-033, two C# types of
  one name in one file in a call, and TD-034, a type written with a namespace outside the repo read by its simple name,
  both `main`'s and due in `fix(csharp)` PRs. The corpus and the hold-out are the same.
- 2026-10-31: PR #60 is validated on a live install (the twenty-second round). No live snapshot holds what it touches:
  the dry-runs of `main` and of the PR's head are identical on the 10 snapshots, the graph holds them, and the 27 calls
  give the same answers.
- 2026-10-31: a method a dispatching call may run instead of another `OVERRIDES` it, as the instance's language says,
  PR #61 (`feat(graph)`, H5-D33). C# follows `override`, `new`, `static` and interface implementation, by name and
  number of parameters; Python, what each class's MRO finds first, a mixin's method included, and the last definition
  of a name in a class. On the micro set, `CALLS` are the same and the six C# and Python repos gain 126 to 8,000 edges,
  every one method to method; the pairs of one name the edges leave out are other numbers of parameters, methods that
  do not say `override`, static methods, past a `new`, or classes with no MRO, and the edges no such pair gives are a
  mixin's or a base class's that implements a subclass's interface. CPython's `__mro__` gives the Python fixture's edges
  exactly. The overrides cost 0.2 s of umbraco's 5.9 s of calls. The corpus and the hold-out are the same.
