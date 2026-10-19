# ADR-002 — The indexer's parser base: tree-sitter now, SCIP as an enrichment

**Status:** accepted · **Date:** 2026-09-14 · **Phase:** 0 (review in F1.2) · **Records:** the ROADMAP principle
"deterministic extraction (SCIP / tree-sitter)"

## Context

The indexer must turn dozens of repositories (Go, .NET, Node/TS, Python), on several branches each, into a micro
graph (symbols, calls, imports) and a macro one (exposed HTTP routes, outbound calls), and keep it current every 15
minutes running in each dev's Docker — without private registry credentials inside the container and without
requiring the repository to compile.

Two families of technology could produce the micro level:

- **tree-sitter**: an incremental per-file parser, grammars for every target language in a single library
  (`tree-sitter-language-pack`), with no type resolution. It extracts definitions, calls by name and imports;
  `CALLS` resolution is heuristic (same file → same module → unique name in the repo).
- **SCIP** (Sourcegraph Code Intelligence Protocol): an *index format* produced by a per-language indexer
  (`scip-go`, `scip-typescript`, `scip-dotnet`, `scip-python`), each one a full compiler/type checker. It gives
  stable global symbols and references resolved with compiler precision.

## Options considered

| | tree-sitter | SCIP |
|---|---|---|
| Prerequisite | none: parses any file on its own | the project must **compile**: `go mod download`, `npm install`, `dotnet restore` — with access and credentials to the registries |
| Toolchain | 1 Python lib, 6 grammars pre-downloaded into the image | 1 indexer + SDK/runtime per language, at each repo's version |
| Time per snapshot | seconds (26 snapshots in ~30 s) | minutes (build + analysis) |
| Call resolution | by name: ~40 % of Go call sites resolved (measured baseline) | ~100 % of what compiles; interfaces, DI and overloads right |
| Framework semantics (routes, HTTP clients, topics) | not for free — heuristics over the tree | not either: SCIP knows `HandleFunc` is `net/http.(*ServeMux).HandleFunc`, not that `"POST /v1/x"` is a route |
| Partial failure | a file with a syntax error does not bring the repo down | a broken build = a snapshot without an index |
| Fit for continuous update | high | low in the dev's Docker; viable on a server/CI with a dependency cache |

## Decision

1. **tree-sitter is the universal base** of the micro level and the only source of the macro one. Every repository
   enters the graph in the first minute, whether it compiles or not; continuous update (U1–U3) stays cheap.
2. **SCIP comes in F1.2 as an optional per-repository enrichment**, not as a replacement: when the language's SCIP
   indexer manages to run for a snapshot, that snapshot's `CALLS` edges gain `resolved: true` and the `Symbol` nodes
   gain `scip_symbol`; when it doesn't, resolution by name stays (`resolved: false`, `strategy`). The schema already
   has both fields (`neo4j/SCHEMA.md`, `Symbol.scip_symbol?`, `CALLS.resolved/strategy`).
3. The integrations layer (`integrations.py`: exposed routes, outbound HTTP calls, future gRPC and messaging) is
   **independent of the resolver** — framework heuristics over the tree, calibrated on a public corpus, with
   `evidence` and `confidence` on each candidate. It is not provisional: it stays on top of SCIP once SCIP exists.
   *Addendum (2026-10-17, F1.14):* it consults a resolver — by name, or SCIP when there is an index — only at the
   points where the decision needs the type of an expression not declared in sight (`needs-resolver`); the rest
   (values, conventions, what is syntactically determined) stays on the tree (`docs/indexer-evolution.md` §8).
4. An LLM is not the parser in any of the layers (the ROADMAP principle). Where a pattern is not statically
   recognizable, the limitation is recorded, not estimated.

## Consequences

- Phase 0's `who_calls`/`symbol_context` have a precision that depends on the code's discipline (unique names per
  module). The `scan` skill already reports each edge's `strategy` and treats `unique-name` as "probable", not
  "certain".
- The trigger to invest in SCIP is a metric, not a principle: when cross-repo `impact` (F2) is limited by the
  resolution rate (~40 % today in Go), F1.2 comes in with that number to beat. Measure per language before choosing
  where to start (Go through `scip-go` is the natural candidate: a single toolchain, fast builds, a cacheable
  `go mod download`).
- Running SCIP will need the server/CI setting (F3): a dependency cache, registry credentials through `token_env`,
  per-language indexers in the image — and per-repo isolation so that a broken build does not block the queue.
- The indexer's per-language modularization (ADR-003, proposed) must make SCIP's entry point explicit: a per-language
  enricher that receives the already extracted snapshot and returns resolutions, without rewriting the pipeline.
