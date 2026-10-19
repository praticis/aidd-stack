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

## Docs (H4 phase 0a)

- 2026-10-19: H4 phase 0a: the working docs recycled (`AGENTS.md`, `history.md` and `decisions.md`), and every doc in
  English (H4-D1).

## H5 and H6 (`feature/h5-refactor`, draft PR #7)

- 2026-10-19: H5's safe steps (0–2, 3a, 4a/b, 7a, 8, 9, 10 in part), with the corpus identical at each one.
- 2026-10-19: the H6 handoff is registered: the extraction as a parallel map, a reduce and a per-file cache
  (H6-D1–D4). H5's steps 3, 5 and 6 are designed with it.
- 2026-10-19: H6 step 0 measures the pipeline phase by phase. What it found:
  - the resolver was quadratic in Go and C#, taking 31–38 min on two repos. The HTTP corpus never runs it;
  - an index built once (PR #9, merged into `main`) brings it to seconds;
  - full dry-runs of `main`, H5 and the fix are identical on 12 repos, and that check joins H5's protocol.
