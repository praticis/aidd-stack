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

## H5 and H6 (PR #9; the H6 design, PRs #13–#16; H5's first part, PR #7; step 5 in Go, PRs #17 and #20; C#'s refactor, PR #23; its change of behavior and what a name means, PRs #25 and #27; which extension method a call reaches, PR #30)

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
