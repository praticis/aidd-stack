# Handoff H5 — Refactor the indexer before SCIP

> Paste this file (or ask for `docs/handoffs/H5-indexer-refactor.md` to be read) at the start of a new chat. Before
> anything else, the chat should read `docs/indexer/README.md` and the documents of its reading order, in that order:
> `AGENTS.md`, this file's "State", the method, the judgment and the scripts. Then, for the refactor's context:
> - `docs/ROADMAP.md`: "Where we are", "Principles", F1.1, F1.2 and F1.13;
> - ADRs 002 and 003;
> - `docs/indexer-evolution.md`: §2 Code map, §5 How to measure and §8 the boundary with SCIP;
> - `docs/corpus-report.md`: the method, where the extractor stands and the baselines table (the current one is
>   `2026-10-18-v2-baseline-29`).

## State (2026-10-29)

**Merged.** Steps 0–2, 4 and 7–9, and parts of 3 and 10 (PR #7, a checkpoint, H5-D8). Step 5 for Go (refactor #17,
change of behavior #20, `fix(mcp)` #19) and for C# (refactor #23, change of behavior #25, what a name means #27, which
extension method a call reaches #30). Python's step 5: its case table (#42), its scope index (#44), its types (#45) and
its change of behavior (#47); before the last, `fix(python)` #46 tries an import's roots in a fixed order, where a set's
order followed the hash seed, and after it `fix(python)` #49 looks for an absolute import under the directory its
package runs from (H5-D28), and `fix(python)` #51 follows a star import as CPython binds it; `fix(graph)` #53 keeps
one `CALLS` edge per caller, callee, line and method, and `fix(python)` #55 has the client wrappers ask the type index;
`chore(scripts)` #56 has the per-site attribution read what the resolver makes of a receiver too (G2), and
`refactor(graph)` #57 and `refactor(resolve)` #58 make room in the graph writer and the resolver before F1.16 grows
them, and `feat(graph)` #59 writes the types' bases and marks the calls that do not dispatch; `fix(resolve)` #60
sends a call that does not dispatch to no implementation and no homonym, and a Python `super()` to what follows the
caller's class in each MRO (H5-D32); `feat(graph)` #61 writes `OVERRIDES`, what a dispatching call may run instead,
as each language says (H5-D33); `feat(graph)` #62 has a dispatching call keep its receiver's type and an override the
receivers on which it may run (H5-D34); and `feat(mcp)` #63 has `who_calls` list a method's dispatching callers and what
it overrides, and `impact_of` follow a dispatch at any hop (H5-D35), which closes F1.16. Each merge and its live
validation are in `docs/history.md`; the results are in the sections below and in `corpus-report.md`.

**Step 5 is closed for C# and for Python, with debts.** The defects it leaves are `docs/tech-debt.md` (TD-001 to TD-022), each with a
strict xfail test; those due before F1.2 are `fix(csharp)` PRs. Python's leaves TD-025 (H5-D26), due in F1.2, and TD-026 (H5-D28), due in step 6. The judgment of H5-D18 was the review of an agent that
did not write it (H7-D6): a person's check is not feasible today. Steps 6 and 12 are open for C# as for every language,
and two debts of the core are due in them: TD-023, the syntax of each language it holds, and TD-024 (step 6), the
names of frameworks and client libraries it holds:

| Language | Step 5 (`TypeIndex`) | Step 6 (recognizers, catalog) | Step 12: the largest module over 300 lines |
|---|---|---|---|
| C# | merged (#23, #25, #27, #30) | not started; `_controller` and `_invocation` first | `languages/csharp/http.py`, 1401 |
| Go | merged (#17, #20) | not started; `_call` | `languages/go/http.py`, 730 |
| Python | merged (#42, #44, #45, #47) | not started | `languages/python/http.py`, 365 |
| TS | planned in ten PRs (H5-D36, H5-D37, H5-D39, H5-D40, H5-D41, H5-D45, H5-D46, H5-D47, H5-D48) and three more that end it (H5-D49 to H5-D51); the probe in #65, the case table in #66, the scope index in #67, the types in #68, the hierarchy in #69, the module resolution in #72, the CommonJS exports in #73, the declaration files in #79, the workspace packages in #80, the class members and the folder entries in #81, the output of a referenced project in #82, the function members in #83, the receiver's type in #84 | not started; `_read_call` | `languages/typescript/http.py`, 1005 |

The counts are `shape.py`'s on 2026-10-29. The core has modules over 300 lines too: `http_base.py` and `http_expr.py`
go with step 6, and `extract.py` with step 12's last PR (H5-D44). Step 12's other PRs (#74, #75, #77, #78) brought the
conventions, the corpus runner, the MCP's tool groups and the refresher to the targets, but for what H5-D43 accepts.

**Method recovery.** Done: the validation method is in `docs/indexer/` and `indexer/scripts/` (PRs #28 and #29), and
`docs/indexer/resume-test.md` passed all nine criteria in a clone (runs 4 to 8, 2026-10-27 and 2026-10-28). The `live/`
chain ran on #30, and `live/validate.sh` (PR #31) runs it as one command per step; it reproduced #30's numbers on a copy
of its folder. `protocol.sh`, `micro-fresh.sh`, `time-alone.sh` and `mutate.sh` ran before the recovery edited them, or
never: they are exercised again on the next PR of the indexer. The debts check (`debts.py`, PR #33) and the
expected-list tool (`lists/`, PR #34) are in; the new hold-out's tools and the per-site attribution are
`docs/indexer/method.md` §4.11 and §4.12.

**Next.**
1. Step 5 for TS (H5-D19, H5-D36), now that F1.16 is closed (H5-D29). TS had no type service, so it goes in ten PRs, as
   Python's did: the probe for the files of TS's three ids (`chore(scripts)` #65); the case table, with the TypeScript
   compiler as its reference (#66); a refactor in two PRs (H5-D37), TS's scope index proven against TypeScript's binder
   (#67), then TS's typed facts and `TypeIndex` (#68, H5-D38), each with the graph identical; a `feat(graph)` for TS's
   hierarchy and `OVERRIDES` (#69, H5-D39); a `fix` for each of the four gaps the proofs found, the module resolution,
   TD-038 (#72, H5-D40), a CommonJS export, TD-039 (#73, H5-D41), a hand-written declaration file, TD-041 (#79, H5-D45),
   a package of the repo's own workspace, TD-042 (#80, H5-D46), and what a class declares and what a folder names,
   TD-037, TD-043 and TD-049 (#81, H5-D47), and the output of a project the config references, TD-050 in part (#82,
   H5-D48); then three that end it, as the measure of a prototype of the change of behavior asked (60,824 sites judged,
   and the checker confirming 95 to 100 % of the typed edges and 0.1 % or less of the by-name edges they replace): a member of an
   interface or a type literal written as a function (H5-D49), the resolver's change of behavior (H5-D50), and
   the scanner's (H5-D51), judged per site with `attribution.sh typescript,tsx,javascript` and against the compiler on
   ghost and outline ("TS's step 5" below). TD-050, narrowed, and TD-052 are due after the step.
   Before them, `fix(graph)` #70 closes TD-040, a signature that lost the `>` it ends with, which #69's live
   validation found. The `fix(csharp)` PRs of the debts due before F1.2 (TD-033 and TD-034 among them, H5-D32) do
   not hold it.
2. Step 6 (recognizers and the catalog, with the core's HTTP modules), step 12's last PR (the pipeline's `extract` and
   `resolve`, after TS's step 5: H5-D44), the rest of step 10, step 11 (docs).
3. Plug in H6 (`docs/handoffs/H6-extraction-pipeline.md`): the extraction as a parallel map, a reduce and a per-file
   cache, designed against ADR-004 to ADR-006. Then the new hold-out (its procedure and tools:
   `docs/indexer/method.md` §4.11), P2 (the indexer in its own repo) and SCIP (F1.1, F1.2).

**Gaps.**
- **G1, closed.** The per-site attribution of a changed call to the answer that explains it exists for every
  language: one probe, `indexer/scripts/judgment/answers.py`, reads each tree's own extraction, and
  `attribution.py` joins it to the changed edges (`docs/indexer/method.md` §4.12, H5-D21). C# was judged with
  `indexer/scripts/judgment/csharp_extensions.py`.
- **G2, closed (#56): a change in the resolver's stage is attributed too.** `answers.py` read only what the
  extraction records for a receiver, so where an import resolves, or how the `TypeIndex` reads a name, gave both trees
  the same answers. It now also records what the resolver makes of each receiver, asked through the hooks the resolver
  asks (`docs/indexer/method.md` §4.12). Replayed on today's image, against the reference the judgments of H5-D28 and
  #51 used, the `TypeIndex`'s verdict on each receiver read from Python's own index in both trees:
  - H5-D28's import roots (`c4f1b8d` to `03e8447`), 8,726 changed sites of netbox and mattermost: `main`'s probe
    explains none, this one all. The verdict explains 8,435 of them. The other 291 are receivers whose root an import
    bound to a package and now binds to the repo's module (`from netbox.ui import layout`), which the verdict cannot
    see;
  - the star imports (#51, `e90d912` to `533d574`), 4,657 changed sites of netbox and dispatch: `main`'s probe explains
    792, this one all, and the verdict explains each of them;
  - H5-D28's method declared past a base outside the repo (`03e8447` to `e90d912`): its 15 sites stay `unexplained`,
    since the change is below the receiver, as the verdict leaves them too;
  - Python's change of behavior (#47, `65b510f` to `9a7a585`), in the extraction's stage: the same table and the same
    samples, all 4,186 sites explained.

  The probe now holds the language's extraction for the resolver, as the dry-run does: netbox takes 26–27 s against
  17–18 s, and 671 MiB of peak memory against 389 MiB. Its rows are the same as with the pipeline's whole
  `extract_tree`, so the other languages and the HTTP pass are left out.
- **Judgment is not yet automated (H7-D6).** The verdict record (H7-D2) is to build; until then each change of
  behavior needs the review of an agent that did not write it.
- Live evidence is private, local and has no backup: `.local/indexer/live/` (its README has the layout and the
  integrity checks). Only the PR in flight's "before" picture cannot be regenerated; `merged/` holds the last
  validated PR's pair.

The author's decisions are under "Decisions made". This handoff was born from a review asked for in the middle of the
F1.14 close: after 24 rule commits since corpus v2, the extractor had functions of very high complexity, large files
and two parallel implementations of "what is the type of this". That has to be solved before SCIP (F1.1, F1.2),
because SCIP plugs in exactly at that seam.

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
| 4 | Package facts per language: the language code leaves `core/http_expr.py` and `PackageContext`; typed facts | a test proves `core/` names no language or framework (`test_core_neutral.py` checks that no core module imports a language's module or names a language's id; the syntax of each language the core holds is TD-023, and its framework names are TD-024) |
| 5 | `TypeIndex` (ADR-005), first its API in the core, then one language at a time: Go, C#, Python, TS (H5-D7), each a refactor and then a change of behavior (H5-D10, "Step 5" below). Each language's `file_facts` become typed facts; the per-file answers (a local's, a receiver's, a parameter's type) are one code for the resolver and the scanner, which is what step 3 left; the resolver's indexes (`resolve_setup`) move into the `TypeIndex`. Go's `_declared_type` against `_value_type`/`_field_type`/`_local_type`, C#'s `_local_type` against `_declared_type` and `_reaches_fast`, Python's `_router_class` and its classes by `RepoView.defining`, TS's `_client_of` start consulting it | a single implementation per language of "declared type"; an answer is a value or `Unknown` with its reason, and `Unknown` is what `needs-resolver` was |
| 6 | Recognizers + the YAML catalog, **one language per commit**, in the portfolio's order (H5-D20): C# (`_controller`, `_invocation`), Go (`_call`), Python, TS (`_read_call`) | no function > 9 and no module > 300 lines in those packages and in the core's HTTP modules (`http_expr`, `http_base`, `integrations`, `http_mounts`: H5-D44); each line of the guide's table points to a recognizer |
| 7 | A typed `compose` per language; a typed `Pending` | no positional tuple between the scanner and `compose` |
| 8 | `core/matching.py`; the MCP split; Cypher tested against an ephemeral Neo4j | `who_consumes` uses `normalize_path`; the 11 tools with an integration test |
| 9 | A generated docstring; the corpus loop through `corpus.sh` | the sum of per-repo times at ≤ 60 % of step 0's |
| 10 | A general review of comments and docstrings (architecture, item 11), in the code, the tests and the fixtures; replacing project names | no reference to docs or project names in the code, checked by a test; the comments that stayed say a why |
| 11 | Docs: ADR-003 updated (or a new ADR: recognizers, catalog, type service); `indexer-evolution.md` §2, §5 and §7 | the guide describes the code as it turned out; the shape report in CI shows zero functions and zero modules off target, except `cli.py` until P2 (H5-D5, H5-D6) and what H5-D43 accepts; blocking turns on when the author decides (H5-D3) |
| 12 | The rest of the code to the shape targets (H5-D6): the core (`extract`, `graph`, `resolve`, `mirror`; `http_base` and `http_expr` go with step 6, H5-D44), the languages' `symbols.py` that step 5 leaves, the conventions, the MCP's tool groups, and the scripts and tests the ratchet reads (`http_corpus.py`, `test_conventions.py`, `test_mcp_protocol.py`'s `read`) | the shape report shows nothing off target outside what H5-D44 gives to step 6, but `cli.py` and what H5-D43 accepts |

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
  now proves wrong, as above. The rest is what H5-D16 leaves out, now debts (`docs/tech-debt.md`): the arguments' types
  between overloads (TD-004), a `foreach` variable and a lambda parameter (TD-007, TD-008), a member of a package's type
  (TD-003), and a type with a base outside the repo (TD-009).
- **The time, alone,** on one image: the corpus summed 812 s on `main` and 776 s on the branch, within the noise (the
  C# repos 279 and 274 s; the others, whose code did not change, 533 and 502 s). Full dry-runs of umbraco, elsa,
  bitwarden and smartstore, which run the resolver, take the same time on both.

### What a name means in C# (H5-D17)

C#'s change of behavior gave one answer to a name's type, but the answer still read a name in ways C# does not. A
type's simple name skipped a block namespace and the namespaces around the code, a capitalized member was read as a
homonym type, and a type parameter was read as a type outside the repo. The fix reads each as C# does:

- **A type's simple name** is looked up in the namespace the code is in, then in each one around it out to the global
  namespace, each followed by the `using`s its declaration holds; the file's own `using`s come last, with every
  `global using` of its project. Of the global namespace, only the file's own project counts: other projects keep
  their programs there (bitwarden's `Program`).
- **A type nested in another** is no name of its namespace. Only the file that declares it, and the types deriving
  from the one it is in, see it by its simple name, and it is named with the types around it on both sides
  (`BaseController.Error`).
- **A capitalized name** the caller's type has as a member, on it, on another of its parts or on a base of the repo, is
  that member; else a type nested in the caller's type or a base of it; else a type. With a base outside the repo,
  which may declare the name, it is still read as a type's, and a member after it is a value an extension may take
  (smartstore's `EngineContext.Current.ResolveService<T>()`).
- **A value typed by a type parameter** has the type argument given for it: by the type a local, a parameter or a
  method's result writes (`SutProvider<CiphersController> sutProvider`, `Task<Provider<IPaymentMethod>>`), or by the
  base lists down from the caller's type (`AddFixture : CoreTest<PendingReleaseService>`, whose `TestBase<TSubject>`
  declares `Subject`). Failing that, it has the type its one constraint names (`where TItem : NavigationItem`); with
  none, or more than one, it declares none, and its call goes by name. A method's result typed by one is given its
  argument too, and an extension whose `this` is one takes a value of the type its constraint names (smartstore's
  `GetLocalized<T>(this T entity) where T : class, ILocalizedEntity`).
- **A value of an array type** is the array, `System.Array`, a type outside the repo, never a value of its element's
  type. A call on it reaches the repo's extension methods only.
- **A method of an extension block** (C# 14, `extension(byte[] value) { public byte[] Unzip() .. }`) that is not static
  extends the block's receiver.
- **A call with no receiver** is a method of the caller's type or a base of it, never an `HttpClient`'s: smartstore's
  `CompositeFileSystem.GetAsync(subpath, ..)` was read as a client call, which made `GetDirectoryAsync("images/flags")`
  a request. It is a request only when it is given the request's verb, as bitwarden's
  `SendAsync(HttpMethod.Post, "push/register", body)`, which its `BaseIdentityClientService` sends.

The code:

- `languages/csharp/type_syntax.py` reads how C# writes a type: its simple name, the type arguments it passes, and the
  type parameters a declaration introduces with what their constraints name;
- `languages/csharp/written.py` reads the receiver's written start through the `CsTypeIndex`, with the type arguments
  it is given, then the members after it, for the resolver and the scanner alike;
- the `CsTypeIndex` answers what each type parameter of a type and of its bases is (`bindings`), and a method's result
  with its type arguments (`result_of`);
- `languages/csharp/wiring.py` holds the DI chain and the mediator's handlers, which left `type_index.py` to keep it
  under 300 lines.

**Done (2026-10-23).** Thirty commits: thirteen of cases, each followed by the fixes that pass them, seventeen, each
measured against the commit before. The cases (`indexer/tests/test_cs_names.py`, 42 of them) are each checked on both
sides, the resolver's edges and the scanner's calls through a client wrapper. In order:

1. the namespaces around the code before the `using`s;
2. a capitalized name the caller's type has as a member;
3. a type nested in another;
4. the global namespace, from the file's own project only;
5. a call with no receiver;
6. a member after a type's name is a value; a member typed by a type parameter declares no type; the nested caller
   named with its outer types; a type nested in a base of the caller's;
7. a call with no receiver given the request's verb;
8. `global using`;
9. a type parameter's one constraint;
10. the type argument a base list or the receiver's type gives;
11. an extension whose `this` is a type parameter;
12. a method's result keeps its type arguments;
13. an array is no value of its element's type;
14. a method of an extension block.

Each judgment found what the next fixes closed: the nested types the namespaces' lookup took for top-level ones
(`Attempt`, `RootObject`); the other project's `Program`; the no-receiver call that dropped bitwarden's seven relay
calls; the members typed by a type parameter that a constraint, a base list or a result types; the arrays that
the constraints exposed; and the extension blocks that a typed receiver no longer reaches by name.

- **The corpus and the hold-out:** `0 repo(s) differ` against `-29` and `-26` at the last commit. In between, two
  commits changed the corpus, and a later one undid each. The capitalized member (2) typed smartstore's
  `WebRoot.GetDirectoryAsync("images/flags")`, which reached a "wrapper" built on the type's own `GetAsync`, a false
  `GET /images/flags`; the call with no receiver (5) removed it. That one also dropped bitwarden's seven relay calls
  (`POST /push/register` and the others, checked in its list), which the request's verb (7) brought back. No expected
  list changes, and the baseline stays `-29`.
- **The micro set:** the 8 repos of other languages are identical, and so are clean-arch-dotnet and rapid-blazor. On
  the other 13 C# repos, from `main`: +18,137 and −2,480 typed edges, +2,676 and −674 typed among overloads, +1,403
  and −488 `inherited`, and +2,412 and −5,639 found by name. Judged by case on seeded samples, at each commit and from
  `main`:
  - a capitalized member is the member: umbraco's `ScopeProvider.CreateScope()` reaches `IScopeProvider`, jellyfin's
    `LibraryManager.ParseName(..)` `ILibraryManager` and its implementation, umbraco's `Database.Execute(..)`
    `IUmbracoDatabase`, and notifo's `Mediator.SendAsync(..)` `IMediator` and `DefaultMediator`. `main` read each as
    a static call on the homonym class;
  - the type arguments: bitwarden's `sutProvider.Sut.X()`, about 4,200 sites in its tests, reaches the class under
    test, and radarr's `Subject.X()`, about 1,500, the fixture's subject. umbraco's `MediaEditingService` calls
    `ContentService.SortChildren(..)` on `IMediaService` and `MediaService`, where `main` took `ContentService`'s;
    smartstore's `provider.Value.GetPaymentSummaryAsync()` reaches `IPaymentMethod` through
    `Task<Provider<IPaymentMethod>>`;
  - the constraints: radarr's `Settings.Validate()` reaches `IProviderConfig`, smartstore's `Item.Route(..)` the
    `INavigatable` extension, and smartstore's `product.GetLocalized(x => x.Name)`, an `inherited` edge on `main`, the
    extension;
  - a type nested in a base: bitwarden's `Error.BadRequest(..)` reaches `BaseBillingController.Error`, where `main`
    guessed between two bases' `Error`;
  - the `global using`s type elsa's secret managers and azure-saas's tenant DTOs, and eshop's `mediator.Send(command)`
    reaches `CancelOrderCommandHandler.Handle`;
  - an array's `Tags.Contains("Kids", ..)` reaches jellyfin's `EnumerableExtensions.Contains`, and the `inherited`
    edges to an array's element type go;
  - the extension blocks: elsa's `context.HasScheduledActivity(..)`, an `inherited` edge on `main`, reaches
    `ActivityExecutionContextExtensions`;
  - the guesses by name that go were wrong: a mock's `.Setup(..)` sent to a test class's `Setup`, `Collector.Dispose()`
    to another class's, radarr's `movie.Tags.Remove(tag)` to a service, a `List.Add(..)` to
    `WorkflowDictionaryExtensions.Add`, an `ICollection`'s `IsNullOrEmpty()` to the overload that takes an array.
- **The time, alone,** on one image: the corpus took 259 s of wall time on `main` and 255 s on the branch. Full
  dry-runs of umbraco, elsa, bitwarden and smartstore, which run the resolver, take the same time on both, within 2 s.
- **What stays out:** thirteen gaps, now debts (`docs/tech-debt.md`, TD-010 to TD-022), each with a strict xfail test.

### Python's case table (H5-D22)

The resolver's cases are in `indexer/tests/test_python_types.py`, and the scanner's in
`indexer/tests/test_python_routers.py`. Each case names what CPython does:
- a resolver case names the method CPython runs for its call, and the test runs every case that can run in the test
  image, under `sys.setprofile`, to show it;
- a scanner case names the routes CPython registers, with a router that composes prefixes as FastAPI's does, outside
  the case's repo.

Before the change of behavior (#47), the resolver typed no receiver, so it found every method by name, and the scanner
keyed a router by the core's scopes and followed one only into a function. Every xfail of the table now passes, and no
guard is lost.

| Case | Before #47 | Now | Test |
|---|---|---|---|
| `self.m()`, `cls.m()`, a method only a repo base declares, a repo base ahead of an external one | by name | the method CPython runs, `receiver-type` | `self`, `cls`, `a-method-of-a-repo-base`, `a-repo-base-ahead-of-an-external-one` |
| `super().m()` | the class's own `m`, by name | the base's | `super` |
| `C()`, `x = C()`, `C` under an alias or through its module, `x: C`, `Optional[C]`, `C \| None`, `"C"`, `x: C = f()`, `x = f()` where `f` declares `-> C`, `self.x = C()` in a method, `x: C` in the class body | by name | typed | one per form |
| `mod.f()`, a function of a repo module | the methods named `f`, never the function | the function | `a-function-of-a-repo-module` |
| a name a class body binds, read in a method; a closure's; a `global` bound in a function; a walrus in a comprehension | by name | typed from the binding CPython's scopes give the name | one per form; guards: never the type of the other binding |
| a comprehension's variable; a `global` or `nonlocal` that rebinds; two bindings that disagree; a `for` or `with` target | by name | `Unknown`, so by name | guards: no typed edge |
| `list[C]`, `Union[A, B]`, `Model.objects`, an attribute an external base gives, an external base ahead in the MRO, a base only a star import binds, a method a builtin base gives, a name a module may get by a star import, a class attribute a descriptor reads | by name | `Unknown`, so by name | guards: no typed edge, and the ones CPython can run reach a method by name |
| a value of an external class (`JSONDecoder()`) | the repo's homonym, by name | no edge | `an-instance-of-an-external-class` |
| scanner: a repo class over `APIRouter`, under an alias or over a base of another package; a router handed to a function with an annotated parameter | the prefix reaches the routes | the same | guards |
| scanner: a router a function binds as `global` | `GET /users` | `GET /api/users` | `a-router-a-function-binds-as-global` |
| scanner: a router a class body binds, read in a method, where the module binds the same name | `GET /other/users`, the class body's | `GET /api/users`, the module's | `a-class-body-does-not-enclose-its-methods` |
| scanner: an application a function binds as `global` | no route | `GET /` | `an-application-a-function-binds-as-global` |
| scanner: a router handed to a method of a typed value (`users.register(v1)`) or to a function of an imported module (`routes.register(v1)`) | `GET /users` | `GET /api/users` | `a-router-handed-to-a-method-of-a-typed-value`, `a-router-handed-to-a-function-of-an-imported-module` |
| scanner: a repo router class whose base has a homonym in another package | `GET /users` | `GET /api/users` | `a-repo-router-class-whose-base-has-a-homonym` |

The scope index came in the refactor's first PR (#44, H5-D24), and the test that waited for it is now the check
itself: the index classifies every name of every case as `symtable` does. The types came in the second (#45): read by
them (`test_python_type_index.py`), every case gets its answer, and each `unknown` or `external` case the reason it
names. The table's guards count an `inherited` edge as no method's (H5-D25).

### Python's change of behavior

One answer, with Python's own rule: **a name is the binding CPython's scopes give it, and its type is the one that
binding declares.** An annotation (`C | None`, `Optional[C]` and `"C"` read as `C`), a call of a class, a function's
declared result, `self` and `cls`, `super()`, the import of a repo class or module. Across files, the
`PythonTypeIndex` reads modules and classes as namespaces, and a class's MRO as C3's up to its first base outside the
repo (`languages/python/mro.py`).

- **Outside the repo only where it is proven.** A module of the standard library, an import of a top-level name the
  repo holds nowhere, and a builtin base are outside it. A call of a name outside the repo is an instance of it
  (H5-D26).
- **What the index cannot see is `Unknown`, and the call goes by name as on `main`:**
  - a module the repo holds at the top of a directory that is no package, under a root its imports are not looked for
    in, even with a name of the standard library;
  - a base only a star import binds, and a module with a star import, past its own names;
  - a class attribute's value, which a descriptor may read as another, unless its class is the repo's, all its MRO,
    and declares no `__get__`;
  - `typing.Any`, and a name a `TypeVar` binds;
  - `super()` in a class that a class of the repo may put before another than its base. A class of one base keeps
    its base's MRO; one of several bases whose MRO the index cannot see may reorder any.
- **The resolver.**
  - A typed receiver reaches the method its MRO declares, or the `inherited` edge of H5-D25.
  - A class or a module whose names the index cannot all see gives no type.
  - A method no class of an MRO all the repo's declares goes by name, because a subclass's other base gives it. So
    does a name its module imports from another module. This is `LanguageSupport.member_by_name`, which no other
    language answers.
- **The scanner** asks the same scopes and types (`languages/python/routers.py`):
  - a router's name is keyed by the scope Python binds it in;
  - a router handed to a method of a typed value, or to a function of an imported module, follows the call's receiver
    as the extraction types it (`CallInfo`);
  - a router class is read where the call binds its name, and its bases through the `TypeIndex`'s MRO.

**Done (2026-10-29).** Sixteen commits:

1. the scanner's router cases, each run by CPython (`indexer/tests/test_python_routers.py`);
2. a call's receiver has the type its declarations give it;
3. the scanner keys a router by the scope Python binds it in;
4. a router handed to a method of a typed value takes the caller's prefix;
5. the scanner reads a router class's bases through the `TypeIndex`;
6. a module or a base the types cannot see is unknown, not outside the repo. The judgment of commit 2 found netbox's
   absolute imports, under a root the import resolver does not try (`netbox/`), taken for packages outside the repo:
   `self.assertHttpStatus(..)` lost `TestCase.assertHttpStatus`, and 12,940 edges went;
7. a module with a star import knows only its own names: netbox's `serializers.RackElevationDetailFilterSerializer(..)`,
   through `from .serializers_.racks import *`, had lost its class (55 sites);
8. a class attribute a descriptor may read is unknown, not outside the repo: netbox's `self.rack.get_available_units(..)`,
   through `rack = models.ForeignKey(..)`, had lost `Rack.get_available_units` (34 sites);
9. TD-025, the debt H5-D26 leaves;
10. the docs;
11. to 13, what the review of an agent that did not write the change found (H7-D6):
    - a receiver is unknown where a subclass, typing or a re-export decides its method. netbox's
      `BulkCreateModelMixin`, a class of no base, calls `self.perform_create(..)`, which only its subclass's other base
      gives (5 sites); 39 receivers were annotated `Any` or a `TypeVar`; `pkg.f()` re-exported by its `__init__`, and a
      package of the repo named like the standard library's, had no site in the four repos;
    - the scanner reads a router class where the call binds its name, so a router class a function imports is read
      again;
    - `super()` is unknown where a class of several bases the index cannot see may reorder the MRO. netbox's
      `CustomFieldsMixin.clean` calls `super().clean()`, and in a model the class after it is another mixin of the
      repo, not `models.Model` (6 sites);
14. the docs of commits 11 to 13;
15. the overrides' decision (H5-D27);
16. the live validation copies only the package a dry-run imports.

Every xfail of the table is gained, and no guard is lost.

- **The corpus and the hold-out:** `0 repo(s) differ` at commits 5, 6, 7, 8, 12 and 13, against `-29` and `-26`. No
  expected list changes, and the baseline stays `-29`.
- **The micro set:** the other 8 repos are identical, so the core's new hook changes no language but Python. From
  `main`: dispatch −3,174 and +1,429 `CALLS`, netbox −3,797 and +2,085, mattermost −42 and +17, grafana −2.
- **The per-site attribution** (`attribution.sh python`) explains all 4,188 changed sites, with none unexplained:

  | Kind | Sites |
  |---|---|
  | keep their method, now found by type | 2,070 |
  | change it | 630 |
  | narrow it | 654 |
  | gain one | 87 |
  | widen | 19 |
  | lose theirs | 728 |

  The share found among several homonyms:

  | Repo | Of the edges | Of the sites |
  |---|---|---|
  | dispatch | 65.6 % → 53.0 % | 40.4 % → 28.5 % |
  | netbox | 63.1 % → 61.7 % | 38.2 % → 37.1 % |
- **Judged by case on seeded samples.** The review drew 47 seeded rows, read each at the source, and found none
  wrong.
  - Typed:
    - dispatch's `@message_dispatcher.add(..)` reaches `MessageDispatcher.add`, not three plugins' `add`;
    - `case_service.create(..)` reaches the case service's function, not a plugin's method.
  - Lost, and wrong on `main`:
    - a call on a value of a class outside the repo: 236 on FastAPI's `APIRouter` in dispatch (`@router.get(..)`),
      and 74 on SQLAlchemy's `Session`;
    - Django's test client;
    - a method an outside base gives, called inside its own type (83 sites, H5-D25);
    - Python scripts' `m.group(1)` that reached a Go or a TS method in mattermost and grafana.
  - Lost, and right on `main`: about 40 sites of netbox on the result of a function outside the repo,
    `get_object_or_404(Token, ..)` among them. This is TD-025 (H5-D26).
- **The cost**, in three rounds interleaved with `main`, on commit 9 and on commit 13:
  - netbox's extraction, where receivers are now typed:
    - commit 9: from 7.5–8.0 s to 8.5–8.7 s;
    - commit 13: from 8.7–9.5 s to 9.6–11.1 s, in a noisier round.
  - netbox's HTTP pass, where the scanner builds a file's scope index again, on its first question about a router's
    scope, and only then:
    - commit 9: from 5.2–5.3 s to 6.5–6.9 s;
    - commit 13: from 5.6–7.5 s to 7.6–8.1 s.
  - peak memory grows by 4 MiB, then by 9 MiB once `super()` reads the MRO of every class.

  Keeping the index beside the tree instead cost about 270 MiB (#45), so it is built again. dispatch's HTTP pass goes
  from 1.8–2.1 s to 2.3–2.4 s.
- **What the judgment leaves open:**
  - netbox's absolute imports resolved to nothing, so most of its classes had an MRO the index could not see. They
    resolve since H5-D28, judged in the next section;
  - a typed `self.m()` reaches the method its class's MRO gives, not a subclass's override, as in C# and Go. In
    netbox, 67 narrowed sites lose an override the guess by name found, 46 of them `_get_queryset`. The query reaches
    them (H5-D27, F1.16);
  - a class defined in a function is not seen, so one of several bases there could reorder an MRO the index reads.
- **On a live install** (the fourteenth golden round): the install still ran #30's package, so one pair covers #44 to
  #47. The dry-runs are identical, the graph holds them before and after the reinstall, and the 27 calls give the
  same answers. The live snapshots hold no Python file, so the round checks the install, not the change.

### Where a Python absolute import is looked for (H5-D28)

The judgment of Python's change of behavior found that none of netbox's 7,661 absolute imports resolved. netbox runs
from `netbox/`, where its `manage.py` is, and the import resolver tried only the root of the file's module, the repo's
root and `src/` (#46). The core took netbox's own classes for a package's and skipped the calls on them.

- **The rule is CPython's.** An absolute import is looked for first under the directory above the file's top regular
  package, or under the file's own directory for a module of none (`languages/python/modules.py`). CPython finds a
  package by its name, or runs a file as a script, only with that directory on `sys.path`.
- **A directory a regular package holds is a namespace portion of it, never a root.** open-webui's
  `retrieval/vector/dbs/` has no `__init__.py`; as a root it would make `import redis` its own `redis.py`.
- **One fix led to another.** With the imports resolved, a method that a class of the repo declares past a base outside
  the repo got no edge at all:
  - `_inherited` skips a call inside its own type;
  - `member_by_name` refused the name because of the outside base.

  That base may give the method first, so the answer is `Unknown`, and the call goes by name
  (`PythonTypeIndex.declared_past_outside`).

**Done (2026-10-30).** Four commits:
1. an absolute import is looked for under the directory its package runs from, with two cases CPython runs: a
   project's `manage.py` that imports its package, and a namespace portion inside a package, which is no root;
2. a method a class of the repo declares past a base outside it is found by name, with its case;
3. TD-026, Django's model managers found by name, with its strict xfail;
4. the docs.

- **The imports.** The corpus's 14 Python repos have 42,155 absolute imports.
  - The rule resolves 4,054 more: netbox 3,765, elsa 271, mealie 14, flask 3 and azure-saas 1.
  - It changes none of today's answers, and no import is found under two roots.
  - Under the roots the indexer tries, CPython's `FileFinder` finds the indexer's file for each of the 19,522 imports it
    resolves, and no other. So `x/__init__.py` before `x.py` changes nothing either.
- **The corpus and the hold-out:** `0 repo(s) differ` against `-29` and `-26`.
- **The micro set:**
  - the other 10 repos are identical;
  - netbox: −2,130 and +17,350 `CALLS`, and its 3,765 `IMPORTS` now reach the repo's module. Its edges found by type
    go from 2,024 to 4,877, and `inherited` ones from 61 to 305. The share found among several homonyms goes from
    61.7 % to 64.0 % of the edges, and from 37.1 % to 39.3 % of the sites;
  - mattermost: −2 and +17 `CALLS`, from a test that imports its sibling script.
- **The per-site attribution cannot explain this change.** `answers.py` reads the extraction's answer for a receiver,
  which names the import, while where the import resolves is the resolver's. Each changed site was explained instead
  by the `TypeIndex`'s verdict on its receivers, in both trees.
- **Where netbox's new edges come from:**

  | Sites | Edges | Found |
  |---|---|---|
  | 3,075 | 3,082 | by type |
  | 5,179 | 13,520 | by name, on Django's ORM chains (`Model.objects.<method>(..)`) |
  | 396 | 711 | by name, elsewhere |

  The ORM's chains already had 15,961 edges by name on `main`, on names a star import binds. They now have 29,474. The
  author keeps the change, and that growth is TD-026, due in step 6 (H5-D28).
- **Judged by an agent that did not write it (H7-D6).** It read 46 seeded rows at the source.
  - 33 rows are right, 2 partly and 11 wrong. Against `main`, 35 are better and 11 worse.
  - Every typed edge it checked is the method CPython runs, apart from a `self.m()` that reaches the base's method, not
    its subclasses' overrides (H5-D27).
  - The wrong rows:
    - seven Django manager chains, and a `dict` subclass's method read through a subscript, found by name as the rule
      says (TD-026 for the first);
    - two calls of a mixin's method past Django's bases, which got no edge. Commit 2 fixes them, in 15 sites: 14
      have `main`'s edges again, and the guess by name reaches the mixin's method only where it is among the
      nearest homonyms.
- **On a live install** (the fifteenth golden round): the dry-runs are identical, the graph holds them before and
  after the reinstall, and the 27 calls give the same answers. The live snapshots hold no Python file, so the round
  checks the install, not the change.
- **The cost** in netbox, over three rounds interleaved with `main`:
  - the extraction is the same: 9.1–9.6 s against 9.2–9.6 s;
  - the HTTP pass grows from 7.5–7.7 s to 8.4–8.6 s;
  - peak memory is the same, 666–667 MiB.
- **What stays open:**
  - a root only configuration gives (`PYTHONPATH`, pytest's `pythonpath`, setuptools' `package-dir`,
    `sys.path.insert`): about 50 imports in the corpus. When a repo of the portfolio needs one, the options are to read
    the declarative configuration as data, or to let a person declare the repo's roots in `atlas.yaml`;
  - a project inside a directory a regular package holds: aiohttp-demos' `demos/moderator_bot`, 4 imports. The
    language cannot tell it from a namespace portion, so it needs roots in `atlas.yaml`, or SCIP in the installed
    environment;
  - a name only a star import binds: followed since #51, in the next section.

### What a Python star import binds

A name that only a star import could bind was `Unknown`, so the call went by name. A class whose base came through a
star import had an MRO the index could not see. netbox imports its models through `from dcim.models import *`, and
`dcim/models/__init__.py` re-exports them through `from .sites import *`: 9,108 receivers of netbox were such names.

- **The rule is CPython's** (`languages/python/stars.py`). `from m import *` binds each name of `m`'s `__all__`, or,
  with none, each name of `m`'s namespace that does not begin with `_`, those its own star imports bind included.
  Statements run in order, so of a module's own binding of a name and a star import that binds it too, the later one
  holds it.
- **What the facts record** (`type_facts.py`): a module's star imports, in order and where each is, where each name
  it binds is bound last, and its `__all__` when it is a literal list or tuple of strings, with what `+=` adds.
- **The extraction** passes a name only a star import may bind to the resolver as a name of the module, and the
  `TypeIndex` follows the star imports from the last to the first.
- **What stays `Unknown`:**
  - an `__all__` the index does not read: any other binding of it, or any read of it;
  - a star import of a module outside the repo;
  - a name a function binds as `global` that a star import binds too, which no position orders.

**Done (2026-10-30).** Three commits: the rule, with its cases; the module an import names, found once per file
and import; and the docs.

- **The cases.** CPython runs each case:
  - a base a star import binds;
  - a chain of two star imports;
  - a name out of the module's `__all__`;
  - a private name of a module with no `__all__`;
  - a later star import that binds a name again;
  - the module's own binding after a star import;
  - a package's `__all__` that names a submodule;
  - a star import of a package's module;
  - an `__all__` the module computes.

  Disabling the `__all__`, the order or the private names fails its cases. The data of the star cases is
  `indexer/tests/python_star_cases.py`, which keeps the case table under 300 lines.
- **The corpus's star imports.** Of 703, all name a module of the repo, every chain is seen whole, and no `__all__` is
  computed. In netbox, 7,630 of the 9,108 receivers find their name in the chain; the rest are builtins or names
  nothing binds.
- **The corpus and the hold-out:** `0 repo(s) differ` against `-29` and `-26`.
- **The micro set:**
  - the other 10 repos are identical;
  - netbox: −8,651 and +3,923 `CALLS`;
  - dispatch: −8 and +7 `CALLS`.

  netbox's Python calls, by how their edges are found:

  | | `main` | branch |
  |---|---|---|
  | `receiver-type` | 4,877 | 8,319 |
  | `inherited` | 305 | 770 |
  | Share of edges among several homonyms | 64.0 % | 60.2 % |
  | Share of sites among several homonyms | 39.3 % | 35.5 % |
- **Each changed site explained.** 4,650 sites of netbox changed. The per-site attribution explains 792 by the
  extraction's answer. The rest change in the resolver's stage (a class's MRO seen through a star import), as G2 says;
  the `TypeIndex`'s verdict on each receiver, in both trees, explains them all:
  - 1,880 keep their targets, now found by type;
  - 707 drop guesses on a test client: `self.client`, which netbox's test classes inherit from Django, through bases
    imported by a star import;
  - the rest change, narrow or gain a target, typed now.
- **Judged by an agent that did not write it (H7-D6).** It read 43 seeded rows at the source and followed each star
  chain by hand.
  - 40 are right, 3 partly and none wrong; all 43 are better than `main`.
  - Every typed edge is the first declaration of the C3 MRO, and every `inherited` one a method only Django declares.
  - The 3 partly keep guesses by name that `main` has, on what an untyped method returns.
- **On a live install** (the sixteenth golden round): the dry-runs are identical, the graph holds them before and
  after the reinstall, and the 27 calls give the same answers. The live snapshots hold no Python file, so the round
  checks the install, not the change.
- **The cost.** The rule types many more values, and each looked the module of its import up again. So the module
  an import of a file names is now found once per file and import, which changes no answer (the micro set is
  identical with and without it). netbox, over three rounds interleaved with `main`:
  - the whole run takes 20.0–20.3 s, against 21.3–21.5 s;
  - the HTTP pass takes 7.3–7.5 s, against 8.2–8.5 s;
  - peak memory grows by 2 MiB.
- **What stays open:**
  - a call with no receiver of a name a star import binds (`CustomField(..)`, `post_data(..)`) still goes by name;
  - a package with no `__all__` also binds the submodules its own imports load, which the index does not model;
  - the graph writer merged `CALLS` edges of one caller, target and line that differ in `strategy` or `method` (3,088
    groups in the micro set): the `fix(graph)` of the next section.

### One `CALLS` edge per caller, callee, line and method

The writer merged a snapshot's `CALLS` on their caller, callee and line, the last row written winning, and the resolver
gave one row per call. Where calls of one line reach one target, the graph lost what told them apart:
- **Two methods of a package base on one line** (`db.Add(a); db.Remove(a)`, or a Python constructor and an inherited
  method, `Model(..).save()`): one edge lost its `method`. 161 edges in the micro set: grafana 71, netbox 59, dispatch
  23, umbraco 6, gitea 2.
- **One target found by two strategies:** the graph showed the last, not the strongest. 2,910 edges. Most are a
  receiver's interface method found again through its implementation: when the implementation does not declare the
  method, a base outside the repo gives it, and the lookup through the implementation's own bases ends at the
  interface's method (umbraco 2,596, btcpayserver 147, jellyfin 112).
- Neither `graph_vs_dry.py` nor the writer's test saw it: both counted a call by the key that merged it.

What changes (`fix(graph)` #53):
- **The resolver gives one edge per caller, callee, line and method** (`one_per_edge`, `core/resolve.py`), with the
  strongest strategy of the calls that give it: by the receiver's type, the message's, a base outside the repo, then
  the nearest homonym, and the unambiguous before the `-ambiguous`. The dry-run is the graph, record by record.
- **The writer creates each edge.** A `MERGE` cannot key on a `method` that is null, and the snapshot's edges were just
  dropped.
- `neo4j/SCHEMA.md` states the identity. `graph_vs_dry.py` and `test_graph_writer_neo4j.py` count a call by it, and the
  test checks one edge per call. `tests/mcp_it/accounts` gains the three shapes: one target found by the receiver's
  type and by its implementation, one call twice on a line, and two methods of a package base on a line.

The proof:
- **Cases that fail on `main`:** `test_call_edges.py`, where the resolver gives four rows for one call's line, and the
  writer's test against a throwaway Neo4j, where the graph keeps one of `Add` and `Remove` and the dry-run repeats
  calls.
- **The micro set:** the 12 repos differ, by 68,769 records removed and none added. Most are one call of one target
  twice on its line (grafana 36,811, vikunja 15,331). A check proves, for each repo:
  - no key repeats, and none is lost or new;
  - each edge keeps the strongest strategy of its calls, at the place of the first;
  - the other sections are the same.
- **Corpus and hold-out:** `0 repo(s) differ` against `2026-10-18-v2-baseline-29` and `2026-10-18-v2-holdout-26`.
- **The cost:** `one_per_edge` takes 182 ms on grafana's 610,110 calls, and 17 ms on netbox's 83,416.
- **On a live install** (the seventeenth golden round): the branch's dry-runs lose 142 repeated records, the graph
  holds `main`'s before the reinstall and the branch's after, strategies included, and 2 edges of one snapshot take the
  strongest strategy. The 27 calls give the same answers.
- **What stays open:**
  - the graph keeps no column, so the calls of one target on one line stay one edge;
  - TD-027, due in a `fix(csharp)` PR before F1.2: the implementation an interface receiver reaches gets no edge when
    a base outside the repo gives it the method. The lookup on the implementation found the interface's method again,
    the 2,596 edges of umbraco above among them; the answer is an `inherited-impl` edge to it, with `method`.

### A client wrapper's receiver, from the type index

The Python scanner had a type service of its own for client wrappers (`_class_of`): `self`, a local or module variable
assigned `Client(..)`, `self.x` assigned so in the class, all by the class's simple name, with the bases as written and
walked level by level. Beside the `PythonTypeIndex` that was a second answer, which step 5 makes one (H5-D10), as C#'s
scanner asks the `CsTypeIndex` (H5-D11). It missed what the resolver types (an annotated parameter, an attribute a
base's `__init__` assigns, a module variable another module imports), took two classes of one name for one, where two
wrappers of different shapes gave nothing, and took a direct base's wrapper before the one C3 puts first.

What changes (`fix(python)` #55):
- **A call on a receiver reaches the wrapper of the class the index finds declaring the method,** up the MRO of the type
  the extraction gives the receiver: `types.method`, the question the routers already asked (`PyRouters.declaring`). A
  class is named as the index names it (`app/clients:Client`), and a method's wrapper key from its scopes
  (`forms.path`).
- **The scanner publishes no class bases:** the index walks the MRO. `_class_of` by name, `_constructed`,
  `_attribute_class` and `_value_of` go.

The proof:
- **Five cases** (`test_python_wrappers.py`), each checked on both sides: an annotated parameter, an attribute a base
  assigns, a module variable another module imports, two classes of one name, and a diamond whose C3 order CPython
  confirms. On `main` the resolver passes all five and the scanner fails all five.
- **The corpus, the hold-out and the micro set:** `0 repo(s) differ`.
- **An oracle over the 15 Python repos** of the corpus, the hold-out and the micro set, with both codes: the same
  outbound calls in all. The index types 3,652 receivers `main` did not, and leaves 1,142 that `main` typed by name,
  among them ctfd's `cache.delete`, a method its class gets from `flask_caching`. None reaches a wrapper.
- **The cost,** three rounds interleaved with `main`; memory the same:

  | | `main` | branch |
  |---|---|---|
  | open-webui, the HTTP pass | 7.5–8.0 s | 7.3–7.7 s |
  | zulip | 10.0–10.9 s | 8.9–9.7 s |
  | netbox | 6.7–7.3 s | 5.9–6.3 s |
- **On a live install** (the eighteenth golden round): the dry-runs of `main` and of the branch are identical on the 10
  snapshots, which hold no Python file, and the 27 calls give the same answers.
- **What stays open:**
  - TD-028, due in F1.2: a class a function holds has no name in the index, so a call on `self` in its methods reaches
    no wrapper of it, where `main` found it by the class's name. No site in the corpus;
  - a call on a function through its module (`api.get_json("/x")`) reaches no wrapper, as on `main`.

### TS's step 5 (H5-D36)

Before its step 5, TS had no type service. `TypeScriptSupport` (`languages/typescript/symbols.py`), which serves
`typescript`, `tsx` and `javascript`, overrode none of the type hooks, so the extraction records no receiver's type and
the resolver finds every TS or JS call by name; `bases` gives nothing, so TS has no `EXTENDS`, `IMPLEMENTS` or
`OVERRIDES`. The HTTP scanner kept answers of its own: a module's clients (`axios.create`, `new ApiClient(..)`), a class
with a base field, the class around `this.m()`, `const c = new Client()`, each by a class's simple name. It never reads
a type annotation.

The case table is `indexer/tests/test_ts_types.py` (#66). Each case names the declarations TypeScript's own checker
resolves its call to, and the test checks every case against that checker on each run: `typescript@6.0.3`, the last
line with the compiler's JavaScript API, with Node, in the test image only (`indexer/scripts/checks/ts_checker.js`; it
reads and types the files and runs nothing). Every typed case has homonyms of its method in other classes, so a call
found by name cannot reach the right one by luck.

| Case | The checker | Today | Test |
|---|---|---|---|
| `this.m()` in a method, in a field's initializer, in an arrow function in a method; in JS too | the class's method | the file's homonym, by name | xfail, one per form |
| `this.m()` that a repo base gives by `extends` | the base's method | by name | xfail `a-method-of-a-repo-base` |
| `new C().m()`, a local of it, through an aliased or a namespace import, in JS | `C.m` | by name | xfail, one per form |
| a typed parameter (also in a `.tsx`), a parameter property, a typed field, a field assigned `new C()`, `x as C`, `x?.m()`, an instance a module exports | the declared type's method | by name | xfail, one per form |
| a typed local (`const x: Base = new B()`) | the declared type's, `Base.m` | by name | xfail `a-typed-local` |
| a function's declared result, called or kept in a local | its type's method | by name | xfail, one per form |
| a call on an interface; on a type parameter with a constraint | the interface's method; the constraint's | by name | xfail, one each |
| `any`, a JS parameter, a type parameter with no constraint, `this` in a `function` in a method | none | by name | guard: no typed edge |
| a union, an intersection | each type's method | by name | guard: no typed edge |
| a union the checker narrows by control flow, a result the function does not declare, a callback's parameter a generic infers | one method | by name | guard: no typed edge, since a declaration's answer does not give it |
| a value of a package's class | none (the test image holds no package) | the repo's homonym, by name | xfail `a-value-of-a-package-class`: no edge |
| scope: a block that shadows a name, a `var` used before its declaration, a `let` reassigned from `any`, a function declared after its use, a closure, a destructured parameter (#67) | the declared type's method | by name | xfail, one per form |
| scope: a type parameter that shadows an import; a `for…of` variable (#67) | none; one a generic infers | by name | guard: no typed edge |
| scanner: a module's client, a client named for its role (`http`), a repo client constructed in a module constant or a local | — | found | guards |
| scanner: a parameter, a parameter property, a field and a declared result of a repo client's type; a parameter and a parameter property of a client library's type (`AxiosInstance`) | the client's method, for the repo's | not found | xfail, one per form |

The table corrects two items H5-D36 listed as `Unknown`. A `let` takes its initializer's type in TS, so a second
assignment does not make it two types; what the checker does and a declaration does not is narrowing a union by
control flow. A parameter injected by token declares its type in its annotation; the token only decides which
implementation runs, which is a dispatch. A client library the scanner does not know (Angular's `HttpClient` under
another name than `http`) is the catalog's, step 6's (TD-024), not a type's.

The three ids share one index, since a `.ts` file imports from `.tsx` and `.js`. `languages/typescript/http.py` is over
the module target, so the new code goes into modules of its own. The probe reads the three ids together
(`answers.py typescript,tsx,javascript`), with `this`, the node that binds it at the use, and `closures`.

#### TS's scope index (#67, H5-D37)

The refactor goes in two PRs, as Python's did. The first is the scope index: which declaration of the file each name
binds to, and which node binds each `this`. The core's scopes, which the scanner reads, look a name up in the function
around it and take the last assignment before the use, so a block that shadows a name, a `var` read before its
declaration and a `let` reassigned bind elsewhere in TS. Nothing in the extraction reads the index yet, so the graph is
identical.
- **Where it lives.** `languages/typescript/scope_model.py` holds a scope and what it binds, in which of TypeScript's
  meanings (a value, a type, a namespace); `scope_enter.py` the scope each node opens; `scope_build.py` what each
  declaration binds and where each name read is looked up; `scopes.py` the lookup (`TsScopes`).
- **The rules, each the binder's:**
  - a `var`, a function declaration outside strict code, a namespace and an import belong to the function, static
    block, namespace or file around them; a `let`, a `const`, a class, an enum, an interface, a type alias and a
    function declaration in strict code, to their block;
  - a function's parameters and type parameters are seen from its signature, what its body declares from the body
    only;
  - a class's, an interface's and a type alias's type parameters are theirs; a named function or class expression sees
    its own name; an `infer` type is its conditional type's, seen in its `extends` and in the branch that holds; a
    mapped type's key is its own;
  - a decorator is read outside what it decorates; a namespace that declares only types is no value; code is strict in
    a module, under a "use strict" prologue and in a class.
- **The proof.** `checks/ts_scopes.py` compares the index with the binder (`checks/ts_scopes.js`) over every TS and JS
  file the indexer extracts from the corpus, in 6 minutes: of 51,598 files, 51,025 are compared, 4,702,668 names and
  202,297 `this`. Every one binds as the binder binds it, but for two kinds of difference counted apart, each with a
  test:
  - `misread`, 61 names in code tree-sitter reads as other code: 48 in a generic tag of a template (`styled.div<Props>`
    before a template, which it reads as two comparisons, or `sql<T>` before one in an arrow function, which it closes
    early), 9 a `using` declaration declares, which it reads as an assignment, and 4 a minified `let[a, b]` declares,
    which it reads as an index into a variable `let`;
  - `require`, 16 names: a JS `const` a `require` initializes, which the binder binds as an import in the function
    around it, where JS binds it in its block (two `catch` blocks that each require one module).

  Counted apart too: 560 files where tree-sitter finds an error, mostly syntax its grammar does not parse yet (`export
  type * from`, `typeof import(..)` in a type argument), and 13 the compiler does not parse.
- **What the oracle sets aside**, where the binder's answer is not a scope's: an assignment to a property, which the
  binder records as a declaration in JS and on a function (`f.priority = 1`), and the file itself (a CommonJS module's
  `exports`) declare no name; a name is looked up with the checker's `resolveName`, since `getSymbolAtLocation` answers
  `exports` in `exports.x = ..` with the member it declares; a script is bound alone, since the scripts of one program
  share a global scope where two of them may declare one name.
- **The tests.** `test_ts_scopes.py` compares 34 rules and the case table's files with the binder on every run, and
  the table gains its scope cases (above). Each rule was broken once, and a test failed.

#### TS's types (#68, H5-D38)

The second PR is the types: TS's facts, one `TypeIndex` for the three ids, and the scanner's answers read through them.
TS's `call_receiver` still answers nothing, so the resolver asks none of the type hooks and the graph is identical.
- **Where it lives.** In `languages/typescript/`:
  - `forms.py`: how a type is written for the index to read across files, in the terms of the file's module: a type's
    name (`B`, `m.B`), `call:f` (what a call of `f` returns) and `value:x` (what the module's name `x` holds). A type
    parameter reads as its constraint, and `B | null` and `B | undefined` as `B` (H5-D38);
  - `type_facts.py`: a file's facts as values with no tree node (`TsTypes`): what each name of the module denotes; each
    class's and interface's bases, fields and methods, where a class's fields are its instance's (its fields, its
    parameter properties and its getters) and a static member is the class's own; and what the file exports,
    re-exports and exports all of;
  - `type_index.py`: the `TsTypeIndex`, which looks a name up among its module's names, then through what the module
    imports and exports, and a member among a class's or an interface's own, then its bases', in order. What a package
    declares is `Outside`, and none of the repo's methods is its;
  - `modules.py`: the file of the repo, or the package, an import names, moved out of `symbols.py` so that the import
    resolver and the index give one answer;
  - `receivers.py`: the type a call's receiver's base declares, read through the scope index's binding, with the
    members that follow it, and the class whose members a `this` reaches.

  The core gains `LanguageSupport.type_family`: `RepoTypes` builds one index per family, and TS's three ids are one.
- **The scanner.** Its class of a `this` (`this.m()`, and a client class's own request, `this.fetch("/batch")`) is the
  class around the method, the field or the static block that binds the `this`, as the scope index says. Its class of a
  `new C()` is the type index's, through imports, re-exports and default exports. No site changed on the corpus, the
  hold-out or the micro set. The first corpus run showed one difference, the PR's own: the grammar reads `await
  this.fetch<T>(..)` with the `await` in the callee, which the walk to the `this` did not step through.
  `route-patterns-ts` now holds that form.
- **The proof.**
  - `test_ts_type_index.py` reads the case table by the types, with `call_receiver` set as the change of behavior will
    set it. The 30 typed cases reach the declaration the checker names, with `receiver-type`; each of the 11 `unknown`
    cases gives the reason it names; a value of a package's class reaches no method.
  - `ts_type_rules.py` holds 45 rules past the table, which the test reads the same way:
    - the forms: a generic class, a type alias, `B | undefined`, a module namespace's type (`m.B`), a type parameter's
      constraint, and a module's value written `as`, a call's result, another name's value or a function;
    - across files: a re-export and a renamed one; `export *`, which leaves the default out, and `export * as`; a
      default export of a class and of a name; a `declare`d value and an exported `declare`d class; `import m =
      require(..)`; and in JS a `require`, a destructured one, and one in a function, which no module's names hold;
    - members: an interface's field and its base's, a getter, a destructured parameter and local, a static field (the
      class's own), and a member of a package's value;
    - what stays `Unknown`: a package's type, a global type, a type a function or a static block declares, the `this`
      of a static member, of a class expression, of a class a function declares, of an object literal's method,
      outside a class and in a namespace, a catch clause's variable, an element of a destructured array, a function a
      local holds, and a method's result.
  - Besides: the shared index, the implementers and supertypes (each once, through a diamond and a cycle), the type
    service's questions across files, and a base outside the repo.
  - Each of the forms', the facts', the index's, the receivers' and the scanner's rules was broken once, 91 mutants,
    and a test failed each time. A first round left 29 alive. They found three gaps of the facts: an `export declare`d
    class or value, `import m = require(..)`, whose module its clause holds, and a JS destructured `require`, which the
    receiver did not read through the facts. They also found two branches the code could not reach, now gone: a name
    an `infer` or a mapped type binds, which no annotation the forms read holds, and a class body's holder that is no
    class.
  - The facts are values: `checks/dump.py` twice for each id over the corpus gives the same facts, for 35,250 TS,
    12,013 TSX and 8,543 JS files.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, goes from 39.8 s to 41.6 s, and its
    peak memory from 1,616 MiB to 1,642 MiB.
- **What differs from the plan.** The facts tell a type parameter by the declarations around the name, without the
  scope index, which is built for a file only where a question needs it. `member_by_name` keeps the core's answer,
  since TS checks a call against its receiver's type; whether a method a JS prototype assignment adds needs it is the
  change of behavior's question.

#### TS's hierarchy (#69, H5-D39)

The fifth PR writes TS's `EXTENDS`, `IMPLEMENTS` and `OVERRIDES`. Calls are still found by name, with the abstract
methods among their candidates now, since an abstract method is a symbol.
- **Where it lives.** `languages/typescript/dispatch.py` holds what a dispatching call runs on an instance. The facts
  tell a class's `extends` from its `implements`, and the index answers `extended`, `implemented` and `holds`;
  `symbols.py` has the hooks `bases`, `implemented` and `dispatched`. The core asks the language which bases a type
  implements (`LanguageSupport.implemented`, by default the kinds' rule), since TS's `implements` may name a class. TS's
  query captures `abstract_method_signature` as a method.
- **The rules.** A type's bases are the declarations TS's type index resolves its clauses' names to; one it cannot see
  gives no edge. On an instance of a class, a dispatching call runs what JS finds for the name: nothing of the graph
  where a class of the `extends` chain declares the name a field or a parameter property, which the instance holds as
  its own; else the nearest class whose prototype holds it, nothing where that is an accessor, and else its last
  declaration of the method with a body, after its overload signatures; an abstract method holds nothing there. An
  interface's method runs what the instance's lookup finds. A static method, an accessor and a constructor dispatch
  nothing, and an instance of an interface runs nothing.
- **The proof:**
  - `test_ts_hierarchy.py`: the case's edges are the declarations TypeScript's checker resolves its heritage clauses to
    (`checks/ts_heritage.js`), and its overrides what Node runs on an instance of each class of the case
    (`checks/ts_runs.js`, which compiles the case's own files and runs them, never a repository's), both on each run;
    the closure of the edges is `supertypes`. The case spans `.ts`, `.tsx` and `.js` files, re-exports, a default and a
    namespace import, a generic base, a class implemented, a mixin and a package's base; and each guard of the rule has
    a case that tells it apart: a static and an instance method of one name, a method under a getter and under a field,
    an abstract method over a concrete one, overloads, a method named `get`, constructors.
  - Each rule broken once, 23 mutants: a test failed each time.
  - `checks/ts_heritage.py` compares the index's bases with the checker's over every TS and JS file the indexer extracts
    from the corpus, each file read with its `tsconfig.json`'s `paths` and `baseUrl`: of the 10,542 heritage clauses of
    a module's class or interface, the index names the checker's declaration at all 2,888 where both name one of the
    repo, and another at none, and neither names one at 3,462. Where the checker names one and the index gives
    `Unknown`, 3,284, two gaps `main` has, registered, give 3,277: 3,225 are a name the repo's `tsconfig.json` maps to
    its own file (TD-038), and 52 a CommonJS export (TD-039); the other 7 are a class another browser script declares,
    which scripts share in one global scope and the index, which reads a module's names, does not see. 16 are the
    index's alone: an alias the clone's configuration does not map (SvelteKit's `$lib` and Nuxt's `~`, which a generated
    `tsconfig.json` maps), and a `.js` the index takes where TS takes the `.d.ts` beside it. Counted apart: 886 declared
    in a function or a namespace, and 6 names a module declares twice, which TS merges.
  - Corpus and hold-out: 0 repo(s) differ. Micro: the five repos with no TS or JS are identical; the seven with them
    gain 4,087 hierarchy edges (1,803 `EXTENDS`, 299 `IMPLEMENTS`, 1,985 `OVERRIDES`) and 148 abstract methods, and
    change CALLS at 417 sites, each one where an abstract method joins the homonyms a call by name reaches. Against the
    checker's resolution of outline's and ghost's calls, of their 249 such sites the callees hold more of its
    declarations at 57, as many at 61 and fewer at 20, where the abstract method, nearer, pushes one of three homonyms
    out; the checker names none at 111, mostly mocks in tests.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, goes from 42.1 s to 42.7 s, and its peak
    memory from 1,641 MiB to 1,649 MiB.
- **What differs from the plan:** the corpus oracle reads each file's `tsconfig.json`, where the index reads only the
  usual aliases, which is TD-038; and the proof found TD-038 and TD-039, which the author placed before the change of
  behavior, so TS's step 5 is eight PRs.

#### TS's module resolution (#72, H5-D40)

- **Where it lives.** `languages/typescript/tsconfig.py` reads the repo's `tsconfig.json` and `jsconfig.json` files,
  with the comments and trailing commas TypeScript allows, once for each context that resolves an import: the resolver,
  the type index and the HTTP scanner's view each hold their own files, so a config is read from the repo's tree, as
  Go reads its `go.mod`. `modules.py` asks it first.
- **The rules, each TypeScript's:** the nearest config above the file, its `extends` followed within the repo, a
  config another package publishes adding nothing; where it maps no path and only refers to other projects, the one
  whose `files` or `include` holds the file. Then a relative path; the `paths` pattern that matches, the exact one
  first, else the longest prefix, each target in turn, relative to `baseUrl` or to the config that writes them, and
  nothing below `baseUrl` after a pattern that matches and names no file; a name below `baseUrl`. Where no config maps
  it, a conventional alias still names a file below the usual roots, as a bundler's config the clone does not hold
  declares it. A path written with a trailing `/` names a folder, and `..` may name the repo's root.
- **The proof:**
  - The case (`test_ts_modules.py`), checked on each run: each import resolves to the file TypeScript's module
    resolution gives it (`checks/ts_modules.js`), and the case resolves as it states; it spans exact and wildcard
    patterns, several targets, `baseUrl`, an array `extends`, a config that only refers to others, a `jsconfig.json`, a
    pattern that matches and names no file, the root and a trailing `/`. 20 mutants, each killed.
  - Over the corpus (`checks/ts_modules.py`): of the imports of the TS and JS files the indexer extracts, TypeScript
    gave 48,017 a file of the repo the index read as a package or none, 37,856 by `paths` and 9,429 by `baseUrl`; the
    index now names TypeScript's file at all of them, and 230,490 imports resolve the same. What differs is the two
    gaps the proof found, TD-041 (1,199 `.d.ts` and 2 `.d.cts`) and TD-042 (25,497, and 2 a package's import of
    itself); 27 in the folders discovery skips as build output or vendored (`build`, `target`, `vendor`); and 1,773 where the index's conventional alias, a `.vue` or a JSON file gives a file
    TypeScript does not resolve with the clone's configs. `checks/ts_heritage.py` now gives the checker's declaration
    at 6,111 heritage clauses, where it gave it at 2,888; the 2 left are declaration files.
  - The graph: the hold-out, 0 repo(s) differ; the corpus differs at outline alone, by 2 calls to Microsoft Graph
    through the app's own `request` wrapper, which an import by `@server/*` now reaches, outside its list's scope. Micro: grafana, umbraco, mattermost, ghost and
    outline move 39,441 `IMPORTS` from a package to a file and gain 720 they had none for; their `CALLS` only gain,
    17,778, each where a name an alias imports is now found by name as a relative import's is; and their hierarchy
    gains 4,684 edges, 4,503 in umbraco. Against TypeScript's checker, which now reads each file's config too, outline's
    3,071 sites that gain callees hold its declaration at 47 %, where its other sites do at 36 %.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 54.5 s, from 54.8 s, and peaks at
    1,447 MiB, from 1,459 MiB; umbraco's and mattermost's micro runs take as long or less.
- **What differs from the plan:** `checks/ts_checker.js`, the change of behavior's reference for calls, read no config,
  so a receiver an alias imports had no declaration; it reads each file's config now.

#### TS's CommonJS exports (#73, H5-D41)

- **Where it lives.** `languages/typescript/commonjs.py` reads what a module exports by assigning it, and the TS facts
  (`type_facts.py`) hold it: the module's own value under a name no name of a module can be, and each name it assigns
  beside the ones its `export` statements give. A value no name of the module holds, as `new S()` or an object
  literal's `d: new D()`, is held under the name its exports give it. The type index takes the own value for a whole
  module's import and for a default import; the receivers read `require("./m").a` as the facts do.
- **The rules, each TypeScript's:** a JS file with no `import` or `export` is a CommonJS module, whose last
  `module.exports = x` at the top level is its own value; an object literal it assigns gives a name for each property
  instead, and `exports.a = x` and `module.exports.a = x` export `a` beside it; a value that is a `require` re-exports
  that module, or its name. A TS module's `export = x` is its own value; where `x` is a namespace, its export clauses
  give the module's names, and the class or function it merges with is the own value, since a namespace merges into
  the class, the function or the enum it names. A `require`, `import x = require(..)`, a namespace import and a default
  import take the own value, even beside a `default` the module assigns; a named import, a destructured `require` and
  `require("./m").a`, a name of it.
- **The proof:**
  - The case (`test_ts_commonjs.py`), checked on each run: each base its classes extend and each method its calls
    reach is the declaration TypeScript's checker resolves it to (`checks/ts_heritage.js`, `checks/ts_checker.js`). It
    spans `module.exports` of a name, a `new`, an object literal, a `require` and two assignments; `exports.a` and
    `module.exports.a`, also beside an own value; `require("./m").a` and a TS module's `.default`; a file with ES module
    syntax, which assigns nothing; a class expression, `export =` of a class, of a namespace and of a class a namespace
    merges with; and each import form. 24 mutants, each killed.
  - The heritage oracle reads a value a class extends by the checker's base type: an object literal's class is a
    property to the symbol. Over the corpus (`checks/ts_heritage.py`), the index names the checker's declaration at
    6,153 heritage clauses, where it gave it at 6,111, among them the 42 TD-039 counted, all in ghost, and another at
    none; 3 name a class expression, TD-043.
  - Against the checker's calls on ghost, read by the types as the change of behavior will read them: of 223,704
    method call sites, the method the type index gives changes at 7,577; it is the checker's at 1,275, and no site
    loses the checker's. At 223 it is the class whose instance `module.exports` holds, where TypeScript reads the
    hand-written `index.d.ts` beside it, TD-041; at 100 the checker names none, 59 a `require` in a TS file, which
    TypeScript does not bind and Node runs, and 41 a module a hand-written declaration file describes. Outline: 2 sites
    change, from one `Unknown` to another.
  - The graph: the corpus and the hold-out as on `main`; micro: ghost gains 42 `EXTENDS` and 48 `OVERRIDES`, and
    nothing else changes in the twelve repos.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 60.5 s, where it took 59.4 s,
    each side's runs spread over 5 s, and peaks at 1,446 MiB, where it peaked at 1,447 MiB.
- **What differs from the plan:** the corpus had one clause the plan's forms left out, a name a `require` reads
  (`require("./m").default`), which 464 bindings of the corpus write; it is read as a destructured `require` is. A
  namespace no longer replaces the class it merges with, and `import * as` of an `export =` module takes its own value,
  as the checker does.

#### TS's declaration files (#79, H5-D45)

- **Where it lives.** `core/config.py` no longer lists `.d.ts` among the generated suffixes, so discovery reads a
  hand-written declaration file. `languages/typescript/modules.py` resolves an import to one by TypeScript's order,
  `.ts`, `.tsx`, the declaration file, then the JS, in each of its extensions, and `declarations.py` pairs a JS file
  with the declaration file that describes it (`a.d.ts` beside `a.js` or `a.jsx`, `a.d.mts` beside `a.mjs`, `a.d.cts`
  beside `a.cjs`). The type index asks that file for a name the JS does not give.
- **The rule, option B of the plan:** beside a JS file, an import names the JS file, whose values are the JS's, as an
  override is what the JS runs (H5-D39) and a `require` in a TS file is what Node runs (H5-D41); a name the JS cannot
  declare is the declaration file's, asked after the JS's own names and its `export *`. It diverges from the checker on
  purpose at the import of such a pair and at what its instance is. An ambient `declare module 'pkg'` stays a package's,
  and a global declaration names no module.
- **The proof:**
  - The case (`test_ts_declarations.py`), checked on each run against TypeScript's resolution and checker
    (`checks/ts_modules.js`, `ts_heritage.js`, `ts_checker.js`): a types-only module, a folder's `index.d.ts`, a
    `.d.mts` and a `.d.cts`, a `.js` written for its `.d.ts`, a pair in each extension, the JS's names before the
    declaration file's, an ambient module and a global script. The checker names a declaration file `x.d` now, as the
    index does. 14 mutants, each killed after a case was added for the one that survived.
  - Over the corpus (`checks/ts_modules.py`), the imports TypeScript resolves to a `.d.ts` that the index did not
    extract go from 1,199 to 1; the index names the checker's file at 904 more. 495 are a JS file beside its `.d.ts`,
    by decision: ghost 312, fastify and directus; and 158, all fastify's, are a folder's `package.json` entry,
    which the index did not read before either, TD-049. The 73 new imports of a file the index names and the checker
    does not are `.vue` components a declaration file imports, as in the others.
  - Over the corpus (`checks/ts_heritage.py`), the index names the checker's declaration at 6,205 heritage clauses,
    where it gave it at 6,153, fastify's 18 among them. The 35 new "index only" are the Cloudflare runtime's types that
    two generated `worker-configuration.d.ts` declare: the repo's config sets no DOM `lib`, which the oracle does not
    read.
  - Against the checker's calls on ghost, read by the types as the change of behavior will read them: the type
    index gives the checker's method at 204 more of 223,704 sites and loses it at none; the 223 of the settings cache
    stay `CacheManager`'s. Outline and mattermost: no site changes.
  - The graph: the corpus differs from the baseline by outline's 2 calls only (#72's), the hold-out by none; micro:
    9 of 12 repos differ, by 157 files, 517 symbols and 96 imports, all in declaration files, with none removed, and
    by `CALLS` found by name: 7,303 edges come and 3,018 go. A site that reached an unrelated homonym of another package
    now reaches the command or the method its declaration file declares (mattermost's `cy.visit()`, 3,407 sites);
    112 are a site that reaches both a JS class and the `declare class` beside it. The ambiguous ones, as outline's
    koa-passport typings, go when the resolver reads the receivers' types, in the change of behavior.
  - With the reference convention and a probe that uses every key of the format, the six TS repos of the micro set
    gain 153 files, all in the probe's layer for declarations, 498 symbols, 11 entry points and 42 violations, all of
    them in or about a declaration file; nothing else in their output changes.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 44.9 s, where it took 45.0 s, and
    peaks at 1,450 MiB, where it peaked at 1,447 MiB.
- **What differs from the plan:** the proof found TD-049, which the plan did not count; and the `ts_checker.js` naming
  of a declaration file, which the plan placed in the test, is in the case's commit.

#### TS's workspace packages (#80, H5-D46)

- **Where it lives.** `languages/typescript/workspaces.py` (97 lines) reads the workspaces a repo declares, once for
  each context: every `package.json` above a file of the repo, since a manifest shares its folder's module with the
  first the folder has (grafana's root is a Go module), their `workspaces` and `pnpm-workspace.yaml` globs, and
  `member(file, name)`, the folder of the package a file sees under that name. `exports.py` (52 lines) gives the file a
  package's entry names for a subpath. `modules.py` asks them after the aliases and before the npm package, and
  `tsconfig.py` reads `customConditions`. `type_index.py` and the core do not change.
- **The rule.** The members, who sees them and how the entry is read are H5-D46's. Not adopted: a `lerna.json`, which
  the oracle cannot prove, and a `src/` for a build the clone lacks, which would be a guess: TD-050.
- **The proof:**
  - The oracle gained the link a package manager makes (`checks/ts_link.js`, a compiler host that serves
    `<ancestor>/node_modules/<name>` from the workspaces, with a glob expansion that does not share the index's code),
    which `ts_modules.js`, `ts_heritage.js` and `ts_checker.js` take with `--link`, and the config's
    `customConditions`. The case (`test_ts_workspaces.py`) is checked first against real symlinks and then against the
    emulation, for the imports and for the bases: `exports` by condition and by default, with `require` before `import`,
    a custom condition and a condition read through `extends`, a target the clone lacks that falls to the next, an
    exact subpath, two patterns of which the longest wins, a subpath `exports` does not map, `exports` as a string,
    `types`, `typings`, `main` and `index`, a nested workspace of its own (a list and `{packages}`), a `pnpm-workspace.yaml`,
    `!` and `./` globs, a package below a member, a sibling folder that shares a prefix with a root, a package with no
    name, one that is no member and shares its name with a package of the registry, a `paths` pattern that wins over
    a member, and a root that is a Go module as well. The xfail of TD-042 passes and goes; TD-050's takes its place.
  - 36 mutants, each rule broken once: 15 died at the first run, and 34 die after the case grew by the rules the
    others left alive. Two live by design: a workspace that lists `**` taking its own root as a member, and two members of one name, which the
    package managers refuse.
  - Over the corpus (`checks/ts_modules.py`, 259,454 imports), the index names the checker's file at 14,907 more, and
    nothing it named changes. The bucket the oracle counted apart, a package whose entry is a build the clone lacks,
    holds 10,614: mattermost 4,213, ghost 3,131, directus 2,288, grafana 612, immich 210, docmost 91, umbraco 35 and
    nest 34 (TD-050). The 12 it names another file for are a JS file beside its `.d.ts`, H5-D45's decision, in directus.
    A first run found the defect the case now holds: grafana's workspace was not seen, since its root is a Go module.
  - Over the corpus (`checks/ts_heritage.py`, with the link on both sides), the index names the checker's declaration
    at 6,642 clauses, where it named it at 6,205: the 437 of a package the repo's `tsconfig.json` maps to its file,
    grafana's and mattermost's, and no other clause changes.
  - Against the checker's calls on ghost, mattermost and grafana, read by the types as the change of behavior will
    read them: the type index gives the checker's method at 1,876 more sites, 1,850 of them grafana's, and loses it at
    none. In 58 grafana sites it gives the interface's method where the checker, which narrows what an assignment
    gives (`let echo: EchoSrv; echo = new Echo()`), gives the class's.
  - The graph: the corpus differs from the baseline by outline's 2 calls only, and the hold-out by none, both as at
    #79; every repo's output is the same as at #79. Micro: grafana, mattermost and ghost differ, the other nine are
    identical. 13,178, 494 and 282 `IMPORTS` go from a package to a file, and 8, 1 and 6 packages leave the graph;
    grafana gains 471 hierarchy edges (323 `EXTENDS`, 36 `IMPLEMENTS`, 112 `OVERRIDES`), and one `OVERRIDES` it had
    gains a receiver, a class that extends the one it was found on; and `CALLS` found by name come: 4,767 in grafana, 47 in mattermost, 2 in
    ghost, 0 gone. The checker confirms 181 and 27 of them, 3,832 are ambiguous among homonyms, and 2,571 reach
    the minified yarn release `.yarn/releases`; they are calls on a receiver the resolver does not type, which went
    unseen while an import of the package made the receiver an external. A site that reached nothing now reaches a
    homonym, as an import of a file by its relative path does on `main`; the change of behavior gives them their
    receivers' types. One grafana endpoint reads `config.namespace`, a field of an instance
    that `merge(this, options)` fills at run time, and its path goes from `/apis/{param}/namespaces/{param}/datasources`
    to `.../namespaces/default/datasources`, as it does through a relative import on `main`: TD-051, due in F1.2.
  - With the reference convention and the probe of #79, the six TS repos of the micro set change by 6 violations in
    ghost, for the imports of a `.d.mts` file, and 3 in grafana, those of `window.d.ts`, with the one of that endpoint; mattermost does not change.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 42.6 s, where it took 42.6 s,
    and peaks at 1,448 MiB, where it peaked at 1,446 MiB; grafana's, run once on each side, takes 136.3 s and peaks at 4,198 MiB, where it took 135.6 s and peaked at 4,199 MiB.
- **What differs from the plan:** a file sees the members of every workspace root above it, not of the deepest alone,
  which the oracle showed; a `lerna.json` is not read; and the case grew, with the oracle's `--link` in the heritage and
  checker scripts too, from what the first corpus run and the mutants left out. The plan's count of the imports that
  stay a package was about 10,100, with 470 of a name that is no member: 10,614 are the former, and the latter are
  what the rule leaves alone.

#### TS's class members and folder entries (#81, H5-D47)

- **Where it lives.** `queries.scm` and `queries.javascript.scm` give a symbol to a class field that holds a function
  (`method`), and to a class a module's statement declares by an expression (`class`: the binding of a `const`, a `var`
  or an `export`, and in a JS file `module.exports =`, `exports.X =` and `module.exports.X =`). `class_expressions.py`
  (27 lines) gives the facts of such a class the name that gives it one, which `type_facts.py` asks (300 lines, at the
  target); `dispatch.py` has an instance's own field run the function it holds; `modules.py` asks a folder's
  `package.json` for its entry (`manifest` of `exports.py`) before the folder's `index.*`.
- **The rule.** H5-D47's. A field of the nearest class of the chain wins, since a base initializes its fields first;
  what stays out is a field that holds a function by reference, a parameter property, a static field, a class
  expression with no name and one a function holds.
- **The proof:**
  - The case of the fields (`test_ts_hierarchy.py`) is what JS runs (`ts_runs.js`, which compiles the case and runs
    it): a field that implements an abstract method, overrides a method or a field, is shadowed by a base's field, holds a
    function by reference, is static, and a JS class's field. The case of the class expressions
    (`test_ts_class_expressions.py`) is what the checker resolves (`ts_heritage.js` names a class expression as the index
    does and visits it), in each form and in a JS and a TS module, with the unnamed and the nested apart. The case of the
    folders (`test_ts_modules.py`) is what TypeScript resolves: `types`, `typings`, `main` without its extension or as a
    folder, a `main` that names nothing, an `exports` that does not count, and a file beside the folder. Each xfail
    (TD-037, TD-043, TD-049) passes and goes.
  - 32 mutants, each rule or query broken once: all die, after the first run left 13 alive that added the JS forms, the
    `var` form and the nested one, and took out what no case could reach: the CommonJS queries of the TS grammar and
    two conditions of the dispatch.
  - Over the corpus (`checks/ts_modules.py`), the 158 imports of a folder TypeScript resolves through a `package.json`,
    all fastify's, go to none, and the index names the checker's file at 158 more; no other import changes.
  - Over the corpus (`checks/ts_heritage.py`), the checker's declaration at 6,646 clauses, from 6,642; the clauses that
    name a class expression, counted apart, go from 3 to 1, a minified bundle's of ctfd; 7 clauses of class expressions
    that extend a package's, as umbraco's bundles, join those neither names.
  - Against the checker's calls on ghost, mattermost and grafana, read by the types as the change of behavior will read
    them: the type index gives the checker's method at 374 more sites, all ghost's, and loses it at none. At 55 sites
    of ghost it gives a method where the checker, which reads a JS file with no JSDoc, gives none of the repo's, and at 3
    the method of a JS file where the checker gives its `.d.ts` beside, H5-D45's decision.
  - The graph: the corpus differs from the baseline by outline's 2 calls (#72's) and by the caller of 583 calls, in
    mattermost, outline and gotify, a class before and the method now; every endpoint and call is the same but for it.
    The hold-out does not change. Micro: umbraco, grafana, mattermost, gitea, ghost and outline differ, the other six
    are identical: 3,776 `method` and 93 `class` symbols gain, 664 change their scope, 171 hierarchy edges come (168
    `OVERRIDES`, 3 `EXTENDS`) and none goes. `CALLS` found by name: the calls to a symbol this
    change creates are 10,875 in mattermost, 3,635 in ghost and 5,309 in grafana, and the checker confirms 2,196 of the
    4,104 member calls it knows in mattermost, 320 of 1,078 in ghost and 521 of 1,960 in grafana; the others are a
    homonym the resolver chose by name, which the change of behavior replaces with the receiver's method. The edges that go
    are a call whose name stopped being unique, as a TS call of `searchUsers` that reached a Go function of mattermost's
    server.
  - With the reference convention and the probe of #80, the violations are equal in count on ghost, mattermost, umbraco,
    outline, gitea and grafana, and 564 of `clients-live-in-outbound` change symbol from the class to the method
    (mattermost 502, outline 54, grafana 8); ghost, umbraco and gitea do not change.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 46.3 s, where it took 41.0 s
    (13 % more, every branch run above every `main` run), and peaks at 1,453 MiB, where it peaked at 1,450 MiB.
- **What differs from the plan:** the oracle of the folders showed that a relative import reads the manifest from a
  `.ts` file as from a `.js`, and that its `exports` do not count; the class expression's name for a `const` is its
  binding's, not its own (`const X = class Y` is `X`), which is how an import names it; and the CommonJS forms of a
  class expression are in the JS queries only, since a TS module's CommonJS is no export.


#### TS's referenced projects (#82, H5-D48)

A prototype of the change of behavior (the resolver reading the receiver's type, in a copy outside the repo) showed what
it would leave without an edge: 1,241 sites of mattermost, grafana and ghost whose receiver comes from a package of the
repo's workspace with no build, TD-050. mattermost declares the build's output: `@mattermost/client` is `composite`, its
`outDir` is `./lib` and its `rootDir` `./src`, and the `tsconfig` of `channels` references it, so TypeScript reads
`lib/index.d.ts` as `src/index.ts`, built or not. The author asked for a search before taking the trade-off, which found
the compiler's rule and the configs that declare it, and moved the PR ahead of the change of behavior.

- **Where it lives.** `tsconfig.py` reads, of each project a config references, directly or through another, its
  `declarationDir`, `outDir` and `rootDir` (with what it inherits by `extends`) and the sources its `files` and `include`
  hold, as `Config.projects`; `references.py` (30 lines) gives the source of a declaration file; `modules.py` asks it for
  every path it tries (a relative import, a `paths` target, a name below `baseUrl`, a workspace package's entry, a
  folder), the declaration file taking the place of the file where both are there.
- **The oracle.** `ts_configs.js` gives a program of the files of a config with the projects it references and
  `useSourceOfProjectReferenceRedirect`, and `ts_modules.js`, `ts_heritage.js` and `ts_checker.js` read it, where the
  config has references; `ts_modules.js` falls back to `resolveModuleName` for a specifier the program does not read as an
  import, a `require` in a TS file, which a first run showed.
- **The proof:**
  - `test_ts_references.py`: the compiler's file for 25 imports (21 resolve, 4 do not) and the 25 heritage clauses on them, each checked against the index:
    `types`, `main` alone, `exports` with a subpath, a path below the output, a relative one and a folder's, a `paths`
    target, a name below `baseUrl`, a `declarationDir`, the `rootDir` a config writes, an `extends` writes, or its
    folder, a `.mts`, `.cts` and `.tsx` source, a project referenced through another, a built output beside its source,
    a source its `include` does not hold, and a project not referenced. On `main` the index fails the ones that
    resolve. Two of the table's guesses were wrong and the compiler corrected them: a project with no `rootDir` mirrors
    from its config's folder, not from the common folder of its sources (TypeScript 6.0's default), and a reference of a
    reference counts.
  - 22 mutants, each rule broken once, 21 die, and the one left is equivalent (a project that emits nothing never
    matches a prefix). The first run left 3 alive: a folder import of a package, and the order of a built output and its
    source, which the case then got, and which found the index wrong where the build is there too.
  - Over the corpus (`checks/ts_modules.py`), the imports of a package of the repo's workspace that neither the index nor
    the checker resolved go from 10,614 to 5,853 and the index names the checker's file at 4,761 more (ghost 3,131 to
    1,732, mattermost 4,213 to 851); no other category moves. The heritage (`checks/ts_heritage.py`) is as it was, 6,646
    clauses at the checker's declaration, since no clause of the corpus extends a class the redirect brings.
  - The corpus and the hold-out: `0 repo(s) differ`. Micro: mattermost and ghost differ, by 3,359 and 1,352 `IMPORTS` that
    go from a package to a file and 6 `CALLS` found by name in ghost, a call on a value an import brings that reaches a
    homonym, which the change of behavior types; the other ten repos are identical.
  - With the reference convention and the probe of #81: ghost's violations are the same, and mattermost's gain 2, a `decl-into-code` of a `.d.ts` that imports the source of `@mattermost/types`, a file of the repo now.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 47.0 s, where it took 47.1 s, and
    peaks at 1,454 MiB, where it peaked at 1,451 MiB.
- **What differs from the plan:** a project with no `rootDir` mirrors from its config's folder (TypeScript 6.0), so the
  common folder of the sources is not computed; and the condition `source` a bundler enables, which the plan left as a
  debt, TD-052, has the number: ghost's 32 members.

#### TS's function members (#83, H5-D49)

With the resolver reading the receiver's type, a call `api.push(1)` on an `api: Api` goes to the member TypeScript
declares, and a member that is no symbol leaves the call with no edge. The prototype of the change of behavior found
that 47 % of the declarations the checker leads a call to in ghost, 39 % in grafana and 25 % in mattermost are no
symbol. A first reading took about 70 % of grafana's gap for interface members; measured by the form of the member's
type, the function types written in place are 36 % of it, 11 % of ghost's and 8 % of mattermost's, and the rest has a
number and a debt.

- **Where it lives.** `queries.scm` only: a `property_signature` named by a `property_identifier` whose type is a
  `function_type`, in an `interface_body`, in the `object_type` that is the value of a `type_alias_declaration`, or in
  one that is an operand of the alias's intersection or union, or of one of the same kind nested in it, is a `method`.
  No `.py` changes: its owner and qualified name come from the syntactic scope, as a method signature's (`Api.push`,
  `Handlers.run`, `Props.onX`); `dispatch.py` gives the `OVERRIDES` of a class that implements the interface with a
  method or with a field that holds a function; the type facts already read the property as a value field.
- **The rule.** H5-D49's. An optional, a `readonly` and a generic function type are in, and so is an operand of the
  alias's intersection or union: the first implementation left it out with the anonymous object types, and the review
  found that a method signature there already belongs to the alias and the checker names the member by it (240 sites,
  193 of grafana), so the rule follows both. A type name, `typeof`, a union, an intersection, a generic or a lookup as
  the member's type is TD-053; a function an object literal holds, and a member of an object type no declaration names
  (a parameter's, a return type's), TD-054; the alias's object types below more wrappers than the query reaches (a
  union of four, which the grammar nests to the left, a pair of parentheses, a union of an intersection), where a
  method signature is a member of the alias, TD-055, which the second review found and the first had written as a
  plain exclusion; a data property, a constructor type, a name written as a string or computed, an object type below a
  generic or an array, and a JS file stay out.
- **The proof:**
  - `test_ts_signatures.py`: the checker resolves 17 calls to the member the case names (a property, an optional, a
    `readonly` and a generic one, two of type literals, one through an interface that extends its owner, and eight
    through an intersection or a union, among them the members of the first operand of a three-way chain, a member of
    the interface an intersection holds, and a union whose operands the owner and an interface share), and each is a
    `method` of the index with that qualified name and its first line as its signature; a member two operands declare
    is two symbols, which a test counts, since a map by name would not tell; a class that implements the interface
    with methods, and one with fields that hold functions, override the members as they override the method signature
    beside them; 10 forms have no symbol. On `main` the index fails the symbols and the overrides. TD-053's 3 cases,
    TD-054's 2 and TD-055's 5 are the checker's declaration, each a strict xfail of `test_ts_debts.py`, and a test of
    the same file checks that the checker gives each of them.
  - 19 mutants, each rule broken once, all die: no function type, no interface branch, no type literal branch, no
    intersection and no union branch, none of the nested ones, any wrapper (one down and two down), a parenthesized
    mix, a parenthesized operand, a union of an intersection, a third level of unions, three wrappers down, no direct
    parent, any name, a constructor type, a function type at any depth and a `function` for a `method`. The first 10
    left none alive; the extension left one, any wrapper of the alias's value, which a guard of an array's element
    type kills; and the review found that the guards of the wrappers tested parentheses only, so the deficient forms
    became TD-055's cases, which kill the last four.
  - Against the checker's calls on grafana, ghost and mattermost (`ts_checker.js`, read with `forms.py`), the call
    sites whose declaration is no symbol go from 10,416 to 6,466 in grafana, 15,898 to 14,123 in ghost and 3,492 to
    3,160 in mattermost: the members of function type, in an interface, a type literal and an operand of its
    intersection or union, go to none, and nothing else moves but two counted apart. A name the checker qualifies by
    its namespace (`global.Window.dispose`, where the index has `Window.dispose`, since the index qualifies no name by
    a namespace) is the same difference for every symbol: 25 sites of grafana and 1 of mattermost, one more each. And
    ghost's `ModelClass.count`, a method signature in the object type a member returns, now sits under that member and
    carries the checker's name, `ModelClass.getFilteredCollection.count`.
  - The corpus and the hold-out: `0 repo(s) differ`.
  - Micro: umbraco, grafana, mattermost, gitea, ghost, outline, vikunja and dispatch differ, the other four are
    identical. 7,018 `method` symbols come, 4,200 of an interface and 2,818 of a type alias (grafana 3,222, mattermost
    1,867, ghost 1,258, outline 404, umbraco 213, vikunja 36, gitea 17, dispatch 1), 1 changes its scope (ghost's
    `count`, counted in no list) and none goes; 265 `OVERRIDES` come (umbraco 145, grafana 120), each a class that
    implements the member's interface, or one whose subclass does, and none goes. The symbols of an alias's
    intersection or union are the ones a scan of the corpus counts: 178 of mattermost, 45 of grafana, 45 of outline,
    37 of ghost, 12 of umbraco, 6 of vikunja and 2 of gitea, 325 of the 7,018. `CALLS` found by name: 51,809 edges
    come and 34,525 go, as the new members join every call of their name, 1 to 2 % of the calls of the repos that grow
    most. The checker confirms 1,456 of the 12,493 edges to a new member it knows in ghost (11.7 %), 1,730 of 11,237
    in grafana (15.4 %) and 321 of 5,813 in mattermost (5.5 %): callbacks of props (`onChange`, `filter`) that share
    their name with many. The edges that go and leave their site with none are a homonym the name no longer makes
    unique (a global `setTimeout` that reached `BrowserService.setTimeout`, C# code that reached a TS method): the
    checker confirms 0 of 258 in ghost, 2 of 1,300 in grafana and 0 of 586 in mattermost. Per site, the callees hold
    the checker's declaration at 1,458 more and 49 fewer in ghost (30 to 1), 1,812 and 115 in grafana (16 to 1), 320
    and 131 in mattermost (2.4 to 1); a site that loses it reached it by a name a new member makes no longer unique,
    or is a function a member call reaches by name, which a new method of its name now takes
    (`UserActions.patchUser()` on a namespace import, to a props' `Actions.patchUser`), until the change of behavior
    types the receiver.
  - With the reference convention and the probe of #82, the violations and the roles of ghost, mattermost, umbraco and
    grafana are the same, record by record: a role a `declares` gives is its type's, and the new methods take none.
  - The cost: ghost's dry-run, the median of three alternated with `main`'s, takes 48.5 s, where it took 46.7 s (4 %
    more, every branch run above every `main` run, from 7,018 symbols and the calls by name that reach them), and
    peaks at 1,463 MiB, where it peaked at 1,457 MiB.
- **What differs from the plan:** a member's signature has no `;`, which is a token beside it, as a method
  signature's; a class that implements a type alias has no `IMPLEMENTS` edge (the heritage oracle names such a clause
  `other`), so a type literal's member has no `OVERRIDES`, as its method signature has none, and the case's overrides
  are an interface's; and the alias's intersection and union are in the rule, where the plan left them out with the
  anonymous object types. The by-name acceptance was judged after the measure, not before it, and mattermost is the
  repo that gains the least, 2.4 sites for each it loses; the plans of the change of behavior declare their criterion
  before they measure. A string-named member is no debt: no call of the corpus the checker resolves reaches one. A
  method or a field with a `#private` name has no symbol either, ghost's 190 sites, which this PR does not touch.

#### TS's resolver reads the receiver's type (#84, H5-D50)

The first of the two PRs of the change of behavior: a call on a receiver whose type the code declares reaches the
methods of that type and its bases, and no homonym. The prototype measured before #81 found the checker confirming 95 to
100 % of the typed edges and 0.1 % or less of the by-name edges they replace; this PR declared its acceptance criterion
before it measured, and a round of research (six investigations, a synthesis and a challenger that tried to refute it)
changed the criterion and the rule before the code was written.

- **Where it lives.** `symbols.py`: `file_index` builds the file's `TsScopes` and `call_receiver` answers with
  `receiver_of`, with the flag of a JS file; `modules.py`: a `Package` is `local` where the repo holds the package and
  its entry is a build the clone lacks; `workspaces.py`: a `file:`, `link:` or `portal:` dependency of a `package.json`
  links a package of the repo under the dependency's own name, for the files below that manifest, with the
  `workspaces` members, the deepest manifest first; `scopes.py` and `receivers.py`: a value a function tests with
  `instanceof` has no type (`narrowed`); `type_index.py`: a local package with no entry is
  `Unknown`, not what a package declares, also through an `export *` (299 lines of 300). The core does not change. `languages/base.py` changes one
  docstring, `member_by_name`'s. `scripts/checks/ts_link.js`, the host the checker's oracle resolves links through,
  learns the same dependencies, so the emulated link equals the one a manager makes.
- **The rule.** Where the type is known the call reaches its hierarchy, as in Go, C# and Python (`receiver-type`,
  `receiver-type-impl`, `inherited`, the `-ambiguous` variants); where it is not (`any`, a parameter of JS, a union, an
  unconstrained type parameter, a result the function does not declare, a value a function tests with `instanceof`), the call
  goes by name as before. A package of
  the repo with no entry, and a class or an interface whose bases reach one, whatever its other bases are, go by name
  too, since the method may be the package's and its source is in the repo; a package of npm declares no method of the repo. Two things the first
  design got wrong, found by the challenger and measured: the `file:` dependencies, the largest population of by-name
  edges it lost (mattermost's end-to-end tests link `@mattermost/client` that way, 357 sites), and the base of an unknown
  package, which gave a class `inherited` and a `this.m()` in it no edge.
- **The criterion, declared before the measure, and what it gave:**

| | The criterion | The measure |
|---|---|---|
| A1 | typed edges the change adds that the checker confirms, ≥ 95 % | of those it names a declaration of the repo for: ghost 97.3 %, grafana 99.9 %, mattermost 100 %. A `receiver-type` edge is judged by its method (ghost 97.1 % when a declaration file and its implementation are two, grafana 99.9 %) and an `inherited` edge, which goes to a class, by the owner of the declaration the checker names (ghost 888 of 916, the 28 being TD-058's factory classes; grafana 1 of 3, the two being TD-053's; mattermost none contradicted). The edges it names none for, or no site, are 5.5, 3.9 and 0.5 % of those added |
| A2 | by-name edges it takes away that the checker confirms, ≤ 1 % | 0.34 %, 0.05 %, 0 % |
| A3 | sites that gain the checker's declaration against those that lose it, ≥ 20 to 1 | ghost 1,140 to 51 (38 to 1 with the pairs), grafana 4,481 to 13, mattermost 527 to 0 |
| A4 | changed sites no change in the type answered explains, ≤ 0.1 % | ghost 0 of 12,021, mattermost 0 of 8,575, grafana 10 of 20,367: a chain over lines whose edge keeps its target and gains `receiver-type`. It detects changes with no type behind them; the type's correctness is A1 to A3 and the sample |
| A5 | `CALLS` of the repo, -15 to +2 % | -4.9 % (240,635), -3.6 % (570,261), -1.6 % (297,862) |
| A6 | sites that lose the edge to the source of a package with no entry, 0 | 0 in the three (the prototype lost 6 in mattermost, 2 in ghost, 1 in grafana) |
| A7 | cost, up to +25 % of time and +5 % of memory | Ghost's dry-run, the median of five alternated with `main`'s, takes 62.2 s where `main` takes 50.8 s (+22.4 %; the rounds give +21.7 to +25.0 %, every run of the branch above every run of `main`) and peaks at 1,488 MiB where `main` peaks at 1,463 (+1.7 %); mattermost, the median of three, 98.6 s against 89.4 (+10.3 %) and 2,322 MiB against 2,302 (+0.9 %); grafana, the mean of two, 180.0 s against 165.9 (+8.5 %) and 4,251 MiB against 4,237 (+0.3 %): inside the +25 % of time and +5 % of memory the author accepted, nearly all of it the scope index's construction, which the per-file cache of H6 pays once per file that changes |
| A8 | the corpus and the hold-out | `0 repo(s) differ` in both |
| A9 | the table of cases, the mutants, the gates | green; 25 mutants, all die |

- **The proof:**
  - `test_ts_types.py`: the 30 typed cases and the package's class leave the strict xfail, and a test now checks that the
    extraction records why each of the unknown ones has no type. `test_ts_local_packages.py` (13 cases, 26 tests): a package with
    and without an entry, in a workspace and in a `file:` dependency, a package of npm, and a class whose base is one,
    inside it, outside it, two levels down, with its own method and with a package's, with another base beside it and
    through an `export *`, each checked against the checker. `test_ts_narrowing.py` (8 cases, 20 tests): a value a function
    tests with `instanceof`, as a parameter, a member, a field and a member of the one narrowed, and a value it does not
    test, one it tests under another name or in another function.
    `test_ts_workspaces.py`: the `file:`, `link:` and `portal:` dependencies, an alias's name, a tarball and a folder
    with no manifest (which link nothing), a manifest below another, with the links a manager makes and with the host that
    emulates them.
  - 25 mutants, each rule broken once: `call_receiver` answers none, no index, the flag of JS loose (which only the
    recorded reason shows), an absent package as one of npm, a present one as absent, the flag dropped, any package absent,
    an absent package given no edge by name, each of the three prefixes and the dev and optional sections, the shallowest
    manifest first, a spec that names no package of the repo, an absent base counted as external, none by name, only a
    class's own bases read, an absent base that gives way to another base, a star export that does not carry the
    absent package, and the dependency that outranks the member, a test that reaches beyond its function, one that matches a longer name, one
    that matches no member of the value, and none at all. All die: the last by a test of the choice, since the
    managers leave it undefined and the checker cannot judge it.
  - Against the checker, ghost, grafana and mattermost: the sample of 30 sites of the two classes the plan names,
    with the cause of each read at the source. The 30 by-name edges taken where the checker is silent are, in mattermost, a
    receiver typed to a package (`react`, `@testing-library/user-event`, `node:fs`, `@playwright/test`: 30 of 30); in
    ghost, 25 a package, 3 a class that extends one (`EventEmitter`, `lexical`'s `TextNode`), 1 an interface whose bases
    are a package of npm and an alias, and 1 a class a factory makes (TD-058); in grafana, 22 a package, 7 a class that
    extends `SceneObjectBase` (`this.setState`) and 1 a cast to a package's class. The homonyms dropped are right in 29
    of ghost's 30 and in all the others; the one that is not is the factory's class, where the method the factory
    declares was one of the candidates by name and is now reached by none. The typed edges the checker places elsewhere are, in ghost, 30 of 30 one thing (TD-061): the checker names the
    interface of a `.d.ts` beside the JS (`SettingsCache.get`) and the index the class that implements it
    (`CacheManager.get`, what runs); in grafana, 12 before the `instanceof` rule and 7 after it: 2 a class field typed as a function (TD-056), 3 a type
    parameter whose argument an alias gives (TD-057) and 2 an overloaded function's result (TD-060), and the 5 that were
    a receiver the function tests with `instanceof` go by name now; mattermost has none.
  - The corpus and the hold-out, the gates and the shape: the corpus and the hold-out give `0 repo(s) differ` against #83's runs, the gates pass (precision, no win lost, the hold-out untouched, the micro graph judged under `graph-change`), and the shape against `main` finds nothing new or worse over a target. The conventions and the module resolution: with the reference convention and the probe of #82, the violations, the modules, what they provide and require, and the packages of ghost, umbraco and grafana are the same, record by record, and so are mattermost's but for the package its `file:` dependency links, which the micro set shows removed. Over mattermost and grafana (94,493 imports) `checks/ts_modules.py` gives `same` 92,965 where `main` gives 92,963, the packages of the repo's workspace that neither resolves 1,461 where `main` gives 1,463, and no other kind changes.
  - Micro: ten repos differ, in `CALLS`. 22,247 edges go and 9,854 come in ghost, 34,825 and 13,536 in grafana,
    18,001 and 13,878 in umbraco, 10,841 and 5,901 in mattermost, 8,216 and 3,461 in outline, 391 and 12 in vikunja, 290
    and 27 in dispatch, 165 and 101 in gitea, 125 and 89 in netbox, 11 and 11 in btcpayserver; jellyfin and eshop are
    identical. Mattermost also has two `IMPORTS` that change from a package to a file (the end-to-end configs'
    `@mattermost/eslint-plugin`, a `file:` dependency) and loses that package.
- **What differs from the plan and from the measure before it.** The criterion's A1 was written with `.d.ts` pairs as
  one declaration, after the research found a ghost figure of 88 % by the strict count; on the head the strict count is
  97.1 % and the pair changes it by 0.2 points. The checker script that anchored A2 hid 11,145 of ghost's 15,092 edges as
  "no site" by comparing a path with its extension to one without. The "1,241 sites" the plan cited for the packages with
  no entry does not reproduce on the current `main`. A `file:` dependency is linked under its own name, as the managers
  do, where the plan said a folder whose manifest names the dependency. The by-name layer that is left is the least precise:
  `-ambiguous` is 12.8 to 20 % of what it gives, and `impact_of` discounts only that. A review by three agents that
  did not write the change (correctness against the checker, the repo's rules, the losses), with a second reader for
  each blocking objection, found: the receiver the flow narrows, which goes by name when its function tests it with `instanceof` and is TD-059
  for a type guard, and the overloaded result and the module beside a declaration file, which the sample had explained
  away and which have a debt and a case each; a class with
  another base beside the absent package's, and a star export of it, which lost the by-name edge to its source and are
  fixed with a case each; A1 counted only the edges the checker names a declaration for, which it now says, with the
  `inherited` ones judged by their owner; the 19th mutant, now pinned by a test; a docstring of `member_by_name` that
  was false for Python; and a project name of the live install in two lines of the docs, now left out.

Next, the last PR of the change of behavior (H5-D51: the scanner reads a client by the type its receiver declares).

## Decisions made (2026-10-18, by the author)

- **H5-D1, the order: everything before SCIP.** Revised the same day: the author wanted to put an end to H2 before
  H5.
  1. close the whole of F1.14, in the order recorded in it: item 2 (Go), item 7's reassigned router, item 5 (the
     model: the same route in two apps), item 3 (Python client wrapper, fixture only), item 4 (TS/JS, all of it) and
     the new hold-out, measured once. What it shows becomes a separate handoff, without reopening F1.14. The code of
     those items meets the targets from the start (H5-D3). *Done on 2026-10-18, without the new hold-out, which went
     to step 4 (H2-D21);*
  2. H4 phase 0a (recycling the working docs). *Done on 2026-10-19 (PR #6);*
  3. do H5, which absorbs the refactoring part of item 7 (the catalog and the `built_bundle` thresholds). The regression
     net is the corpus (`2026-10-18-v2-baseline-28`; `-29` since Go's change of behavior, H5-D12) and the 3-repo
     hold-out (`2026-10-18-v2-holdout-26`), identical at every step;
  4. the new hold-out, measured once with H5's code and with the commit before it, and the handoff of what it shows,
     already in the recognizer format. Any difference between the two commits is an H5 regression, which is fixed
     first;
  5. only then SCIP (F1.1/F1.2).

  P2 (the indexer in its own repo) also comes before SCIP, after H5, to take the already clean code. Its
  position was set by H6-D1: after H6 is plugged in and the new hold-out.
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
  things stay out, now debts (`docs/tech-debt.md`, TD-003, TD-004, TD-007 to TD-009): a `foreach`, `out var` or pattern
  variable, a lambda parameter, the arguments' types between overloads of one arity, a member of a package's type, and
  an extension of a type outside the repo on a type with a base outside it.
- **H5-D17 (2026-10-22), what a name means in C# goes in a `fix(csharp)` PR of its own, right after C#'s change of
  behavior.** The lookup counts a file's namespace only when it is file-scoped (`namespace X;`). In `namespace X { }`,
  a type of `X` loses to a homonym that a `using` shows: btcpay's `result.StoreData` reads as
  `BTCPayServer.Client.Models.StoreData`. C# looks in the enclosing namespaces before the `using`s. The same judgment
  found a second case: a capitalized name that is a member the caller's type inherits from a base of the repo is read
  as a static access to a homonym type. In elsa's features, `Module.UseWorkflowManagement(..)` is `FeatureBase.Module`,
  an `IModule`. `main` has no edge there either.

  Widened on 2026-10-23, by the author: what the PR's judgment found of the same kind goes in it, even if the scope
  grows, and what does not is recorded in detail. In: the namespaces around the code, a type nested in another, the
  global namespace from its own project, `global using`, a type parameter's constraint and type argument, a method's
  result with its type arguments, an array, an extension block and a call with no receiver. Out: thirteen gaps, now
  debts (TD-010 to TD-022).
- **H5-D18 (2026-10-26), a C# call that only the repo's extension methods can serve reaches one only where C# can
  bind it.** A call written with type arguments needs a method that declares type parameters. A receiver whose
  type, outside the repo, ends its chain takes no extension of a type of the repo, read in the extension's file by
  C#'s scopes and arity. Dropping those may only take targets away. It fixes the wrong edge PR #27 exposed. On 2026-10-27 the author decided its acceptance (`docs/decisions.md`, H5-D18 and H7-D6). Merged as PR #30.
- **H5-D19 (2026-10-28), step 5 goes on with Python, then TS, before the `fix(csharp)` PRs, and each language's
  probe comes first.** The language's `<lang>_answers.py` (G1) goes in a `chore(scripts)` PR of its own, before its
  refactor. The `fix(csharp)` PRs of the debts due before F1.2 come before F1.2, in the order the author picks. F1.2
  comes after H6, the new hold-out and P2, so those debts do not hold the refactor, and with the probe first the
  language's first judgment already attributes each changed site. Amended by H5-D21: one probe for every language.
- **H5-D20 (2026-10-28), step 6 goes in the portfolio's order: C#, Go, Python, TS.** The steps table and ADR-006 had
  "from the worst to the smallest" (TS before Python), against the portfolio priority the constraints give step 6. The
  same order as step 5's.
- **H5-D21 (2026-10-28), the per-site attribution has one probe for every language, read from each tree's own
  extraction.** `answers.py` reads the receiver's type from each call the extractor records (`CallInfo.receiver_type`),
  so the sites and the types are the ones the tree's resolver reads, whatever the language does inside, and a refactor
  may change the language's typing hook without breaking it. `attribution.sh LANG` replaces Go's probe and runner; on
  Go's change of local typing (`52b1e1b` to `1d56070`) it gives the same table and samples. It amends H5-D19: a fact a
  language's cases need goes into the probe, in a `chore(scripts)` PR before the language's refactor.
- **H5-D22 (2026-10-28), Python's step 5 separates scoping from typing.** A table of cases (`self`, `x = C()`, an
  annotated parameter, a closure) would mix which binding a name refers to with what type that binding declares, and
  the core's generic scopes already get the first wrong in Python: they bind a comprehension's variable to an
  assignment outside it. So:
  - Python's scoping (the function scope, a class body that does not enclose its methods, comprehensions, `global` and
    `nonlocal`) is modeled once in Python's per-file index, and the resolver and the scanner share it.
  - It is proven against CPython's `symtable` over every Python file of the corpus, an oracle kept in the checks
    (ADR-002). Comprehensions, which CPython 3.12 inlines (PEP 709), are checked apart.
  - Types come from a table of declaration forms on any binding: an annotation (`C | None`, `Optional[C]` and `"C"`
    read as `C`; containers and unions of several types do not), a call of a class, a function's declared result,
    the import of a repo class or module.
  - Bindings that disagree, and an external base ahead in the MRO, give `Unknown` with its reason.
  - Modules and classes are both namespaces, through one hook of the core.

  It goes in three PRs:
  1. the case table, with guards and strict xfails, each case's method the one CPython runs (#42);
  2. the refactor, with the graph identical: the scope index, checked against `symtable` on the table's scope traps
     and over every Python file of the corpus; Python in `checks/dump.py`; the `TypeIndex` and the hook. It goes in
     two PRs (H5-D24);
  3. the change of behavior, judged with `attribution.sh python`, which reports Python's ambiguous share and the
     reasons of `Unknown` (H5-D23). Of the `CALLS` made in Python files on `main`'s tree of 2026-10-28, the resolver
     found among several homonyms 65.6 % of the edges and 40.4 % of the sites in `dispatch`, and 63.1 % and 38.2 % in
     `netbox`.
- **H5-D23 (2026-10-28), what the per-site attribution reports for Python's change of behavior.** The eighth resume
  run found that H5-D22's third PR promised the ambiguous share and the reasons of `Unknown`, and the probe reported
  neither.
  - The ambiguous share comes from the edges' strategies, so `attribution.py` reports it for every language, in a
    `chore(scripts)` PR before Python's refactor (#43): of the language's files, the share of the edges and of the
    sites found among several homonyms, beside the edges by strategy.
  - The reason of an `Unknown` travels in the contract that carries the type: the refactor puts it beside
    `CallInfo.receiver_type`, and `answers.py` reads it as it reads the type. Read from Python's own typing, it would
    couple the probe to it, which H5-D21 removed.
- **H5-D24 (2026-10-28), Python's refactor goes in two PRs.** The scope index carries the step's largest risk and has
  an oracle of its own, CPython's `symtable`; joined to the types, it made one PR of two proofs.
  1. The scope index (#44), in `languages/python/scope_build.py` (what each statement binds, and where) and
     `scopes.py` (what a name refers to). `checks/python_scopes.py` compares it with `symtable` over every Python file
     of the corpus: of 7,124, CPython 3.12 compiles 7,114, and every name of every scope is classified the same. The
     ten others are written in Python 3.14's syntax (`except A, B:`). CPython 3.12 inlines list, set and dict
     comprehensions (PEP 709), so the check gives symtable each as the generator expression whose rules it keeps.
     Where a file defers annotations (`from __future__ import annotations`), an annotation's names read nothing, as
     in the compiler, and still know their scope. Nothing in production reads the index yet.
  2. The types (#45):
     - the core builds a language's per-file index once and hands it to the hooks that read one file
       (`LanguageSupport.file_index`); Python's is its scopes, and it lives only while its file is extracted: kept
       beside the tree, it cost netbox's dry-run about 270 MiB of peak memory, and nothing read it after;
     - Python's declaration forms (`forms.py`, how a type is written; `declared.py`, what a binding declares;
       `receivers.py`, a call's receiver), its type facts (`type_facts.py`, each module's and class's names) and its
       `TypeIndex` (`type_index.py`): modules and classes are namespaces, and a class's MRO is C3's, read up to its
       first base outside the repo;
     - the resolver's hooks, and the core's hook for a member's name (`member_name`: `path:function` beside
       `path:Class.method`);
     - the reason of an `Unknown` beside the type in `CallInfo` (`receiver_unknown`, H5-D23), which `answers.py`
       writes and `attribution.py` reports by reason.

     Python's `call_receiver` still answers nothing, so the graph stays identical.
- **H5-D25 (2026-10-28), Python's case table counts an `inherited` edge as no method's.** With the receivers read by the
  types, a call whose method neither its class nor a base of the repo ahead of one outside it declares gets, as in Go
  and C#, an `inherited` edge to the type. In `C(Thread, Base)`, CPython runs `Thread.run` for `self.run()`; leaving the
  receiver untyped would find `Base.run` by name again. The table's guards count only the edges that reach a method by
  type.
- **H5-D26 (2026-10-29), a Python call of a name outside the repo stays an instance of it.** The judgment of
  Python's change of behavior found that the type index takes the result of a call of a function outside the
  repo for an instance of the function: `get_object_or_404(Token, ..)` is not a `Token` to it, so about 40 sites
  of netbox lose what the guess by name found. Only the package's code tells a class from a function. The author
  keeps the rule, which removes 454 guesses by name on the four repos judged, and registers the loss as TD-025,
  due in F1.2.
- **H5-D27 (2026-10-29), a `CALLS` edge is the declaration the receiver's type gives, in every language.** A typed
  `self.m()` reaches the method its class's MRO declares, as C# and Go already do and SCIP's references will; a
  subclass's override is reached in the query. Each language's type index writes `EXTENDS`, and `who_calls` and
  `impact_of` expand a method through the methods it overrides and those that override it, marked as a dispatch that
  may happen (F1.16). Edges to every override would make one fact of a call into many and mix "calls" with "may
  call".

## Pitfalls

- **`python -m` inside the image runs the image's code.** Its `WORKDIR` is `/app`, where the package is. With `-m`
  (`-m cProfile`, `-m aidd_indexer.cli`), the working directory enters `sys.path` before `PYTHONPATH`, and the code
  mounted at `/src` does not run. Use `-w /src`, and check the version or the package path on the log's first line.
  That cost a dry-run in PR #5's validation and two profiles in step 3. `corpus.sh` and `test.sh` do not have the
  problem: the first runs by script path and the second already uses `-w /src`.
- **tree-sitter node identity.** `node.child_by_field_name(..)` creates a new object on every call, so `a is b` is
  always false. Compare by `node.id`, which holds within one tree. That cost a debugging session in F1.14 item 2.
- **`monkeypatch.setattr` on a language object leaves a method behind.** Undoing a patch of a hook of
  `languages.by_id(..)` puts the old bound method back as the object's own attribute, so a later patch of the class
  (`PythonSupport.call_receiver`) no longer reaches the registry's object. Patch the object, as the tests do. That cost
  a run of the whole suite in Python's types (#45).
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
- **Each merge that changes `indexer/aidd_indexer` is reinstalled and validated before the next.** Otherwise the next
  PR's `validate.sh before` refuses, since the install is not `main`'s, and one pair has to cover every PR since.
- **An IDE watching the repo builds a C# project that appears under it**, writing `obj/` in place: a fixture's in a
  copy of `indexer/`, a snapshot's under `.local/`. `validate.sh` copies only the package, and discovery skips `obj/`.
  The IDE also writes the `obj/` of a project it loaded back to that project's path once the path is deleted, so a
  failed `before` deleted and taken again found its snapshot folders already there, with only that output in them.
  `dryrun-live.sh` now copies the snapshots to a folder no earlier run used and checks each copy against its sha.

## Constraints and conventions

H2's:
- **Commits:** one conventional line, with no body and no `Co-Authored-By`.
- **Language:** everything in the repo is in English: code, commits, PRs and docs (H4-D1).
- **Privacy:** no tenant or private project name in the docs, the code, the tests or the fixtures.
- **Parser:** an LLM is never the parser.
- **Design:** by contracts, boundaries and proof (`docs/design.md`). Every plan has a section of that name.
- **Temporary files:** in the session's scratchpad.
- **Corpus repos:** do not run Python inside the clones; use `python -I`, or Docker with the guide's mounts.
- **Portfolio priority:** .NET first, then Go and Python, then TS. It sets the order of step 6 (H5-D20).

## Expected deliverables

- The code in the target architecture's modules, with the corpus and the hold-out identical to the starting
  baseline, but for step 5's judged changes (H5-D12).
- The new unit tests (`paths`, `mounts`, `scopes`, `expr`, one per recognizer) and the MCP's integration test against
  Neo4j.
- In CI, the shape ratchet (H5-D9), and the report of `ruff C901` (`max-complexity = 9`) and of modules above 300
  lines at zero but for `cli.py` (H5-D6) and what H5-D43 accepts. Full blocking is the author's call (H5-D3).
- In `corpus-report.md`, an "H5" section with times before and after, the profiles and the shape metrics before and
  after.
- ADR-003 updated, or a new ADR, and `indexer-evolution.md` (§2, §5, §7) describing the new code.
- In the ROADMAP: the H5 item checked, and SCIP (F1.1/F1.2) with the `TypeIndex` seam ready.
