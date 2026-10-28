# HTTP extractor — corpus report

This report gives the precision and recall of the HTTP integration extractor (`core/integrations.py` and
`languages/<lang>/http.py`) on a public corpus. The corpus has 55 repositories, 54 of them with an expected list,
and each is pinned to a commit in `CORPUS` of `indexer/scripts/http_corpus.py`.

Beside the corpus there is a hold-out: repositories the rules never saw, measured once (H2-D20). Its current set has
three repositories, in `HOLDOUT`.

What is where:

- **This report:** the method, where the extractor stands today, what is left with where each gap goes, and the list
  of baselines.
- **The narrative of each step:**
  - v1 and the cheap fixes, v2, each H2b step, the first hold-out, and each F1.14 increment with its judged diff;
  - it was cut from this file in the H4 recycling of 2026-10-19 and lives in git: `git show 1d73bb0:docs/corpus-report.md`.
- **The rules and the cycle of a change:** `docs/indexer-evolution.md` (§3 and §5).
- **The decisions behind the method:** `docs/decisions.md` (H2-D*).

## How it is measured

**Running it.** `indexer/scripts/corpus.sh` runs one container per repository, the largest first, each under a
memory cap. Then it writes one report: the diff against a baseline, and precision and recall against the expected
lists.

- The corpus against a baseline: `--baseline <run>`. The hold-out: `--holdout`.
- Clones and runs live outside the repository (H2-D3), in `~/.cache/aidd-corpus/{repos,runs}`.
- To rescore a saved run after editing expected lists: `http_corpus.py --reuse <run> --expected`. Never use it to
  measure a change to the extractor.

**Two measures per repository**, kept apart because they answer different questions:

1. **Precision from a seeded sample of what was extracted** (`checked`):
   - 20 routes and 20 calls per repository, drawn with `--sample 20 --seed <n>`;
   - each item is judged at its evidence line against what the application serves or requests;
   - this is precision over the whole repository.
2. **Precision and recall against an expected list** (`endpoints` and `calls`, with a `scope`):
   - the list is a committed spec checked against the code, or files read end to end within a scope fixed first
     (H2-D4, H2-D15);
   - only extracted items inside the scope count;
   - recall is measured only this way (H2-D6): sampling what was extracted never shows a miss.

**Judging rules** (`docs/decisions.md`):

- **Matching:**
  - by `(method, path_key)` over distinct pairs;
  - placeholder names do not matter, and ANY matches any method;
  - an ASP.NET route matches without case, as the linker links it.
- **A lost prefix:**
  - a route or call that lost a prefix the code holds is **wrong** (H2-D12);
  - a prefix from config or the environment belongs to the linker.
- **Calls** are expected only when their path is a literal or a template in the code (H2-D5).
- **What the graph receives** is what is measured, after `_dedupe` (H2-D13).
- **Precision before recall:**
  - a rule that raises recall and lowers precision somewhere does not go in (H2-D11);
  - an item that is wrong only by inheriting a defect already categorized counts, but does not block the rule
    (H2-D14).
- **One category per miss:** the most specific one (H2-D16).
- **Language:** an item counts in the language of its file (H2-D17).

**The hold-out** (H2-D20):

- its expected lists are written **before** the extractor runs on it;
- its sample is seeded and judged at the source;
- it is measured once, and no rule is tuned on it;
- a hold-out repository that F1.14 worked on became corpus.

The next hold-out is measured after the H5 refactor, on the H5 code and on the commit before it (H2-D21).

**Before a merge to `main`**, a change to the extractor is also checked on a live install:

- a dry-run of `main` and of the branch on each snapshot;
- a picture of the graph before and after the reinstall.

That is how PR #5 found its increment 12.

## Closing F1.14 and H2 (2026-10-18)

F1.14 took what H2b and its hold-out left to the extractor, in twelve increments. Items 1 to 6 each end with a rule
that has a fixture and a judged corpus, or with a limitation recorded in the guide. Of item 7, the gRPC custom verb
and the reassigned Go router are done. Its framework catalog as data and the `built_bundle` thresholds are
refactoring, so they go to H5 with the recognizers. Django stays out, because the portfolio is FastAPI and Flask.

The corpus grew from 42 repositories to 55, 54 with an expected list. The 13 hold-out repositories F1.14 worked on
became corpus, and the hold-out keeps three: Kavita, go-boilerplate and sftpgo. The final baseline is
`2026-10-18-v2-baseline-28`, with indexer 0.2.15.

**The new hold-out moves after H5.** F1.14 was to close with a new hold-out, measured once (H2-D20). On 2026-10-18
the author moved it to after the H5 refactor, as the first step of its own handoff:

- H5 changes no behavior, and the corpus stays identical at every step, so the number would be the same before
  or after;
- what the hold-out shows would be fixed after H5 anyway, and is then fixed in the refactored code;
- the measurement also runs the commit before H5, so any difference between the two is an H5 regression in code
  the corpus does not cover.

The cost is that a precision defect no one has seen yet stays in the extractor during H5. Until the new hold-out,
H5's regression net is the corpus and the three-repository hold-out.

### The hold-out's repositories, then and now

The 13 repositories as the hold-out measured them on 2026-10-17, against today. Some lists were corrected at the
source while F1.14 worked on them (H2-D15), so a few expected counts moved: Smartstore 551 → 526, vikunja 172 → 187,
photoprism 165 → 167, memos 185 → 186, Umbraco 528 → 529, and docmost's calls 41 → 42.

| Language | Kind | Repositories | R list, hold-out | R list, now |
|---|---|---|---|---|
| C# | routes | Umbraco, Radarr, btcpayserver, Smartstore, Elsa | 32.2 % (531/1648) | 99.8 % (1621/1624) |
| Go | routes | photoprism, vikunja, memos | 0 % (0/522) | 79.3 % (428/540); 95.7 % (428/447) without memos' Connect RPCs |
| Python | routes | mealie, open-webui | 83.8 % (145/173) | 100 % (173/173) |
| TS/JS | routes | directus, outline, docmost | 74.1 % (289/390) | 99.2 % (387/390) |
| TS/JS | calls | Umbraco, open-webui, outline, docmost | 76.5 % (513/671), P 77.8 % | 100 % (672/672), P 99.6 % |

Sampled route precision moved the same way:

| Repository | Before | After |
|---|---|---|
| Umbraco | 0 % | 100 % |
| Radarr | 30 % | 100 % |
| Elsa | 60 % | 90 % |
| photoprism | 0 % | 95 % |
| vikunja | 10 % | 94.7 % |
| mealie | 65 % | 100 % |
| outline | 65 % | 100 % |

Sampled call precision rose from 5 % to 100 % in outline, from 0 % to 100 % in docmost and from 35 % to 100 % in
open-webui. photoprism's calls only went from 30 % to 35 %, because `rest.js` dispatches statically on the subclass.

Two notes on the three repositories left in the hold-out:

- Nothing moved on them through F1.14. Kavita's routes are at 100 % / 100 % (522), and go-boilerplate's and
  sftpgo's together at 100 % / 99.2 % (128/129).
- Kavita's calls stay at 0/20 on the sample, as measured, because no rule was written for them.

### Where the corpus ends

Over the 54 expected lists (`--expected`, `2026-10-18-v2-baseline-28`):

| Language | Kind | P sample | P list | R list |
|---|---|---|---|---|
| C# | routes | 98.8 % (249/252) | 100 % | 99.3 % (1931/1944) |
| C# | calls | 97.2 % (141/145) | 100 % | 99.0 % (201/203) |
| Go | routes | 93.1 % (258/277) | 98.9 % | 93.3 % (1936/2074); 97.7 % (1936/1981) without memos' Connect RPCs |
| Go | calls | 100 % (23/23) | 100 % | 93.6 % (103/110) |
| Python | routes | 99.2 % (130/131) | 99.3 % | 28.2 % (560/1988); 98.6 % (560/568) without Django |
| Python | calls | 100 % (26/26) | 100 % | 66.7 % (2/3) |
| TS/JS | routes | 87.7 % (193/220) | 98.1 % | 91.7 % (1372/1496) |
| TS/JS | calls | 86.9 % (251/289) | 98.4 % | 99.0 % (1074/1085) |

### What is left, and where it goes

| Category | Wrong | Missed | Repos | Goes to |
|---|---|---|---|---|
| `django-urlconf` | 0 | 1420 | 2 | out of F1.14: a scanner when a portfolio asks |
| `prefix-as-param` | 13 | 119 | 6 | limitation: a prefix known only at run time (NodeBB's plugin names, options, configuration) |
| `connect-rpc` | 0 | 93 | 1 | F2.1, with the proto as the source |
| `prefix-in-client-wrapper` (calls) | 20 | 9 | 2 | limitation: NodeBB's AMD `api` module, whose prefix is picked at run time from the path, and mattermost's `Client4.getBaseRoute()` |
| `test-app-folder` | 20 | 0 | 2 | F1.1, per-repository excludes |
| `url-from-helper` (calls) | 13 | 3 | 2 | limitation: photoprism's static dispatch on a subclass; go-kit's paths passed to a helper as a parameter |
| `segment-from-method` | 0 | 15 | 1 | limitation: vikunja's migrator name, from a method called through an interface |
| `library-code` | 13 | 0 | 1 | limitation: chi's mountable profiler |
| `prefix-in-router-type` | 1 | 12 | 1 | limitation: kratos' `RouterAdmin` prefix is a field set at run time |
| `route-by-name-convention` | 0 | 10 | 1 | the project's convention (F0.4.5 `route_patterns`) |
| `multi-app-repo` | 0 | 8 | 4 | limitation: two apps inside one module |
| 24 other categories | 12 | 35 | — | none above 5 items; each is in its expected lists' notes, for when a portfolio shows it |

The choice of what came next is recorded in the ROADMAP. First comes the H4 recycling of the working docs, then the
H5 refactor. After it, the new hold-out is measured, then P2, the indexer in its own repository. SCIP (F1.1, F1.2)
comes last. A gap whose decision needs the type of an expression not declared in sight stays `needs-resolver`, for
F1.2's resolver.

## Baselines

Each run is `~/.cache/aidd-corpus/runs/<name>/`, one JSON per repository. A new baseline is saved only after its diff
against the previous one was judged item by item. The **current** ones are `2026-10-18-v2-baseline-29` (corpus) and
`2026-10-18-v2-holdout-26` (hold-out).

| Baseline | What changed |
|---|---|
| `2026-10-14-baseline` | v1: 15 repositories, the extractor of H2a (F0.4.3a) |
| `2026-10-15-v2-baseline` | v2: 39 repositories, mostly real applications; the extractor of Phase 3 |
| `-2` | the cheap defects of v2 |
| `-3` | the mount graph, step 1 (inside a file) |
| `-4` | C#: inherited `[Route]`, endpoint classes |
| `-5` | C# calls: constants in templates, the app's own client wrappers |
| `-6` | NSwag clients and the rest of .NET; 42 repositories |
| `-7` | the mount graph, step 2 (across files, Go and Python) |
| `-8` | route chains (H2b item 4) |
| `-9` | Go calls and Go generated clients |
| `-10` | Go generated servers (grpc-gateway, go-swagger) |
| `-11` | flask-restx, hand-applied decorators |
| `-12` | the mount graph across files in TS/JS |
| `-13` | Nest's global prefix and controller constants |
| `-14` | the project's own route registrars in TS/JS |
| `-15` | TS generated clients, requests described by an object |
| `-16` | the last cheap fixes; **H2b closed** (42 repositories) |
| `2026-10-17-holdout` | **the first hold-out, measured once:** 16 repositories |
| `-17`, `-18` | F1.14 increment 1: the hold-out's precision defects and its .NET; 46 repositories |
| `-19` | increment 2: the rest of the hold-out's .NET; 48 |
| `-20` | increment 3: the hold-out's Go; 50 |
| `-21` | increment 4: the hold-out's Python; 51 |
| `-22` | increment 5: the hold-out's TS/JS; 55. **PR #4** |
| `-23` | increment 6: FastEndpoints groups, gRPC custom verbs |
| `-24` | increment 7: Go routers through declared types, named closures (increment 8 left it identical) |
| `-25` | increment 9: one endpoint per app in a monorepo |
| `-26` | increment 10: Python client wrappers |
| `-27` | increment 11: TS/JS client wrappers, listed mounts, autoload, Next.js |
| `-28` | increment 12: two TS wrapper defects the live validation found. **PR #5** |
| `-29` | H5 step 5, Go's change of behavior: a local typed by a constructor's declared result (vikunja `POST /api/v2/mcp`, memos `ANY /`) |
| `2026-10-18-v2-holdout-26` | the hold-out's three repositories, unchanged since increment 5 |

## H5 baseline (2026-10-19)

The H5 refactor (`docs/handoffs/H5-indexer-refactor.md`) changes no behavior. At every step the corpus must give
`0 repo(s) differ` against `2026-10-18-v2-baseline-28`, and the hold-out the same against `2026-10-18-v2-holdout-26`.
Step 0 measured the starting point, alone on the machine. Step 5's changes of behavior are judged instead and close
with a new baseline (H5-D12): after Go's, the steps compare against `2026-10-18-v2-baseline-29`.

**Corpus:**

- `0 repo(s) differ`;
- 483 s of wall time, 3 containers at once;
- **1,449 s summed over the repositories**. The largest are mattermost (250 s), bitwarden (140), photoprism (109),
  umbraco (106), elsa (74) and ghost (68);
- the largest memory peak is mattermost's, at 2.2 GiB.

The target of step 9 is that sum at ≤ 60 %, so ≤ ~870 s.

**Hold-out:** `0 repo(s) differ`, in 43 s.

**Shape** (`indexer/scripts/shape.py`, also a report-only CI job):

- **58 functions above complexity 9.** The worst are:

  | Function | Complexity |
  |---|---|
  | `build_server` | 44 |
  | Go's `_call` | 34 |
  | `collect_constants` | 29 |
  | C#'s `_controller` | 29 |
  | Go's `file_facts` | 26 |
  | `resolve_calls` | 25 |
  | conventions' `apply` | 23 |
  | C#'s `_recipe` | 23 |

- **14 modules above 300 lines.** The longest are:

  | Module | Lines |
  |---|---|
  | `languages/csharp/http.py` | 1,471 |
  | `languages/typescript/http.py` | 998 |
  | `core/http_expr.py` | 937 |
  | `mcp/server.py` | 870 |
  | `languages/go/http.py` | 766 |
  | `core/http_base.py` | 734 |
  | `cli.py` (the P2's) | 710 |
  | `languages/csharp/symbols.py` | 663 |

**Profiles.** cProfile, one repository at a time, so the absolute times include its overhead. The shares say where
the time goes:

| Repository | Total | Own time in `walk` | `walk` with what it calls | The next largest |
|---|---|---|---|---|
| mattermost | 426 s | 176 s (41 %) | 247 s | Go's `_declared_type`, 215 s cumulative over 395 k calls; `collect_constants`, 64 s |
| umbraco | 174 s | 56 s (32 %) | 82 s | `collect_constants`, 31 s; C#'s `_local_type`, 28 s |
| ghost | 106 s | 27 s (25 %) | 37 s | `collect_constants`, 31 s; TS `run`, 36 s |
| vikunja | 99 s | 37 s (37 %) | 51 s | Go's `_declared_type`, 31 s; `collect_constants`, 14 s |

The tree walk that builds a list of children for every node, and the scope scans repeated for each question (Go's
declared type, C#'s local type, `Scopes._assignments`), are what steps 2 and 3 (`tree.py` and `FileIndex`) replace.

### H5 steps

Each refactor step must give `0 repo(s) differ` on both sets against the starting baselines. Step 5's changes of
behavior are the exception: judged at the source, they close with a new baseline when the corpus changes (H5-D12).

| Step | Corpus / hold-out | Summed time | Note |
|---|---|---|---|
| 0 | 0 differ / 0 differ | 1,449 s | the starting point |
| 1 | no change to the code | — | 147 unit tests: `paths`, the mount graph, `Scopes`, `path_of`. Turning off any rule of `normalize_path` breaks a named case |
| 2 | 0 differ / 0 differ | 944 s | `aidd_indexer/tree.py` with a cursor walk; the language registry loads on first use, so the import cycle is gone |
| 3a | 0 differ / 0 differ | 780 s | Go's declared type and C#'s local type answer from an index of each function's declarations, built in one pass (`NodeCache`), instead of walking the function for every question |
| 4a | 0 differ / 0 differ | 771 s | the language's own package facts (Go's pass-through functions, Python's router classes, TS's clients with a base and enum members) leave `core/http_expr.py` (937 → 699 lines) for `languages/<lang>/package_facts.py`, read through `LanguageSupport.package_facts` in the same pass |
| 4b | 0 differ / 0 differ | 777 s | Go's own path expressions (`url.URL`, a read of `u.Path`, grpc-gateway's patterns) leave the core's `path_of` for the Go scanner (`languages/go/paths.py`, through a `_call_path` hook); `core/http_expr.py` 699 → 656 lines |
| 7 (in part) | 0 differ / 0 differ | 772 s | the client wrappers' facts and pending calls are named tuples (`WrapperShape`, `WrappedCall`) instead of positional ones, read by field in `core/http_wrappers.py` |
| 9 (in part) | no change to the extractor | — | `http_corpus.py`'s docstring no longer holds counts edited by hand: `--reuse runs/<baseline> --show 0` prints them, and `corpus.sh` writes them in every report. The summed time is at 54 % of step 0's (777 of 1,449 s), against a target of ≤ 60 %, within the timing noise noted above |
| 10 (in part) | comments and docstrings only (the AST of each file is unchanged) | — | 13 doc and planning references and about 70 project names leave the code's comments; an example now describes the shape, with neutral names. `tests/test_code_hygiene.py` keeps them out. What stays is the `knowledge` server's instructions to the agent, which point at the contract it serves. The review of what each comment says is still to do |
| 8 (in part) | the MCP is not in the extraction | — | `mcp/server.py` (870 lines; `build_server` at complexity 44) splits into `store.py` and one module per tool group, and the server only assembles them. `tools/list` is byte-identical in fixed and multi-tenant mode: 11 tools, same order, same descriptions and schemas. The 70 Cypher strings are identical too |
| 8 (in part) | the extraction does not use it | — | `core/matching.py`: the rule for whether a call and a route meet (keys, case per framework, methods, suffixes), used by the linker, the MCP and the corpus scorer. Rescoring the baseline gives the same report line for line. The MCP's `who_consumes` now keys the path it is asked about as a route (`query_key`): `/users/:id` or `api/x` find the route, where before they did not |
| 8 (in part) | tests only | — | `scripts/mcp-it.sh`: every atlas tool against a real Neo4j. The script starts a throwaway Neo4j, seeds it by indexing three small repositories (`tests/mcp_it`: a Go service on two branches, an ASP.NET one, a TS client of both), runs `tests/test_mcp_neo4j.py` (14 cases) and removes it. An ASP.NET route asked in either case is found and linked |
| 4c | 0 differ / 0 differ | 777 s | each language's package facts are a dataclass whose fields declare how two files' values join (one value or none, the last one, a union); `PackageContext` holds them by key, with no field of its own that is a language's; a lookup across the repo is a question to the view (`RepoView.defining`). The micro set is identical too |
| 7 | 0 differ / 0 differ | 761 s | every fact a file publishes and every request it leaves pending is a `NamedTuple` of its kind (`languages/<lang>/http_facts.py`), looked up by its type: no text key and no positional tuple is left between a scanner and its `compose`. The micro set is identical too |
| 4d | 0 differ / 0 differ | 771 s | C#'s qualified constants are a question to the view (`RepoView.constant_values`), not a loop over every directory, and a test keeps the view the only code that walks the directories. Go's two direct reads of an imported directory miss the repo's root package; a strict xfail holds that gap for its own fix. The micro set is identical too |
| 5, Go's refactor | 0 differ / 0 differ | 811 s | the `TypeIndex` API in the core, Go's type facts as typed values, and Go's resolver asking `GoTypeIndex` (PR #17). Its three commits summed 952, 906 and 811 s, against 771 s at 4d: within the 28 % noise, and not measured alone. The micro graph was identical on the 12 repos and on the corpus's 13 other Go repos |
| 5, Go's change of behavior | 2 differ, judged / 0 differ | 768 s | one answer for the resolver and the scanner, with Go's scoping, and the type service's three older gaps closed: promoted methods, type parameters, a method's declared result (H5-D15). The corpus's two items are right and outside their lists' scope: vikunja's MCP route gets its `/api/v2`, memos gains its frontend's `ANY /`. The micro set, judged by case on the 17 Go repos: +18,874 typed edges, −4,339 `inherited` turned into the promoted method, −11,077 guesses by name. Alone, on one image, the corpus summed 763 s on `main` and 768 s on the branch. New baseline `-29` |
| 5, C#'s refactor | 0 differ / 0 differ | 774 s | C#'s type facts as typed values, equal to the old dicts on the 35,255 C# files of the corpus and the hold-out, and C#'s resolver asking `CsTypeIndex` (PR #23). The micro graph is identical on the 12 repos and on the corpus's 11 other C# repos. Alone, on one image, the corpus summed 746 s on `main` and 774 s on the branch: the C# repos 264 and 268 s, the others, whose code did not change, 482 and 506 s. Full dry-runs of umbraco, elsa, bitwarden and smartstore, which run the resolver, take the same time on both |
| 5, C#'s change of behavior | 0 differ / 0 differ | 776 s | one answer for the resolver and the scanner, with C#'s scoping, and four older gaps of the type service closed (H5-D16): `partial` types, a method's declared result, the repo's extension methods on a typed receiver, a type written with its namespace. The corpus and the hold-out are unchanged, so the baseline stays `-29`. The micro set, judged by case on the 12 C# repos that changed: +11,742 typed edges, about 5,900 call sites that reach the repo's extension method, −5,848 guesses by name. Alone, on one image, the corpus summed 812 s on `main` and 776 s on the branch |
| 5, what a name means in C# (H5-D17) | 0 differ / 0 differ | 255 s wall | a type's simple name looked up as C# does (the namespaces around the code, then the `using`s and the project's `global using`s), nested types, a capitalized member, a type parameter's type argument and constraint, an array as `System.Array`, extension blocks, and a call with no receiver, which is a request only when given the verb. The corpus and the hold-out are unchanged at the last commit, so the baseline stays `-29`. The micro set, judged by case on the 13 C# repos that changed: +18,137 typed edges, +1,403 `inherited`, −5,639 guesses by name; bitwarden's `sutProvider.Sut.X()` and radarr's `Subject.X()` reach the class under test. Alone, on one image, the corpus took 259 s of wall time on `main` and 255 s on the branch |

Two notes on step 2:

- **The real gain.** The walk is 2.5× faster on the same trees: over mattermost's 1,500 Go files, with 8 M nodes, it
  went from 2.67 s to 1.08 s, finding the same calls.
- **Timing noise.** Between two runs of the same code, the summed time moved by 28 %. The corpus time alone does not
  isolate a step, which is why the walk was benchmarked on the same trees.

Profiles after step 3a, against step 0. These use cProfile, and their shares are comparable:

| Repository | Total | Own time in `walk` | What changed |
|---|---|---|---|
| vikunja | 99 → 61 s (−39 %) | 37 → 18 % | — |
| mattermost | 426 → 189 s (−56 %) | 41 → 19 % | Go's `_declared_type`: 215 s cumulative before, 12 s for the index now |

Step 3's criterion is met on vikunja: the walk is below 20 %.

## H6 baseline (2026-10-19)

H6's step 0 (`docs/handoffs/H6-extraction-pipeline.md`) measures the whole pipeline phase by phase, the resolver
included, with no change to the code:

- **What ran:** a script that calls the same functions as `aidd index`, in the same order, on the H5 branch
  (`e5796a0`).
- **How it ran:**
  - one container per run, with a 9 GB cap, alone on an 8-CPU machine;
  - 3 runs, interleaved across the repos.
- **Two exceptions:**
  - the resolver ran in the first round only, since it took 31 and 38 minutes on two repos;
  - vikunja ran it in all three rounds.
- **The write to Neo4j is not measured** (a dry-run).

**Time per phase**, in seconds, as the median (range):

| Repo | Files (parsed) | Discover | Parse only | Extract | HTTP pass 1 | HTTP pass 2 | Compose | Resolve | Resolve, with the index |
|---|---|---|---|---|---|---|---|---|---|
| vikunja | 2,134 (1,704) | 0.5 | 1.6 | 10.5 (10.0–10.6) | 2.0 | 6.6 | 0.0 | 16.9 (16.6–17.2) | 0.4 |
| ghost | 7,956 (6,948) | 1.9 | 3.6 | 20.4 (20.2–20.9) | 4.8 | 9.1 | 0.1 | 1.1 | 1.1 |
| umbraco | 17,453 (17,173) | 4.2 | 6.9 | 37.4 (36.4–39.6) | 4.8 | 19.8 | 0.3 | 2,279 | 4.9 |
| mattermost | 9,648 (8,532) | 3.2 | 6.6 | 43.7 (43.1–44.0) | 9.1 | 12.7 | 0.1 | 493 | 3.3 |
| grafana | 20,646 (16,580) | 7.5 | 11.1 | 72.7 (72.3–73.8) | 15.1 | 25.4 | 0.1 | 1,889 | 8.7 |

- **Spread:** every phase measured three times varied less than 5 % between runs.
- **"Resolve, with the index":** PR #9, merged into `main` (see below).

**Memory**, in MiB:

| Repo | Peak, extracting with each tree dropped | Peak, every tree kept (today) | Container peak, whole run (3 runs) |
|---|---|---|---|
| vikunja | 233 | 647 | 678–706 |
| ghost | 67 | 1,234 | 1,373–1,427 |
| umbraco | 220 | 1,736 | 1,945–2,001 |
| mattermost | 73 | 2,228 | 2,501–2,546 |
| grafana | 271 | 3,709 | 4,165–4,271 |

**The second read.** A file has an HTTP shape when its scan added an endpoint, a call, a pending item or a fact. The
facts make this an upper bound on what a second map would re-read.

| Repo | Files scanned | With an HTTP shape | Reading another file's facts | Reads per reading file, median / p90 | Parse, all files / shaped files (s) | Summaries, raw / zlib (MB) |
|---|---|---|---|---|---|---|
| vikunja | 968 | 237 (24 %) | 243 (25 %) | 6 / 31 | 1.4 / 0.6 | 20.6 / 4.3 |
| ghost | 4,451 | 2,679 (60 %) | 2,366 (53 %) | 6 / 29 | 2.8 / 1.0 | 41.3 / 9.7 |
| umbraco | 14,067 | 7,695 (55 %) | 2,562 (18 %) | 6 / 25 | 4.9 / 2.2 | 80.5 / 21.6 |
| mattermost | 4,562 | 2,009 (44 %) | 1,766 (39 %) | 7 / 31 | 5.6 / 1.2 | 85.9 / 17.8 |
| grafana | 10,866 | 2,621 (24 %) | 5,223 (48 %) | 5 / 29 | 9.2 / 1.3 | 145.9 / 34.7 |

Every summary could be pickled.

**What a push changes.** The count covers the last 1,000 changes on the default branch, counting first parents (a
merged PR or a direct push) and only the files of a parsed language:

| Repo | Parsed files | Median | p90 | p99 | Changes touching ≤ 5 files |
|---|---|---|---|---|---|
| ghost | 7,061 | 3 | 16 | 59 | 65 % |
| umbraco | 17,194 | 2 | 28 | 417 | 66 % |
| mattermost | 8,670 | 3 | 20 | 118 | 66 % |
| vikunja | 1,721 | 1 | 5 | 21 | 91 % |

The live install's three mirrors that have history agree: a median of 0 to 2 files, and 69–100 % of changes touching
≤ 5.

**What it says:**

1. **The resolver was the largest phase, by far.**
   - The cause: Go and C# looked types and package files up by scanning every file of the repo, once per call with a
     typed receiver, which is quadratic.
   - The fix: an index built once (PR #9) brings the phase to 0.4–8.7 s.
   - The check: full dry-runs of `main` and the branch, compared record by record on 12 repos, are identical. The
     repos are eshop, jellyfin, btcpayserver, umbraco, vikunja, gitea, mattermost, grafana, dispatch, netbox, ghost and
     outline.
   - For H6: recomputing `CALLS` in the reduce is cheap, so caching them per file is not needed.
2. **The memory is the trees.**
   - Dropping each tree once its file is extracted takes the peak from 0.65–3.7 GB to 67–271 MiB, with no change in
     time. That peak follows the largest file.
   - Goal 1 is within reach with or without parallelism.
3. **The map's cost is extraction, not parsing.**
   - Parsing is 15–18 % of extraction, and the rest is Python, so worker processes pay off.
   - A second map that re-parses the files with an HTTP shape (option B) adds 0.6–2.2 s per repo.
4. **The second read is broad.** 18–53 % of the scanned files read a fact another file produced, with a median of 5
   to 7 reads and a p90 of 25 to 31. A key per file made of the reads (option C) records that many entries, and a
   digest per package (option D) avoids them.
5. **The summaries are small:** 4–35 MB compressed per snapshot.
6. **A push touches 1 to 3 files at the median.** With the per-file cache, a refresh costs those files' map plus the
   reduce.
7. **The HTTP corpus never runs the resolver**, so it neither saw item 1 nor compares `CALLS`. The full dry-run,
   compared record by record, is what covers the micro graph. It joins H5's regression protocol and H7's gates.


## H6 step 1 (2026-10-20)

H6's step 1 prototypes the extraction as a map, a reduce and a per-file cache, and measures the options for the
second read (`docs/handoffs/H6-extraction-pipeline.md`, "Open question 1").

**What ran:** a prototype on a throwaway branch, `h6/step1-proto`, cut from the H5 branch at `374e243` and never
merged. It replaces `extract_tree` with three stages:

- **map 1, in worker processes** (`ProcessPoolExecutor`, started with `fork`): each file is extracted and its tree
  dropped. The worker returns a summary: the symbols, calls, imports and facts, plus what the file adds to its
  directory's HTTP context;
- **the reduce:** the directories' contexts are joined in file order. Each file's additions are replayed, and the
  context's rules of "one value, else none" are kept;
- **map 2, the second read as option B:** each file a scanner reads is extracted again and scanned with its
  directory's context.

A per-file cache keeps both maps' results:

- map 1 is keyed by the file: its id, path, language, content hash and module;
- map 2 is keyed by option D per package (below).

No line of a scanner changed.

**How it ran:**

- one container per run, alone on an 8-CPU machine;
- 3 rounds, interleaved across vikunja, mattermost and grafana;
- each figure is the median, with the range (min–max).

**Correctness:**

- **The tests:** 350 passed.
- **The HTTP corpus:** `0 repo(s) differ` against `2026-10-18-v2-baseline-28`, on 55 repos.
- **The micro set:** the full dry-runs are identical to `main`'s on the 12 repos, record by record.
- **The bench:** each of its 45 prototype runs (cold and warm, with 1 to 4 workers) is identical to today's run of the
  same tree.
- **Real pushes:** a warm run equals a cold one on 6 pushes, and again on a second warm run with no change.

**Time**, in seconds, for a full dry-run (warm uses 2 workers):

| Repo | Today | 1 worker | 2 workers | 4 workers | Warm, nothing changed |
|---|---|---|---|---|---|
| vikunja | 21.1 (21.0–22.3) | 26.2 (26.1–26.9) | 17.0 (16.9–17.8) | 14.7 (14.7–15.6) | 3.2 (3.2–4.2) |
| mattermost | 73.1 (73.1–73.7) | 91.5 (91.1–93.0) | 52.7 (52.4–53.7) | 31.2 (30.8–32.5) | 14.1 (13.6–16.3) |
| grafana | 132.5 (132.4–135.2) | 154.5 (154.3–159.1) | 95.3 (95.1–97.0) | 60.5 (59.6–63.8) | 33.0 (33.0–34.0) |

**Memory**, the container's peak in MiB (median):

| Repo | Today | 1 worker | 2 workers | 4 workers | Warm |
|---|---|---|---|---|---|
| vikunja | 658 | 408 | 505 | 652 | 423 |
| mattermost | 2,286 | 1,136 | 1,190 | 1,324 | 1,242 |
| grafana | 4,283 | 2,268 | 2,368 | 2,357 | 2,489 |

**The cache on real pushes.** The cache was filled on the commit before each push, and the runs used 2 workers.
"Map 2 re-run" is the number of scans whose key missed:

| Push | Parsed files changed | Map 2 re-run | Cold (s) | Warm (s) | Warm again, no change (s) | Warm equals cold |
|---|---|---|---|---|---|---|
| vikunja k12 | 7 | 10 | 17.1 | 3.3 | 3.0 | yes |
| vikunja k28 | 3 | 102 | 17.0 | 4.2 | 2.9 | yes |
| vikunja k38 | 2 | 5 | 17.0 | 3.4 | 2.9 | yes |
| mattermost k19 | 5 | 40 | 59.6 | 16.2 | 12.4 | yes |
| mattermost k25 | 18 | 496 | 53.9 | 23.4 | 12.2 | yes |
| mattermost k30 | 11 | 72 | 53.7 | 20.6 | 13.8 | yes |

**The second read's policies, on 39 consecutive pushes per repo.** Each push was replayed from the default branch's
first-parent history, and each commit was indexed cold. For each file, the replay recorded:

- the file's key and the digests of its summary and of its scan;
- the directories its scan looked up;
- the questions it asked of the repo's structure: an import's target, a manifest's directory, the files under a
  directory;
- the context entries it read.

A policy misses a change when a file's key hits but its scan differs:

| Policy: a scan re-runs when… | vikunja: scans re-run per push, median / p90 / max | mattermost | Keys that missed a change |
|---|---|---|---|
| B: always | 970 / 972 / 972 | 4,572 / 4,589 / 4,589 | 0 |
| D, whole repo: any context or the structure changed | 969 / 972 / 972 | 4,563 / 4,587 / 4,589 | 0 |
| D per package, raw context: its directory's context, a directory it looked up, or an answer to its questions changed | 3 / 97 / 102 | 114 / 444 / 496 | 0 |
| D per package, as built: the same, over what a scanner reads of the context | 1 / 97 / 102 | 40 / 438 / 496 | 0 |
| C: an entry it read, or an answer to its questions, changed | 1 / 10 / 11 | 8 / 108 / 144 | 0 |
| Only when its own file changed (A's floor) | 1 / 2 / 3 | 2 / 10 / 27 | 0 |

Other figures from the replay:

- **Files per push:** a median of 2 parsed files changed on vikunja (max 7) and 5 on mattermost (p90 22, max 42).
- **Map 1 keys:** across the 78 pushes, no key hit with a different summary.
- **Map 2's CPU per push on mattermost** (median / p90): 0.2 / 10.2 s with D per package, 0.1 / 2.9 s with C, and
  36 / 42 s with B.

**What it says:**

1. **B with D per package works as built.** Its output is identical everywhere, and no scanner changed. On
   mattermost, a warm run takes 14 s with nothing changed and 16–23 s after a real push, against 73 s today.
2. **The map scales with workers.**
   - With 4 workers, grafana goes from 132 s to 60 s, and mattermost from 73 s to 31 s.
   - With 1 worker, the prototype is 20–25 % slower than today. Map 2 extracts each scanned file again: the scanners
     need the file's symbols tied to its tree's nodes, so a parse alone is not enough.
   - H5's per-file index (step 3), rebuilt from a parse, would remove that cost.
   - Step 0's estimate for B (0.6–2.2 s, the files with an HTTP shape parsed again) was too low. Which files have a
     shape is known only after the scan, so map 2 reads every file a scanner reads: 53–66 % of the parsed files.
3. **Memory halves, but grafana stays above F1.13's 2 GB.** Grafana goes from 4.3 to 2.3 GB, and mattermost from
   2.3 to 1.1 GB.
   - With no tree kept, the peak at 1 worker belongs to the parent: the summaries, the resolver and the dry-run's
     output.
   - Workers add little: 2.27 GB at 1 worker, 2.36 GB at 4.
   - The write to Neo4j was not measured.
4. **A warm run's floor is not the scans.** On mattermost, a run with nothing to re-run still takes 14 s:
   - discovery reads and hashes every file;
   - reading the cache's 8.5 thousand entries takes 3.9 s;
   - the resolver and the output take the rest.
5. **C re-runs 4 times fewer scans than D at the p90** (108 against 438 on mattermost).
   - The tail of D comes from Go's large packages. A push that adds a function or a struct field to
     `server/channels/app` (168 scanned files) changes the package's context, and every file of the package can read
     it.
   - C costs read tracking in every scan, about 19 % of map 2's time. Its key holds a median of 0 entries per file, a
     p90 of 10–17 and a maximum of 9,605.
   - D per package records a median of 2–3 questions and directories per file, and a p90 of 7.
6. **The cache store.** Entries written as files, through a temporary file and a rename, cost more than the
   extraction on Docker Desktop's bind mount: filling the cache took 84 s on mattermost (13 thousand entries),
   against 53 s cold. SQLite, or one file per snapshot, is the next measurement (Open question 4). The summaries,
   compressed: 4.6, 19.3 and 37.6 MiB for map 1 (vikunja, mattermost, grafana), plus 0.6, 1.8 and 4.2 MiB for map 2.
7. **The batches.**
   - Cut by count, the largest files went into one batch, and the run waited on it.
   - Cut by size in lines, map 1 scales: vikunja's goes from 12.3 s to 6.7 s and 4.5 s.
   - A vendored bundle the bundle rule does not catch (`scalar.standalone.js` in vikunja) takes 8.3 s of map 2's
     12.4 s of CPU. It is map 2's floor at any worker count.
8. **What the cache must get right**, found while building it:
   - **ids carry the ref** (`tenant/repo@ref/…`). For one summary to serve two refs, the ids must be made relative,
     and the reduce must stamp the ref;
   - **a digest needs a canonical encoding.** Pickle shares equal objects by identity, so equal values gave
     different digests from run to run;
   - **the repo's structure cannot be one digest,** or any new file re-runs every scan. Each scan records its
     questions, and on the next run the questions are asked again;
   - **a context holds what scanners read**, such as a function's name and id, and not its lines (the raw row
     against the built one). That is the shape H5's steps 4 and 7 give the facts.
9. **Option A was not built.** Its floor in the replay is the changed files only.
   - 15 functions of the scanners read a value another file produced, at 33 sites.
   - Several of these reads decide control flow, not only a value: Go's verb lists and field types, TS clients and
     their bases, Python's router classes. Under A, each one becomes a conditional item that the reduce settles.

### The cache store (H6 step 2, 2026-10-20)

The 13 thousand entries of a real mattermost cache (21 MiB) were written and read again by three stores, in seconds,
as the median of 3 rounds:

- a cold run fills the store;
- a warm run reads every entry;
- a push reads every entry and writes 1 % new ones.

| Store | Docker Desktop's bind mount: fill / warm / push | The container's own disk: fill / warm / push |
|---|---|---|
| One file per entry (the prototype) | 102 / 16.3 (1.7–32.8) / 2.5 | 0.48 / 0.15 / 0.15 |
| SQLite, one transaction per run | 1.5 / 0.21 / 0.12 | 0.18 / 0.09 / 0.09 |
| One file per snapshot, rewritten per run | 0.02 / 0.02 / 0.05 | 0.01 / 0.01 / 0.02 |

ADR-004 chose SQLite: one entry per file across every ref, and one database per repo. A file per snapshot is
faster, but it stores a file shared by two refs twice. The script is `indexer/scripts/h6-step1/store_bench.py` on
`h6/step1-proto`.

### What a directory's context should hold (H6 step 2, 2026-10-20)

The step 1 replay was evaluated again, with each directory's context digest cut to the facts a scanner reads: Go's
struct fields, out of all of `file_facts`. On mattermost, a push re-runs this many scans:

| Directory context in map 2's key | Median | p90 | Max |
|---|---|---|---|
| Every fact of every file | 40 | 438 | 496 |
| Cut to what scanners read | 10 | 300 | 411 |
| C: only the entries read | 8 | 108 | 144 |

- No key missed a change.
- Vikunja does not change: 1 / 97 / 102.
- What is left in the cut row is mostly the functions by name. ADR-005 records each such lookup as a question.

### Batches by package (H6 step 2, 2026-10-20)

Step 1's batches extract every scanned file twice: in map 1, and again in map 2 to scan it. This bench measured
batches of whole packages instead, which H6-D6 now decides:

- a worker extracts its batch's packages, builds each package's context from them, and scans the package's files
  while their trees live;
- each scan records its reads with the answers it got: a directory's context, a pass over every directory, the
  directories of a class, a question to the repo's structure;
- the reduce asks each read again of the whole repo. A scan whose answers all hold is final, and the others go to
  map 2;
- a package larger than the total over 4 × workers is split into batches of files, and its files' scans go to map 2.

**What ran:**

- the prototype at `31d3990` on `h6/step1-proto`, with batches by package as the default;
- one container per run, on an 8-CPU machine, 3 rounds, each figure the median;
- a second bench at 2 workers, the refresher's quota, with batches of files and of packages interleaved.

**Correctness:**

- **The tests:** 350 passed.
- **The HTTP corpus:** `0 repo(s) differ` against `2026-10-18-v2-baseline-28`, on 55 repos.
- **The micro set:** the full dry-runs are identical to `main`'s on the 12 repos, record by record.
- **The bench:** each of its 81 runs (batches of files and of packages, 1 to 4 workers) is identical to today's run of
  the same tree.

**Time**, in seconds, for a full dry-run, batches of files / of packages:

| Repo | Today | 1 worker | 2 workers | 4 workers |
|---|---|---|---|---|
| vikunja | 21.7 | 28.0 / 22.9 | 17.7 / 13.2 | 15.2 / 15.0 |
| mattermost | 73.9 | 91.6 / 81.4 | 55.4 / 48.6 | 31.3 / 28.6 |
| grafana | 130.3 | 153.3 / 136.0 | 97.9 / 86.1 | 59.0 / 54–81 |

**Map 2's share** with batches by package, at 1 worker:

| Repo | Scans | Not accepted, read again in map 2 | Their CPU in map 2 |
|---|---|---|---|
| vikunja | 968 | 24 (2.5 %) | 0.3 s |
| mattermost | 4,562 | 142 (3.1 %) | 7.1 s |
| grafana | 10,866 | 491 (4.5 %) | 6.0 s |

With more workers, the largest packages are split. At 4 workers, map 2 reads 122 scans on vikunja and 368 on
mattermost, but none of grafana's packages is split.

**What it says:**

1. **Batches by package cost less everywhere it was measured, for the same output.** They take 14–22 % less CPU
   than batches of files, and 12–25 % less time at 2 workers.
2. **At 1 worker, they are 4–10 % slower than today,** against 18–29 % for batches of files.
   - Most of the gap is the scans read again. They are few, but large files: on mattermost, 50 ms each, against 7 ms
     for an average scan in map 2.
   - H5's per-file index, rebuilt from a parse, makes them cheaper.
3. **At 4 workers, the parent's serial work weighs.**
   - On grafana, discovery takes 5 s, and the resolver with the output 16–23 s: close to 40 % of the run.
   - On vikunja, one vendored bundle is the floor, 8 s, in map 1 or in map 2.
4. **Grafana's runs with workers are noisy.**
   - At 4 workers, batches by package took 54–81 s over 6 rounds. In the slowest, the workers' time per file, summed,
     went from 109 s to 183 s for the same work: the machine's other load.
   - A probe of the parent's garbage collector found 1–3 s per run. Freezing the heap after map 1 (`gc.freeze()`)
     changed nothing.
5. **A read the scans did not record.** A fixture's output differed with 2 workers.
   - An early scan had read every directory's context, made of its batch only. The read was not recorded, so the
     reduce accepted it.
   - The read is Go's `_passthrough_index`. For a method `x.M` whose operand is not an imported package, it looks for
     a function `M` that returns a parameter, in every directory (`view.contexts.values()`).
   - Step 1's key did not cover it either, so that key was not sound by construction. No push of the replay changed
     such a function, which is why the replay found no missed change.
   - 1.0–1.1 % of the scans make that pass (10 on vikunja, 52 on mattermost). The prototype now records it as a read
     of every directory, which re-runs those scans on any change of context.
   - ADR-004 and ADR-006 make it a question, with its answer.
6. **What a scan reads.** A median of 2–3 recorded reads per scan, and a p90 of 7. On vikunja and mattermost:
   - an import's target, in 76–78 % of the scans;
   - a manifest's directory, in 30–70 %;
   - another directory's context, in 2.1–2.7 %;
   - another directory's constants, in 1.7–1.9 %.

The scripts are `packages_chain.sh`, `packages_2w_chain.sh`, `count_reads.py` and `aggregate.py`, in
`indexer/scripts/h6-step1/` on `h6/step1-proto`. The runs' text is in `results/packages/` and
`results/packages-2w/`.
