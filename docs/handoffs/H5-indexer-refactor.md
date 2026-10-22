# Handoff H5 — Refactor the indexer before SCIP

> Paste this file (or ask for `docs/handoffs/H5-indexer-refactor.md` to be read) at the start of a new chat. Before
> anything else, the chat should read:
> - `AGENTS.md`, the entry point;
> - `docs/ROADMAP.md`: "Where we are", "Principles", F1.1, F1.2 and F1.13;
> - ADRs 002 and 003;
> - `docs/indexer-evolution.md`: §2 Code map, §5 How to measure and §8 the boundary with SCIP;
> - `docs/corpus-report.md`: the method, where the extractor stands and the baselines table (the current one is
>   `2026-10-18-v2-baseline-29`).
>
> **State (2026-10-22):** in progress. The first part merged as PR #7 (`efeb63d`), a checkpoint the author decided on
> 2026-10-21 (H5-D8): steps 0–2, 4 and 7–9, and 3 and 10 in part. Step 5's Go refactor merged as PR #17 (`3d20873`).
> The rest follows in new PRs, each validated on a live install before its merge. Each is a refactor under the gates,
> except step 5's changes of behavior, which are judged (H5-D10, H5-D12).
>
> - **Done on the night of 2026-10-19.** Corpus and hold-out gave `0 repo(s) differ` against the starting baselines
>   at every code step; the numbers are in `corpus-report.md`, under "H5 baseline" and "H5 steps".
>   - **Step 0:** the baseline and `indexer/scripts/shape.py`, with a CI job that only reports.
>   - **Step 1:** 147 unit tests (`paths`, mounts, `Scopes`, `path_of`).
>   - **Step 2:** `tree.py` (a cursor `walk`, 2.5× faster), the on-demand registry and the end of the import cycle.
>   - **Step 3, in part:** a per-function declarations index for Go's declared type and C#'s locals (`NodeCache`).
>     On vikunja, `walk` dropped to 18 %. The shared `FileIndex` was not done: keeping every node of a file weighs on
>     memory (mattermost has 8 M nodes), and the design is to be decided with the author.
>   - **Step 4:**
>     - Go's, Python's and TS's package facts left the core (`languages/<lang>/package_facts.py`, the
>       `LanguageSupport.package_facts` hook);
>     - Go's `url.URL` and grpc-gateway went to `languages/go/paths.py`;
>     - no core decision tests the language's name any more;
>     - **on 2026-10-20, the typed facts.** Each language's facts are a dataclass (`GoFacts`, `PyFacts`, `TsFacts`)
>       whose fields each declare how two files' values join: one value or none, the last one, or a union
>       (`core/package_facts.py`). The core's `PackageContext` holds them by key and no field of its own is a
>       language's. Go's verb lists and its passthrough lookup left `core/http_expr.py`. A lookup across the repo
>       is a question to the view (`RepoView.defining`; C#'s qualified constants by `RepoView.constant_values`),
>       never a loop over the directories, and a test keeps the view the only code that walks them
>       (`test_repo_view.py`). Tests keep the core free of a language's module or id (`test_core_neutral.py`).
>
>     What the core still names is frameworks, in `http_base`'s receiver catalog and in examples: step 6's catalog.
>   - **Step 7:** every fact a file publishes and every request it leaves pending is a `NamedTuple` of its
>     language, read by field (`languages/<lang>/http_facts.py`; the mount and client-wrapper kinds the core's
>     machinery shares live in the core). A fact is published and looked up by its type (`HttpResult.publish`,
>     `facts_of`), and a pending item carries its request (`Pending.wait`, `HttpResult.waiting`). A shared kind adds
>     its language's scope (`mount_scope`), so each language composes its own. No text key and no positional tuple is
>     left between a scanner and its `compose`. `compose` as an ordered list of steps comes with step 6's
>     `http/compose.py`.
>   - **Step 8:** `core/matching.py`, the MCP split (`tools/list` byte for byte the same) and the Cypher tested
>     against a real Neo4j (`scripts/mcp-it.sh`, 14 cases).
>   - **Step 9:** the docstring without hand-written numbers. The summed time is at 54 % of step 0, within the noise.
>   - **Step 10, in part:** the comments without references to docs or project names, with a test that keeps it so.
>     Reviewing what each comment says is still missing.
> - **The micro graph, checked afterwards (2026-10-19).** The protocol's corpus does not run the resolver, so step 3a's
>   changes to Go's and C#'s types were proven for `CALLS` only by the fixtures. Since then, full dry-runs of `main`
>   (`d055783`) and of the branch (`e5796a0`) have been compared record by record on 12 repos, and they are
>   identical. That check is now item 4 of the protocol.
> - **Step 5, Go's refactor (PR #17, merged on 2026-10-21 and validated on a live install, the seventh golden
>   round).** Three commits, each under the protocol, with the graph identical:
>   - **The `TypeIndex` API in the core** (`core/types.py`). `RepoTypes` builds each language's index once per repo,
>     on its first question, and the HTTP pass and the resolver share the instance (`ExtractionResult.types`).
>   - **Go's type facts as typed values with no tree node** (`languages/go/type_facts.py`). They were checked equal to
>     the old dicts on the 21,624 Go files of the corpus and the hold-out. A C# generic call tests every homonym as an
>     extension method, so it now leaves out the symbols of another language: a Go method of the same name would
>     have had its typed facts read as C#'s dict.
>   - **Go's resolver asks `GoTypeIndex`** (`languages/go/type_index.py`), which holds PR #9's indexes: the files by
>     package and the method sets. The micro graph was compared on the 12 repos and on the corpus's 13 other Go
>     repos, and all are identical. The protocol first caught a crash: a `#` inside a call's own text
>     (`doc.Find("#id").Children()`) was read as a result number. `test_a_hash_in_the_text_of_a_call_is_no_result_number`
>     holds the case.
>
>   `go/symbols.py` went from 497 to 288 lines. The scanner's read of a field through the index went to the change of
>   behavior (H5-D11).
> - **Step 5, Go's change of behavior (PR #20, merged on 2026-10-21 and validated on a live install, the eighth
>   golden round).** One answer for the resolver and the scanner, Go's own scoping, three older gaps of the type service
>   closed (H5-D15), judged by case, and baseline `-29`. "Go's change of behavior" below has the results.
> - **Step 5, C#'s refactor (PR #23, merged on 2026-10-22 and validated on a live install, the ninth golden round).**
>   Two commits, each under the protocol, with the graph identical:
>   - **C#'s type facts as typed values with no tree node** (`languages/csharp/type_facts.py`: `CsTypes`, `CsType`).
>     They were checked equal to the old dicts, in their order, on the 35,255 C# files of the corpus and the hold-out.
>   - **C#'s resolver asks `CsTypeIndex`** (`languages/csharp/type_index.py`), which holds the indexes the resolver
>     kept in the context: the types by simple and by qualified name, the implementers and the DI chains. A type is
>     found from a file as before: the only one of its name, or the only one among the namespaces the file sees. A
>     type found that way has a single declaration, so the API by `TypeRef` answers what the old tuples did, partial
>     types included.
>
>   The micro graph was compared on the 12 repos and on the corpus's 11 other C# repos, and all are identical.
>   Alone, on one image, the corpus summed 746 s on `main` and 774 s on the branch, within the noise: the repos whose
>   code did not change moved more than the C# ones. `csharp/symbols.py` went from 674 to 396 lines. The scanner takes
>   `members` and `type_text` from the facts module; its read of a local's type goes to the change of behavior.
> - **Step 5, C#'s change of behavior (PR #25, merged on 2026-10-22 and validated on a live install, the tenth golden
>   round).** One answer for the resolver and the scanner, with C#'s own scoping, and four older gaps of the type
>   service closed (H5-D16): a `partial` type is one type, a method's declared result, the repo's extension methods on
>   a typed receiver, and a type written with its namespace and type arguments. Judged by case; the corpus and the
>   hold-out are unchanged, so the baseline stays `-29`. "C#'s change of behavior" below has the results. Two more gaps
>   of what a name means in C# go in a PR of their own, right after (H5-D17).
> - **Next (H6-D1):** H6 (`docs/handoffs/H6-extraction-pipeline.md`) is designed: the extraction as a parallel map,
>   a reduce and a per-file cache, with ADR-004 to ADR-006 accepted on 2026-10-20. Step 3's `FileIndex` becomes H6's
>   per-file index, and steps 5 and 6 are designed against it (ADR-005, ADR-006). Then, built toward that design:
>   - 5 (`TypeIndex`, built in the reduce, and from a batch's facts for the scans made in map 1): the API in the
>     core, then Go, C#, Python and TS, each a refactor and then a change of behavior (H5-D7, H5-D10). Go's refactor
>     and its change of behavior are done, and the `fix(mcp)` for the order of `symbol_context`'s imports merged as
>     PR #19. C#'s refactor and its change of behavior are done. Next: the `fix(csharp)` of H5-D17, then Python and
>     TS;
>   - 6 (recognizers with a YAML catalog, one language per commit);
>   - 12 (the rest of the code to the shape targets, H5-D6);
>   - the rest of 10;
>   - 11 (docs).
>
>   Then H6 is plugged in.
>
> The author's decisions are under "Decisions made". The handoff was born from a review asked for in the middle of
> the F1.14 close. After 24 rule commits since corpus v2, the extractor's code had functions of very high complexity,
> large files and two parallel implementations of "what is the type of this". That has to be solved before SCIP
> (F1.1/F1.2), because SCIP plugs in exactly at that seam.

## Context in one paragraph

H2 and F1.14 took the HTTP extractor from almost nothing to 99–100 % precision and 89–99 % recall on the 55-repo
corpus. The method was one rule per increment, each with a fixture and a judged corpus run. The method worked. What
it did not do was reorganize the code between one rule and the next. Each rule went in where it fit: one more `if`
in the method that already handled calls, one more field in `PackageContext`, one more fact with a text key. The
result measures well and reads badly. H5 is a refactor **with no behavior change**: the corpus and the hold-out must
come out identical to the starting baseline, step by step. The one exception is step 5's changes of behavior, each
judged at the source and closed with a new baseline (H5-D10, H5-D12). It prepares three things: SCIP (a single point
where the type of an expression is asked), scale (F1.13) and maintenance (rules as units that are tested on their
own).

## Diagnosis (measured on 2026-10-18, over `713fec8` + F1.14 item 2 in progress)

**Size and complexity.** 11,957 non-empty lines in 54 files and 736 functions. Cyclomatic complexity counts the
branches (`if`, loops, `and`/`or`, `except`); 10 is the usual limit of a function that is easy to test.

| Complexity | Functions | | Size | Functions |
|---|---|---|---|---|
| 1–10 | 545 | | 1–30 lines | 664 |
| 11–20 | 127 | | 31–60 | 55 |
| 21–40 | 51 | | 61–120 | 15 |
| 41–80 | 11 | | more than 120 | 2 |
| more than 80 | 2 | | | |

The worst ones:

| Function | Complexity | Lines |
|---|---|---|
| C# `_controller` | 118 | 118 |
| Go `_call` | 95 | 104 |
| MCP `build_server` | 74 | 610 |
| `_path_of_call` | 69 | 59 |
| `collect_constants` | 66 | 76, nesting 7 |
| TS `_read_call` | 62 | 69 |
| `resolve_calls` | 55 | 95 |
| C# `_fast_endpoint` | 51 | 58 |
| C# `_route_attribute` | 50 | 58 |

The files above 600 non-empty lines:

| File | Lines |
|---|---|
| `languages/csharp/http.py` | 1410 |
| `languages/typescript/http.py` | 892 |
| `core/http_expr.py` | 831 |
| `mcp/server.py` | 793 |
| `languages/go/http.py` | 685 |
| `cli.py` | 617 |
| `core/http_base.py` | 609 |

**Mixed responsibilities.**

1. **`core/` knows the languages, which ADR-003 forbids.** ADR-003 says the core "never looks at the language id".
   Even so:
   - `core/http_expr.py:92` does `go, py = fx.file.language == "go", ..` and holds language rules: `_ts_client`,
     `_ts_interceptor`, `_ts_client_class`, `_py_class`, `_go_struct`, `_passthrough`, `_enum_member`, Go's
     `url.URL` and grpc-gateway's `runtime.NewPattern`;
   - `PackageContext` (`core/http_base.py`) has fields for each language: `client_bases` (TS), `classes` (Python),
     `struct_fields`, `passthrough` and `verb_lists` (Go).
2. **Two type systems in parallel.** The micro resolver (`languages/*/symbols.py`, with `file_facts` and
   `ResolveContext.facts`) and the HTTP scanners each answer, in their own way, "what is the type of this value":
   - Go: `go/symbols.py:_declared_type` and `go/http.py:_value_type`. Both read the receiver, the parameters and
     `x := &T{}`. F1.14 item 2 went as far as duplicating the struct fields too (`PackageContext.struct_fields`);
     before the commit, it switched to reading the resolver's `file_facts["structs"]`, handed on per directory
     (`PackageContext.file_facts`). It is a patch until `TypeIndex`;
   - C#: `csharp/symbols.py:_local_type` and `csharp/http.py:_declared_type`;
   - per language, also: `router_param_type`, Python's `_router_class`, TS's `_client_of`, `RepoView`'s
     `classes_named`, and C#'s `_reaches_fast` and `_inherited_route`.

   SCIP is going to answer that question. Today it would have to come in at ten places.
3. **Framework knowledge is scattered in code.** Verbs, registrars, prefix carriers, app constructors and client
   receivers are in loose constants per scanner (`GO_REGISTRARS`, `GO_MOUNTS`, `GO_PREFIXED`, `CS_MAP`, `FE_VERBS`,
   `TS_ROUTER_VERBS`, `KOA_ROUTERS`, `CLIENT_RECEIVER` ..). The framework name written on the route is decided inside
   Go's `_call` by a heuristic on the method name. F1.14 item 7 already asked for the catalog as data.
4. **The methods are "all-in-one".** `_call` (Go), `_read_call` (TS), `_invocation` and `_controller` (C#) classify
   the callee and decide between a route, a mount, a router handed on, a generated client and an outbound call, in a
   single flow of `if`s. A new rule is one more `if` in that flow, and the order between them is implicit.
5. **Facts and pending calls are typed by text.** There are about 35 fact keys (`"cs.fe-group"`,
   `"ts.mount-wrapper"`, `"go.encoder"` ..) with values in positional tuples, unpacked far from where they were born
   (`bases, controller, prefixes, area, own, uses, versions = p.key`).
6. **The path-matching rule exists in more than one place.** The linker compares an ASP.NET route case-insensitively,
   and the MCP only started doing the same today (`98b8368`). `who_consumes` still computes the key with a regex of
   its own (`mcp/server.py:608`), not with `paths.normalize_path` + `path_key`, so an asked `:id` is not normalized.
7. **There is an import cycle.** `core/http_base` imports `languages/base`, which goes through
   `languages/__init__`, which imports every language, which import `core/http_base`. Importing
   `aidd_indexer.core.http_base` first fails. It only works because the usual import order hides the cycle.

**Performance.** A profile of vikunja's whole extraction (2134 files, 51 s without the profiler):

| Function | Calls | Cumulative time | Share of the total (93 s, with the profiler) |
|---|---|---|---|
| `walk` | 55.6 million | 52 s | 56 % |
| `go/symbols.py:_declared_type` (through `call_receiver`) | 63,820 | 32 s | |
| `collect_constants` | | 14 s | |
| the TS scanner's `run` | | 15 s | |

- `walk` is a Python generator that materializes the list of children of each node. Almost half of it comes from
  `_declared_type`, which walks the whole function for each call receiver: it is quadratic per function.
- Each file is walked whole four to six times: the extractor's queries, `file_facts`, `collect_constants`, the
  scanner's `run` and the sub-walks (`function_of`, `_param_values` ..).
- In the corpus, HTTP is 208 s of 1255 s of extraction, and the rest is parsing, symbols and resolution. mattermost
  takes 219 s, bitwarden 128 s, photoprism 101 s (only 8 s of HTTP).
- A whole corpus run takes about 21 min in series. That is each step's regression cycle, so shortening it is part of
  the goal.

**Scale (F1.13).** `extract_http` receives all the repo's extractors with their trees alive, because the two passes
(constants, then scanners) need them. grafana dies of memory at 7.7 GB. The refactor does not solve F1.13, but it must
not close the door: the second pass has to be able to re-parse a file, instead of requiring the stored tree.

**Tests.**
- The whole of HTTP goes through one parametrized test (`tests/test_fixtures.py`, 16 fixtures). When it fails, it
  says which routes are missing, not which rule broke.
- There is no unit test for `core/paths.py`: `normalize_path` has 19 regexes whose order matters. There is none for
  `http_mounts`, `http_scope` or `http_expr` either.
- `test_mcp_protocol` uses a fake store and runs no Cypher. What proves the queries are the golden questions, run by
  hand.

**What is good and should stay.**
- The `core/integrations.py` orchestrator is lean.
- The mount graph (`core/http_mounts.py`) is small and general.
- The F1.13 rule holds: a scanner never reads another file's tree; what crosses files goes through facts and
  `compose`.
- The `except Exception` blocks are deliberate boundaries, per file and per repo, and they are commented.
- The rule → fixture → judged corpus cycle is the project's best asset, and H5 uses it as its net.

## Goal

At the end of H5:
- the corpus and the hold-out are **identical** to the starting baseline, but for step 5's judged changes (H5-D12);
- extracting the whole corpus takes **≤ 60 %** of today's time (a target to confirm in step 0);
- the shape targets the author decided hold:
  - **single-digit complexity**: no function above 9 (`ruff`, rule `C901`, `max-complexity = 9`), with no
    exception. A dispatcher is a lookup in the catalog, not a chain of `if`s;
  - **no module longer than 300 lines**, counted over the whole file the way `wc -l` counts: docstrings and comments
    included. That is about 12 thousand lines of today split into packages per language and per role;
  - `core/` with no language or framework name at all, checked by a test;
  - a single type service that the micro resolver and the HTTP scanners consult, and where F1.2 plugs SCIP in;
  - rules as units: each one with a name, a cheap precondition, a fixture and a test of its own.

## Target architecture

1. **Neutral tree utilities** (`aidd_indexer/tree.py`):
   - `node_text`, `walk` with a `TreeCursor` (no list of children per node) and a per-file index (`FileIndex`);
   - `languages/base` and `core/` import from here, and the cycle goes away;
   - the language registry loads on demand.
2. **`FileIndex`, one pass per file.** It is built once, right after the parse, and shared by the symbol extractor,
   the constants collector and the scanner. It has:
   - the nodes by type;
   - the functions by id, with each one's parent;
   - the declarations and assignments per scope, which today are `Scopes._assignments` and `_declared_type`;
   - the identifiers by name and scope;
   - the calls.

   The ad hoc walks (`function_of`, `_idents`, `_param_values`, `walk(scope)`) start consulting it.
3. **A type service** (`TypeIndex`, SCIP's seam). The questions are:
   - `declared_type(value)`: receiver, parameter, `var x T`, composite literal, struct or class field;
   - `bases(type)`, `method(type, name)` and `field(type, name)`;
   - `return_type(function)`, when declared.

   The current implementation comes from each language's `file_facts`, consolidated per repo. The micro resolver
   (`call_receiver`) and the HTTP scanners use the same instance. What is `needs-resolver` today (ADR-002, addendum)
   becomes a call to that service that returns "I don't know". In F1.2, a SCIP implementation answers the same
   questions when there is an index.
4. **Package facts per language.** The core's `PackageContext` keeps what is general: path constants, constant
   pieces, `env_hints` and functions by name. Each language registers its own collector
   (`LanguageSupport.collect_package_facts`) and its own typed facts class: TS's clients with a base, Python's router
   classes, Go's passthrough and verb lists. The code of `_ts_client`, `_py_class`, `_go_struct`, `url.URL` and
   grpc-gateway moves to `languages/<lang>/`.
5. **Rules as recognizers.** Each language's `_call`/`_invocation`/`_read_call` becomes a dispatcher over an ordered
   list of recognizers. Each one declares:
   - a cheap precondition, such as the node type and the callee's name in a set, for the dispatcher to index;
   - `apply(node) -> bool`.

   The order is explicit in the list. Each recognizer matches one line of the guide's table (`indexer-evolution.md`
   §3), with its fixture case and its test. C#'s `_controller` is split the same way: reading attributes, detecting
   the controller, publishing inheritance, FastEndpoints and the actions. With 300 lines per module, each language
   becomes a package (`languages/<lang>/http/`), with one module per group of recognizers (routes by attribute,
   routes by call, mounts, clients), plus `compose` and the facts.
6. **The framework catalog as data, in YAML** (F1.14 item 7; H5-D2):
   - one file per language (`languages/<lang>/frameworks.yaml`). Per framework, it holds the name written on the
     route, the verbs, the registrars, the prefix carriers, the app/router constructors and the client receivers;
   - a schema validated at load time, with a test. An invalid catalog fails loudly in the test and degrades with a
     warning during indexing, like the conventions;
   - the recognizers read the catalog. The conventions (F0.4.5), which are already YAML, extend the same catalog;
   - the `built_bundle` thresholds become named parameters.
7. **Typed facts and pending calls.** Each fact is a `NamedTuple` of its kind (for example `FeGroup(prefix,
   parent)`, published under the group's name), and each language's `compose` is an ordered list of steps that
   consume typed facts. The text keys and the positional tuples go away.
8. **One path-matching rule.** A module (`core/matching.py`) with `path_key` and the case-sensitive or insensitive
   comparison per framework. The linker, the MCP and the corpus scorer use it.
9. **The MCP split.**
   - `build_server` (610 lines) is split into modules per group of tools.
   - The Cypher becomes named constants in a queries module.
   - An integration test runs each query against a real Neo4j (an ephemeral container) with a small graph seeded by
     the fixture. It is the `who_consumes` lesson.
10. **A shorter corpus loop.**
    - Parallelism already exists since 2026-10-18: `indexer/scripts/corpus.sh` runs one container per repo, the
      largest first, with a memory cap on each, and joins the report at the end. This step measures the gain in what
      each repo spends, not on the clock: the sum of the per-repo times the script records (1,382 s on `baseline-26`,
      with 3 in parallel).
    - The docstring's numbers are generated from the baseline, instead of edited by hand on every increment.
11. **Comments with only what is strictly pertinent** (H5-D4). The docs are still going to be reorganized, so the
    code does not point at them. The rules:
    - a comment says the why the code does not: a contract, an edge case, the reason for an order. It does not
      narrate the code or catalog the cases that motivated the rule;
    - no reference to docs or planning items: ROADMAP, `F1.x`, `H2-Dx`, ADR, guide sections, the corpus report;
    - no project name. A private name (tenant, a client's service) never appears, and where the comment needs an
      example, it uses a neutral name (`orders-api`, `PARTNER_API_URL`). The names of the corpus's public apps, such
      as vikunja and gitea, go too: the example describes the shape of the code (`a group passed through a struct
      field`), and only a framework or library name stays when it is what defines the behavior (gin, FastEndpoints,
      grpc-gateway);
    - the fixtures follow the same rule: the comment describes the shape, not the app it came from. The corpus's
      expected lists (`tests/corpus_expected/`) keep the names, because they are about those repos.

## Steps

Each step is one commit, or a few, with the done criterion below **and** the regression protocol. The order goes from
the safest and cheapest to the most structural. The test nets go in before code is moved.

| # | Step | Done when |
|---|---|---|
| 0 | Baseline: freeze `v2-baseline-N` and the hold-out; measure alone (with no other load) the corpus time and the profile of 4 repos (mattermost, vikunja, umbraco, ghost); in CI, a report (not blocking) of `ruff C901` with `max-complexity = 9` and of modules above 300 lines | the numbers recorded in `corpus-report.md` (an "H5 baseline" section), with the count of functions and modules off target |
| 1 | A unit test net: a case table for `normalize_path`/`mask_placeholders`/`path_key` (each regex with a case, and the pairs whose order matters), `http_mounts`, `Scopes`, `path_of` | covers each rule of `paths.py`; mutating a regex breaks a named test |
| 2 | `aidd_indexer/tree.py`: a `TreeCursor` `walk`, `node_text`, the end of the import cycle, the on-demand registry | `import aidd_indexer.core.http_base` alone works; the `walk` profile drops |
| 3 | `FileIndex` (designed in H6, as the per-file index inside a worker): one pass per file; `_declared_type` (Go), `_local_type` (C#), `Scopes`, `function_of`, `_idents` consult the index | no scope walk per call; vikunja's profile: `walk` < 20 % |
| 4 | Package facts per language: the language code leaves `core/http_expr.py` and `PackageContext`; typed facts | a test proves `core/` names no language or framework |
| 5 | `TypeIndex` (ADR-005), first its API in the core, then one language at a time: Go, C#, Python, TS (H5-D7), each a refactor and then a change of behavior (H5-D10, "Step 5" below). Each language's `file_facts` become typed facts; the per-file answers (a local's, a receiver's, a parameter's type) are one code for the resolver and the scanner, which is what step 3 left; the resolver's indexes (`resolve_setup`) move into the `TypeIndex`. Go's `_declared_type` against `_value_type`/`_field_type`/`_local_type`, C#'s `_local_type` against `_declared_type` and `_reaches_fast`, Python's `_router_class` and its classes by `RepoView.defining`, TS's `_client_of` start consulting it | a single implementation per language of "declared type"; an answer is a value or `Unknown` with its reason, and `Unknown` is what `needs-resolver` was |
| 6 | Recognizers + the YAML catalog, **one language per commit**, from the worst to the smallest: C# (`_controller`, `_invocation`), Go (`_call`), TS (`_read_call`), Python | no function > 9 and no module > 300 lines in those packages; each line of the guide's table points to a recognizer |
| 7 | A typed `compose` per language; a typed `Pending` | no positional tuple between the scanner and `compose` |
| 8 | `core/matching.py`; the MCP split; Cypher tested against an ephemeral Neo4j | `who_consumes` uses `normalize_path`; the 11 tools with an integration test |
| 9 | A generated docstring; the corpus loop through `corpus.sh` | the sum of per-repo times at ≤ 60 % of step 0's |
| 10 | A general review of comments and docstrings (architecture, item 11), in the code, the tests and the fixtures; replacing project names | no reference to docs or project names in the code, checked by a test; the comments that stayed say a why |
| 11 | Docs: ADR-003 updated (or a new ADR: recognizers, catalog, type service); `indexer-evolution.md` §2, §5 and §7 | the guide describes the code as it turned out; the shape report in CI shows zero functions and zero modules off target, except `cli.py` until P2 (H5-D5, H5-D6); blocking turns on when the author decides (H5-D3) |
| 12 | The rest of the code to the shape targets (H5-D6): the core (`http_base`, `http_expr`, `extract`, `graph`, `resolve`, `mirror`), the languages' `symbols.py` that step 5 leaves, the conventions, the MCP's tool groups, and the scripts and tests the ratchet reads (`http_corpus.py`, `test_conventions.py`, `test_mcp_protocol.py`'s `read`) | the shape report shows nothing off target but `cli.py` |

**Regression protocol (every step).** Items 1 to 4 run in CI on every push (`.github/workflows/indexer.yml`, H7's
first slice). H5's code commits are `refactor:`, so its PRs are read as refactors, where any difference fails. Step 5's
changes of behavior are `feat:` or `fix:` PRs instead: the corpus and the micro set are judged (H5-D14), and the
hold-out is read only in aggregate (H5-D13). Locally: `test.sh`, `corpus.sh`, `micro.sh` and `gates.sh`.
1. tests green;
2. the corpus against the starting baseline: "0 repo(s) differ";
3. the hold-out identical;
4. **the micro graph identical:** `indexer/scripts/micro.sh`, full dry-runs (`aidd index --dry-run --out`) of `main`
   and of the step, compared record by record. This covers files, symbols, `CALLS`, `IMPORTS` and violations, over H6 step 0's 12 repos:
   - C#: eshop, jellyfin, btcpayserver, umbraco;
   - Go: vikunja, gitea, mattermost, grafana;
   - Python: dispatch, netbox;
   - TS: ghost, outline.

   The HTTP corpus does not run the resolver, so items 2 and 3 cannot see a change to `CALLS`;
5. the step's time, measured alone, no worse than the previous one, unless justified;
6. **the shape no worse:** `indexer/scripts/shape.py --against main` finds nothing new or grown over a target (in CI
   too, H5-D9).

A difference in the corpus is a defect of the step, not a gain. If the refactor reveals a real bug, it is recorded,
fixed in a separate commit, with a fixture case, and goes into the baseline by explicit decision.

## Step 5: one type answer, without losing what either side answers (H5-D10)

Each language answers "what type does the code declare for this value" twice: the micro resolver types call
receivers for `CALLS`, and the HTTP scanner follows a router into a method of a typed value. The two answers differ,
and each side answers cases the other misses. One answer for both changes the graph on at least one side, so step 5
goes in two PRs per language:

1. **A refactor, with the graph identical.** The `TypeIndex` API and the language's typed type facts; the resolver asks
   the `TypeIndex`, with PR #9's indexes inside it.
2. **A change of behavior, right after.** One answer inside a file for both sides, and the scanner reading a field
   through the `TypeIndex` and taking its whole answer (H5-D11). Every difference below has its case. The corpus and
   the micro set are judged at the source under `graph-change`, and the PR must gain the xfails and lose no guard.

**Go**, in `indexer/tests/test_go_types.py`. A guard passes today; an xfail is strict, so it fails the suite once it
passes.

| Case | Resolver | Scanner | Test |
|---|---|---|---|
| `h := &T{}` | typed | typed | guard `composite-literal` |
| `s.F`, a direct field of the package's struct | typed | typed | guard `field` |
| `h = &T{}`, a plain assignment | — | typed | guard `assignment` |
| a block's local that shadows a parameter | the parameter's type | the local's | guard (scanner), xfail (resolver) `block-shadows-a-parameter` |
| a block's local that has gone out of scope at the use | the parameter's type | the block's local | guard (resolver), xfail (scanner) `a-block-local-out-of-scope` |
| `h, err := h.Copy()`, a `:=` that only assigns a parameter again | the parameter's type | — | guard (resolver), xfail (scanner) `a-redeclaration-keeps-a-parameters-type` |
| the same `:=` after `h := &T{}` in its block | the call's result | — | xfail (both) `a-redeclaration-keeps-its-type` |
| `h = h.With(..)`, a plain assignment to a parameter | the parameter's type | — | guard (resolver), xfail (scanner) `a-plain-assignment-keeps-the-type` |
| a closure inside a closure | one function out only | every function out | guard (scanner), xfail (resolver) `closure-in-a-closure` |
| a closure's local of the same name, before the use | read as the function's | kept inside | xfail (resolver) `a-closure-keeps-its-locals` |
| `h := T{}` without a pointer, and `h := &T[X]{}` of a generic type | typed | typed | guards `value-literal`, `generic-literal` / `test_a_generic_type_reaches_its_method` |
| `var h = &T{}`, a `var` with a value | — | typed | guard (scanner), xfail (resolver) `var-with-a-value` |
| `h := pkg.New()` | the constructor's declared result | — | xfail (scanner) `constructor-result` |
| `h, err := pkg.New()` | its first declared result | — | guard (resolver), xfail (scanner) `constructor-of-two-results` |
| `var h = pkg.New()` | — | — | xfail (both) `var-with-a-constructor`: what the two rows above give together |
| `var h T` | typed | — | guard (resolver), xfail (scanner) `var-declaration` |
| a named result | typed | — | guard (resolver), xfail (scanner) `named-result` |
| a field promoted from an embedded struct | typed, 4 levels deep | — | xfail (scanner) `promoted-field` |
| a field of another package's struct | typed | — | xfail (scanner) `field-of-another-package` |
| a struct declared in two files of the package (build tags) | the first file that declares it | any file whose struct has the field | guard (scanner), xfail (resolver) `a_struct_declared_in_two_files` / `a_field_of_a_struct_declared_in_two_files` |
| a field's type under the alias of the struct's own file | resolved in that file | resolved with the scanned file's imports | xfail (scanner) `test_a_field_type_under_the_alias_of_the_file_that_declares_it` |
| a package in a directory whose name has a dot (`web.handlers/`) | finds none of its files, so none of its structs | typed, by the directory's path | guard (scanner) `test_a_package_in_a_directory_with_a_dot`, xfail (resolver) `test_a_field_of_a_package_in_a_directory_with_a_dot` |

On the scanner's side, each xfail is a route that loses its group's prefix (`GET /users` for `GET /api/users`). On the
resolver's side, each is a `CALLS` edge to the wrong method, or one found by name instead of by type. The two answers
also write a type differently: the resolver's is normalized (`*pkg.T` and `[]T` become `pkg.T` and `T`), the scanner's
is the text as written. A plain assignment of another type to a variable that a `var` declared with an interface type
is left out on purpose: which method it reaches is not a fact the declaration states.

Neither side reads a type assertion (`h := x.(*T)`), a type switch, a `range` variable or a package-level variable.
Those are left out of step 5: each would be a rule of its own, with its own cycle, and here every change has to come
from a case of the table.

Past a local's own declaration, the micro set of the one answer showed three gaps of the type service, older than
step 5. Each lost edges the wrong answers had found by luck, so they close in the same PR (H5-D15), in
`indexer/tests/test_go_declared_types.py`:

| Case | Today | Test |
|---|---|---|
| a method an embedded struct promotes, at any depth and from another package | a typed receiver finds no method, so no edge | xfail `test_a_call_reaches_a_method_its_receivers_type_promotes`, guard `its-own-method-wins` |
| a type parameter (`func F[T any]() T`, `x T`, a field `v T`) | taken for a type the package declares, so no edge | xfail `test_a_type_parameter_types_nothing_so_the_call_is_found_by_name`, guard `a-methods-result` |
| `y := x.M()`, the result a method declares: own, an interface's, promoted, through a field, in a chain | untyped, so the call is found by name | xfail `test_a_local_has_the_type_its_methods_result_declares`, `test_an_error_a_method_returns_reaches_no_error_type_of_the_repo` and, for the scanner, `test_a_group_reaches_the_method_of_a_local_a_method_returns` |

### Go's change of behavior

One answer, with Go's own rule: **a variable's type is the one its declaration gives it**, from the nearest
declaration in scope before the use, from the innermost block and function out. A receiver, a parameter and a named
result declare a type, and so do `var x T`, `x := T{}` or `&T{}`, and `x := pkg.New()` when `New` declares its result.
A plain assignment never changes a variable's type, so it types nothing: the guard `assignment` passes through its
`var`. Nor does a `:=` that names a variable its own block already declares, or a parameter at the top of the
function's body: Go only assigns that variable again.

- **The boundary with SCIP stays where the guide puts it** (`indexer-evolution.md` §8): only a declared type counts.
  A function's result counts when its signature declares it, never by following its `return`s. The scanner does not
  follow an interface to its single implementer: that is dispatch through an interface, `needs-resolver`, and stays
  the resolver's `receiver-type-impl`.
- **One code inside a file.** A Go module answers a local's type for the resolver's `call_receiver` and for the
  scanner alike, on step 3a's index of each function's declarations.
- **Across files, the `TypeIndex`.** The scanner asks through `view.types`, so that H6 can record each question with
  its answer (ADR-005, ADR-006). A field gets the whole answer (H5-D11): every file that declares the struct, the
  imports of the file that declares it, promoted fields and other packages' structs. `PackageContext.file_facts`, which
  only the scanner's field lookup reads, goes away.
- **The cases first.** Before any code, probes tried the forms the table did not hold: `var x = expr`, a `range`
  variable, a type switch and a type assertion, `h, err := pkg.New()`, `T{}` without a pointer, a generic `T[X]{}` and
  a package-level variable. The ones a side reads are in the table now, and the ones neither reads are left out.
- **Judged, not identical.**
  - The corpus goes through the guide's cycle, with the expected lists in commits of their own.
  - The micro set is judged by case (H5-D14), and the hold-out is read only in aggregate (H5-D13).
  - Then come a new baseline, new rows in the guide's §3, the live install and a golden round, because Q4's
    `impact_of` reads `CALLS`.
- **The time,** measured alone, keeps step 3a's gain (protocol item 5).

**Done (2026-10-21).** Eight commits, each measured against the one before:

1. the cases (`indexer/tests/test_go_types.py`), with a redeclaration and a plain assignment, which a first run of
   the one answer showed the table missed;
2. one answer inside a file (`languages/go/locals.py`);
3. fields through the `TypeIndex` (the scanner asks `view.types`; `PackageContext.file_facts` is gone);
4. the cases of the three gaps (`indexer/tests/test_go_declared_types.py`, H5-D15);
5. a method an embedded struct promotes, the shallowest first (Go's `supertypes`);
6. a type parameter declares no type;
7. a method's declared result (`TypeIndex.method_return_type`);
8. the embedded types found once per type.

Every xfail of both tables is gained and no guard is lost.

- **The corpus:** two items, both from commit 3, both right at the source and both outside their lists' scope, so
  no expected list changes. vikunja's `POST /mcp` is `POST /api/v2/mcp` (`m, err := mcpmodule.New(..)`, then
  `m.Register(a)`; the repo's own `RoutePrefix` is `apiv2.GroupPrefix + "/mcp"`). memos gains `ANY /`, its
  frontend's `mux.Handle("/", s.Handler(fallback))`, as argo-cd's list holds `mux.Handle("/", assetsHandler)`. The
  hold-out gives `0 repo(s) differ`, read in aggregate. The new baseline is `2026-10-18-v2-baseline-29`.
- **The micro set:** the 8 repos of other languages are identical. On the 17 Go repos, from `main`: +18,874 and −47
  typed edges, −4,339 and +353 `inherited`, −11,077 and +482 found by name. Judged by case on seeded samples:
  - the one answer types a receiver in a closure inside a closure, keeps a closure's or a block's local inside it,
    and reads `token, err := token.CreateToken(..)` as the package's function;
  - promoted methods turn 4,332 `inherited` edges into the method itself (gitea's `ctx.Tr` was
    `services.context.Context`, and is `services.context.Base.Tr`);
  - type parameters give gitea's `AssertExistsAndLoadBean[T]` locals their calls by name back;
  - a method's result removes guesses that were wrong (`err.Error()` to an error type of the repo,
    `response.Status()` to a fake).
- **What stays lost** is what H5-D15 leaves out. A guess by name on a receiver whose declared type is an interface
  goes (mattermost's `store.Store`, kratos's `persistence.Persister`: about 750 edges), as `main` already does for
  the same variables nested less deep. A variable of a form neither side reads (`range`, a type switch, an
  assertion) loses what `main` read from an out-of-scope declaration of the same name (about 60 sites). In a
  function the grammar does not parse (grafana's Go 1.26 `new(expr)`), scopes are what error recovery left. A
  generic's inferred type (`u := AssertExistsAndLoadBean(t, &User{})`) is SCIP's.
- **The time, alone,** on one image: the corpus summed 763 s on `main` and 768 s on the branch.

**C#**, in `indexer/tests/test_cs_types.py`. Where a side was wrong before the change, its column says what it gave.

| Case | Resolver | Scanner | Test |
|---|---|---|---|
| a parameter, `var x = new T(..)`, `T x = Make()`, a field, a property, a primary constructor's parameter | typed | typed | guards `a-parameter`, `a-local-created-with-new`, `a-local-of-a-written-type`, `a-field`, `a-property`, `a-primary-constructor-parameter` |
| a field whose type is an interface | the interface and its single implementer | typed | guard `an-interface-typed-field` |
| `var x = sp.GetRequiredService<T>()`, the result of an own method, awaited or not | typed | typed | guards `a-service-the-container-builds`, `the-result-of-an-own-method`, `an-awaited-own-result` |
| a closure seeing its function's local, `using var`, a local function's parameter, a lambda's typed parameter over a field, a block's local before the use | typed | typed | guards |
| a field a base class declares | typed | no type | `a-field-a-base-class-declares` |
| `this.x`, `h.Svc` (a field of a field), `sp.GetRequiredService<T>().M()` | typed | no type: a receiver that is not a name | `this-field`, `a-field-of-a-field`, `a-service-built-inline` |
| a block's local declared after the use | typed | the block's local | `a-block-local-after-the-use` |
| the enclosing class has the simple name of a type a `using` shows | no type: two visible types | typed | `the-enclosing-class-shares-a-visible-name` |
| a sibling block's local, or a lambda's, out of scope at the use | the out-of-scope local's type | the same | `a-sibling-block-local-out-of-scope`, `a-lambda-local-out-of-scope` |
| `var x = Unknown()`, a declaration that states no type, over a field of its name | the field's type | no type | `an-untyped-local-hides-a-field` |
| `x =>`, an implicit lambda parameter, over a field | the field's type | the field's type | `an-implicit-lambda-parameter-hides-a-field` |
| `(x) =>`, a typeless lambda parameter, over a local | the local's type | no type | `a-typeless-lambda-parameter-hides-a-local` |

On the resolver's side, each wrong answer is a `CALLS` edge to the wrong method, or none. On the scanner's, it is a
call that misses its client wrapper.

Past a local's own declaration, four older gaps of the type service lost edges that `main`'s wrong answers had found
by luck, so they close in the same PR (H5-D16), with their cases first, in `indexer/tests/test_cs_declared_types.py`
and `indexer/tests/test_cs_extension_methods.py`:

| Case | Before | Test |
|---|---|---|
| a member or a base that another part of a `partial` type declares | two types of one name, so no type | `test_a_call_reaches_a_member_another_part_declares` and its scanner twin; guard `test_two_types_of_one_name_that_are_not_partial_stay_apart` |
| `var x = y.M()`, the result another type's method declares: awaited, an interface's, a base's, through a property, on a field | read only on the caller's own type | `test_a_local_has_the_type_its_methods_result_declares`, `test_a_wrapper_call_on_a_local_a_method_returns`; guard `test_overloads_of_two_results_type_nothing` |
| a typed receiver none of whose methods, nor its implementation's, takes the arguments: the repo's extension method whose `this` takes the type, a base or an interface it names, the nearest first; failing that, the only one that takes any value, and on a type with a base outside the repo only when no other method of the repo has its name | no edge, `inherited`, or a method that does not take the arguments | 10 cases; 10 guards: the type's own method, another type, an array, a predefined type, a homonym type, two of any value, a name another method has, a type outside the repo (twice), a call on the type's name |
| a type written with its namespace and type arguments (`this Microsoft.EntityFrameworkCore.DbSet<T>`) | the name `DbSet<T>`, which matches nothing | `an-extension-of-a-package-type-written-with-its-namespace` |

### C#'s change of behavior

One answer, with C#'s own rule: **a name is what its nearest declaration in scope makes it.** That is a block's local
declared before the use, from the innermost block out (a `switch`'s sections are one scope); a parameter of the
function; from a lambda, an anonymous method or a local function, the function around it; then a member of the
enclosing type, found by its qualified name, or one it inherits. A declaration that states no type (`var x =
Unknown()`, `x =>`, `(x) =>`) types nothing and still hides what is outside it.

- **The boundary with SCIP stays where the guide puts it.** Only a declared type counts: a method's result when its
  signature declares it, and what awaiting its `Task<T>` gives, never its `return`s. Between an instance method and
  an extension, the argument count is the only test. C# takes an instance method that applies, and which one applies
  when both take that many arguments is a question of their types.
- **One code inside a file.** `languages/csharp/locals.py` answers a name's type for the resolver's `call_receiver`
  and for the scanner's client wrappers alike.
- **Across files, the `CsTypeIndex`.** The scanner asks through `view.types` and takes the whole answer (H5-D11): a
  member that another part of a `partial` type declares, a base's field, `this.x`, a field of a field. A method's
  result is a question of its own (`method_result`), and so is a type's chain of bases with the names it gives to
  bases outside the repo (`ancestry`), which `supertypes` and `has_external_base` read too.
- **The resolver's typed branch** (`Resolver._on_type`). When no method of the receiver's type or of its
  implementation takes the arguments, it asks the language what it calls on the type instead
  (`LanguageSupport.extension_methods`), and C# answers with the repo's extension methods. A call on a type's name
  (`Type.M()`) has no value to extend.

**Done (2026-10-22).** Fourteen commits, each code commit measured against the one before:

1. the cases (`indexer/tests/test_cs_types.py`);
2. the cases of two gaps (`indexer/tests/test_cs_declared_types.py`);
3. a `partial` type is one type;
4. the cases of a declaration that states no type;
5. one answer inside a file (`languages/csharp/locals.py`);
6. the scanner reads members through the `CsTypeIndex`;
7. a method's declared result;
8. the cases of the extension methods (`indexer/tests/test_cs_extension_methods.py`);
9. a typed receiver reaches the repo's extension method;
10. the cases of an extension of any value on a type with a base outside the repo, and of a type written with its
    namespace;
11. that type is named by its last name;
12. an extension that may take the value, on a type with a base outside the repo;
13. the cases of a call on a type's name and of an extension of a type outside the repo;
14. neither reaches an extension. The judgment of commit 12 found NPoco's `Database.ExecuteScalarAsync(..)` and a
    `DbContext`'s `AddRange(..)` sent to an extension of another type outside the repo, and the static
    `JsonSerializer.SerializeToNode(..)` sent to an extension of any value.

Every xfail of the three tables is gained, and no guard is lost.

- **The corpus and the hold-out:** `0 repo(s) differ` at every commit, against `-29` and `-26`. No expected list
  changes, and the baseline stays `-29`.
- **The micro set:** the 8 repos of other languages are identical, and so are 3 of the 15 C# repos
  (ardalis-clean-arch, azure-saas, clean-arch-dotnet). On the other 12, from `main`: +11,742 and −163 typed edges,
  +2,536 and −74 typed among overloads, +677 and −656 `inherited`, and +452 and −5,848 found by name. Judged by case on
  seeded samples:
  - a `partial` type's other parts give it their members and bases: smartstore's `_db.SaveChangesAsync()` reaches
    `HookingDbContext`, the base that one of `SmartDbContext`'s parts names, and notifo's `SendAsync` reaches
    `TelekomSmsIntegration`'s, declared in its `.Sms.cs` part;
  - the enclosing class, found by its qualified name, types radarr's `InstallUpdateService` and elsa's `Feature`, which
    a homonym in a visible namespace hid;
  - extension methods:
    - 4,789 sites with no edge reach the repo's extension (umbraco's `request.HasTemplate()`, btcpay's
      `this.CreateValidationError(ModelState)` through `ControllerBase`);
    - 802 `inherited` edges become the extension (smartstore's `_db.LoadCollectionAsync(..)`, jellyfin's
      `item.TrySetProviderId(..)`);
    - 293 typed edges to a method that does not take the arguments become the extension that does (jellyfin's
      `item.HasImage(ImageType.Primary)`, against `BaseItem.HasImage(type, index)`);
  - a type written with its namespace: btcpay's `ctx.Offerings.Where(..)` reaches the repo's
    `Extensions.Where(this DbSet<TEntity>)`, and jellyfin's `base.SetInitialItemValues(..)` reaches `ItemResolver<T>`'s;
  - the guesses by name that go were wrong. smartstore's `_db.MeasureDimensions.FindByIdAsync(..)` went to
    `RoleManagerExtensions`, umbraco's `created.GetValue<string>(..)` to `DictionaryExtensions`, and btcpay's LINQ
    `invoices.Where(..)` to the `DbSet` one.
- **What stays lost:** 188 edges to extension methods that `main` had. Most were guesses that the receiver's type
  now proves wrong, as above. The rest is what H5-D16 leaves out:
  - an instance method and an extension that take as many arguments, which only the arguments' types tell apart
    (about 20 sites: smartstore's `_mediaService.GetUrl(file, thumbPictureSize, host)`, elsa's `Get(blockId)`);
  - a form neither side reads, where the call goes back to a guess by name, or to none (about 20 sites). These are a
    lambda parameter without a type (btcpay's `coin => coin.Value.GetValue(..)`, umbraco's `(source, target,
    context) => target.EnableChangeTracking()`) and a `foreach` variable, typed or not;
  - a member of a package's type, whose own type is not known (`_httpRequest.HttpContext.GetItemAsync(..)`, 3 sites);
  - an extension of a type outside the repo on a type with a base outside it (notifo's
    `user.Settings.GetOrDefault(..)`, 4 sites): that base may declare the method, as `DbContext.AddRange` and NPoco's
    `ExecuteScalarAsync` do;
  - the block namespace of H5-D17 (btcpay's `result.StoreData.GetStoreBlob()`).
- **The time, alone,** on one image: the corpus summed 812 s on `main` and 776 s on the branch, within the noise (the
  C# repos 279 and 274 s; the others, whose code did not change, 533 and 502 s). Full dry-runs of umbraco, elsa,
  bitwarden and smartstore, which run the resolver, take the same time on both.

## Decisions made (2026-10-18, by the author)

- **H5-D1, the order: everything before SCIP.** Revised the same day: the author wanted to put an end to H2 before
  H5.
  1. close the whole of F1.14, in the order recorded in it: item 2 (Go), item 7's reassigned router, item 5 (the
     model: the same route in two apps), item 3 (Python client wrapper, fixture only), item 4 (TS/JS, all of it) and
     the new hold-out, measured once. What it shows becomes a separate handoff, without reopening F1.14. The code of
     those items meets the targets from the start (H5-D3). *Done on 2026-10-18, without the new hold-out, which went
     to step 4 (H2-D21);*
  2. H4 phase 0a (recycling the working docs). *Done on 2026-10-19 (PR #6);*
  3. do H5, which absorbs the refactoring part of item 7 (the catalog and the `built_bundle` thresholds). The
     regression net is the corpus (`2026-10-18-v2-baseline-28`) and the 3-repo hold-out (`2026-10-18-v2-holdout-26`),
     identical at every step;
  4. the new hold-out, measured once with H5's code and with the commit before it, and the handoff of what it shows,
     already in the recognizer format. Any difference between the two commits is an H5 regression, which is fixed
     first;
  5. only then SCIP (F1.1/F1.2).

  P2 (the indexer in its own repo) also comes before SCIP, after H5, to take the already clean code. Its exact
  position is to be confirmed with the author.
- **H5-D2, the catalog is YAML** (architecture, item 6), with a validated schema and a test, in the same format the
  conventions are already written in.
- **H5-D3, the targets are complexity ≤ 9 and modules ≤ 300 lines.** During H5, CI only reports, without blocking. The
  intent is for it to become blocking; the author turns it on, when the whole code meets the targets. Amended by
  H5-D9.
- **H5-D4, a general review of the comments** (architecture, item 11; step 10): only what is strictly pertinent
  stays, with no reference to docs, because the docs are still going to be reorganized, and with no project name.
  The private names that were in the docs (a service in the ROADMAP log, an environment variable in
  `H2-public-corpus.md`) were replaced on 2026-10-18. The `core/model.py` comment that named a private service was
  replaced the same day.
- **H5-D5, the scope includes the MCP** (step 8). `cli.py` waits until P2 touches it.
- **H5-D6 (2026-10-21), step 12 brings the rest of the code to the shape targets:** the core, the languages'
  `symbols.py`, the conventions and the MCP's tool groups. Step 6 covers only the languages' HTTP packages, and the
  core's `http_base.py` grew while facts moved through it. `cli.py` stays off target until P2, so step 11's zero
  excludes it.
- **H5-D7 (2026-10-21), step 5 goes Go, C#, Python, TS,** one language per commit after the `TypeIndex` API. Go has
  the clearest pair of type answers, the resolver's and the scanner's, and the measurement behind ADR-005. Amended by
  H5-D10: two PRs per language.
- **H5-D8 (2026-10-21), PR #7 merges as a checkpoint,** with the steps done so far; the rest follows in new PRs. The
  steps left are the largest, a smaller PR is easier to review and to validate live, a regression is easier to place,
  and the branch stops piling up rebases.
- **H5-D9 (2026-10-21), a shape ratchet in CI.** A pull request fails when a function above complexity 9 or a module
  above 300 lines is new, or worse than at its base (`indexer/scripts/shape.py --against`, a job that the required
  `gates` needs). What is over a target and does not grow passes. During the first part, seven modules over the limit
  grew and the MCP split added two functions at complexity 12, and nothing flagged them.
- **H5-D10 (2026-10-21), step 5 goes in two PRs per language:** a refactor that leaves the graph identical, then a
  change of behavior that makes the resolver and the scanner share one answer. The second must gain every xfail of
  the language's type cases and lose no guard ("Step 5" above). The author asked for great care here: only real gains,
  and nothing that exists today lost.
- **H5-D11 (2026-10-21), the scanner reads fields through the `TypeIndex` in the change of behavior, not in the
  refactor.** A struct declared in two files of its package (build tags) gets two answers today. The resolver reads
  the first file that declares it; the scanner reads any file whose struct has the field. Through the index, the
  refactor would either lose the scanner's guard or keep a second answer inside the index, and step 5 exists to
  remove that second answer. The change of behavior gives one answer that holds both cases.
- **H5-D12 (2026-10-21), H5's identity has one exception: step 5's changes of behavior.** "The corpus and the hold-out
  identical to the starting baseline" holds for every refactor. A change of behavior (H5-D10) is judged at the source
  and closes with a new baseline. H2-D21 is amended to match: on the new hold-out, a difference between H5's code and
  the commit before H5 is explained by a judged case of step 5, or it is an H5 regression.
- **H5-D13 (2026-10-21), the hold-out in a change of behavior is read only in aggregate:** the repos that changed, and
  precision and recall against the lists written before the run. Its items are not opened, because a hold-out that
  gets worked on becomes corpus (H2-D20). The author decides `holdout-measurement` from those numbers, and a drop in
  precision is looked for in the corpus.
- **H5-D14 (2026-10-21), the micro graph of a change of behavior is judged by case.** Each changed edge says which
  case of the language's table changed it. The changes are counted per case, and a seeded sample per case and repo is
  judged at the source. One wrong item in a case blocks the PR. The micro set's Go repos hold about a million `CALLS`,
  too many to judge one by one, and a case is what a wrong item would share.
- **H5-D15 (2026-10-21), Go's change of behavior also closes three older gaps of the type service.** A method an
  embedded struct promotes, a type parameter (which declares no type) and the result a method declares, each with its
  cases first; the type service answers a method's result as a question of its own. The one answer reaches more
  receivers, and its micro set lost edges where `main`'s wrong answers had found the right method by luck. The
  interface's dispatch, a form neither side reads (`range`, a type switch, an assertion), a generic's inferred type
  and a file the grammar does not parse stay out.
- **H5-D16 (2026-10-22), C#'s change of behavior also closes four older gaps of the type service.** A `partial` type
  is one type; a method's declared result counts on any type; a typed receiver reaches the repo's extension methods;
  and a type written with its namespace and type arguments is named by its last name. Each comes with its cases first.
  The one answer types more receivers, and its micro set lost the edges `main`'s guesses had found on them. Some
  things stay out:
  - a `foreach`, `out var` or pattern variable;
  - the arguments' types between overloads of one arity;
  - a member of a package's type;
  - an extension of a type outside the repo on a type with a base outside it.
- **H5-D17 (2026-10-22), what a name means in C# goes in a `fix(csharp)` PR of its own, right after C#'s change of
  behavior.** The lookup counts a file's namespace only when it is file-scoped (`namespace X;`). In `namespace X { }`,
  a type of `X` loses to a homonym that a `using` shows: btcpay's `result.StoreData` reads as
  `BTCPayServer.Client.Models.StoreData`. C# looks in the enclosing namespaces before the `using`s. The same judgment
  found a second case: a capitalized name that is a member the caller's type inherits from a base of the repo is read
  as a static access to a homonym type. In elsa's features, `Module.UseWorkflowManagement(..)` is `FeatureBase.Module`,
  an `IModule`. `main` has no edge there either.

## Pitfalls

- **`python -m` inside the image runs the image's code.** Its `WORKDIR` is `/app`, where the package is. With `-m`
  (`-m cProfile`, `-m aidd_indexer.cli`), the working directory enters `sys.path` before `PYTHONPATH`, and the code
  mounted at `/src` does not run. Use `-w /src`, and check the version or the package path on the log's first line.
  That cost a dry-run in PR #5's validation and two profiles in step 3. `corpus.sh` and `test.sh` do not have the
  problem: the first runs by script path and the second already uses `-w /src`.
- **tree-sitter node identity.** `node.child_by_field_name(..)` creates a new object on every call, so `a is b` is
  always false. Compare by `node.id`, which holds within one tree. That cost a debugging session in F1.14 item 2.
- **The order of the regexes in `normalize_path` is semantic.** Examples: the optional `:x?` before cutting the query,
  Hono's constraint before the `?`. Move a regex only with step 1's unit test in place.
- **Per-file × per-repo state.** The scanners are per file, and `compose` is per repo. An index or cache that outlives
  the file leaks memory and mixes node ids from different trees.
- **Measuring performance with the corpus running alongside** distorts the profile. Measure alone, three times, and
  use the median.
- **Don't edit the indexer's code with a corpus run in progress**, because it imports the modules.
- **Refactoring and changing a rule in the same commit** erases the net: "0 repos differ" stops proving anything.
- **A global group's own prefix is a fact of the router, not of the edge.** A group that other files name (a package
  variable, a returned router, a parameter) publishes its own prefix (`go.mount.own`), and `compose` puts it after
  the prefix of each chain that reaches the router. Hanging it on the edges of the file that defines it, as it was
  until 2026-10-18, lost the prefix when the reassignment (`router = router.WithPrefix("/x")`, `r = r.Group("/x")`)
  gave only an edge from the router to itself, and when another file mounted the router. The `route-patterns-go`
  fixture (`internal/reassigned/`) covers both cases.
- **Docker Desktop and the run folders (macOS).**
  - A folder deleted and made again at the same path can no longer be bind-mounted in that session: the container
    sees no folder, or gets an I/O error. A new path works.
  - `micro.sh` deletes its run folder (`micro/<date>-<sha>[-dirty]`) on each run. A second run on the same tree state
    therefore fails every dry-run of the tree, with `FileNotFoundError: /out/<repo>.json`.
  - Give each corpus run a new label, and run `micro.sh` once per commit. CI, on Linux, does not have the problem.
  - A file a container has just written can be read cut short through another bind mount: copy a run's folder to a
    new path before another container compares it.
- **A reinstall copies the working tree and builds a new image.** `setup/install.sh` copies whatever branch is
  checked out into `~/.aidd`, so check out `main` before one, unless a branch is what the live install should run.
  The micro set's base runs are keyed by the image's id, so after a reinstall they are made again (`micro.sh
  --base-only`).

## Constraints and conventions

H2's:
- **Commits:** one conventional line, with no body and no `Co-Authored-By`.
- **Language:** everything in the repo is in English: code, commits, PRs and docs (H4-D1).
- **Privacy:** no tenant or private project name in the docs, the code, the tests or the fixtures.
- **Parser:** an LLM is never the parser.
- **Temporary files:** in the session's scratchpad.
- **Corpus repos:** do not run Python inside the clones; use `python -I`, or Docker with the guide's mounts.
- **Portfolio priority:** .NET first, then Go and Python, then TS. It guides the order of step 6.

## Expected deliverables

- The code in the target architecture's modules, with the corpus and the hold-out identical to the starting
  baseline, but for step 5's judged changes (H5-D12).
- The new unit tests (`paths`, `mounts`, `scopes`, `expr`, one per recognizer) and the MCP's integration test against
  Neo4j.
- In CI, the shape ratchet (H5-D9), and the report of `ruff C901` (`max-complexity = 9`) and of modules above 300
  lines at zero but for `cli.py` (H5-D6). Full blocking is the author's call (H5-D3).
- In `corpus-report.md`, an "H5" section with times before and after, the profiles and the shape metrics before and
  after.
- ADR-003 updated, or a new ADR, and `indexer-evolution.md` (§2, §5, §7) describing the new code.
- In the ROADMAP: the H5 item checked, and SCIP (F1.1/F1.2) with the `TypeIndex` seam ready.
