# Handoff H5 — Refactor the indexer before SCIP

> Paste this file (or ask for `docs/handoffs/H5-indexer-refactor.md` to be read) at the start of a new chat. Before
> anything else, the chat should read:
> - `AGENTS.md`, the entry point;
> - `docs/ROADMAP.md`: "Where we are", "Principles", F1.1, F1.2 and F1.13;
> - ADRs 002 and 003;
> - `docs/indexer-evolution.md`: §2 Code map, §5 How to measure and §8 the boundary with SCIP;
> - `docs/corpus-report.md`: the method, where the extractor stands and the baselines table (the current one is
>   `2026-10-18-v2-baseline-28`).
>
> **State (2026-10-19):** in progress, on the `feature/h5-refactor` branch.
>
> - **Done on the night of 2026-10-19.** Corpus and hold-out gave `0 repo(s) differ` against the starting baselines
>   at every code step; the numbers are in `corpus-report.md`, under "H5 baseline" and "H5 steps".
>   - **Step 0:** the baseline and `indexer/scripts/shape.py`, with a CI job that only reports.
>   - **Step 1:** 147 unit tests (`paths`, mounts, `Scopes`, `path_of`).
>   - **Step 2:** `tree.py` (a cursor `walk`, 2.5× faster), the on-demand registry and the end of the import cycle.
>   - **Step 3, in part:** a per-function declarations index for Go's declared type and C#'s locals (`NodeCache`).
>     On vikunja, `walk` dropped to 18 %. The shared `FileIndex` was not done: keeping every node of a file weighs on
>     memory (mattermost has 8 M nodes), and the design is to be decided with the author.
>   - **Step 4, in part:**
>     - Go's, Python's and TS's package facts left the core (`languages/<lang>/package_facts.py`, the
>       `LanguageSupport.package_facts` hook);
>     - Go's `url.URL` and grpc-gateway went to `languages/go/paths.py`;
>     - no core decision tests the language's name any more.
>
>     Still missing: the typed facts in `PackageContext` (the per-language fields) and `http_base`'s receiver
>     catalog, which is step 6.
>   - **Step 7, in part:** the client wrappers' facts and pending calls are `NamedTuple`s (`WrapperShape`,
>     `WrappedCall`), read by field. The other kinds of fact and of pending call are still missing.
>   - **Step 8:** `core/matching.py`, the MCP split (`tools/list` byte for byte the same) and the Cypher tested
>     against a real Neo4j (`scripts/mcp-it.sh`, 14 cases).
>   - **Step 9:** the docstring without hand-written numbers. The summed time is at 54 % of step 0, within the noise.
>   - **Step 10, in part:** the comments without references to docs or project names, with a test that keeps it so.
>     Reviewing what each comment says is still missing.
> - **The micro graph, checked afterwards (2026-10-19).** The protocol's corpus does not run the resolver, so step 3a's
>   changes to Go's and C#'s types were proven for `CALLS` only by the fixtures. Since then, full dry-runs of `main`
>   (`d055783`) and of the branch (`e5796a0`) have been compared record by record on 12 repos, and they are
>   identical. That check is now item 4 of the protocol.
> - **Next (H6-D1):** H6 (`docs/handoffs/H6-extraction-pipeline.md`) is designed first: the extraction as a parallel
>   map, a reduce and a per-file cache. Step 3's `FileIndex` becomes H6's per-file index, and steps 5 and 6 are
>   designed against it (ADR-005, ADR-006). Then, built toward that design:
>   - the rest of 4, and 7 (typed facts and `Pending`, serializable, with no tree node inside);
>   - 5 (`TypeIndex`, built in the reduce);
>   - 6 (recognizers with a YAML catalog, one language per commit);
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
come out identical to the starting baseline, step by step. It prepares three things: SCIP (a single point where the
type of an expression is asked), scale (F1.13) and maintenance (rules as units that are tested on their own).

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
- the corpus and the hold-out are **identical** to the starting baseline;
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
7. **Typed facts and pending calls.** Each fact is a registered dataclass (for example `FeGroup(name, prefix,
   parent)`), and each language's `compose` is an ordered list of steps that consume typed facts. The text keys and
   the positional tuples go away.
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
| 5 | `TypeIndex`: one service for the micro resolver and HTTP; `struct_fields`/`_value_type`/`_router_class`/`_client_of`/`classes_named`/`_reaches_fast` start consulting it | a single implementation per language of "declared type"; `needs-resolver` is an answer of the service |
| 6 | Recognizers + the YAML catalog, **one language per commit**, from the worst to the smallest: C# (`_controller`, `_invocation`), Go (`_call`), TS (`_read_call`), Python | no function > 9 and no module > 300 lines in those packages; each line of the guide's table points to a recognizer |
| 7 | A typed `compose` per language; a typed `Pending` | no positional tuple between the scanner and `compose` |
| 8 | `core/matching.py`; the MCP split; Cypher tested against an ephemeral Neo4j | `who_consumes` uses `normalize_path`; the 11 tools with an integration test |
| 9 | A generated docstring; the corpus loop through `corpus.sh` | the sum of per-repo times at ≤ 60 % of step 0's |
| 10 | A general review of comments and docstrings (architecture, item 11), in the code, the tests and the fixtures; replacing project names | no reference to docs or project names in the code, checked by a test; the comments that stayed say a why |
| 11 | Docs: ADR-003 updated (or a new ADR: recognizers, catalog, type service); `indexer-evolution.md` §2, §5 and §7 | the guide describes the code as it turned out; the shape report in CI shows zero functions and zero modules off target (blocking turns on when the author decides, H5-D3) |

**Regression protocol (every step):**
1. tests green;
2. the corpus against the starting baseline: "0 repo(s) differ";
3. the hold-out identical;
4. **the micro graph identical:** full dry-runs (`aidd index --dry-run --out`) of `main` and of the step, compared
   record by record. This covers files, symbols, `CALLS`, `IMPORTS` and violations, over H6 step 0's 12 repos:
   - C#: eshop, jellyfin, btcpayserver, umbraco;
   - Go: vikunja, gitea, mattermost, grafana;
   - Python: dispatch, netbox;
   - TS: ghost, outline.

   The HTTP corpus does not run the resolver, so items 2 and 3 cannot see a change to `CALLS`;
5. the step's time, measured alone, no worse than the previous one, unless justified.

A difference in the corpus is a defect of the step, not a gain. If the refactor reveals a real bug, it is recorded,
fixed in a separate commit, with a fixture case, and goes into the baseline by explicit decision.

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
  intent is for it to become blocking; the author turns it on, when the whole code meets the targets.
- **H5-D4, a general review of the comments** (architecture, item 11; step 10): only what is strictly pertinent
  stays, with no reference to docs, because the docs are still going to be reorganized, and with no project name.
  The private names that were in the docs (a service in the ROADMAP log, an environment variable in
  `H2-public-corpus.md`) were replaced on 2026-10-18. The `core/model.py` comment that named a private service was
  replaced the same day.
- **H5-D5, the scope includes the MCP** (step 8). `cli.py` waits until P2 touches it.

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
  baseline.
- The new unit tests (`paths`, `mounts`, `scopes`, `expr`, one per recognizer) and the MCP's integration test against
  Neo4j.
- In CI, the report of `ruff C901` (`max-complexity = 9`) and of modules above 300 lines, at zero, still not blocking
  (H5-D3).
- In `corpus-report.md`, an "H5" section with times before and after, the profiles and the shape metrics before and
  after.
- ADR-003 updated, or a new ADR, and `indexer-evolution.md` (§2, §5, §7) describing the new code.
- In the ROADMAP: the H5 item checked, and SCIP (F1.1/F1.2) with the `TypeIndex` seam ready.
