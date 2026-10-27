# PR #27's validation: what ran, what it gave, and what is still open

> **Provenance.** These numbers were derived on 2026-10-24 from the previous session's outputs, which lived in a
> volatile scratchpad (`$S`, see [the inventory](../validation-inventory.md)); a reboot emptied it on 2026-10-26:
> - `$S/h5/runs/csn-n*/{corpus,holdout,micro}.txt`;
> - `$S/h5/why/out/main-n17.txt`;
> - the background task outputs next to `$S`;
> - `$S/livecsn/`.
>
> The raw outputs are not copied here: the live ones name the install's tenants, and the others are large. What
> follows is the summary, and a manifest of the live "before" picture so that its integrity can be checked before it
> is compared.
>
> Two of the summaries were re-derived on 2026-10-24 with the persisted scripts, and came out identical to the saved
> ones: `chain_diff.py` on the micro runs (§3), and `dry_sections.py` and `graph_vs_dry.py` on `$S/livecsn` (§5).
>
> **Local copies (2026-10-24).** The before picture, the dry-runs, the five pre-merge logs and the original golden
> script were then copied byte for byte to `.local/indexer/pr27/`, with the 27 calls as `golden-calls.json`. Each
> copy's SHA-256 equals its source's. That folder is ignored by git, private, and on this disk only, with no backup.
> Its `README.md` says how to check it and how to use it.

## 1. The PR

- **The PR:** #27, `fix(csharp)`, H5-D17 ("what a name means in C#"), branch `fix/h5-csharp-names`.
- **The commits:** 30, 13 of cases and 17 of fixes, plus the docs commit `8ccf450`.
- **The merge:** into `main` on 2026-10-24 at 06:34:33 UTC as `0725d47`, with the `graph-change` label.
- **CI:** run `40032444886`: `changes` 4 s, `tests` 1m59s, `shape` 10 s, `corpus` 7m18s, `micro` 6m35s, `gates` 35 s,
  all passing. The push to `main` after the merge, run `40070748413`, passed too.

## 2. The protocol on each fix commit

Run by [`protocol.sh`](../../../indexer/scripts/protocol/protocol.sh) on each commit's worktree, one after another,
on 2026-10-23.

- **The corpus** is measured against `2026-10-18-v2-baseline-29`, and **the hold-out** against
  `2026-10-18-v2-holdout-26`.
- **The micro graph** is measured against `main` (`274d63b`'s tree), on 23 repos: the 12 of `micro.py` and the 11
  C# corpus repos below.
- **The micro column** counts the repos that differ from `main`. For a change of behavior, that is expected, and each
  difference is judged by case.

| Run | Commit | Corpus | Hold-out | Micro |
|---|---|---|---|---|
| n1 | `f043452` (inferred: the run's line holds no sha) | 0 differ | 0 differ | 12 differ |
| n2 | `4bf262c` | 1 differ: smartstore | 0 differ | 12 differ |
| n3 | `5691150` | 1 differ: smartstore | 0 differ | 13 differ |
| n4 | `1000b0b` | 1 differ: smartstore | 0 differ | 13 differ |
| n5 | `69ef20c` | 1 differ: bitwarden | 0 differ | 13 differ |
| n6 | `df7a90b` | 1 differ: bitwarden | 0 differ | 13 differ |
| n7 | `478f6ee` | 1 differ: bitwarden | 0 differ | 13 differ |
| n8 | `3cef530` | 1 differ: bitwarden | 0 differ | 13 differ |
| n9 | `f7a62a1` | 1 differ: bitwarden | 0 differ | 13 differ |
| n10 | `cdb53a5` | 0 differ | 0 differ | 13 differ |
| n11 | `11a2681` | 0 differ | 0 differ | 13 differ |
| n12 | `5e95e88` | 0 differ | 0 differ | 13 differ |
| n13 | `6e9830c` | 0 differ | 0 differ | 13 differ |
| n14 | `61ba7c1` | 0 differ | 0 differ | 13 differ |
| n15 | `699d07e` | 0 differ | 0 differ | 13 differ |
| n16 | `4108aef` | 0 differ | 0 differ | 13 differ |
| n17 | `53a87c0` | 0 differ | 0 differ | 13 differ |

The two corpus differences were judged at the source, and later commits undid both (the H5 handoff, "What a name
means in C#"):

- **smartstore, n2 to n4:** a false `GET /images/flags`, which the call with no receiver (n5) removed;
- **bitwarden, n5 to n9:** seven relay calls dropped, which the request's verb (n10) brought back.

**The micro set:**

- the 12 repos of `micro.py`;
- 11 more C# repos of the corpus: ardalis-clean-arch, azure-saas, bitwarden, clean-arch-dotnet, eshop-on-web,
  eshop-support, notifo, radarr, rapid-blazor, elsa and smartstore.

Go's change of behavior (PR #20) used the 12 plus 13 Go repos instead: alertmanager, argo-cd, chi, fiber-recipes,
gin-examples, gin-realworld, go-feature-flag, go-kit-examples, gorilla-mux, gotify, kratos, memos and photoprism.

At n17, the repos that differ are the 13 C# ones that changed:

- eshop, jellyfin, btcpayserver, umbraco;
- ardalis-clean-arch, azure-saas, bitwarden, eshop-on-web, eshop-support;
- notifo, radarr, elsa, smartstore.

The 10 others are identical: 8 of other languages, plus clean-arch-dotnet and rapid-blazor.

## 3. The micro graph's judgment, from `main` to the tip

From [`chain_diff.py`](../../../indexer/scripts/judgment/chain_diff.py) over `main`'s base runs and n17's runs, with
seed `20261021` and 40 samples per kind. A site is a call's file and line. An edge's class comes from its strategy:

- **typed:** `receiver-type*`;
- **inherited:** `inherited*`;
- **name:** any other strategy;
- **~amb:** the strategy is ambiguous.

Sites by kind of change:

| Kind | Sites |
|---|---|
| added (no edge before) | 11,152 |
| widened (more callees) | 4,335 |
| strategy (same callees, another strategy) | 2,367 |
| changed | 1,822 |
| dropped (no edge now) | 761 |
| narrowed (fewer callees) | 494 |

Edges by class:

| Class | Added | Removed |
|---|---|---|
| typed | 18,137 | 2,480 |
| typed ~amb | 2,676 | 674 |
| inherited | 1,403 | 488 |
| name | 1,528 | 2,099 |
| name ~amb | 884 | 3,540 |

The handoff's "found by name: +2,412 and −5,639" is the sum of the two name rows (1,528 + 884 and 2,099 + 3,540).
The judged samples, with their source lines, were in `$S/h5/why/out/*.view.txt`, emptied on 2026-10-26, and a new
draw does not give the same items; their verdicts were not recorded one
by one (H7-D2).

## 4. The time, alone, on one image

From [`time-alone.sh`](../../../indexer/scripts/protocol/time-alone.sh) on `main`'s worktree (`274d63b`) and n17's, on
2026-10-23. Both corpus runs gave `0 repo(s) differ` against `-29`.

| Measure | `main` | n17 |
|---|---|---|
| Corpus, wall time (3 at once under 3g each) | 259 s | 255 s |
| umbraco, full dry-run | 65 s, 202,731 `CALLS` | 64 s, 209,071 `CALLS` |
| elsa | 40 s, 91,550 | 40 s, 93,392 |
| bitwarden | 36 s, 75,022 | 38 s, 79,571 |
| smartstore | 28 s, 88,677 | 27 s, 90,715 |

One run per side, not the median of three (the inventory's V17).

## 5. The live install before the merge

The run was read-only, on 2026-10-23 at about 22:17–22:19 UTC, with the steps of
[`pre-merge.sh`](../../../indexer/scripts/live/pre-merge.sh) (then `val/live-csn.sh`). Snapshots are named by number
only.

- **The dry-runs:** 20 runs, one of `main` and one of the branch for each of the 10 snapshots, every one at rc 0.
- **Section by section:** identical on all 10 (`dry_sections.py`).
- **The graph against `main`'s dry-run,** by the writer's merge keys: all match on all 10, and "mismatching
  snapshots: 0" (`graph_vs_dry.py`, with the before picture on both sides).
- **The picture:** 15 lists, below.
- **The golden calls:** 27 calls, 26 without an error, and the write refused as expected.

### The manifest of the "before" picture

`$S/livecsn/before/`, taken on 2026-10-23 at about 22:18 UTC, while the graph still held `main`'s build. Each list's
rows are `wc -l`, and its digest is the first 16 hex digits of `shasum -a 256`. The golden answers' file names name
the install's repositories, so they are given only as a count and one combined digest: `shasum -a 256 *.json | sort
-k2 | shasum -a 256`, run in `golden/`.

| List | Rows | sha256 (first 16) |
|---|---|---|
| `called_from.txt` | 1 | `4b59d190b928fc4a` |
| `calls_edges.txt` | 23,682 | `0dc6a356e2d4d75e` |
| `consumes.txt` | 1 | `15c512a78eec840f` |
| `counts_macro.txt` | 18 | `84b9966083eb966a` |
| `counts_micro.txt` | 10 | `582699fc376530a6` |
| `depends_on.txt` | 3 | `39f886d7cbebfa5e` |
| `endpoint_nodes.txt` | 159 | `50005e484fa7656d` |
| `endpoints.txt` | 286 | `721741460bd49803` |
| `http_calls.txt` | 160 | `7cd65f2cef086c2a` |
| `imports_edges.txt` | 15,890 | `61fb350a811d8721` |
| `labels.txt` | 36 | `e2bf0143976fd8b7` |
| `modules.txt` | 351 | `0358bc75794afc20` |
| `snapshots.txt` | 10 | `6cd644ef03a10bab` |
| `symbols.txt` | 10,607 | `765fffb62db1d57a` |
| `violations.txt` | 0 | `e3b0c44298fc1c14` |
| `golden/`: 27 files | — | combined `cd6ee12fe87cc861` |

The copy in `.local/indexer/pr27/before/` was checked against this table on 2026-10-24: 15 of 15 lists and the
combined digest match.

## 6. After the merge (checked on 2026-10-24)

- `~/.aidd/indexer/aidd_indexer` is identical to `main`'s `indexer/aidd_indexer` (`diff -rq`).
- The image `aidd-indexer:local` was built at 06:35:55 UTC, with id `f07550cbe2e2`.
- `atlas_status`:
  - every snapshot is at build `0.2.15+ccc54d86dbc7`;
  - the 10 snapshots were indexed between 06:36:48 and 06:37:12 UTC, and none is `outdated`;
  - every tenant's last scheduled refresh ended at rc 0 with `changed: 0`.

## 7. What is still open

Each item was checked against the files on 2026-10-24, and checked again later the same day, after the local copies.
Closing them is a later step, which this document does not take.

| # | Item | State on 2026-10-24 | How it is done |
|---|---|---|---|
| 1 | The "after" picture | not taken: neither `$S/livecsn/after/` nor `.local/indexer/pr27/after/` exists | [`foto.sh`](../../../indexer/scripts/live/foto.sh) into `.local/indexer/pr27/after/` |
| 2 | The "after" picture compared with the "before" one | not done. No dedicated script does it; `graph_vs_dry.py` covers `CALLS` | check the local copy with its `SHA256SUMS` and the manifest above first; then, per list, `diff` before and after, with the build masked in `snapshots.txt` and the tenant in `labels.txt` (the commands are under V23 in the inventory); then [`graph_vs_dry.py`](../../../indexer/scripts/live/graph_vs_dry.py) with the local `before/`, `after/` and `dry/` |
| 3 | The golden answers after | not taken | [`golden.py`](../../../indexer/scripts/live/golden.py) with `.local/indexer/pr27/golden-calls.json`; compare with `cmp` against the local `before/golden/`, then [`json_paths_diff.py`](../../../indexer/scripts/live/json_paths_diff.py) for those that differ |
| 4 | The eleventh golden round | absent: `docs/golden-questions.md` ends at the tenth | a docs PR, as #21, #24 and #26 were |
| 5 | PR #27's line in `docs/history.md` | absent | the same docs PR |
| 6 | The state in `docs/ROADMAP.md` and in the H5 handoff | out of date: both still say H5-D17 goes to review | the same docs PR |
| 7 | The micro base for `main`'s tree and the new image | absent: no `micro/base-ed46a54b…-f07550cbe2e2` | `indexer/scripts/micro.sh --base-only`, before the next local `micro.sh` or `protocol.sh` |
| 8 | A private copy of the 27 golden calls | **done on 2026-10-24**, with the author's authorization: `.local/indexer/pr27/original/golden.py` (verbatim) and `golden-calls.json` (27 calls, unique labels, all 11 tools, labels equal to the 27 before answers) | local and private, with no backup |
| 9 | A durable copy of the "before" picture and answers | **done on 2026-10-24**, with the author's authorization: `.local/indexer/pr27/before/`, with `dry/` and the pre-merge logs, each SHA-256 equal to its source's | local and private, with no backup: a reboot no longer loses it, but deleting the folder would |
| 10 | `install-check.sh`'s output for the 2026-10-24 reinstall | unknown: the author ran it, and it was not seen | the author's output, or a new run |

**On 2026-10-26** (§8):

- item 7 was done;
- items 1 to 3 could not be done, because the install's Neo4j was down;
- item 10 is still unknown for 2026-10-24, and a run that day failed on the same cause;
- item 6 was corrected in the working tree, uncommitted;
- items 4 and 5 wait for 1 to 3.

**Later on 2026-10-26** (§9), after the author recreated the install's Neo4j container:

- items 1 to 3 were done, and pass;
- item 10 is still unknown for 2026-10-24; a run after the recreation passes;
- items 4 and 5 can be written: they wait only for a docs PR.

## 8. The validation attempt of 2026-10-26

With the author's authorization for four kinds of run: offline analyses of saved data, the indexer in Docker,
read-only live checks, and `install-check.sh`. Private outputs went to a new folder,
`.local/indexer/pr27/post-merge-2026-10-26/`, and nothing in `before/`, `dry/` or `pre-merge/` was written.

### What ran, and what it gave

| Step | What ran | Result | Kind |
|---|---|---|---|
| Integrity | `shasum -a 256 -c SHA256SUMS` in `.local/indexer/pr27/` | 89 of 89 OK | check |
| Pre-merge sections | `live/dry_sections.py` on the local `dry/`, before its fix | byte-identical to `pre-merge/`'s output | re-derived |
| Pre-merge graph against the dry-runs | `live/graph_vs_dry.py` with `before/` on both sides | byte-identical; "mismatching snapshots: 0" | re-derived |
| The dry-runs, record by record | every list of each snapshot's two dry-runs, compared as multisets of whole records, as `micro.py` compares a run. A one-off check, not a persisted script | **10 of 10 snapshots identical in all 12 lists** | a new analysis of saved data |
| The micro base for `main` | `micro.sh --base-only` (tree `ed46a54b…`, image `f07550cbe2e2`), 14:19–14:24 UTC | 12 of 12 base runs | fresh |
| The protocol on `main` | `protocol/protocol.sh 2026-10-26-audit-main-0725d47`, 14:24–14:35 UTC | corpus `0 repo(s) differ` against `-29`; hold-out `0` against `-26`; micro `0 repo(s) differ`, 12 of 12 identical | fresh |
| The judgment's counts | `judgment/chain_diff.py`, `main` (`-base`) to n17 (`-copy`), N 40, twice | the counts equal §3, line for line. The two runs' samples shared 8 of 200 items; after sorting the sites, the samples were byte-identical | fresh analysis of saved runs |
| `install-check.sh` | the script, its output kept private | rc 1: 48 OK, 10 FAIL, 3 WARN. Every failure follows from the install's Neo4j being down | live, read-only |

The corpus's wall time, 301 s, is no timing measurement: the machine was not quiet.

**What the fresh runs show.** `main` at `0725d47`, which holds PR #27, gives the same corpus and hold-out items as
the baselines `-29` and `-26`. So a run of `0725d47` can stand for those baselines, which are not published. Its
micro set is identical to its own base, as a refactor's would be. That second check proves the protocol and its
scripts run as documented. It does not prove PR #27's changes right: the judgment of §3 did.

### What could not run

- **The after picture, the golden answers after, and their comparison with the before side.** The install's Neo4j
  has looped on restart since the reboot of 2026-10-26: 149 restarts when checked.
  - Its log says `Failed to read config: dbms.security.procedures.unrestricted declared multiple times`.
  - Its `neo4j.conf` lives in the container's own layer (the container was created on 2026-10-12, and the reinstall
    kept it). It holds 35 NUL bytes, and the setting 164 times.
  - The image's entrypoint appends the setting at each start, and the NUL bytes make its check read the file as
    binary.
  - The graph lives in the `neo4j_data` volume.
  - That the reboot wrote the NUL bytes is an inference. Recreating the container is a change to the install, and
    was not done.
- **The live build and freshness** could not be read: the `atlas` MCP is unhealthy while Neo4j is down.
- **`install-check.sh`'s output of 2026-10-24** stays unknown. The run above is today's, on a broken install.

The author recreated the container later that day, and the after side was then taken (§9).

**What to expect when the after side is taken.** The 10 snapshots' dry-runs by `main`'s code (`274d63b`) and the
branch's (`8ccf450`, whose `indexer/` tree is `0725d47`'s) are identical record by record. So the after picture
should equal the before one, but for the build and one more `IndexRun` per snapshot. A snapshot whose sha moved
since 2026-10-23 would differ for that reason alone. This is an expectation, not a result.

### A new judgment, as a test of the process

Five items, the first sample of each kind of `chain_diff.py`'s sorted draw from `main` to n17 (seed `20261021`,
N 40). Each was judged by reading, in the public repo at its pin, the declaration that decides the receiver's type.

- **This is not PR #27's historical judgment,** whose items are lost. These five were judged by an agent reading the
  source, for the author's review, and they feed no gate.
- **The sides:**
  - the base is `main` at `274d63b` (tree `b15e9385…`), with the image `927f5b4115c5`, inferred (§6 of the
    operational workflow);
  - the head is n17, `53a87c0`.

| # | Kind, repo, site | Was → now | What the source says | Verdict | The sources' term | Rule |
|---|---|---|---|---|---|---|
| 1 | `added`, elsa, `…/BulkDispatchWorkflows/Workflows/FruitWorkflow.cs:16`, `x.GetInput<string>(item)` | none → `ActivityExtensions.GetInput`, `unique-name` | `x =>` can only bind `WriteLine(Func<ExpressionExecutionContext, string?>)`, so `x` is an `ExpressionExecutionContext`; `item` is the `InputDefinition` that `WithInput<T>` returns; the method called is `GetInput<T>(InputDefinition)` of `extension(ExpressionExecutionContext)`. `ActivityExtensions.GetInput` extends `IActivity` and takes a string | **wrong** | a wrong guess by name (FP) | a typeless lambda parameter goes by name (H5-D16, "what stays lost"); the guess now reaches an extension block's method (H5-D17) |
| 2 | `changed`, elsa, `UserTaskRepositoryConformanceTests.cs:195`, `Repository.AddProjectionAsync(tagged)` | `FaultingUserTaskRepository.AddProjectionAsync`, `same-module` → `IUserTaskRepository.AddProjectionAsync`, `receiver-type` | `Repository` is `protected IUserTaskRepository Repository => Fixture.Repository;` in the base class; the interface has several implementations | right | a wrong guess by name removed | a capitalized member is that member (H5-D17) |
| 3 | `dropped`, smartstore, `DataExporterContext.cs:137`, `_globalTranslationEntities.Contains(entityName)` | three `same-module-ambiguous` `Contains` of repo collections → none | `_globalTranslationEntities` is a `string[]` | right | wrong guesses by name removed | an array is no value of its element's type (H5-D17) |
| 4 | `narrowed`, bitwarden, `ImportCiphersController.cs:58`, `model.Ciphers.Select(..).ToList()` | `inherited` edges to `CipherRequestModel` and `CipherWithIdRequestModel`, plus `ToCipherDetails` → only `ToCipherDetails` | `Ciphers` is a `CipherRequestModel[]`; `Select` and `ToList` are LINQ's | right | wrong `inherited` edges removed | the same |
| 5 | `widened`, umbraco, `MediaNavigationServiceTests.Sort.cs:64`, `MediaEditingService.SortAsync(..)` | `MediaEditingService.SortAsync`, `receiver-type` → `IMediaEditingService.SortAsync`, `receiver-type`, and `MediaEditingService.SortAsync`, `receiver-type-impl` | `MediaEditingService` is `protected IMediaEditingService MediaEditingService => …` in the base that another part of the `partial` class names; `MediaEditingService` is the interface's one implementation | right | a static call on a homonym class replaced by the member | a capitalized member, on a base another part declares (H5-D17) |

**Item 1 is new evidence.** `main` had no edge there, and the branch adds a wrong one. By H5-D14 a wrong item in a
case blocks a PR; by H2-D14 an item wrong only because it inherits a defect already categorized does not block the
rule. Which applies here, and whether a case should start from it, is the author's decision. Why the resolver chose
this `GetInput` among the repo's was not traced.

## 9. The after side, on 2026-10-26

Later that day the author deleted and recreated the install's Neo4j container, the change §8 left to the author, and
asked for the blocked steps to be resumed. They ran read-only: Cypher reads, the 27 calls through the MCP, and
`install-check.sh`.

- **Private outputs:**
  - the picture and the 27 answers went to `.local/indexer/pr27/after/`;
  - the logs, return codes and comparisons went to `post-merge-2026-10-26/`, with a `SHA256SUMS` of their own (60
    files).
- **The earlier copies were not written:** nothing in `before/`, `dry/` or `pre-merge/` changed, nor the folder's
  `SHA256SUMS`, which still checks 89 of 89.

### The install, before the picture

| Check | Result |
|---|---|
| Neo4j | the recreated container, 5.26.30: healthy, 0 restarts, no error in its log. Its `neo4j.conf` has no NUL byte, and the setting once |
| The databases | `atlas` online, and the default, so it is what `cypher-shell` and `foto.sh` read; `system` online |
| The data | the `neo4j_data` volume is on `/data`. `atlas` holds 16,030 nodes, 63,884 relationships, and 10 snapshots of 3 tenants, all at build `0.2.15+ccc54d86dbc7`. The before picture's labels add up to 16,020 nodes |
| The code | `~/.aidd/indexer/aidd_indexer` is identical to `main`'s. The running MCP container's Python hashes as `main`'s. `~/.aidd/docker-compose.yml` is identical to the repo's |
| The refresher | 10 cycles from 14:51 to 17:07 UTC, each `rc=0` with `0 of 10` snapshots changed or new |
| `install-check.sh` | 17:09–17:10 UTC: rc 0, 70 OK, 0 FAIL, 0 WARN, "All checks passed." |

The picture was taken between two cycles, from 17:08:19 to 17:08:40 UTC, after the cycle that ended at 17:07:56.

### The picture after, against the before one (V23)

- **The before side, checked first:** `SHA256SUMS` 89 of 89. The 15 lists and the golden digest equal §5's manifest.
- **`foto.sh after`:** rc 0, 15 lists, every row count equal to the manifest's.
- **13 of 15 lists are byte-identical,** `calls_edges` (23,682) and `imports_edges` (15,890) among them.
- **`snapshots.txt`** is identical with the build masked.
  - The 10 commit shas are those of 2026-10-23, so no snapshot moved.
  - The build went from `0.2.15+e3a6590925af` to `0.2.15+ccc54d86dbc7`.
- **`labels.txt`:** only `IndexRun` changed, by +6, +2 and +2 in the tenants that hold 6, 2 and 2 snapshots.
  - Through `HAS_RUN`, each snapshot has exactly one run started after the before picture.
  - Each of those runs was on 2026-10-24, between 06:36:48 and 06:37:12 UTC: `ok`, with no error, at the
    snapshot's sha.
- **`graph_vs_dry.py before after dry`:** rc 0. On all 10 snapshots, the graph before holds `main`'s dry-run and the
  graph after holds the branch's, with no edge added, removed or changed in strategy. "mismatching snapshots: 0".

The after picture's manifest, in §5's form:

- the 13 identical lists have §5's digests;
- `labels.txt` has 36 rows, `e35474befb2d4d60`;
- `snapshots.txt` has 10 rows, `50abb5de42984e5e`;
- `golden/` has 27 files, combined `255ccad3fa0f6eb7`.

**V23 passes.** Every list is identical but for the build and one more `IndexRun` per snapshot. That is exactly what
the dry-runs said: they are identical record by record (§8).

### The golden answers after (V25)

- **`golden.py`** with `golden-calls.json`, 17:10:26–17:10:29 UTC: rc 0, and the 27 calls reached the MCP.
  - 26 gave no error, and the write was refused, as before. The tool's guard refuses it before Neo4j is reached:
    "only read-only Cypher is allowed".
  - The graph held 16,030 nodes after.
- **`cmp` against `before/golden/`:** 22 of 27 are byte for byte the same.
- **The other 5, read with `json_paths_diff.py`:** `atlas_status`, Q5's `ref_diff` and three `repo_map` calls. They
  differ only in `indexer_build`, `indexed_at`, `age_min`, `last_finished_at`, `last_success_at` and
  `success_age_min`.
- **`atlas_status` after:** 10 snapshots, none `outdated`, and 3 tenants with `last_rc` 0, `stale` false and
  `changed` 0. That is the same as before, but for the build.

**V25 passes.** The answers are the same, leaving out the time and build fields.

- Q1–Q4 are among the 22 identical answers, and Q5 differs only in `indexed_at`. That is "✅ the same", as the sixth
  to tenth rounds count it.
- The 22-and-5 split is the ninth and tenth rounds'.
- That the before answers are the tenth round's state is inferred: they have its build, and their `indexed_at` is
  its reindex, 2026-10-22 at 18:43 UTC.

### The install after the merge (V24)

- **B4:** each snapshot was re-indexed once, on 2026-10-24, with no error. No refresh since has re-indexed one (§6,
  and the 10 cycles above).
- **B8:** `last_rc` 0, `stale` false and `changed` 0, after many cycles.
- **The install's code** equals `main`'s.
- **`install-check.sh`** passes on 2026-10-26, after the recreation. Its output for the 2026-10-24 reinstall stays
  unknown, since this run shows the install now, not then.

### What it means for PR #27

On the live install, PR #27 changed nothing in its 10 snapshots' graph but the build, as the dry-runs said. Like
PR #25's (the tenth round), the change reaches none of the calls in these snapshots' code.

This shows that the live graph matches the merged code. It does not judge the change. The change's effect was judged
on the corpus, in §3 and in §8's new judgment, and §8's wrong item 1 waits for the author.

### What is left

- **§7 items 4 and 5:** the eleventh golden round and PR #27's line in `docs/history.md`, in a docs PR.
- **§8's item 1:** the author's decision.
- **A backup** of `.local/indexer/pr27/`, which now holds `after/` too.
- **The tag moved.** `aidd-indexer:local` now names `9e6dd3753826`, not `f07550cbe2e2`.
  - Both were built at 2026-10-24 06:35:55 UTC, from the same layers and with the same config, but for compose's
    service label: `refresher` on one, `mcp-atlas` on the other.
  - How and when the tag moved is not known: Docker kept no event of it.
  - `micro.sh` keys its base by the tagged image's id, so its next run will build `micro/base-ed46a54b…-9e6dd3753826`.
    §8's base stays valid for `f07550cbe2e2`.

## 10. The wrong edge of §8, traced (2026-10-26)

§8's item 1 was judged wrong at the source but not traced. It was traced the same day, after the after side, with
dry-runs of the public corpus only. Nothing private is involved.

### The site, and what C# binds it to

elsa at `df0697f`, `…/Composition/BulkDispatchWorkflows/Workflows/FruitWorkflow.cs:16` (under
`core/test/component/Elsa.Workflows.ComponentTests/Scenarios/Activities/`):

```csharp
var item = builder.WithInput<string>("Item");
builder.Root = new WriteLine(x => $"Mixing {x.GetInput<string>(item)}");
```

- **`item`** is an `InputDefinition`, since `IWorkflowBuilder.WithInput<T>` returns one.
- **`x`** can only be an `ExpressionExecutionContext`. Of `WriteLine`'s constructors, only
  `WriteLine(Func<ExpressionExecutionContext, string?>)` takes a lambda of one parameter.
- **The method** is therefore `GetInput<T>(InputDefinition)`, a member of `ExpressionExecutionContextExtensions`'s
  `extension(ExpressionExecutionContext)` block.
- **The edge** went to `ActivityExtensions.GetInput(string)`, a member of an `extension(IActivity)` block. It has no
  type parameter, so C# cannot bind a call written with type arguments to it.

### The causal trace, in `main`'s code

The code is `0725d47`'s, whose `aidd_indexer` tree, `ed46a54b`, is n17's.

1. **The extraction** records the call with receiver `x`, no receiver type (a lambda parameter without a type, the
   gap H5-D16 leaves), type arguments, and one argument.
2. **`core/resolve.py`, the path of a receiver of unknown type:** a call written with type arguments may reach only
   the repo's extension methods. The language's `is_extension_method` filters the six `GetInput`s of the repo.
3. **`languages/csharp/symbols.py`, `is_extension_method`:** for a receiver of unknown type, it keeps an extension
   whose `this` may be anything, an interface included.
   - `IActivity` is an interface, so the method is kept.
   - `ExpressionExecutionContext` is a class, so the right method is dropped.
   - The other four `GetInput`s are no extensions.
4. **The one candidate left** is neither in the caller's file nor in its module, so it becomes `unique-name`.
5. **Nothing on that path** checks that a call written with type arguments needs a method that declares type
   parameters.

**Why the edge appears at n17.** Until n16, `type_facts.py` recorded only extensions with a `this` parameter. So an
extension block's methods had no extension fact, the filter kept nothing, and the site had no edge. n17 (`53a87c0`,
"a method of an extension block that is not static extends the block's receiver") recorded them, which is right for
C#. That made `ActivityExtensions.GetInput` pass the filter of step 3. Between n16 and n17, that function is the only
change in `aidd_indexer`.

### The comparisons

| Side | Run | The site's edges |
|---|---|---|
| `main` before PR #27 (`274d63b`) | `$C/micro-fresh/csn-n17-183358-base` | none |
| n1 to n16, one run per commit | `$C/micro-fresh/csn-n<k>-*-copy` | none |
| n17 (`53a87c0`) | `$C/micro-fresh/csn-n17-183358-copy` | `ActivityExtensions.GetInput`, `unique-name` |
| `main` (`0725d47`), a fresh dry-run on 2026-10-26 | a new folder under `$C/diag/` | the same. The run equals n17's record by record, in all 12 lists |
| A small repo of the same shape, with `4108aef`'s code (n16) | the same folder | no extension fact for the block's methods, and no edge |
| The same repo, with `0725d47`'s code | the same folder | the block's `IActivity` fact passes the filter, and the edge is `unique-name` |

- **Reading the site:** `indexer/scripts/judgment/site_edges.py elsa FruitWorkflow.cs:16 <run dirs>`.
- **Which run is which commit:** this comes from §2's table and from the runs' times, since the runs record no sha.
  The small repo, run with each commit's code, does not depend on that mapping.

### The attribution

| Question | Answer | Evidence |
|---|---|---|
| Who introduced the edge? | PR #27, at `53a87c0` | the comparisons above |
| Who introduced the cause? | older code | the filter of step 3 came in `5428eb1` (2026-10-16); no code ever checked a call's type arguments |
| Was it categorized? | in part | H5-D16 leaves a lambda parameter without a type to a guess by name or to none. H5-D17's fifth gap says an extension on an interface is still taken for a receiver outside the repo. Neither names the missing check of type arguments |

So the edge is a new defect, which the PR exposed through an older, uncategorized one. H2-D14 does not apply cleanly,
since H2-D14 covers a defect already categorized. **The semantic gate stood blocked** until a fix or the author's
acceptance.

### How far it reaches

The measure ran on the 15 C# repos of PR #27's protocol, through a copy of `main`'s code with one line added to
record the filter's input and output. The repository's code was not changed. Each flagged method's declaration was
then read again from the clone.

- **104 edges** go from a call written with type arguments to a method that declares no type parameter.
- **24** go to an extension block's method, the path n17 opened: elsa 20, smartstore 4. Of these, 11 are
  `x.GetInput<..>` sites and 6 `x.GetOutput<..>` sites in elsa.
- **80** go to an extension with a `this` parameter, which is older than PR #27: elsa 45, radarr 18, umbraco 9,
  smartstore 6, jellyfin 1 and notifo 1.
  - radarr's `Builder().Join<Blocklist, Movie>(..)` reaches `StringExtensions.Join(this IEnumerable<string>,
    string)`, where it should reach `BuilderExtensions.Join<TLeft, TRight>(this SqlBuilder, ..)`.
  - umbraco's `_serviceProvider.CreateInstance<TNotification>(msgObject, type)` is ambiguous between the generic
    method and the overload that takes a `Type`.

### The fix

H5-D18 fixes the cause by C#'s binding rules, in a PR of its own. Its code, its judgment and its validation are in
[H5-D18's evidence](h5-d18-validation-state.md). It is not merged.
