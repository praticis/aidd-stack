# Handoff H5 — Refactor the indexer before SCIP

> Paste this file (or ask for `docs/handoffs/H5-indexer-refactor.md` to be read) at the start of a new chat. Before
> anything else, the chat should read `docs/indexer/README.md` and the documents of its reading order, in that order:
> `AGENTS.md`, this file's "State", the method, the judgment and the scripts. Then, for the refactor's context:
> - `docs/ROADMAP.md`: "Where we are", "Principles", F1.1, F1.2 and F1.13;
> - ADRs 002 to 006;
> - `docs/indexer-evolution.md`: §2 Code map, §5 How to measure and §8 the boundary with SCIP;
> - `docs/corpus-report.md`: the method, where the extractor stands and the baselines table (the current one is
>   `2026-10-18-v2-baseline-29`).

## State (2026-11-09)

**Merged.** Steps 0–2, 4 and 7–9, and parts of 3 and 10 (PR #7, a checkpoint, H5-D8), and step 5 in the four languages (the table below); F1.16 is closed (`feat(mcp)` #63, H5-D35). Each merge and its live validation are in `docs/history.md`; the results are in each PR's body and in `corpus-report.md`.

**Step 5 is closed for Go, C#, Python and TS, with debts.** The defects it leaves are `docs/tech-debt.md` (TD-001 to TD-069), each with a
strict xfail test; those due before F1.2 are `fix(csharp)` PRs (19), `fix(typescript)` PRs (8: TD-052, TD-053, TD-055, TD-056, TD-058,
TD-061, TD-062 and TD-063), `fix(go)` (TD-029, TD-065 and TD-066), `fix(resolve)` (TD-064), `fix(python)` (TD-069) and `fix(conventions)` (TD-048); TD-057, TD-059 and TD-060 are due in F1.2 (H5-D52). Python's leaves TD-025 (H5-D26), due in F1.2, and TD-026 (H5-D28), due in step 6. The judgment of H5-D18 was the review of an agent that
did not write it (H7-D6): a person's check is not feasible today. Steps 6 and 12 are open for C# as for every language,
and two debts of the core are due in them: TD-023, the syntax of each language it holds, and TD-024 (step 6), the
names of frameworks and client libraries it holds:

| Language | Step 5 (`TypeIndex`) | Step 6 (recognizers, catalog) | Step 12: the largest module over 300 lines |
|---|---|---|---|
| C# | merged (#23, #25, #27, #30) | not started; `_controller` and `_invocation` first | `languages/csharp/http.py`, 1401 |
| Go | merged (#17, #20) | not started; `_call` | `languages/go/http.py`, 730 |
| Python | merged (#42, #44, #45, #47) | not started | `languages/python/http.py`, 363 |
| TS | merged, in ten PRs (H5-D36, H5-D37, H5-D39, H5-D40, H5-D41, H5-D45, H5-D46, H5-D47, H5-D48) and three more that end it (H5-D49 to H5-D51); the probe in #65, the case table in #66, the scope index in #67, the types in #68, the hierarchy in #69, the module resolution in #72, the CommonJS exports in #73, the declaration files in #79, the workspace packages in #80, the class members and the folder entries in #81, the output of a referenced project in #82, the function members in #83, the receiver's type in #84, the scanner's client type in #85 | not started; `_read_call` | `languages/typescript/http.py`, 1004 |

The counts are `shape.py`'s on 2026-11-09. The core has modules over 300 lines too: `http_base.py` and `http_expr.py`
go with step 6, and `extract.py` with step 12's last PR (H5-D44). Step 12's other PRs (#74, #75, #77, #78) brought the
conventions, the corpus runner, the MCP's tool groups and the refresher to the targets, but for what H5-D43 accepts.

**Next.**
1. The `fix(...)` PRs of the debts due before F1.2: `fix(csharp)` (H5-D19; 17 debts), `fix(typescript)` (8 debts, after a
   refactor of TS's scope builder that returns the cost step 5 added to the scanner), `fix(go)` (TD-029) and `fix(conventions)`
   (TD-048). TS's step 5 is closed (#65 to #85, H5-D36 to H5-D51; the PR-by-PR record is in "TS's step 5" below and in
   `docs/history.md`).
2. Step 6 (recognizers and the catalog, with the core's HTTP modules), step 12's last PR (the pipeline's `extract` and
   `resolve`, unblocked since TS's step 5 closed: H5-D44), the rest of step 10, step 11 (docs).
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
  behavior needs the review of an agent that did not write it (H8: `indexer/scripts/review/independent-review.js`, and
  `research-round.js` for its Tier 2; advisory, never a gate).
- Live evidence is private, local and has no backup: `.local/indexer/live/` (its README has the layout and the
  integrity checks). Only the PR in flight's "before" picture cannot be regenerated; `merged/` holds the last
  validated PR's pair.

## Context in one paragraph

H2 and F1.14 took the HTTP extractor from almost nothing to 98–100 % precision against the expected lists and, apart from
Python (28 % of its routes, 98.6 % without Django's, and 2 of 3 calls), 92–99 % recall on the 55-repo corpus
(`docs/corpus-report.md`). The method was one rule per increment, each with a fixture and a judged corpus run. The method worked. What
it did not do was reorganize the code between one rule and the next. Each rule went in where it fit: one more `if`
in the method that already handled calls, one more field in `PackageContext`, one more fact with a text key. The
result measures well and reads badly. H5 is a refactor **with no behavior change**: the corpus and the hold-out must
come out identical to the starting baseline, step by step. The one exception is step 5's changes of behavior, each
judged at the source and closed with a new baseline (H5-D10, H5-D12). It prepares three things: SCIP (a single point
where the type of an expression is asked), scale (F1.13) and maintenance (rules as units that are tested on their
own).

## Diagnosis (measured on 2026-10-18, over `713fec8` + F1.14 item 2 in progress)

**Mixed responsibilities.**

1. **`core/` knows the languages, which ADR-003 forbids.** ADR-003 says the core "never looks at the language id".
   (built: step 4)
2. **Two type systems in parallel.** The micro resolver (`languages/*/symbols.py`, with `file_facts` and
   `ResolveContext.facts`) and the HTTP scanners each answer, in their own way, "what is the type of this value":
   (built: step 5)
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
   (built: step 7)
6. **The path-matching rule exists in more than one place.** The linker compares an ASP.NET route case-insensitively,
   and the MCP only started doing the same today (`98b8368`). `who_consumes` still computes the key with a regex of
   its own (`mcp/server.py:608`), not with `paths.normalize_path` + `path_key`, so an asked `:id` is not normalized.
   (built: step 8)
7. **There is an import cycle.** `core/http_base` imports `languages/base`, which goes through
   `languages/__init__`, which imports every language, which import `core/http_base`. Importing
   `aidd_indexer.core.http_base` first fails. It only works because the usual import order hides the cycle.
   (built: step 2)

**Scale (F1.13).** `extract_http` receives all the repo's extractors with their trees alive, because the two passes
(constants, then scanners) need them. grafana dies of memory at 7.7 GB. The refactor does not solve F1.13, but it must
not close the door: the second pass has to be able to re-parse a file, instead of requiring the stored tree.

**What is good and should stay.**
- The `core/integrations.py` orchestrator is lean.
- The mount graph (`core/http_mounts.py`) is small and general.
- The F1.13 rule holds: a scanner never reads another file's tree; what crosses files goes through facts and
  `compose`.
- The `except Exception` blocks are deliberate boundaries, per file and per repo, and they are commented.
- The rule → fixture → judged corpus cycle is the project's best asset, and H5 uses it as its net.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Diagnosis (measured on 2026-10-18, over `713fec8` + F1.14 item 2 in progress)"._

## Goal

At the end of H5:
- the corpus and the hold-out are **identical** to the starting baseline, but for step 5's judged changes (H5-D12);
- extracting the whole corpus takes **≤ 60 %** of today's time (870 s of the 1,449 s that step 0 measured);
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
   (built: step 2)
2. **`FileIndex`, one pass per file.** It is built once, right after the parse, and shared by the symbol extractor,
   the constants collector and the scanner. It has:
   - the nodes by type;
   - the functions by id, with each one's parent;
   - the declarations and assignments per scope, which today are `Scopes._assignments` and `_declared_type`;
   - the identifiers by name and scope;
   - the calls.

   The ad hoc walks (`function_of`, `_idents`, `_param_values`, `walk(scope)`) start consulting it.
3. **A type service** (`TypeIndex`, SCIP's seam). The questions are:
   (built: step 5)
4. **Package facts per language.** The core's `PackageContext` keeps what is general: path constants, constant
   pieces, `env_hints` and functions by name. Each language registers its own collector
   (`LanguageSupport.collect_package_facts`) and its own typed facts class: TS's clients with a base, Python's router
   classes, Go's passthrough and verb lists. The code of `_ts_client`, `_py_class`, `_go_struct`, `url.URL` and
   grpc-gateway moves to `languages/<lang>/`.
   (built: step 4)
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
   (built: step 7)
8. **One path-matching rule.** A module (`core/matching.py`) with `path_key` and the case-sensitive or insensitive
   comparison per framework. The linker, the MCP and the corpus scorer use it.
   (built: step 8)
9. **The MCP split.**
   (built: step 8)
10. **A shorter corpus loop.**
   (built: step 9)
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

Neither side reads a type assertion (`h := x.(*T)`), a type switch, a `range` variable or a package-level variable.
Those are left out of step 5: each would be a rule of its own, with its own cycle, and here every change has to come
from a case of the table.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Step 5: one type answer, without losing what either side answers (H5-D10)"._

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

- **What stays lost** is what H5-D15 leaves out. A guess by name on a receiver whose declared type is an interface
  goes (mattermost's `store.Store`, kratos's `persistence.Persister`: about 750 edges), as `main` already does for
  the same variables nested less deep. A variable of a form neither side reads (`range`, a type switch, an
  assertion) loses what `main` read from an out-of-scope declaration of the same name (about 60 sites). In a
  function the grammar does not parse (grafana's Go 1.26 `new(expr)`), scopes are what error recovery left. A
  generic's inferred type (`u := AssertExistsAndLoadBean(t, &User{})`) is SCIP's.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Go's change of behavior"._

**C#**, in `indexer/tests/test_cs_types.py`. Where a side was wrong before the change, its column says what it gave.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Step 5: one type answer, without losing what either side answers (H5-D10)"._

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

- **What stays lost:** 188 edges to extension methods that `main` had. Most were guesses that the receiver's type
  now proves wrong, as above. The rest is what H5-D16 leaves out, now debts (`docs/tech-debt.md`): the arguments' types
  between overloads (TD-004), a `foreach` variable and a lambda parameter (TD-007, TD-008), a member of a package's type
  (TD-003), and a type with a base outside the repo (TD-009).

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "C#'s change of behavior"._

### What a name means in C# (H5-D17)

C#'s change of behavior gave one answer to a name's type, but the answer still read a name in ways C# does not. A
type's simple name skipped a block namespace and the namespaces around the code, a capitalized member was read as a
homonym type, and a type parameter was read as a type outside the repo. The fix reads each as C# does; the rules are the docstring of `indexer/tests/test_cs_names.py`, with
their cases.

- **What stays out:** thirteen gaps, now debts (`docs/tech-debt.md`, TD-010 to TD-022), each with a strict xfail test.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "What a name means in C# (H5-D17)"._

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

The scope index came in the refactor's first PR (#44, H5-D24), and the test that waited for it is now the check
itself: the index classifies every name of every case as `symtable` does. The types came in the second (#45): read by
them (`test_python_type_index.py`), every case gets its answer, and each `unknown` or `external` case the reason it
names. The table's guards count an `inherited` edge as no method's (H5-D25).

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Python's case table (H5-D22)"._

### Python's change of behavior

One answer, with Python's own rule: **a name is the binding CPython's scopes give it, and its type is the one that
binding declares.** An annotation (`C | None`, `Optional[C]` and `"C"` read as `C`), a call of a class, a function's
declared result, `self` and `cls`, `super()`, the import of a repo class or module. Across files, the
`PythonTypeIndex` reads modules and classes as namespaces, and a class's MRO as C3's up to its first base outside the
repo (`languages/python/mro.py`).

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

- **What the judgment leaves open:**
  - netbox's absolute imports resolved to nothing, so most of its classes had an MRO the index could not see. They
    resolve since H5-D28, judged in the next section;
  - a typed `self.m()` reaches the method its class's MRO gives, not a subclass's override, as in C# and Go. In
    netbox, 67 narrowed sites lose an override the guess by name found, 46 of them `_get_queryset`. The query reaches
    them (H5-D27, F1.16);
  - a class defined in a function is not seen, so one of several bases there could reorder an MRO the index reads.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Python's change of behavior"._

### Where a Python absolute import is looked for (H5-D28)

The judgment of Python's change of behavior found that none of netbox's 7,661 absolute imports resolved. netbox runs
from `netbox/`, where its `manage.py` is, and the import resolver tried only the root of the file's module, the repo's
root and `src/` (#46). The core took netbox's own classes for a package's and skipped the calls on them.

- **One fix led to another.** With the imports resolved, a method that a class of the repo declares past a base outside
  the repo got no edge at all:
  - `_inherited` skips a call inside its own type;
  - `member_by_name` refused the name because of the outside base.

  That base may give the method first, so the answer is `Unknown`, and the call goes by name
  (`PythonTypeIndex.declared_past_outside`).

- **What stays open:**
  - a root only configuration gives (`PYTHONPATH`, pytest's `pythonpath`, setuptools' `package-dir`,
    `sys.path.insert`): about 50 imports in the corpus. When a repo of the portfolio needs one, the options are to read
    the declarative configuration as data, or to let a person declare the repo's roots in `atlas.yaml`;
  - a project inside a directory a regular package holds: aiohttp-demos' `demos/moderator_bot`, 4 imports. The
    language cannot tell it from a namespace portion, so it needs roots in `atlas.yaml`, or SCIP in the installed
    environment;
  - a name only a star import binds: followed since #51, in the next section.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Where a Python absolute import is looked for (H5-D28)"._

### What a Python star import binds

A name that only a star import could bind was `Unknown`, so the call went by name. A class whose base came through a
star import had an MRO the index could not see. netbox imports its models through `from dcim.models import *`, and
`dcim/models/__init__.py` re-exports them through `from .sites import *`: 9,108 receivers of netbox were such names.

- **What stays `Unknown`:**
  - an `__all__` the index does not read: any other binding of it, or any read of it;
  - a star import of a module outside the repo;
  - a name a function binds as `global` that a star import binds too, which no position orders.

- **What stays open:**
  - a call with no receiver of a name a star import binds (`CustomField(..)`, `post_data(..)`) still goes by name;
  - a package with no `__all__` also binds the submodules its own imports load, which the index does not model;
  - the graph writer merged `CALLS` edges of one caller, target and line that differ in `strategy` or `method` (3,088
    groups in the micro set): the `fix(graph)` of the next section.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "What a Python star import binds"._

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

- **What stays open:**
  - the graph keeps no column, so the calls of one target on one line stay one edge;
  - TD-027, due in a `fix(csharp)` PR before F1.2: the implementation an interface receiver reaches gets no edge when
    a base outside the repo gives it the method. The lookup on the implementation found the interface's method again,
    the 2,596 edges of umbraco above among them; the answer is an `inherited-impl` edge to it, with `method`.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "One `CALLS` edge per caller, callee, line and method"._

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

- **What stays open:**
  - TD-028, due in F1.2: a class a function holds has no name in the index, so a call on `self` in its methods reaches
    no wrapper of it, where `main` found it by the class's name. No site in the corpus;
  - a call on a function through its module (`api.get_json("/x")`) reaches no wrapper, as on `main`.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "A client wrapper's receiver, from the type index"._

### TS's step 5 (H5-D36)

| PR | Decision | Debts (+ the PR's proof found it, - its xfail goes, no sign: named) | One number: ghost's dry-run in s, `main` to the PR (median of three alternated with `main`'s) |
|---|---|---|---|
| #65 | H5-D36 | - | - |
| #66 | H5-D36 | - | - |
| #67 | H5-D37 | - | 51,025 files compared with the binder |
| #68 | H5-D38 | - | 39.8 to 41.6 |
| #69 | H5-D39 | +TD-038, +TD-039 | 42.1 to 42.7 |
| #72 | H5-D40 | +TD-041, +TD-042 | 54.8 to 54.5 |
| #73 | H5-D41 | TD-039, TD-043 | 59.4 to 60.5 |
| #79 | H5-D45 | +TD-049 | 45.0 to 44.9 |
| #80 | H5-D46 | -TD-042, +TD-050, TD-051 | 42.6 to 42.6 |
| #81 | H5-D47 | -TD-037, -TD-043, -TD-049 | 41.0 to 46.3 (13 % more) |
| #82 | H5-D48 | TD-052 | 47.1 to 47.0 |
| #83 | H5-D49 | +TD-053, +TD-054, +TD-055 | 46.7 to 48.5 (4 % more) |
| #84 | H5-D50 | +TD-056, +TD-057, +TD-058, +TD-059, +TD-060, +TD-061 | 50.8 to 62.2 (+22.4 %, median of five) |
| #85 | H5-D51 | +TD-062 | +9.6 to +11.8 % of the scanner's pass in ghost |

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

The table corrects two items H5-D36 listed as `Unknown`. A `let` takes its initializer's type in TS, so a second
assignment does not make it two types; what the checker does and a declaration does not is narrowing a union by
control flow. A parameter injected by token declares its type in its annotation; the token only decides which
implementation runs, which is a dispatch. A client library the scanner does not know (Angular's `HttpClient` under
another name than `http`) is the catalog's, step 6's (TD-024), not a type's.

The three ids share one index, since a `.ts` file imports from `.tsx` and `.js`. `languages/typescript/http.py` is over
the module target, so the new code goes into modules of its own. The probe reads the three ids together
(`answers.py typescript,tsx,javascript`), with `this`, the node that binds it at the use, and `closures`.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's step 5 (H5-D36)"._

#### TS's scope index (#67, H5-D37)

The refactor goes in two PRs, as Python's did. The first is the scope index: which declaration of the file each name
binds to, and which node binds each `this`. The core's scopes, which the scanner reads, look a name up in the function
around it and take the last assignment before the use, so a block that shadows a name, a `var` read before its
declaration and a `let` reassigned bind elsewhere in TS. Nothing in the extraction reads the index yet, so the graph is
identical.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's scope index (#67, H5-D37)"._

#### TS's types (#68, H5-D38)

The second PR is the types: TS's facts, one `TypeIndex` for the three ids, and the scanner's answers read through them.
TS's `call_receiver` still answers nothing, so the resolver asks none of the type hooks and the graph is identical.

- **What differs from the plan.** The facts tell a type parameter by the declarations around the name, without the
  scope index, which is built for a file only where a question needs it. `member_by_name` keeps the core's answer,
  since TS checks a call against its receiver's type; whether a method a JS prototype assignment adds needs it is the
  change of behavior's question.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's types (#68, H5-D38)"._

#### TS's hierarchy (#69, H5-D39)

The fifth PR writes TS's `EXTENDS`, `IMPLEMENTS` and `OVERRIDES`. Calls are still found by name, with the abstract
methods among their candidates now, since an abstract method is a symbol.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's hierarchy (#69, H5-D39)"._

#### TS's module resolution (#72, H5-D40)

- **Where it lives.** `languages/typescript/tsconfig.py` reads the repo's `tsconfig.json` and `jsconfig.json` files,
  with the comments and trailing commas TypeScript allows, once for each context that resolves an import: the resolver,
  the type index and the HTTP scanner's view each hold their own files, so a config is read from the repo's tree, as
  Go reads its `go.mod`. `modules.py` asks it first.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's module resolution (#72, H5-D40)"._

#### TS's CommonJS exports (#73, H5-D41)

- **Where it lives.** `languages/typescript/commonjs.py` reads what a module exports by assigning it, and the TS facts
  (`type_facts.py`) hold it: the module's own value under a name no name of a module can be, and each name it assigns
  beside the ones its `export` statements give. A value no name of the module holds, as `new S()` or an object
  literal's `d: new D()`, is held under the name its exports give it. The type index takes the own value for a whole
  module's import and for a default import; the receivers read `require("./m").a` as the facts do.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's CommonJS exports (#73, H5-D41)"._

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

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's declaration files (#79, H5-D45)"._

#### TS's workspace packages (#80, H5-D46)

- **Where it lives.** `languages/typescript/workspaces.py` (97 lines) reads the workspaces a repo declares, once for
  each context: every `package.json` above a file of the repo, since a manifest shares its folder's module with the
  first the folder has (grafana's root is a Go module), their `workspaces` and `pnpm-workspace.yaml` globs, and
  `member(file, name)`, the folder of the package a file sees under that name. `exports.py` (52 lines) gives the file a
  package's entry names for a subpath. `modules.py` asks them after the aliases and before the npm package, and
  `tsconfig.py` reads `customConditions`. `type_index.py` and the core do not change.
- **The rule.** The members, who sees them and how the entry is read are H5-D46's. Not adopted: a `lerna.json`, which
  the oracle cannot prove, and a `src/` for a build the clone lacks, which would be a guess: TD-050.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's workspace packages (#80, H5-D46)"._

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

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's class members and folder entries (#81, H5-D47)"._

#### TS's referenced projects (#82, H5-D48)

A prototype of the change of behavior (the resolver reading the receiver's type, in a copy outside the repo) showed what
it would leave without an edge: 1,241 sites of mattermost, grafana and ghost whose receiver comes from a package of the
repo's workspace with no build, TD-050. mattermost declares the build's output: `@mattermost/client` is `composite`, its
`outDir` is `./lib` and its `rootDir` `./src`, and the `tsconfig` of `channels` references it, so TypeScript reads
`lib/index.d.ts` as `src/index.ts`, built or not. The author asked for a search before taking the trade-off, which found
the compiler's rule and the configs that declare it, and moved the PR ahead of the change of behavior.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's referenced projects (#82, H5-D48)"._

#### TS's function members (#83, H5-D49)

With the resolver reading the receiver's type, a call `api.push(1)` on an `api: Api` goes to the member TypeScript
declares, and a member that is no symbol leaves the call with no edge. The prototype of the change of behavior found
that 47 % of the declarations the checker leads a call to in ghost, 39 % in grafana and 25 % in mattermost are no
symbol. A first reading took about 70 % of grafana's gap for interface members; measured by the form of the member's
type, the function types written in place are 36 % of it, 11 % of ghost's and 8 % of mattermost's, and the rest has a
number and a debt.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's function members (#83, H5-D49)"._

#### TS's resolver reads the receiver's type (#84, H5-D50)

The first of the two PRs of the change of behavior: a call on a receiver whose type the code declares reaches the
methods of that type and its bases, and no homonym. The prototype measured before #81 (60,824 sites judged) found the checker confirming 95 to
100 % of the typed edges and 0.1 % or less of the by-name edges they replace; this PR declared its acceptance criterion
before it measured, and a round of research (six investigations, a synthesis and a challenger that tried to refute it)
changed the criterion and the rule before the code was written.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's resolver reads the receiver's type (#84, H5-D50)"._

#### TS's scanner reads a client by the type its receiver declares (#85, H5-D51)

The last PR of the change of behavior and of TS's step 5: the HTTP scanner finds a client by the type the code declares
for its receiver, as the resolver finds a method by it (H5-D50). A receiver is a client where its name, a `new` of the
file or an import of a client library says so, as before, or where its declared type does: a class of the repo, whose
wrappers the call reaches, or a type of a client library that a request is made on (`CLIENT_TYPES`). The scanner asks
the index the resolver's question (`receiver_of`, then `typed`) in a module of its own, `client_types.py` (the mixin
`TsClientTypes`, which also builds the file's scope index for the scanner); `http.py` shrinks (1,005 to 1,004 lines),
`client_wrappers.py` shrinks (295 to 291) and `type_index.py` (300 lines) now says which name an import takes from a
package (`Outside.member`).

- **Debts.** TD-062, a receiver typed by an interface the repo declares reaches no wrapper (the scanner's lookups are by
  class, and the resolver's `-impl` dispatch, which needs the index to say which class runs behind the interface and what
  to do when two do, is a decision of the model), due in a `fix(typescript)` PR. The first design's other three are fixed.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "TS's scanner reads a client by the type its receiver declares (#85, H5-D51)"._

## Decisions made (2026-10-18, by the author)

The decisions of H5, H5-D1 on, are the rows of `docs/decisions.md`; this section held the first 27 of them, word for word.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Decisions made (2026-10-18, by the author)"._

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

- **Refactoring and changing a rule in the same commit** erases the net: "0 repos differ" stops proving anything.
- **A global group's own prefix is a fact of the router, not of the edge.** A group that other files name (a package
  variable, a returned router, a parameter) publishes its own prefix (`go.mount.own`), and `compose` puts it after
  the prefix of each chain that reaches the router. Hanging it on the edges of the file that defines it, as it was
  until 2026-10-18, lost the prefix when the reassignment (`router = router.WithPrefix("/x")`, `r = r.Group("/x")`)
  gave only an edge from the router to itself, and when another file mounted the router. The `route-patterns-go`
  fixture (`internal/reassigned/`) covers both cases.

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Pitfalls"._

## Constraints and conventions

- **Temporary files:** in the session's scratchpad.
- **Corpus repos:** do not run Python inside the clones; use `python -I`, or Docker with the guide's mounts.

The rules of commits, language, privacy and design are in `AGENTS.md`, "For contributors" and "Principles".

_The measures, the review and the per-commit list of this section are in git: `git show before-h5-condensation:docs/handoffs/H5-indexer-refactor.md`, section "Constraints and conventions"._

## Expected deliverables

- The code in the target architecture's modules, with the corpus and the hold-out identical to the starting
  baseline, but for step 5's judged changes (H5-D12).
  (open)
- The new unit tests (`paths`, `mounts`, `scopes`, `expr`, one per recognizer) and the MCP's integration test against
  Neo4j.
  (open)
- In CI, the shape ratchet (H5-D9), and the report of `ruff C901` (`max-complexity = 9`) and of modules above 300
  lines at zero but for `cli.py` (H5-D6) and what H5-D43 accepts. Full blocking is the author's call (H5-D3).
  (open)
- In `corpus-report.md`, an "H5" section with times before and after, the profiles and the shape metrics before and
  after.
  (open)
- ADR-003 updated, or a new ADR, and `indexer-evolution.md` (§2, §5, §7) describing the new code.
  (open)
- In the ROADMAP: the H5 item checked, and SCIP (F1.1/F1.2) with the `TypeIndex` seam ready.
  (open)
