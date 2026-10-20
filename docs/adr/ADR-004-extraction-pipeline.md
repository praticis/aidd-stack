# ADR-004 — The extraction as a map, a reduce and a per-file cache

**Status:** proposed · **Date:** 2026-10-20 · **Phase:** 1 (H6) · **Records:** H6-D1–D6; the measurements in
`docs/corpus-report.md`, "H6 baseline" and "H6 step 1"

## Context

`extract_tree` extracts a snapshot in one process:

- it keeps every file's tree and text until the HTTP pass ends, because that pass reads the trees again after it
  has collected what crosses files;
- every refresh extracts every file again, even when a push changed one.

H6 asks for four things (`docs/handoffs/H6-extraction-pipeline.md`):

1. memory bounded by the workers, not by the repo;
2. time that scales with cores;
3. a per-file cache (H6-D2);
4. the same graph.

What the measurements found:

- **Step 0** found the memory in the trees: 3.7 of grafana's 4.2 GB. Extraction is Python, and parsing is only 15–18 %
  of it. A push touches 1 to 3 files at the median.
- **Step 1** built the shape below on a throwaway branch (`h6/step1-proto`). It was identical to today on:
  - the tests;
  - the corpus;
  - the micro set;
  - 45 bench runs;
  - 6 real pushes.

  On 78 more pushes, it compared the cache's policies.

The hard part is **the second read**. An HTTP scan reads one file's tree and facts that other files produced at the
same time: its directory's constants, struct fields, functions and clients.

## Decision

### 1. The shape

```
discover ─▶ MAP 1, in workers: per file, extract → a summary; the tree dies in the worker
         ─▶ REDUCE, in the parent, in file order: the directories' contexts, the repo view (later the TypeIndex)
         ─▶ MAP 2, in workers: per scanned file, read the file again → scan it with its directory's context, read-only
         ─▶ compose, per language, from the scans' facts ─▶ resolve (CALLS) ─▶ write
```

- **Map 1** returns a summary per file:
  - the symbols, calls, imports and the language's facts;
  - what the file adds to its directory's context.

  A summary holds values only, never a tree node or a node id.
- **The reduce** joins each file's additions in file order, under the context's rules:
  - one value, or none when two files disagree;
  - a union;
  - the last one wins.

  Then it builds the repo view.
- **Map 2 is the second read: option B, chosen by measurement (H6-D3, H6-D5).** The scanners keep reading one tree and
  a context, now read-only, so no scanner changes.
  - Until H5's per-file index can be rebuilt from a parse, map 2 extracts the file again.
  - Map 2 reads every file a scanner reads, 53–66 % of the parsed files. Whether a file has an HTTP shape is known only
    after its scan.
- **compose and the resolver stay in the reduce.** With its index, the resolver takes 0.4–8.7 s, so its `CALLS` need
  no cache per file.

### 2. The cache

**Map 1's key** is the file's path, language, content hash and module, under a namespace that changes with:

- the indexer's build (`indexer_build()`);
- the extraction's config: the conventions' patterns and the dispatch calls.

**Map 2's key is option D, cut per package.** It is map 1's key plus the digest of the file's directory context. The
digest covers only what scanners read: a function's name and id, for instance, but not its lines.

Each map 2 entry also records the scan's other dependencies. The entry is a hit only while each one still holds:

- the digest of each other directory whose context the scan looked up;
- the directories that define a class the scan named;
- each question the scan asked of the repo's structure, with its answer. The questions are an import's target, a
  manifest's directory, the files under a directory, and which directory's constants. Each is asked again on the next
  run.

**Digests are taken over a canonical encoding:** dicts in order, sets sorted, dataclasses by field. They are never
taken over pickle, which shares equal objects by identity and so gave different bytes for equal values.

**ids in a summary are relative to the snapshot,** and the reduce stamps the tenant, the repo and the ref. Then one
entry serves every ref of a repo, as cache item 7 of the handoff asks. The prototype kept the ref in the key; this part
is still to build.

**An entry is written once and never updated.** A read that fails is a miss. A new build starts an empty namespace,
and the old namespaces are collected.

### 3. The store

**SQLite**, with one database per repo:

- all the repo's refs share it;
- the parent alone writes it, in one transaction per run (`INSERT OR IGNORE`, WAL mode).

Measured on mattermost's 13 thousand entries (21 MiB):

| Where | One file per entry | SQLite | One file per snapshot |
|---|---|---|---|
| Docker Desktop's bind mount: fill / read all / a push | 102 / 1.7–33 / 2.5 s | 1.5 / 0.2 / 0.1 s | 0.02 / 0.02 / 0.05 s |
| The container's own disk | 0.48 / 0.15 / 0.15 s | 0.18 / 0.09 / 0.09 s | 0.01 / 0.01 / 0.02 s |

Why SQLite and not the others:

- **One file per snapshot is faster,** but it stores a file shared by two refs twice and rewrites everything on each
  run.
- **SQLite keeps one entry per file across every ref,** and a crash leaves the database consistent.
- **One database per repo keeps one writer at a time.** The refresher already runs one refresh at a time
  (`refresh_lock`), and the corpus runs one container per repo.

**Where the cache lives:**

- the refresher's cache goes in a named Docker volume, not a bind mount of the host's disk;
- the corpus keeps its cache under `~/.cache/aidd-corpus/`;
- CI keeps it in the Actions cache.

### 4. The workers

- **The pool:** `concurrent.futures.ProcessPoolExecutor`, started with `fork` in the image (Linux). Each worker loads
  the grammars once and opens no connection.
- **The count:** a setting, `AIDD_WORKERS`. By default it follows the container's CPU quota (cgroup), not
  `os.cpu_count()`; the refresher runs on 2 CPUs. In the corpus, the workers times the jobs must fit the machine.
- **The batches (H6-D6):** files, largest first, cut to a target size in lines (the total over 16 × workers).
  - A module is not a unit, because the reduce joins the contexts and a package can be split.
  - A cut by count put the largest files in one batch, and the run waited on it.
- **The order:** results are put back in file order, and nothing depends on the order workers finish.
- **Failures** follow today's rules (H6-D4):
  - a weird file is a warning;
  - a worker that dies (`BrokenProcessPool`) gets its batch retried once in a new pool. If that fails too, the
    snapshot fails, as a crash does today.

### 5. What keeps it right

- **A gate (H7's slice 5):** a warm run equals a cold one, record by record, on the corpus and the micro set.
- **A unit test:** edit one file, and check that only that file's entries change, plus the entries of the scans that
  depended on it.
- **The step 1 replay** (`indexer/scripts/h6-step1/` on `h6/step1-proto`) checks any new key against real pushes. A
  key that hits while the scan differs is a defect.

## Consequences

**Measured on the prototype** (full dry-runs, median of 3 rounds):

| | vikunja | mattermost | grafana |
|---|---|---|---|
| Today | 21 s, 658 MiB | 73 s, 2.3 GB | 132 s, 4.3 GB |
| 4 workers, cold | 15 s | 31 s | 60 s |
| 1 worker, cold | 26 s, 408 MiB | 92 s, 1.1 GB | 155 s, 2.3 GB |
| Warm, nothing changed | 3.2 s | 14 s | 33 s |
| Warm, after a real push | 3.3–4.2 s | 16–23 s | — |

**What it costs:**

- **Map 2 extracts again:** +20–25 % at 1 worker. The scanners tie symbols to nodes, so a parse is not enough. H5's
  per-file index, rebuilt from a parse, removes most of it.
- **The warm floor is not the scans.** It is discovery, which reads and hashes every file, then reading the cache, the
  resolver and the write.
  - With git's blob ids (`git ls-tree -r`), a run would not read the files that did not change. That is to be
    measured.
- **Memory:** grafana's 2.3 GB at 1 worker is the parent's: the summaries, the resolver and the output. That misses
  F1.13's 2 GB. Streaming the write belongs to F1.4's second half, after the write is measured.
- **D's tail is large Go packages.** At the p90, a push re-runs 438 scans on mattermost, against 108 under C:
  - the package's context includes all its files' facts;
  - adding a method to `server/channels/app` (168 scanned files) changes the context.

  ADR-005's typed facts and recorded questions shrink what the digest covers. With the facts cut to what scanners
  read, the p90 falls from 438 to 300. With every lookup recorded as a question, it falls to C's 108.
- **The scans must read nothing the key does not cover:** no env var, no clock, no file next door. The cold-equals-warm
  gate is the net.

## Alternatives considered

| Alternative | Why not |
|---|---|
| **A: resolve in the reduce.** The map emits path expressions with their references still open | 15 scanner functions read a value from another file, at 33 sites. Several of those reads decide control flow (Go's verb lists and field types, TS clients, Python routers), so each becomes a conditional item for the reduce to settle. That is a large change, with a high risk to "0 differ" |
| **C: key map 2 by the context entries the scan read** | 4 times fewer scans re-run at the p90. But it costs about 19 % of map 2 to track the reads, and a key of up to 9,605 entries per file. Kept as a refinement if refresh times show D's tail |
| **D for the whole repo** | Any constant or new file re-runs every scan: 969 of 972 on vikunja, at the median |
| **A queue or a broker** (Redis, Kafka, NATS), **Ray, Dask** | Each adds failure handling inside one snapshot (H6-D4). A queue of snapshots fits F3, a central server |
| **Free-threaded Python** | The summaries stay anyway, because they are what bounds memory and what the cache stores. To watch for when the bindings support it |
| **One file per cache entry; one file per snapshot** | See "The store" |
