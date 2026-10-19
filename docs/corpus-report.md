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
| 24 other categories | 12 | 35 | — | none above 5 items; each is in its gabaritos' notes, for when a portfolio shows it |

The choice of what came next is recorded in the ROADMAP. First comes the H4 recycling of the working docs, then the
H5 refactor. After it, the new hold-out is measured, then P2, the indexer in its own repository. SCIP (F1.1, F1.2)
comes last. A gap whose decision needs the type of an expression not declared in sight stays `needs-resolver`, for
F1.2's resolver.

## Baselines

Each run is `~/.cache/aidd-corpus/runs/<name>/`, one JSON per repository. A new baseline is saved only after its diff
against the previous one was judged item by item. The **current** ones are `2026-10-18-v2-baseline-28` (corpus) and
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
| `2026-10-18-v2-holdout-26` | the hold-out's three repositories, unchanged since increment 5 |

## H5 baseline (2026-10-19)

The H5 refactor (`docs/handoffs/H5-indexer-refactor.md`) changes no behavior. At every step the corpus must give
`0 repo(s) differ` against `2026-10-18-v2-baseline-28`, and the hold-out the same against `2026-10-18-v2-holdout-26`.
Step 0 measured the starting point, alone on the machine.

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

Each step must give `0 repo(s) differ` on both sets against the starting baselines.

| Step | Corpus / hold-out | Summed time | Note |
|---|---|---|---|
| 0 | 0 differ / 0 differ | 1,449 s | the starting point |
| 1 | no change to the code | — | 147 unit tests: `paths`, the mount graph, `Scopes`, `path_of`. Turning off any rule of `normalize_path` breaks a named case |
| 2 | 0 differ / 0 differ | 944 s | `aidd_indexer/tree.py` with a cursor walk; the language registry loads on first use, so the import cycle is gone |
| 3a | 0 differ / 0 differ | 780 s | Go's declared type and C#'s local type answer from an index of each function's declarations, built in one pass (`NodeCache`), instead of walking the function for every question |
| 4a | 0 differ / 0 differ | 771 s | the language's own package facts (Go's pass-through functions, Python's router classes, TS's clients with a base and enum members) leave `core/http_expr.py` (937 → 699 lines) for `languages/<lang>/package_facts.py`, read through `LanguageSupport.package_facts` in the same pass |
| 4b | 0 differ / 0 differ | 777 s | Go's own path expressions (`url.URL`, a read of `u.Path`, grpc-gateway's patterns) leave the core's `path_of` for the Go scanner (`languages/go/paths.py`, through a `_call_path` hook); `core/http_expr.py` 699 → 656 lines |
| 9 (in part) | no change to the extractor | — | `http_corpus.py`'s docstring no longer holds counts edited by hand: `--reuse runs/<baseline> --show 0` prints them, and `corpus.sh` writes them in every report. The summed time is at 54 % of step 0's (777 of 1,449 s), against a target of ≤ 60 %, within the timing noise noted above |

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

