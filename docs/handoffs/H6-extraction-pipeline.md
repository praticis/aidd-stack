# Handoff H6 — The extraction pipeline: partitioned, parallel and incremental

> Paste this file (or ask for `docs/handoffs/H6-extraction-pipeline.md` to be read) at the start of a new chat.
> Before anything else, the chat should read `AGENTS.md`, `docs/handoffs/H5-indexer-refactor.md` (this handoff is
> designed together with it), ROADMAP items F1.4 and F1.13, ADR-002 and ADR-003, and the "H5 baseline" section of
> `docs/corpus-report.md`.
>
> **State (2026-10-19):** a design draft. Nothing measured or built yet. It was born from H5's step 3 (`FileIndex`):
> the author asked for the step to get a handoff of its own, to explore partitioning the extraction, running it in
> parallel and joining the results, with an incremental cache per file as a requirement.

## Context in one paragraph

The indexer extracts a snapshot in one process and keeps every file's tree-sitter tree alive until the HTTP pass
ends, because that pass reads the trees again, after it has collected what crosses files. Memory grows with the repo
(grafana dies at 7.7 GB, F1.13) and time grows with it on one core (mattermost: 250 s in the H5 baseline). Every
refresh re-parses every file of a snapshot, even when a push changed one. H6 turns the extraction into a map over
batches of files, which runs in parallel and returns summaries, and a reduce per repo that joins them, with each
file's summary cached by its content. The graph it writes stays identical.

## The pipeline today

`cli.extract_tree`, then `core/integrations.extract_http`, then the resolver and the graph writer:

1. **discover:** list the files, find the modules and the stack;
2. **extract, per file:** parse, run the queries, build the symbols, calls, imports and the language's `file_facts`.
   The `FileExtractor` keeps the tree and the source;
3. **HTTP, first pass:** per directory, `collect_constants` and the `file_facts` go into a `PackageContext`; a
   `RepoView` gives the repo-level lookups;
4. **HTTP, second pass, per file:** the language's scanner reads the file's tree **and** its directory's
   `PackageContext`;
5. **compose, per repo:** what crosses files (mounts, inherited routes, wrappers) is composed from the summaries the
   scanners left;
6. **resolve:** `CALLS` from the call sites, the symbol table and the `file_facts`;
7. **write** the snapshot to Neo4j.

Steps 2 to 4 hold every tree at once. Step 4 is the only one that needs a tree and a fact from another file at the
same time: that is the "second read" below.

## Goals

1. **Memory bounded by the workers, not by the repo:** grafana indexes under a fixed ceiling (F1.13 suggests 2 GB).
2. **Time that scales with cores** where there are cores: a first index, a bootstrap, the corpus.
3. **Incremental:** a file whose content did not change is not parsed again (the refresher, branches that share most
   files with `main`).
4. **The same graph:** the corpus `0 repo(s) differ`, the hold-out identical, and a run with a warm cache identical to
   a cold one.
5. **No failure handling to build:** the failure semantics stay as today: a weird file is a warning, a broken repo
   fails its snapshot.

## The target shape

```
 files ── batches (modules, split or merged by size; only cache misses) ──┐
                                                                          ▼
 MAP, N worker processes:  parse → per-file index → summary   (the tree never leaves the worker)
                                                                          │
                                         cache: summary by (content, path, build, config)
                                                                          ▼
 REDUCE, per repo, sorted by path:  symbol table + type facts + package constants + mount graph
                                    → compose → CALLS → snapshot
```

## Why the summaries are not a cost of Python

A tree-sitter tree lives in the C memory of the process that parsed it. No transport moves it: a pipe, a queue or a
broker moves bytes. Whatever carries the work, the worker parses the file and returns a serialized summary. And the
summary is what H6 wants anyway: it is what bounds memory (Goal 1) and what the cache stores (Goal 3). Free-threaded
Python would let threads share trees, but keeping every tree is the memory problem, so the summaries stay either way.

## Open question 1 — the second read

The second HTTP pass needs a file's tree and its package's facts at the same time. Two ways, to be chosen by
measurement (H6-D3):

| | A. Resolve in the reduce | B. A second map that re-parses |
|---|---|---|
| How | the map emits, besides the facts, each path expression with its references still open (a constant, a parameter, a wrapper); the reduce evaluates them over the joined facts | map 1 emits the facts; the reduce joins them into a read-only context per package; map 2 re-parses each file that has an HTTP shape and runs today's scanners with that context |
| Parses per file | 1 | 2 for the files map 2 reads |
| Cacheable per file | all of the map | map 1 yes; map 2 only if its key includes what it read from the context (option C) |
| Change to the scanners | large: every rule that reads a value from another file emits a symbolic value instead | small: the scanners keep reading a tree plus a context |
| Risk to "0 differ" | higher | lower |

**C, a variant of B:** map 2 records which context entries it read (names and values), and its cache key includes a
hash of them. That is how incremental compilers memoize. It makes map 2 cacheable at the cost of tracking reads.

**D, B with coarse invalidation:** map 2's key includes a digest of the whole context it can read (its package's
context and the repo-level view), not of the entries it read. It is correct by construction as long as map 2 receives
nothing else, and it costs no read tracking. A change to one of the package's constants re-runs map 2 for the
package's files (the fanout), and a change elsewhere does not. It is what Sorbet does on an edit (see "Prior art").

**The resolve has the same question.** `resolve_calls` reads the repo's symbol table, so it is a reduce. A file's
`CALLS` can be cached the same four ways: recomputed in the reduce (A), recomputed per file in parallel (B), keyed by
the symbol table entries it read (C), or keyed by a digest of the symbol table, so that a push that changes no
declaration only re-resolves the files it changed (D).

**What to measure**, on a throwaway branch, on mattermost, vikunja, umbraco and ghost (the H5 profile set):

- the time to parse alone, per repo: the price of B's second parse;
- the share of files that have any HTTP shape: B only re-parses those;
- with a warm cache and one file changed: the time of A, B and C;
- the peak memory of each;
- the size of the summaries (A's are larger);
- how many lines of scanner code each one changes.

## Prior art

Researched on 2026-10-19: systems that partition code indexing, run it in parallel, or make it incremental.

| System | What it does | What it says about H6 |
|---|---|---|
| [GitHub's stack graphs](https://github.blog/open-source/introducing-stack-graphs) (precise code navigation) | Each file is analyzed alone, with tree-sitter, into a partial graph. References are not resolved at index time; at query time, a path search stitches the graphs of a commit's files | Option A at GitHub's scale. The stated reason: re-analyzing a file's dependents on every change is quadratic in the changed files, and per-file isolation makes it linear, with unchanged files reused across commits |
| [Sorbet](https://blog.jez.io/error-recovery-part-1/) (Stripe's Ruby type checker; [pipeline](https://github.com/sorbet/sorbet/blob/master/docs/namer-resolver-pipeline.md)) | Parallel per-file passes that touch no global state, one sequential step that enters the definitions into the global state, then parallel again with that state immutable and shared | Option B's shape. Sorbet tracks no dependencies: on an edit it checks whether global information changed. If not, it re-checks only the edited file; if so, it redoes everything except the cached parses. That is option D |
| [Meta's Glean](https://engineering.fb.com/2024/12/19/developer-tools/glean-open-source-code-indexing/) | Indexing jobs in parallel; facts in immutable databases. Incremental cost is O(changes), bounded by the fanout (the files that depend on a changed one), computed per language. Databases stack: a layer adds facts to the ones below or hides them | The fanout is what B, C and D compute. Stacked layers fit refs (a branch as a layer over `main`) and F1.4's second half (writing only the difference) |
| [Kythe](https://kythe.io/docs/schema/writing-an-indexer.html) (Google) | Per-compilation-unit indexers run in parallel; their entry streams are deduplicated and joined into serving tables | A map per unit, a dedup, a join |
| [GitHub code search](https://github.blog/engineering/architecture-optimization/the-technology-behind-githubs-new-code-search/) (Blackbird) | Shards by git blob id, so content duplicated across repos and branches is stored once; Kafka between the ingest services | A cache keyed by content; a queue between services, not inside one job |
| [Bazel's remote cache](https://blog.engflow.com/2024/05/13/the-many-caches-of-bazel/) (used by [Uber's Go monorepo](https://www.uber.com/blog/go-monorepo-bazel/)) | An action's key is a digest of every declared input (content, command, environment, tools); outputs go to a content-addressed store; misses come from undeclared inputs | H6's cache key. The pitfall "anything the map reads that is not in the key" is Bazel's hermeticity |
| rustc's incremental compilation and [Salsa](https://rust.googlesource.com/rust/+/f095de4bf105e92b035a7cd64c34bcce56b7cb78/src/tools/rust-analyzer/docs/dev/guide.md) (rust-analyzer) | Memoized pure queries, each with the dependencies it read; a query whose inputs did not change is reused without running ("red-green") | Option C. rust-analyzer only announced persistent caches in 2025: recording dependencies is the costly part |

No public material on code indexing was found from Spotify or YouTube. Uber's is the Go monorepo on Bazel with a
remote cache. Spotify's Backstage is a catalog (F2), not an indexer.

## Open question 2 — what runs the map

| Technology | What it would bring | What it costs in failures | Verdict |
|---|---|---|---|
| `concurrent.futures.ProcessPoolExecutor` (stdlib, `max_tasks_per_child`) | the map in parallel on one machine, with no new service | a worker that dies breaks the pool (`BrokenProcessPool`): retry the batch once in a new pool, then fail the snapshot, as a crash does today | the baseline to measure |
| Redis + a queue (BullMQ, which is Node.js with a partial Python port; RQ, Dramatiq, Celery) | work spread over machines, retries, a durable job state | one more service; delivery is at least once (a job can run twice); stalled jobs, visibility timeouts and a dead-letter queue to handle; and the payload is still a serialized summary | not for the map inside one snapshot. A queue of snapshots fits F3 (a central server, U4) |
| Kafka, NATS | streams between services | more operations than a queue | no |
| Ray, Dask | a distributed task graph in Python | a heavy runtime with its own scheduler and failure model | no |
| Free-threaded CPython (3.13t, 3.14t) | threads instead of processes, no serialization between map and reduce | the tree-sitter bindings must support it, and the summaries stay anyway | watch, and measure when the image's Python and the bindings allow |

**Where parallelism pays.** The refresher runs with 2 CPUs and 4 GB by default (`AIDD_REFRESH_CPUS`,
`AIDD_REFRESH_MEMORY`). There, two workers at most, and the cache is what makes a refresh fast. Parallelism pays on a
first index, a bootstrap and the corpus. The corpus already runs 3 repos at once (`corpus.sh --jobs`), so the
workers per repo times the jobs must fit the machine.

## Open question 3 — batches

A task per file costs more in sending than it gains. A batch per module (a Go package, a `.csproj`, a `package.json`
workspace) is the cut F1.13 proposed and the one SCIP indexes by (F1.1), but modules vary from 1 file to thousands.
To measure:

- the overhead per task (sending a batch and its summaries back), against its size in files and bytes;
- the imbalance at the end of a run, when one large batch keeps one worker busy;
- a strategy: split large modules and merge small ones to a target size in bytes, send the largest first (as
  `corpus.sh` does with repos), and only batch the files that missed the cache.

## Open question 4 — where the summaries live

- **Between a worker and the parent:** pickle, which the pool already uses.
- **The cache on disk**, two candidates:
  - **SQLite** (stdlib): one file, transactions, with the parent as the only writer;
  - **content-addressed files:** one per entry, written once through a temporary file and an atomic rename, with GC
    by directory.
- **The format:** pickle against msgpack, with or without zstd. Measure size and speed.
- **Where:** `~/.aidd/cache/` mounted into the refresher; `~/.cache/aidd-corpus/` for the corpus.

## The incremental cache: what guarantees it

The cache is a requirement (H6-D2). These are what make it safe:

1. **The cached unit is a pure function.** A file's summary depends only on its path, its bytes, its language, the
   indexer build and the extraction config that reaches the map (the conventions' patterns, the dispatch calls). It
   reads nothing from another file. Any rule that needs another file's fact belongs to the reduce, or to option B's
   map 2.
2. **The key** is a hash of the content (or the git blob sha, which `git ls-tree -r` gives for every path without
   reading the files) + the path + the language + `indexer_build()` + a hash of that config. `indexer_build()` already
   fingerprints the code that shapes the graph and the installed convention packages. The path is in the key because
   qualified names and modules depend on it; whether a summary can be made path-free, so that a moved file hits, is
   measured, not assumed.
3. **One namespace per build.** A new indexer build starts an empty namespace, and the old ones are garbage
   collected. A summary never outlives the code that made it.
4. **Write once, never update.** A crash leaves at most a missing entry, never a wrong one, and a read that fails is
   a miss.
5. **The reduce always runs**, in a fixed order (sorted by path). Its time is the floor of a warm run, so it is
   measured on its own.
6. **The net:** a warm run gives the same graph as a cold one, byte for byte, on the whole corpus. That becomes an item
   of the regression protocol. A test edits one file and checks that only that file's entry changes.
7. **The same file on two refs is one entry:** a feature branch that shares 99 % of its files with `main` costs only
   the files it changed, plus the reduce.
8. **The graph write still writes the whole snapshot.** Writing only the difference from the previous snapshot is
   F1.4's second half, after the write's share is measured.

## How H6 relates to H5

The order (H6-D1): design H6 now; H5 refactors toward it; then H6 is plugged in.

H5 builds pieces with H6's shape:

- **Step 4** (package facts) and **step 7** (typed facts): every fact is a typed value that can be serialized, with no
  tree node inside, because it travels from the map to the reduce and into the cache.
- **Step 5** (`TypeIndex`): built in the reduce, from type facts in the summaries, not from trees. ADR-005 records
  its API.
- **Step 6** (recognizers): run inside the map, seeing one file's tree, its per-file index, and the read-only context
  that option B or C gives. ADR-006 records the contract and the catalog.
- **H5's step 3** (`FileIndex`) becomes the per-file index inside the worker. It lives as long as the file, which
  answers the memory concern that stopped it.

## How it is measured

- Each measurement runs alone on the machine, one container per run, at least 3 runs interleaved across the repos so
  that a slow moment does not hit one repo only. The report gives the median and the range (min–max).
- Two options are compared only when their difference is larger than the run-to-run range. The corpus varies about
  28 % between runs of the same code, so a small effect is measured with a microbenchmark on the same trees.
- Correctness comes before speed: each prototype's output is compared with the baseline (`0 differ`), and a warm run
  with a cold one.

## Steps

| # | Step | Done when |
|---|---|---|
| 0 | Measure the pipeline as it is, with no code change: the time and the peak memory of each phase (discover, parse, extract, facts, constants, scanners, compose, resolve, write) on grafana, mattermost, vikunja, umbraco and ghost; the share of files with an HTTP shape; the files a typical push changes, from the corpus repos' history | the numbers in `corpus-report.md` ("H6 baseline") |
| 1 | Prototype the second read on a throwaway branch: A, B and C on one language first (Go: package constants, mounts across files), with a process pool and a cache | the table of "Open question 1" filled in; the branch is not merged |
| 2 | Decide with the author: the second read, the batches, the cache store. Write ADR-004 (the pipeline), then ADR-005 (types) and ADR-006 (recognizers) to match | the ADRs accepted |
| 3 | H5's steps 4, 7, 5 and 6, built toward the ADRs | as in H5 |
| 4 | Plug in the map, the reduce and the cache | the corpus cold, warm, and the baseline are identical; the hold-out identical |
| 5 | Validate at scale: grafana under the ceiling; the refresh time on a live install, cold and after a one-file push | the numbers in the corpus report and in the H5/H6 PR |

## Decisions made (2026-10-19, by the author)

- **H6-D1, the order:** design H6 now, refactor H5 toward the design, then plug H6 in, then the next items (the new
  hold-out, P2, SCIP).
- **H6-D2, the per-file incremental cache is a requirement**, not a bonus.
- **H6-D3, the second read is chosen by measurement**, technical and of performance: resolving in the reduce from the
  summaries, or a second map that re-parses.
- **H6-D4, a technology joins the compose only if it does not add failure handling to build:** what it gains on one
  side must not bring a large set of failures to handle on the other. "Open question 2" holds the analysis.

## Pitfalls

- **Determinism.** Workers finish in any order. The reduce sorts by path before joining, or the graph changes from
  run to run.
- **Node identity does not cross a process.** A summary that holds a tree node, or a node id, is a bug: ids are only
  valid inside one tree.
- **Starting workers.** macOS starts processes with `spawn`, and Linux in the image may use `fork` or `forkserver`.
  Each worker loads the grammars once, at start, and imports nothing that opens a connection.
- **Counting CPUs in a container.** `os.cpu_count()` gives the host's cores, not the container's quota. The worker
  count comes from the cgroup limit or a setting.
- **Nested parallelism.** `corpus.sh` runs repos in parallel; workers per repo times jobs must fit the machine, or
  both slow down.
- **A cache that is wrong is worse than none.** Anything the map reads that is not in the key (an env var, a file
  next door, the clock) makes a warm run differ from a cold one. The cold/warm comparison on the corpus is the net.

## Constraints and conventions

The same as H5's: one-line conventional commits with no body and no attribution; everything in English; no tenant or
private project names; an LLM is never the parser; temporary files in the session scratchpad; no Python run inside
the corpus clones.

## Expected deliverables

- The "H6 baseline" measurements and the prototype's table, in `corpus-report.md`.
- ADR-004 (the pipeline), ADR-005 (the type service) and ADR-006 (recognizers and the catalog), accepted by the
  author.
- The map, the reduce and the cache in the indexer, with the corpus cold, warm and the baseline identical.
- grafana indexed under the memory ceiling; the refresh time on a live install, cold and after a one-file push.
- ROADMAP: F1.13 checked, and F1.4's first half (the per-file cache) checked.
