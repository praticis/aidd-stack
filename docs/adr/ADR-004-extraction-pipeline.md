# ADR-004 — The extraction as a map, a reduce and a per-file cache

**Status:** accepted on 2026-10-20, amended on 2026-10-21 (§2: the digest encodes a fact's kind) · **Date:**
2026-10-20 · **Phase:** 1 (H6) · **Records:** H6-D1–D6; the measurements in `docs/corpus-report.md`, "H6 baseline",
"H6 step 1" and "Batches by package"

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
- **Step 1** built the shape below on a throwaway branch (`h6/step1-proto`), with batches of files. It was identical
  to today on:
  - the tests;
  - the corpus;
  - the micro set;
  - 45 bench runs;
  - 6 real pushes.

  On 78 more pushes, it compared the cache's policies.
- **Step 2** measured batches of whole packages, each package scanned in its worker while its trees live. It was
  identical to today on the corpus, the micro set and 81 more bench runs, and it is the batch this ADR decides.

The hard part is **the second read**. An HTTP scan reads one file's tree and facts that other files produced at the
same time: its directory's constants, struct fields, functions and clients.

## Decision

### 1. The shape

```
discover ─▶ MAP 1, in workers, a batch of whole packages: per file, extract → a summary; then scan each file with
            its package's context while the trees live, recording each read with its answer; the trees die
         ─▶ REDUCE, in the parent, in file order: the directories' contexts, the repo view (later the TypeIndex);
            each early scan's reads checked against the whole repo
         ─▶ MAP 2, in workers: the scans the reduce did not accept, and the files of split packages: read the file
            again → scan it with its directory's context, read-only
         ─▶ compose, per language, from the scans' facts ─▶ resolve (CALLS) ─▶ write
```

- **Map 1** returns a summary per file:
  - the symbols, calls, imports and the language's facts;
  - what the file adds to its directory's context;
  - the file's early scan, when its whole package is in the batch: the scan's result, and each read with the answer
    it got.

  A summary holds values only, never a tree node or a node id.
- **The reduce** joins each file's additions in file order, under the context's rules:
  - one value, or none when two files disagree;
  - a union;
  - the last one wins.

  Then it builds the repo view and checks each early scan. A scan whose every read gets the same answer from the
  whole repo is final. It is the same check as a cache hit (§2).
- **Map 2 is the second read: option B, chosen by measurement (H6-D3, H6-D5).** It runs only what the early scan
  could not settle:
  - the 2.5–4.5 % of early scans that read another directory, or passed over every directory, and got another answer
    from the whole repo;
  - the files of a package that was split across batches;
  - on a warm run, the scans the cache could not reuse.

  The scanners keep reading one tree and a context, now read-only, so no scanner changes. Until H5's per-file index
  can be rebuilt from a parse, map 2 extracts the file again.
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
  manifest's directory, the files under a directory, which directory's constants, and the functions of a name that
  return a parameter across the repo. Each is asked again on the next run.

A scan never loops over the directories' contexts itself: a lookup across the repo is a question, with its answer
(ADR-006).

**An early scan is a map 2 entry** made with its package's context. Its reads are its dependencies, and the reduce
checks them as it checks a hit. One that holds is written to the cache like any other entry.

**Digests are taken over a canonical encoding:** dicts in order, sets sorted, dataclasses and `NamedTuple`s by field
with their kind's name, since two kinds of fact with equal values compare equal. They are never taken over pickle,
which shares equal objects by identity and so gave different bytes for equal values.

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
- **The batches (H6-D6):** whole packages, largest first, packed to a target size in lines (the total over
  16 × workers).
  - A package larger than the total over 4 × workers is split into batches of files, cut to the same size. Its
    files' scans go to map 2.
  - A warm run's misses rarely make whole packages, so their scans go to map 2 with the scans whose dependencies
    changed.
  - Step 1 cut files by size because a cut by count put the largest files in one batch, and the run waited on it.
    Whole packages keep that cut and spare 95.5–97.5 % of the scans the second read.
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
- **Every read goes through a recorded question.** The early scan's check found one that did not. Go's lookup of a
  method `x.M` that returns its parameter passed over every directory's context, and step 1's key did not cover it.
  - No push in the replay changed such a method, so the replay did not see it.
  - A fixture's early scan, checked against the whole repo, did.
  - 1.0–1.1 % of the scans make that pass.
  - The prototype records it as a read of every directory, which re-runs those scans on any change of context. The
    build asks it as a question instead (§2).

## Consequences

**Measured on the prototype** (full dry-runs, median of 3 rounds; cold rows give batches of files / of packages):

| | vikunja | mattermost | grafana |
|---|---|---|---|
| Today | 21.7 s, 636 MiB | 73.9 s, 2.3 GB | 130 s, 4.3 GB |
| 1 worker, cold | 28.0 / 22.9 s, 409 MiB | 91.6 / 81.4 s, 1.1 GB | 153 / 136 s, 2.3 GB |
| 2 workers, cold | 17.7 / 13.2 s | 55.4 / 48.6 s | 97.9 / 86.1 s |
| 4 workers, cold | 15.2 / 15.0 s | 31.3 / 28.6 s | 59.0 / 54–81 s |
| Warm, nothing changed (2 workers) | 3.2 s | 14 s | 33 s |
| Warm, after a real push (2 workers) | 3.3–4.2 s | 16–23 s | — |

- Batches of packages take 14–22 % less CPU than batches of files.
- Grafana at 4 workers ranged over 54–81 s in 6 rounds, with the machine's other load. Its cleanest round took
  54 s, against 58 s with batches of files.
- The warm rows are step 1's, with batches of files; a warm run sends its few misses through map 2 either way.

**What it costs:**

- **Map 2 still reads some files twice.** They are 2.5–4.5 % of the scans, but large files: on mattermost, 142 of
  them take 7 s. At 1 worker, they are most of what keeps the pipeline 4–10 % slower than today. H5's per-file
  index, rebuilt from a parse, makes them cheaper.
- **The warm floor is not the scans.** It is discovery, which reads and hashes every file, then reading the cache, the
  resolver and the write.
  - With git's blob ids (`git ls-tree -r`), a run would not read the files that did not change. That is to be
    measured.
- **The parent's serial work is the next limit.** At 4 workers, grafana spends 5 s in discovery and 16–23 s in the
  resolver and the output, close to 40 % of the run. Its garbage collection takes 1–3 s, so freezing the heap
  (`gc.freeze()`) changed nothing.
- **Memory:** grafana's 2.3 GB at 1 worker is the parent's: the summaries, the resolver and the output. That misses
  F1.13's 2 GB. Streaming the write belongs to F1.4's second half, after the write is measured.
- **D's tail is large Go packages.** At the p90, a push re-runs 438 scans on mattermost, against 108 under C:
  - the package's context includes all its files' facts;
  - adding a method to `server/channels/app` (168 scanned files) changes the context.

  ADR-005's typed facts and recorded questions shrink what the digest covers. With the facts cut to what scanners
  read, the p90 falls from 438 to 300. With every lookup recorded as a question, it falls to C's 108.
- **The scans must read nothing the key does not cover:** no env var, no clock, no file next door. Both the cache and
  the early scan's check rely on it, and the cold-equals-warm gate is the net.

## Alternatives considered

| Alternative | Why not |
|---|---|
| **A: resolve in the reduce.** The map emits path expressions with their references still open | 15 scanner functions read a value from another file, at 33 sites. Several of those reads decide control flow (Go's verb lists and field types, TS clients, Python routers), so each becomes a conditional item for the reduce to settle. That is a large change, with a high risk to "0 differ" |
| **C: key map 2 by the context entries the scan read** | 4 times fewer scans re-run at the p90. But it costs about 19 % of map 2 to track the reads, and a key of up to 9,605 entries per file. Kept as a refinement if refresh times show D's tail |
| **D for the whole repo** | Any constant or new file re-runs every scan: 969 of 972 on vikunja, at the median |
| **Batches of files, cut by size** (step 1) | Every scanned file is extracted twice. Whole packages scan 95.5–97.5 % of them in map 1: 14–22 % less CPU, and 12–25 % less time at 2 workers |
| **A queue or a broker** (Redis, Kafka, NATS), **Ray, Dask** | Each adds failure handling inside one snapshot (H6-D4). A queue of snapshots fits F3, a central server |
| **Free-threaded Python** | The summaries stay anyway, because they are what bounds memory and what the cache stores. To watch for when the bindings support it |
| **One file per cache entry; one file per snapshot** | See "The store" |
