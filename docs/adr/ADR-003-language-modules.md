# ADR-003 — The indexer as a shared core + per-language modules

**Status:** accepted and implemented on 2026-09-17 (F0.4.4) — see "How it turned out" at the end · **Date:**
2026-09-14 · **Phase:** 0

## Context

Today the indexer (`indexer/aidd_indexer/`, ~3.7 k lines) mixes two things: the **pipeline** (discovery, snapshot,
idempotent graph writes, GC, the ref plan, MCP) and the **per-language knowledge** (tree-sitter queries, qualified
name rules, receivers in Go, namespaces in C#, HTTP scanners per framework). The per-language knowledge is scattered:
`extract.py` has `if lang == "csharp"` in several places, `integrations.py` concentrates four scanners in a 900-line
file, `discovery.py` knows every language's extensions and manifests.

Two efforts are going to evolve that knowledge in parallel (handoffs H1 and H2), and SCIP will come in per language
(ADR-002). With the current layout, each effort edits the same large files; conflicts and cross regressions are
inevitable.

## Decision

Split into a **core** and **language modules**, with an explicit contract:

```
aidd_indexer/
├── core/                      # without any `if language ==`
│   ├── pipeline.py            # extract_tree(): discovery → per-file extract → integrations → resolve
│   ├── model.py  ids.py  paths.py (normalize_path, path_key)
│   ├── discovery.py           # walk + modules, consulting the language registry
│   ├── extract.py             # a generic FileExtractor: parse, queries, symbols, calls, imports
│   ├── resolve.py  graph.py  planner.py  manifest.py  gitinfo.py  config.py
│   └── http_base.py           # _BaseScanner: path_of, is_handler_like, resolve_local, add_endpoint/add_call
├── languages/
│   ├── __init__.py            # REGISTRY: language id → LanguageSupport; by_extension(); parseable()
│   ├── base.py                # class LanguageSupport(Protocol)
│   ├── go/        __init__.py  queries.scm  symbols.py  http.py
│   ├── typescript/ (ids: typescript, tsx, javascript)
│   ├── csharp/
│   └── python/
├── mcp/server.py
└── cli.py
```

The `LanguageSupport` contract (what a module declares):

| Member | Lives today in | Example |
|---|---|---|
| `id`, `aliases`, `extensions` | `discovery.LANGUAGE_BY_EXT` | `csharp`, `.cs` |
| `manifests` | `discovery.MANIFESTS` | `go.mod` → `go-module` |
| `grammar` (the name in the language pack) | `extract.load_language` | `csharp` |
| `queries` (a `.scm` file alongside) | `extract.QUERY_DIR` | `languages/go/queries.scm` |
| `qualified_name(chain, name, file)`, `receiver()`, `visibility()`, `namespaces()` | `extract._make_symbol` + ifs | Go: `pkg.Type.Method`; C#: `Namespace.Class.Method` |
| `entry_point_hints` | `extract.ENTRY_POINT_HINTS` / `DECORATOR_ENTRY` | `[HttpGet`, `@Get(` |
| `test_file_patterns` | `integrations.TEST_FILE` | `_test.go`, `Tests.cs` |
| `http_scanner` (a class) | `integrations._GoScanner` etc. | inherits `core.http_base.BaseScanner` |
| `generated_suffixes` | `config.GENERATED_SUFFIXES` | `.pb.go`, `.g.cs` |
| `enrichers` (F1.2) | — | `scip-go` → resolutions for `CALLS` |

Rules:

- The core **never** looks at the language id; only at the registry. Adding a language = creating the folder and
  registering it; nothing changes in `core/`.
- A tenant's specific conventions (the author's architecture pattern, H1) come in as an **optional layer** per
  language (`languages/<lang>/conventions/<name>.py`) switched on by `atlas.yaml` (`conventions: [hexagonal-v1]`),
  never as a global heuristic.
- No dynamic loading of external packages for now (Python entry points wait for a real demand for third-party
  plugins); the registry is static and readable.

## Conventions as extensions (a second layer)

Above the language modules, a **pluggable, versioned** layer for each organization's architecture patterns — which
may be proprietary and evolve at their own pace, and therefore **do not need to live in this repository**.

- A Python package (`aidd_conventions_<name>`, its own repo or a `conventions/` folder here) registers itself at the
  `aidd.conventions` extension point (entry point) and implements the `Convention` contract, all of it optional:

| Hook | Returns | Effect on the graph / MCP |
|---|---|---|
| `classify_module(path, module)` | `layer` (`inbound-http`, `usecase`, `port`, `outbound:<svc>`, `domain`, `platform`) | `Module.layer`, `Symbol.role`; `repo_map` shows named layers |
| `route_patterns(language)` / `client_patterns(language)` | extra HTTP registrars and clients (e.g. `registerRoutes`+`setHandlerSecurity`, `PostJSON`) | go into the language's scanner with `confidence: exact` (a declared convention) |
| `target_of(file, module)` | the target service of an outbound adapter | replaces the heuristic `target_hint` |
| `entry_point(symbol)` | handler / command / job / consumer | the precision of `is_entry_point` |
| `rules()` | structural checks (dependency direction, one handler per path, a single decoder…) | `Violation{rule, severity, evidence}` nodes queryable through the MCP — input for `refine-tech` |

- The declarative part goes in a `convention.yaml` (folder → layer map, registrar/client names, the outbound
  layout); only rules and resolvers need Python.
- Activation per tenant or per repo in `atlas.yaml`: `conventions: [hexagonal-v1]`. Versions coexist
  (`hexagonal-v1`, `-v2`) while the repos migrate.
- The core never imports a convention; it consults the registry. A missing or failing convention degrades to the
  generic behavior **with a warning** — it never brings indexing down.
- Golden rule: nothing specific to one organization goes into `core/` or `languages/`; if a heuristic only makes
  sense for one pattern, it is a convention.

## Migration

A **mechanical refactor, with no behavior change**: the numbers of the public corpus (`scripts/http_corpus.py`) and
of the fixture are the regression — they must come out identical before and after. `INDEXER_VERSION` does not change
(the nodes' semantics are the same), so it does not trigger a re-index.

1. Move `normalize_path`/`path_key` to `core/paths.py`; `_BaseScanner` to `core/http_base.py`.
2. Create `languages/base.py` + the registry; migrate `LANGUAGE_BY_EXT`, `MANIFESTS`, `PARSEABLE`,
   `GENERATED_SUFFIXES`, `TEST_FILE` to the modules.
3. One language per commit: move the `.scm`, extract the `if lang ==` from `extract.py` into `symbols.py`, move the
   scanner into `http.py`. Run the fixture + corpus after each one.
4. `extract.py` and `integrations.py` become thin facades over the registry (or go away).
5. Create the `aidd.conventions` registry, the `Convention` contract and a minimal example convention
   (`conventions/example/`) that only classifies layers by folder — it proves the seam without encoding any real
   pattern. `atlas.yaml` gains `conventions:` (optional).
6. Update `docs/indexer-evolution.md` (the code map, "adding a language", "writing a convention") and the handoffs.

Order: after F0.4.1 (validating the generic extractor on the real portfolio — it separates a bug from the refactor)
and **before** H1/H2 start editing. H1 (the author's pattern) becomes the first real convention written against the
contract, not code inside `integrations.py`.

## Consequences

- H1 and H2 work in different folders (`languages/<lang>/`), and the core stays protected by regression.
- SCIP (ADR-002) has a natural place: `languages/<lang>/enrich.py`.
- Cost: a refactor of a few hours now; the risk is low because the regression is numeric and already exists.
- Left for later: packaging languages as external plugins (entry points) and a declarative `LanguageSupport` in YAML
  — only if third parties need to add languages without touching the repo.

## How it turned out (2026-09-17)

Implemented in a single set of commits, with the planned regression: fixtures 5/5 (3 HTTP + 2 for the conventions
seam) and the **public corpus byte for byte identical** to the baseline — not only the HTTP candidates, but the
symbols, `CALLS`, `IMPORTS`, packages and warnings of the 15 repositories. `INDEXER_VERSION` stays `0.2.1`.

The final layout (differs from the design in details):

```
aidd_indexer/
  cli.py                    extract_tree() stayed here (there was no `core/pipeline.py`)
  core/   config manifest planner gitinfo discovery extract resolve integrations http_base paths graph ids model
  languages/  __init__.py (REGISTRY, by_id, by_extension, parseable, grammars)  base.py (LanguageSupport)
              go/ typescript/ csharp/ python/  → queries.scm  symbols.py  http.py
  conventions/  __init__.py (load/apply)  base.py (Convention, ConventionContext)  declarative.py (convention.yaml)
  mcp/server.py
```

- `LanguageSupport` (`languages/base.py`) has hooks in four groups: identity (`id, grammar, extensions, query_file,
  stack, manifests, manifest_suffixes, builtin_receivers, ecosystem, http_scanner, namespace_nodes,
  entry_point_hints, decorator_entry`), discovery (`discover_modules` — Go packages), symbols (`module_prefix,
  qualified_name, adjust_kind, scope_chain, visibility, doc_extra, import_bindings, file_scope`) and resolution
  (`resolve_setup, resolve_import, link_symbols`). `core/` no longer has any `if language ==`.
- The `typescript` module registers three ids (`typescript`, `tsx`, `javascript`) with the same class and two `.scm`
  files (`queries.scm` for ts/tsx, `queries.javascript.scm` for js).
- The `Dockerfile` pre-downloads the grammars from `languages.grammars()`; `selftest` iterates
  `languages.parseable()`. Adding a language = a folder + one line in `_MODULES`.
- **Left shared** (a conscious decision, nothing gained by splitting now): `TEST_FILE` and the `OUTBOUND` table in
  `core/http_base.py`, `GENERATED_SUFFIXES` in `core/config.py`. If a module needs its own patterns, they become a
  `LanguageSupport` attribute at that point.
- **Conventions** (`aidd_indexer/conventions/`): a `Convention` contract with `configure`, `layer_of`, `target_of`,
  `is_entry_point`, `check(ctx) -> [ViolationInfo]`. Three ways to plug in, all through `atlas.yaml` →
  `tenants.<t>.conventions:` (with optional `repos:`): `path:` for a declarative `convention.yaml` (`layers`,
  `targets`, `entry_points`, `rules`: `forbid_import`, `endpoints_only_in`, `http_calls_only_in`), `id:` for a class
  published at the `aidd.conventions` entry point or referenced as `package.module:Class`. Here we **do use entry
  points**, contrary to what the text above said for languages — conventions are the case where third-party code
  (the organization's) must come in without touching this repo; the language registry stays static.
- Effect on the graph: `File.layer`, `Module.layer` (when all the files agree), a refined `HttpCall.target_hint`,
  `Symbol.is_entry_point`, and `Violation{convention, rule, severity, message, line, evidence}` nodes linked by
  `HAS_VIOLATION` to `File` (and to `Symbol` when attributable); GC by `commit_sha` like the other micro nodes.
  Constraint/indexes in `neo4j/init/schema.cypher`. With no convention configured, nothing changes — that is what the
  test `test_without_conventions_is_untouched` guarantees.
- Not implemented yet (left to H1, which is who needs it): `route_patterns` / `client_patterns` (HTTP registrars and
  clients declared by the convention, going into the language's scanner) and rules beyond the three declarative
  ones. The place is `Convention` + a new hook in `BaseScanner`; no longer another `if` in `integrations.py`.
