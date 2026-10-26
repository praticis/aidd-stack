# The indexer's validation resources: a catalog

> Every script, document and data source that the procedures of [the inventory](validation-inventory.md) use: where
> it lives, where it came from, what it needs, and whether it can be versioned. Written on 2026-10-24, on `main` at
> `0725d47`.
>
> **"Persisted" means in this repository's working tree, not committed yet.** No commit, push or PR was made.
>
> The paths `$S` (the previous session's scratchpad, volatile), `$C` (`~/.cache/aidd-corpus`) and `$T` (the previous
> session's transcript) are defined in the inventory, under "How to read this document".

## How to read the tables

| Field | Values |
|---|---|
| **Nature** | **original:** copied from `$S` byte for byte. **adapted:** copied from `$S` with the edits listed in §7. **reconstructed:** rebuilt from `$T`, since its file was lost. **new:** written on 2026-10-24. **derived:** a summary of other sources. **reference:** outside the repository |
| **State** | **persisted:** in the working tree. **local:** in `.local/`, which git ignores: private, on this disk only, with no backup. **external:** durable, outside the repository. **volatile:** only under `/private/tmp`, which a reboot empties. **not found:** in no recovered source, with the grounds in §5. **not verifiable** |
| **Checked** | **integrity:** `diff` against its source. **syntax:** `bash -n` or `ast.parse`. **shape:** [`shape.sh`](../../indexer/scripts/protocol/shape.sh) `--c901`, every function ≤ 9. **reproduced:** re-run on saved inputs, giving the saved output byte for byte (what the later documents call "re-derived": it checks the script, and measures nothing again). **smoke:** re-run once on real inputs, with no saved output to compare. **not run:** never executed here |
| **Safety** | **safe:** it holds no private name, path or secret. **sanitized:** made safe by an edit in §7. **private:** it must not be versioned |
| **Used by** | the procedure ids of the inventory (V01–V31) |

Every Python script below runs with `python3 -I`, on our own outputs only, or in the indexer's image where it says
so. None of them is run by CI. With the 29 Python files of §2 in the tree, the shape ratchet
(`shape.py --against main`, run on 2026-10-24) gives "0 new or worse over a target". The largest complexity among
them is 7.

## 1. Reproducibility at a glance

| Procedure | What reproduces it from the repository | What it also needs outside the repository | What is still missing |
|---|---|---|---|
| V01–V04, V07 | the CI scripts | the clones and the saved baselines in `$C` (a baseline is recomputed from its commit when missing) | — |
| V05, V06, V16 | the tests | — | — |
| V08, V09 | `gates.py`; [`checks/`](../../indexer/scripts/checks/) for the offline checks | — | a format for verdicts (H7-D2) |
| V10, V13 | `micro.sh`, [`protocol/`](../../indexer/scripts/protocol/) | `$C`; a micro base for the base's tree and image | — |
| V11 | [`judgment/chain_diff.py`](../../indexer/scripts/judgment/chain_diff.py) and its viewers | two directories of micro dry-runs | the per-site case attribution (`why_a.py`, §5), which `edges_join.py`, `kinds.py`, `cases.py` and `view.py` read |
| V12 | the `ext_*.py` and `*loss*`/`lost_ext.py` scripts in [`judgment/`](../../indexer/scripts/judgment/) | two directories of micro dry-runs, and the clones | — |
| V14 | [`probes/`](../../indexer/scripts/probes/) | the indexer's image | — |
| V15 | `shape.py`, [`protocol/shape.sh`](../../indexer/scripts/protocol/shape.sh) | network, for `pip install ruff` in the container | — |
| V17 | [`protocol/time-alone.sh`](../../indexer/scripts/protocol/time-alone.sh) | two worktrees, `$C`, a machine with no other load | — |
| V18 | — (never merged, by decision) | the reference branch `h6/step1-proto` (`indexer/scripts/h6-step1/`), run from a worktree of it; the draft release `h6-step1-results` | its scripts target the prototype's code, not `main`'s (§2, "V18") |
| V19 | [`checks/walkcmp.py`](../../indexer/scripts/checks/walkcmp.py) (the walk) and [`checks/dump.py`](../../indexer/scripts/checks/dump.py) (C#'s type facts) | the clones in `$C/repos`; the two codes to compare | Go's, `tools/list`'s and the ASTs' checks (§5) |
| V20, V27 | `mcp-it.sh`, [`checks/mutate.sh`](../../indexer/scripts/checks/mutate.sh) | Docker | — |
| V21, V22, V24 | [`live/`](../../indexer/scripts/live/) | the live install; the snapshots' clones; `~/.aidd/atlas.yaml` | — |
| V23 | [`live/foto.sh`](../../indexer/scripts/live/foto.sh); [`live/graph_vs_dry.py`](../../indexer/scripts/live/graph_vs_dry.py) for `CALLS` | the live install; for PR #27, the before picture in `.local/indexer/pr27/` | a dedicated script that compares two pictures (§5) |
| V25 | [`live/golden.py`](../../indexer/scripts/live/golden.py) | the live MCP; the private calls file, for PR #27 `.local/indexer/pr27/``golden-calls.json` (§4) | — |
| V26, V28 | the workflow, `gates.py` | — | the "one cause per commit" check (H7 slice 2) |
| V29 | [`recovery/`](../../indexer/scripts/recovery/) | `$T`, the transcript | — |
| V30, V31 | practice; [`protocol/micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh) | — | a mechanical check |

## 2. Scripts persisted under `indexer/scripts/`

The CI's own scripts stay where they were, in `indexer/scripts/`, and are listed in its
[README](../../indexer/scripts/README.md). The folders below hold the local tools.

### `protocol/`: the regression protocol, run locally

| Name | Origin | Nature | Purpose | Needs | State, checked | Safety | Used by |
|---|---|---|---|---|---|---|---|
| [`protocol.sh`](../../indexer/scripts/protocol/protocol.sh) | `$S/h5/protocol.sh` | adapted | the corpus, the hold-out and the micro set on the tree, or on a worktree (`AIDD_REPO`) | the image `aidd-indexer:local`; `$C/repos`; the baselines `-29` and `-26` in `$C/runs` (`AIDD_BASELINE`, `AIDD_HOLDOUT_BASELINE`); a micro base; `micro-fresh.sh` | persisted; integrity, syntax; not run | sanitized | V07, V10, V13 |
| [`micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh) | `$S/h5/micro-fresh.sh` | adapted | `micro.sh`'s comparison through fresh paths, around Docker Desktop's stale mounts | the image; `$C/micro/base-<tree>-<image>` (from `micro.sh --base-only`) | persisted; integrity, syntax; not run | sanitized | V10, V13, V30 |
| [`shape.sh`](../../indexer/scripts/protocol/shape.sh) | `$S/h5/shape.sh` | adapted | `shape.py --against REF` in the image, with ruff; `--c901 PATH…` lists complexities | the image; network for `pip install ruff==0.17.1` | persisted; **smoke: run on 2026-10-24, "0 new or worse"** | sanitized | V15 |
| [`time-alone.sh`](../../indexer/scripts/protocol/time-alone.sh) | `$S/h5/time-csn.sh` | adapted | the corpus's wall time on two worktrees, then full dry-runs of four large C# repos (`AIDD_TIME_REPOS`), with the resolver's time | two worktrees; the image; `$C`; no other load | persisted; integrity, syntax; not run | sanitized | V17 |

### `judgment/`: the micro graph judged by case, and the loss analysis

All from `$S/h5/why/` and `$S/h5/ext/`. Each reads micro dry-runs (`<repo>.json.gz`, as `micro.sh` and
`micro-fresh.sh` leave them) and needs no image unless it says so.

| Name | Nature | Purpose | Needs | State, checked | Safety | Used by |
|---|---|---|---|---|---|---|
| [`edges_lib.py`](../../indexer/scripts/judgment/edges_lib.py) | adapted (docstring) | a run's `CALLS` per site, shared by the others | — | persisted; integrity, syntax; reproduced through `chain_diff.py` | safe | V11, V12 |
| [`chain_diff.py`](../../indexer/scripts/judgment/chain_diff.py) | adapted (2026-10-26: the sites sorted before the draw, §7) | changed sites by kind and edges by class, with seeded samples (seed `20261021`) on stderr | two run directories; the repos to compare | persisted; **reproduced** `$S/h5/why/out/n17.txt` and `main-n17.txt` byte for byte: its counts, on stdout. The samples on stderr were not compared. **Run on 2026-10-26** from `main` to n17: the counts equal the evidence's §3; before the fix two runs' samples shared 8 of 200 items, after it they are byte-identical ([the benchmark protocols](benchmark-and-statistical-protocols.md), §8) | safe | V11 |
| [`show.py`](../../indexer/scripts/judgment/show.py) | original | each sample with its source line | `$C/repos`; samples on stdin | persisted; integrity, syntax; not run | safe | V11 |
| [`samples_view.py`](../../indexer/scripts/judgment/samples_view.py) | original | `chain_diff.py`'s samples with their source lines, shortened | a samples file; `$C/repos` | persisted; integrity, syntax; not run | safe | V11 |
| [`site_edges.py`](../../indexer/scripts/judgment/site_edges.py) | original | the edges of given sites across several runs | run directories | persisted; integrity, syntax; not run | safe | V11, V12 |
| [`edges_join.py`](../../indexer/scripts/judgment/edges_join.py) | original | changed edges by the case each site has, with samples per case and repo | **a per-site attribution file (`WHY.jsonl`) from `why_a.py`, not persisted** | persisted; integrity, syntax; not runnable without its input | safe | V11 |
| [`kinds.py`](../../indexer/scripts/judgment/kinds.py) | original | changed sites by case and kind; what dropped edges had | the same attribution file | persisted; integrity, syntax; not runnable without its input | safe | V11 |
| [`cases.py`](../../indexer/scripts/judgment/cases.py) | original | the attribution file's counts per case, repo and way | the same attribution file | persisted; integrity, syntax; not runnable without its input | safe | V11 |
| [`view.py`](../../indexer/scripts/judgment/view.py) | original | for a Go site, the declaration the answer reads and the signatures of a called function | the image, with `/code` and `/repos` mounted; Go's `locals.FUNCTIONS` and `_DECLARATIONS` (both on `main`); the attribution file | persisted; integrity, syntax; not runnable without its input | safe | V11 |
| [`ext_sites.py`](../../indexer/scripts/judgment/ext_sites.py) | adapted (import path) | the sites that lost an edge to an extension method, with what `this` takes and what the site has now | two run directories | persisted; **smoke: run on 2026-10-24 on two repos** | sanitized | V12 |
| [`ext_back.py`](../../indexer/scripts/judgment/ext_back.py) | adapted (import path) | which of those losses a later run has again | `ext_sites.py`'s output; a run directory | persisted; integrity, syntax; not run | sanitized | V12 |
| [`ext_judge.py`](../../indexer/scripts/judgment/ext_judge.py) | adapted (import path; 2026-10-26: the sites sorted before the draw) | changed sites by class of extension gained, with seeded samples and source lines | two run directories; `$C/repos` | persisted; **run on 2026-10-26** twice on PR #25's runs: identical output after the fix | sanitized | V12 |
| [`this_kind.py`](../../indexer/scripts/judgment/this_kind.py) | adapted (import path) | for each `unique-name` edge gained to an extension, whether its `this` takes any value | two run directories; `$C/repos` | persisted; integrity, syntax; not run | sanitized | V12 |
| [`ext_loss.py`](../../indexer/scripts/judgment/ext_loss.py) | original | per repo, the extension-method edges lost and what the sites have now | two run directories | persisted; integrity, syntax; not run | safe | V12 |
| [`lost_ext.py`](../../indexer/scripts/judgment/lost_ext.py) | original | the sites that lost an edge into a file with C# 14 `extension(…)` blocks | two run directories; `$C/repos` | persisted; integrity, syntax; not run | safe | V12 |

### `probes/`: before the cases

| Name | Origin | Nature | Purpose | Needs | State, checked | Safety | Used by |
|---|---|---|---|---|---|---|---|
| [`probe.py`](../../indexer/scripts/probes/probe.py) | `$S/h5/probe/probe.py` | original | a small C# repo from a JSON dict of files, and the `CALLS` out of its `*Run` methods | the image (`aidd_indexer.cli.extract_and_resolve` and `RepoInfo`, both on `main`) | persisted; integrity, syntax; not run | safe | V14 |
| [`tree.py`](../../indexer/scripts/probes/tree.py) | `$S/h5/probe/tree.py` | original | a C# snippet's tree, named nodes with their fields | the image (the grammars) | persisted; integrity, syntax; not run | safe | V14 |

### `live/`: the live install, before and after a merge

Every script here reads the live install only. Their outputs name the install's tenants and repositories, so the
output directory must be outside the repository.

| Name | Origin | Nature | Purpose | Needs | State, checked | Safety | Used by |
|---|---|---|---|---|---|---|---|
| [`foto.sh`](../../indexer/scripts/live/foto.sh) | `$S/val/foto.sh` | original | the graph's picture: 15 sorted lists, by read-only Cypher | the stack's `aidd-core-neo4j` container | persisted; integrity, syntax; not run here. **Run on 2026-10-26 on the live install,** after the Neo4j container was recreated: rc 0, 15 lists, the before picture's row counts (the PR #27 evidence, §9) | safe (its output is private) | V21, V23 |
| [`golden.py`](../../indexer/scripts/live/golden.py) | `$S/val/golden.py` | **new**: a sanitized rewrite (§7) | the golden calls through the MCP's HTTP, one JSON answer each | the live MCP (`localhost:3005`); a private calls file: for PR #27, `.local/indexer/pr27/``golden-calls.json` (§4) | persisted; **run on 2026-10-26 against a local stand-in for the MCP, not the live one** (which was down): the answers' shapes read as the original's code reads them, two runs byte-identical; its exit code changed (§7). **Later that day, against the live MCP:** rc 0, 27 of 27 calls reached, 22 answers byte-identical to the before ones | safe | V25 |
| [`golden-calls.example.json`](../../indexer/scripts/live/golden-calls.example.json) | — | new | the calls file's shape: one call of each of the 11 tools, plus the refused write, with neutral names | — | persisted; parsed as JSON | safe | V25 |
| [`dryrun-live.sh`](../../indexer/scripts/live/dryrun-live.sh) | `$S/val/dryrun-live.sh` | original | each snapshot exported at its sha and dry-run by two codes | the before picture's `snapshots.txt`; clones at `$HOME/workspace/<tenant>/<repo>`; `~/.aidd/atlas.yaml`; the image. Its first argument is not used | persisted; integrity, syntax; not run here | safe (its output is private) | V22 |
| [`dry_sections.py`](../../indexer/scripts/live/dry_sections.py) | `$S/val/dry_sections.py` | adapted (2026-10-26: the endpoints' key, §7) | the two dry-runs of each snapshot, section by section, with snapshots as numbers | `dryrun-live.sh`'s output | persisted; **reproduced** `$S/livecsn/dry_sections.txt`, and again on 2026-10-26 from the `.local` copies, before the fix; after it, the 10 snapshots still identical | safe | V22 |
| [`graph_vs_dry.py`](../../indexer/scripts/live/graph_vs_dry.py) | `$S/val/graph_vs_dry.py` | adapted (2026-10-26: the exit code, §7) | the live graph's `CALLS` against both dry-runs, by the writer's merge key | two pictures; the dry-runs | persisted; **reproduced** `$S/livecsn/graph_vs_dry.txt`, and again on 2026-10-26 from the `.local` copies; its new exit code checked on a synthetic mismatch (1) and on PR #27's data (0). Later that day, on PR #27's before and after pictures: rc 0, 0 mismatching | safe | V21 |
| [`dry_compare.py`](../../indexer/scripts/live/dry_compare.py) | `$S/val/dry_compare.py` | adapted (docstring) | the dry-runs per section, and `main`'s against the live counts. **It prints each snapshot's tenant and repo:** for local use only | the dry-runs; a picture | persisted; integrity, syntax; not run | safe (its output is private) | V21, V22 |
| [`json_paths_diff.py`](../../indexer/scripts/live/json_paths_diff.py) | `$T`, 2026-10-21 21:29 UTC (a heredoc) | reconstructed | the leaf paths that differ between two JSON answers; values shown only for numbers and a few keys, so names stay out | two JSON files | persisted; syntax; not run. **Run on 2026-10-26** on PR #27's five answers that differ: only time and build paths, and no name in its output | safe | V22, V25 |
| [`pre-merge.sh`](../../indexer/scripts/live/pre-merge.sh) | `$S/val/live-csn.sh` | adapted | the read-only check before a merge: the picture, the golden answers, the dry-runs, then the two comparisons | `LIVE_DIR/main_src/indexer` and `head_src/indexer`, copies of the two codes, checked against `git ls-files` with `shasum` (the commands are in `$T`, 2026-10-22 17:44 UTC); the private calls file | persisted; integrity, syntax; not run | sanitized | V21–V23, V25 |

### `checks/`: offline checks the CI does not run, and the writer's mutation test

| Name | Origin | Nature | Purpose | Needs | State, checked | Safety | Used by |
|---|---|---|---|---|---|---|---|
| [`a2_gabaritos.py`](../../indexer/scripts/checks/a2_gabaritos.py) | `$T`, 2026-10-19 02:07 UTC (Write) | reconstructed, adapted (docstring) | every change between two sets of expected lists, classified (PR #5's A2) | `corpus_metrics` and `aidd_indexer` importable: in the image, `PYTHONPATH=/src:/src/scripts` | persisted; syntax; not run | safe | V02, V09 |
| [`a4_compare.py`](../../indexer/scripts/checks/a4_compare.py) | `$T`, 2026-10-19 02:09 UTC (Write, then an Edit) | reconstructed, adapted (docstring) | `main`'s run against the head's, both scored by today's lists (A4). The Edit `recover.py` reported as not applied is the transcript's second copy of one that did, so this is the last version | as above | persisted; syntax; not run | safe | V08 |
| [`a5_chain.py`](../../indexer/scripts/checks/a5_chain.py) | `$T`, 2026-10-19 02:08 UTC (Write) | reconstructed, adapted (docstring) | no expected pair that any earlier baseline found is missed at the end (A5); CI has no equivalent | as above; `$C/runs` | persisted; syntax; not run | safe | V08 |
| [`mutate.sh`](../../indexer/scripts/checks/mutate.sh) | `$T`, 2026-10-22 (a heredoc, then a `sed -i`) | reconstructed, adapted | `mcp-it.sh` on a copy of the tree with one mutation of the writer (`core/graph.py`); prints the failing tests. The three mutations of 2026-10-22 are in §3, and each anchor still matches once on `main` | Docker; it starts a throwaway Neo4j | persisted; syntax; not run | sanitized | V20, V27 |
| [`walkcmp.py`](../../indexer/scripts/checks/walkcmp.py) | `$T`, 2026-10-19 05:31 UTC (a heredoc) | reconstructed | the cursor walk visits the same nodes, in the same order, as the old stack walk | the image (the grammars); a source file and its language | persisted; syntax; not run | safe | V19 |
| [`dump.py`](../../indexer/scripts/checks/dump.py) | `$T`, 2026-10-22 12:14 UTC (a quoted heredoc, the only write; the one later command that names it runs it, mounted read-only). Rebuilt with `heredoc.py` on 2026-10-24 and again on 2026-10-26, with the same SHA-256 | reconstructed, adapted (one docstring line says so) | every C# file's type facts under `/corpus`, one JSON line each in field order; run once with each code, then `cmp` the two dumps: equal means the facts hold the same data in the same order (PR #23's check) | the image, with the code to test at `/src`, the clones at `/corpus` (read-only) and a writable output; `languages.by_id` and `file_facts`, with facts made of `NamedTuple`s, dicts and tuples (`CsTypes` and `CsType` on `main`). It writes only its output file, and runs no network or subprocess | persisted; syntax, shape; not run | safe | V19 |

**How `dump.py` ran on 2026-10-22** (from `$T`): once with each code, `main`'s from a worktree and the branch's from a
copy of the tree, then the two dumps compared.

```sh
docker run --rm -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 -v "<code>/indexer":/src:ro \
  -v ~/.cache/aidd-corpus/repos:/corpus:ro -v "<scripts>":/scripts:ro -v "<out>":/out \
  --entrypoint python aidd-indexer:local /scripts/dump.py /out/<main|head>.tsv
cmp <out>/main.tsv <out>/head.tsv && echo IDENTICAL
```

It printed 35,255 files on each side, two dumps of 21,626,222 bytes, and `IDENTICAL`. `/corpus` holds every clone
of `$C/repos`, the hold-out's included.

### `recovery/`: rebuilding lost scratchpad files from a transcript

| Name | Origin | Nature | Purpose | Needs | State, checked | Safety | Used by |
|---|---|---|---|---|---|---|---|
| [`recover.py`](../../indexer/scripts/recovery/recover.py) | `$C/recover/recover.py` | original | each Write, then each Edit after it, of the named scratchpad paths | a transcript | persisted; integrity, syntax; smoke: its identical original in `$C` rebuilt the Write-made files of §2–§4 on 2026-10-24 | safe | V29 |
| [`heredoc.py`](../../indexer/scripts/recovery/heredoc.py) | `$C/recover/heredoc.py` | adapted | the files a Bash heredoc wrote; it lists, without replaying, the later `sed -i` and in-place Python edits | a transcript | persisted; integrity, syntax; smoke: its original in `$C`, before the edit of §7, rebuilt the heredoc-made files on 2026-10-24; this copy was not run | sanitized | V29 |

The originals of both stay in `$C/recover/`, beside `out/`, which holds an earlier recovery.

### V18: the reference branch, not the checkout

Checked on 2026-10-24, reading the branch with `git ls-tree` and `git diff`, without checking it out.

- **The branch:** `h6/step1-proto`, local and on `origin`, both at `6ccf4a0`, 27 commits past its base with `main`
  (`bace8c3`). H6 decided it is never merged.
- **Only on the branch, not on `main`:**
  - `indexer/scripts/h6-step1/`: 16 scripts and a README;
  - its `results/`: 201 files;
  - the prototype the scripts measure, `indexer/aidd_indexer/core/pipeline.py` and `pipeline_pkg.py`.

  None of them is in the current checkout, and none was copied to it.
- **On both, in the same version:** `corpus.sh`, `micro.sh`, `micro.py` and `corpus_metrics.py`.
- **On both, in different versions:** `http_corpus.py`, `shape.py`, `mcp-it.sh` and `gates.py`. The branch's are
  older, and they are the ones H6's runs used.
- **What runs where:**
  - `bench.sh`, `run_bench.sh`, `batch_run.sh`, `count_reads.py` and `packages_chain.sh` set `AIDD_PIPELINE` or
    `AIDD_BATCH`, and `replay.py` imports the core as the branch has it. They need the branch's code;
  - `aggregate.py`, `evaluate.py`, `same.py`, `store_bench.py`, `gc_patch.py`, `fetch.sh` and the `chain*.sh` files
    read or move results, and import no indexer module.
- **The canonical place** of every one is the branch: `h6/step1-proto:indexer/scripts/h6-step1/`. To run one,
  make a worktree of the branch (`git worktree add --detach <path> origin/h6/step1-proto`), which leaves the main
  checkout's branch as it is; to read one, `git show origin/h6/step1-proto:<path>`. No procedure needs a branch
  switch of the main checkout. A copy on `main` would duplicate code that targets the prototype.

## 3. Documents and evidence persisted under `docs/indexer/`

| Name | Nature | Purpose | State | Safety |
|---|---|---|---|---|
| [`validation-inventory.md`](validation-inventory.md) | derived | the procedures, their evidence and the recovered state | persisted | safe |
| [`resource-catalog.md`](resource-catalog.md) | derived | this catalog | persisted | safe |
| [`benchmark-and-statistical-protocols.md`](benchmark-and-statistical-protocols.md) | derived, written on 2026-10-26 | the benchmark and statistical procedures: their commands, formulas, thresholds and validity, and PR #27's context | persisted | safe (counts, snapshot numbers and public repos only) |
| [`validation-and-continuity.md`](validation-and-continuity.md) | derived, written on 2026-10-26 | the entry point: the map of these documents, the state of H5 and PR #27, a coverage matrix, the audit of 2026-10-26, the risks and a checklist | persisted | safe (no private name or machine path) |
| [`operational-workflow-and-continuity.md`](operational-workflow-and-continuity.md) | derived, written on 2026-10-26 | where H5's validation stands, the order of its phases, what survives what, the risk classes and their authorizations, and a resumption checklist | persisted | safe (no private name or machine path) |
| [`semantic-judgment-and-regressions.md`](semantic-judgment-and-regressions.md) | derived, written on 2026-10-26 | how a difference becomes a verdict: the sources' terms, the evidence a verdict needs, cases and regression records; a verdict record proposed for H7-D2 | persisted | safe (public repos and a labelled hypothetical example only) |
| [`evidence/pr5-validation-plan.md`](evidence/pr5-validation-plan.md) | reconstructed from `$T` (2026-10-19 01:56 UTC) and translated from Portuguese | the plan where the two-phase validation started | persisted | safe (it names no tenant) |
| [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md) | derived from `$S` | PR #27's per-commit runs, judgment totals, time, live check, a manifest of the "before" picture, and what is open | persisted | safe (numbers and public repos only) |

**The mutations of the writer's test** (2026-10-22, from `$T`), each run as
`checks/mutate.sh NAME OLD NEW`, with the old and new text of `core/graph.py`:

1. `gc`: no orphan cleanup. The anchor is the two lines `WHERE n.indexed_at IS NULL OR n.indexed_at <> datetime($now)`
   and `CALL (n) { DETACH DELETE n }`, and the replacement swaps the `DETACH DELETE n` for `SET n.kept = true`.
2. `strategy`: no strategy on `CALLS`. `SET e.resolved = false, e.strategy = c.strategy, e.method = c.method` becomes
   `SET e.resolved = false, e.method = c.method`.
3. `spec`: imports merged without their spec. `MERGE (f)-[e:IMPORTS {spec: i.spec}]->(t)` becomes
   `MERGE (f)-[e:IMPORTS]->(t) SET e.spec = i.spec`.

The H7 handoff records that each mutation failed the writer's test.

## 4. Kept out of the repository

**On 2026-10-26 a reboot emptied both scratchpads.** Every item marked "volatile" below is gone from `$S`. Those
marked "reconstructable" can still be rebuilt from `$T`. PR #27's private data survives in `.local/indexer/pr27/`,
checked after the reboot (89 of 89 hashes).

| Resource | Where it is | Why it stays out | What stands for it in the repository | State |
|---|---|---|---|---|
| `golden.py`, the original | `$S/val/golden.py` | its 27 calls name the install's tenants, repositories and namespaces | [`live/golden.py`](../../indexer/scripts/live/golden.py) and the example calls | **local**, since 2026-10-24: a verbatim copy in `.local/indexer/pr27/``original/`, SHA-256 equal to its source, and its calls as `golden-calls.json` beside it (27 calls, checked against the 27 before answers). The source in `$S` was emptied by the reboot of 2026-10-26 |
| PR #27's before picture, golden answers, dry-runs and pre-merge logs | `$S/livecsn/` (`before/`, `dry/`, five `*.txt`) | private: they name the tenants | the manifest and summaries in [`evidence/pr27-validation-state.md`](evidence/pr27-validation-state.md) | **local**, since 2026-10-24: 87 files copied to `.local/indexer/pr27/`, each SHA-256 equal to its source; the 15 lists and the 27 answers also match the versioned manifest. The sources in `$S` were emptied by the reboot of 2026-10-26 |
| PR #27's snapshot exports and code copies | `$S/livecsn/snap/` (10 exports of private repos), `main_src/`, `head_src/` | private, and made again from git: `git archive` of each snapshot's sha, and of `274d63b` and `8ccf450` (whose `indexer/` tree is `0725d47`'s) | the local `README.md` says how | **volatile**, not copied |
| PR #25's live pictures | `$S/livecsb/` | private; PR #25's validation is closed (the tenth golden round) | the tenth round | **volatile**, not copied |
| `live/before.md` | `$T`, 2026-10-18 | it names the tenants | the fifth golden round | reconstructable, not persisted |
| The protocol's outputs | `$S/h5/runs/csn-n*/` | large; derived data | the per-commit table in the PR #27 evidence | volatile |
| The judgment's outputs and judged samples | `$S/h5/why/out/`, `$S/h5/n1/`, `$S/h5/n2/` | large; samples hold source lines | the totals in the PR #27 evidence and in the H5 handoff | volatile |
| The background task outputs | next to `$S`, in `tasks/` | transient | the PR #27 evidence (§2, §4) | volatile |
| The per-PR chains: `micro-chain.sh`, `protocol-chain.sh`, `protocol-cs-chain.sh`, `protocol-c8-c9.sh`, `csn-chain.sh` | `$S/h5/` | each hard-codes one PR's worktrees and labels; the pattern is a loop that runs `protocol.sh` with `AIDD_REPO` set to each commit's worktree, one after another | the inventory's V13 | volatile |
| `cmp-micro.sh`, `time-cs.sh`, `time-pair.sh` | `$S/h5/` | superseded by `micro.py --compare` with `chain_diff.py`, and by `time-alone.sh` | — | volatile |
| `unmark.py`, `unmark_cases.py`, `edit_*.py` | `$S/h5/` | one-off edits of code and test files of past commits | the commits themselves | volatile |
| `cs-extra.txt`, `base-main-d42e64b.txt`, `csn-n*-wt.txt` | `$S/h5/` | run metadata | the extended micro sets, listed in the PR #27 evidence | volatile |
| The probes' inputs | `$S/h5/probe/` (`*.cs`, `*.json`, `tree-*`) | transient | — | volatile |
| `shape-now.json` | `$S/` | a report that can be made again | `shape.py --json` | volatile |
| PR bodies and the H5-D17 section's draft | `$S/pr25-body.md`, `$S/pr26-body.md`, `$S/h5/docs/` | already published: PRs #25–#27 and the H5 handoff | GitHub; the handoff | volatile |
| `h6/measure.py` | `$T` (reconstructed: 353 lines) | over the 300-line limit, so the shape ratchet would fail it; written for the code before H5 | the corpus report's "H6 baseline"; the reference branch | reconstructable, not persisted |
| `h6/calls_check.sh`, `h6/calls_diff.py` | `$T` (reconstructed) | superseded by `micro.sh` and `micro.py`, which compare the same records | `micro.sh`, `micro.py` | reconstructable, not persisted |
| `val/dryrun.sh` | `$T` (reconstructed) | superseded: it lacked `-w /code`, so `python -m` ran the image's code | `live/dryrun-live.sh` | reconstructable, not persisted |
| `val/live-cs.sh` | `$T` (an unquoted heredoc) | superseded; the transcript holds it before the shell expanded it, not as it was written | `live/pre-merge.sh` | reconstructable, not persisted |
| `overnight/MORNING.md` | `$T` (reconstructed, in Portuguese) | a status note of 2026-10-19 | `docs/history.md` | reconstructable, not persisted |
| `review/metrics.py` | `$T` (reconstructed) | the AST metrics of the H5 diagnosis | `shape.py` | reconstructable, not persisted |
| `h5/why/why_a.py` | `$T` (reconstructed, 141 lines) | partial: one later in-place edit was not replayed, and it imports `old_locals.py`, a module generated from `main`'s code at PR #17 by a command in `$T` (2026-10-21 17:38 UTC) that was not replayed | — (§1, V11) | reconstructable in part, not persisted |
| `h5/neg.py` | `$T` | a one-off probe of a test helper | — | reconstructable, not persisted |
| `val/go_graph_diff.py` | `$T`, 2026-10-21 21:30 UTC (a quoted heredoc), run on PR #20's two pictures for one public repo | one repo's `CALLS` in two pictures, by merge key: strategy moves, removed edges and whether their site still calls, added strategies. Found on 2026-10-26; persisting it needs the author's authorization | `live/graph_vs_dry.py`, for every snapshot | reconstructable, not persisted |
| `h2b/gab.py`, `h2b/gitea_judge.sh`, `holdout/judge/{prep,show,verdict,categorize}.py` | `$T`, heredocs of 2026-10-15 and 2026-10-17 | one-off editors of the expected lists' `checked` verdicts and miss categories (H2b, the first hold-out). `prep.py` marked a sampled item right when it matched the list, and `verdict.py` gave the others a default verdict with exceptions by index. `gab.py` hard-codes a machine path. Found on 2026-10-26 | the verdicts and categories they wrote, in the lists | reconstructable, not persisted |

## 5. Not found, or never built

Reviewed on 2026-10-24. "Never built" is used only where a document records the item as not built and no recovered
source holds it. Otherwise, "not found in the recovered sources": `$S`, `$T`, `$C/recover` and every git ref.
C#'s type facts check, found in `$T` on 2026-10-24, left this table on 2026-10-26: it is persisted as
[`checks/dump.py`](../../indexer/scripts/checks/dump.py) (§2).

| Resource | Classification | Grounds | Used by |
|---|---|---|---|
| `indexer/scripts/live-check.sh` | **never built** | H7's state (2026-10-22) has slice 4, which delivers it, still open, and the H7 handoff lists it among its expected deliverables. No git ref has a file of that name: `git log --all` finds only `c657a33`, the commit that wrote the handoff. `$T` holds no Write or heredoc that creates it | V21–V25 |
| A dedicated script that compares two live pictures, or two sets of golden answers | **not found in the recovered sources; a partial implementation exists** | `graph_vs_dry.py` compares two pictures' `CALLS` with the dry-runs, `dry_compare.py` compares `main`'s dry-run with one picture's counts, and `go_graph_diff.py` (§4, not persisted) compared one repo's `CALLS` in two pictures. The other 14 lists and the golden answers were compared with commands typed in the session (`$T`, 2026-10-22 18:46 UTC, recorded under V23 and V25). No file was written for it | V23, V25 |
| Go's typed facts check (PR #17), the `tools/list` byte comparison, the ASTs unchanged by the comment edits | **not found in the recovered sources** | the H5 handoff and the corpus report give their results; no file in `$S`, `$T`'s Writes and heredocs, or git holds them. They may have been inline commands | V19 |
| `h5/why/why_a2.py` (C#'s attribution, if it existed), `h5/why/old_locals.py`, `h5/lint.sh`, `h6/dryruns.sh`, `h6/aggregate.py`, `val/live-csb.sh` | **not found in the recovered sources** | named in `$T`, but rebuilt by neither `recover.py` nor `heredoc.py`. `old_locals.py` and `val/live-csb.sh` were made by commands (an `echo` chain, a `sed` of `live-cs.sh`), not written as files. `indexer/scripts/h6-step1/aggregate.py` on the reference branch is H6's later aggregate | V11, V18, V22 |
| The verdicts of each judged item | **never recorded one by one** | H7-D2, the format to record them in, is still a decision to make; the judgments survive as prose and totals | V09, V11, V12 |
| `install-check.sh`'s output for the 2026-10-24 reinstall | **not verifiable** | the author ran it; it was not seen | V24 |

## 6. External references

| Resource | Where | Durable | What it holds | Used by |
|---|---|---|---|---|
| The transcript | `~/.claude/projects/<project-dir>/6d63c0e8-….jsonl` (`$T`, about 950 MB) | while the author keeps it | every Write, Edit and Bash call of the H5 session; the source of every reconstruction here | V29 |
| The previous scratchpad | `$S` | **no**: **emptied by the reboot of 2026-10-26**, and absent since | the originals of §2, and the volatile items of §4 | — |
| PR #27's local data | `.local/indexer/pr27/` (`README.md`, `SHA256SUMS`) | on this disk only: ignored by git, **no backup**, and private (mode 700 and 600) | the before picture, the dry-runs, the pre-merge logs, the original golden script and its calls file | V21–V23, V25 |
| This session's scratchpad | `/private/tmp/claude-<uid>/<project-dir>/0caa56ee-dffd-492d-92bf-6bf730b444b1/scratchpad` (`recovered/`, `recovered-hd/`, `recovered-hd2/`) | **no**: emptied by the same reboot | the reconstructions of 2026-10-24; those worth keeping are persisted in §2 and §3 | — |
| The corpus cache | `$C/repos`, `$C/runs` (33 corpus baselines and `holdout-26`), `$C/micro`, `$C/micro-fresh`, `$C/h6`, `$C/recover` | yes | clones, runs, micro base runs, per-run micro outputs, H6's raw data, the recovery helpers' originals | V01–V04, V07, V10–V13, V17, V18 |
| The H6 reference branch | `origin/h6/step1-proto`, `indexer/scripts/h6-step1/` and `results/` | yes (never to merge) | H6 steps 1–2's bench, replay and store scripts, and their results | V18 |
| The draft release | `h6-step1-results` on GitHub | yes | the replay's records (107 MB) | V18 |
| The CI caches and artifacts | the GitHub Actions cache (the baselines, keyed by the code's tree) and the `corpus`/`micro` artifacts | the cache until evicted; the artifacts 14 days | derived baselines; the runs of a PR | V03, V26 |
| The live install | `~/.aidd/` (the code, `atlas.yaml`), the stack's containers, the workspace's clones | yes | the graph, the MCP, the snapshots' sources | V21–V25 |
| The indexer's images | Docker: `aidd-indexer:local` (`f07550cbe2e2`, built 2026-10-24); `927f5b4115c5`, untagged, the only image with a micro base for `main`'s tree at `274d63b` | until pruned; the untagged one is the first a prune removes | the grammars and the Python that every run and micro base is keyed to | V10, V13, V17 |

## 7. The edits made to persisted files

Each edit was applied by a script that requires its anchor to match exactly once. No edit changes what a script
computes, except where it says so.

| File | Edit | Why |
|---|---|---|
| `protocol/protocol.sh` | the header without the handoff's id; the outputs in `$AIDD_PROTOCOL_RUNS/<label>` (default `~/.cache/aidd-corpus/protocol`) instead of next to the script; the repo's default found from the script's location; `AIDD_BASELINE` and `AIDD_HOLDOUT_BASELINE`, defaulting to the same baselines; `micro-fresh.sh` found from the script's directory, which a `cd` would otherwise break | no machine path; no output inside the repository; a relative invocation works |
| `protocol/micro-fresh.sh`, `protocol/shape.sh`, `checks/mutate.sh` | the repo's path found from the script's location | no machine path |
| `checks/mutate.sh` | the `|| exit 3` that a `sed -i` added to it on 2026-10-22, replayed from `$T`; its work copies in `$AIDD_MUTATE_DIR` (default `~/.cache/aidd-corpus/mutate`) instead of the scratchpad | the reconstruction is the last version; no session path |
| `protocol/time-alone.sh` | renamed from `time-csn.sh`; the header without the change's name; a label made unique by the time (`micro.sh` and `corpus.sh` need a new one per run); `AIDD_BASELINE`; `AIDD_TIME_REPOS`, defaulting to the same four repos | a second run no longer reuses a label |
| `live/pre-merge.sh` | renamed from `live-csn.sh`; `LIVE_DIR` and the calls file as arguments; the scripts found next to it | no session path; `golden.py` now takes a calls file |
| `live/golden.py` | rewritten: the same request, parsing and output line per call, with the calls read from a file and `--url` | its call list named the tenants |
| `judgment/ext_sites.py`, `ext_back.py`, `ext_judge.py`, `this_kind.py` | `edges_lib` imported from the script's own directory, as `chain_diff.py` does | no session path |
| `judgment/edges_lib.py` | its docstring, which was a copy of `edges_join.py`'s, now says what the module is | it described another script |
| `live/dry_compare.py`, `checks/a2_gabaritos.py`, `a4_compare.py`, `a5_chain.py` | the plan item's id (`B2:`, `A2:`, `A4:`, `A5:`) dropped from the docstring | comments point at no plan item; this catalog keeps the mapping |
| `recovery/heredoc.py` | the scratchpad pattern takes any user id (`claude-\d+`), not only the one of the machine that wrote it | not one machine's |
| `checks/dump.py` | one docstring line: "Rebuilt from the transcript of the session that wrote it on 2026-10-22, not recovered as a file." | the author asked the file to name its provenance |
| `judgment/chain_diff.py`, `judgment/ext_judge.py` (2026-10-26) | the sites sorted before the seeded draw | the draw followed a `set`'s order, which changes per process: two runs of `main`→n17 shared 8 of 200 samples. The counts do not change; new samples reproduce; past ones stay unrecoverable |
| `live/dry_sections.py` (2026-10-26) | endpoints and HTTP calls keyed by `file_id`, not `file` | the dry-run has no `file` field, so a route that moved file showed as identical (a synthetic case) |
| `live/graph_vs_dry.py` (2026-10-26) | exits 1 when a snapshot mismatches | it exited 0 whatever it found, and `pre-merge.sh` reports its code |
| `live/golden.py` (2026-10-26) | exits 1 when a call never reached the MCP; an answer with `isError` still counts | with the MCP down, every call failed and it exited 0, as the original did |

## 8. The audit of 2026-10-26: each script against its claims

Done with the author's authorization to run offline analyses, the indexer in Docker, read-only live checks and
`install-check.sh`. Each relevant script was read before it ran. Where it could not run, as the live ones while the
install's Neo4j was down, it was tested on synthetic inputs or not at all, as the row says. Later that day, after the
author recreated the container, the live ones ran too (the PR #27 evidence, §9). **Running is not historical
verification:** a reconstructed script that runs today has still only its reconstruction behind it.

"Fork" says whether a contributor with a fresh clone, Docker and the network, and no private data, can run it.

| Script | Inventory | Provenance | Side effects | Exit code | Deterministic | Tested on 2026-10-26 | Fork | Limits |
|---|---|---|---|---|---|---|---|---|
| `micro.sh`, `micro.py` (CI) | V10 | original, versioned | writes `$C/micro`; Docker | 0 identical, 1 differs or missing, 3 a dry-run failed | yes | `--base-only` for `main`: 12 of 12 | yes | a second run on one tree state fails on Docker Desktop |
| `corpus.sh`, `http_corpus.py`, `corpus_metrics.py` (CI) | V07 | original, versioned | writes `$C/runs`; Docker | 1 when a repo failed; 2 usage | yes | through `protocol.sh` on `main`: corpus and hold-out `0 repo(s) differ` against `-29` and `-26` | yes, but the named baselines are not published: a run of `main` at `0725d47` stands for them (the PR #27 evidence, §8) | — |
| `protocol/protocol.sh` | V13 | adapted | writes `$C/protocol`, `$C/runs`, `$C/micro-fresh`; Docker | prints each step's `rc=`; its own is the last command's | yes | ran on `main` from the repository, its first run outside the scratchpad (the PR #27 evidence, §8) | yes | one protocol at a time |
| `protocol/micro-fresh.sh` | V10, V13 | adapted | writes `$C/micro-fresh` (three folders per run); Docker | 0, 1 as `micro.py`; 2 no base run; 3 a dry-run failed | yes | ran through `protocol.sh` | yes | fixes the home, the image and 2 jobs; **its containers carry no label,** so a search by `aidd.micro` does not find them; the base is `merge-base main HEAD` |
| `protocol/time-alone.sh` | V17 | adapted | writes `$C/runs`; Docker | the last command's | no: a time | no | yes | one run per side; needs a quiet machine |
| `protocol/shape.sh` | V15 | adapted | installs ruff from the network into a throwaway container | `shape.py`'s | yes | no (run on 2026-10-24) | yes | — |
| `judgment/chain_diff.py` | V11 | adapted (sorted draw) | stdout, stderr | 0 | **since the fix, yes** | twice before the fix, twice after (§7) | yes, given micro runs | the class `name` holds `dispatch` |
| `judgment/ext_judge.py` | V12 | adapted (sorted draw) | stdout | 0 | since the fix, yes | twice after the fix | yes | its "extension" includes any static method |
| `judgment/ext_loss.py`, `ext_sites.py`, `ext_back.py`, `lost_ext.py`, `this_kind.py` | V12 | original or adapted (import path) | stdout; `ext_sites.py` and `ext_back.py` write a JSONL | 0 | counts yes; `ext_loss.py` prints a dict whose key order follows a set, and `ext_sites.py`'s rows follow one | `ext_sites.py` smoke-tested on 2026-10-24; the rest no | yes | their definitions differ (the benchmark protocols, §5.8) |
| `judgment/samples_view.py`, `show.py`, `site_edges.py` | V11 | original | stdout | 0 | yes | `samples_view.py` on 2026-10-26 | yes | — |
| `judgment/edges_join.py`, `kinds.py`, `cases.py`, `view.py` | V11 | original | stdout | 0 | yes | no: their input, `why_a.py`'s file, is missing | no | §4 |
| `live/foto.sh` | V23 | original | reads the live Neo4j through `docker exec`; writes OUT_DIR (private) | non-zero when a query fails (`pipefail`) | yes, for a given graph | **no:** the install's Neo4j was down. Later that day, on the live install: rc 0 | no (a private install) | its lists name the tenants |
| `live/golden.py` | V25 | new (a sanitized rewrite) | HTTP calls to the MCP, one of them a write it must refuse; writes OUT_DIR (private) | **since the fix,** 1 when a call never reached the MCP | yes, for given answers | against a local stand-in only; and a closed port (§7). Later that day, the live MCP: rc 0 | no | the calls file is private |
| `live/dryrun-live.sh` | V22 | original | reads the clones at `$HOME/workspace/<tenant>/<repo>` and `~/.aidd/atlas.yaml`; writes LIVE_DIR | always 0; each run's `rc=` is printed | yes | no | no | assumes that workspace layout, not the install's `WORKSPACE_PATH` |
| `live/dry_sections.py` | V22 | adapted (`file_id` key) | stdout | 0: a difference is not a failure | yes | re-derived PR #27's output; a synthetic case before and after the fix | yes, given dry-runs | six sections by keys (the benchmark protocols, §5.9) |
| `live/graph_vs_dry.py` | V21 | adapted (exit code) | stdout | **since the fix,** 1 when a snapshot mismatches | yes | re-derived; a synthetic mismatch; later, PR #27's before and after: 0 mismatching | yes, given pictures and dry-runs | `CALLS` only |
| `live/dry_compare.py` | V21, V22 | adapted (docstring) | stdout, **with names** | 0 | yes | no | yes | private output |
| `live/json_paths_diff.py` | V22, V25 | reconstructed | stdout | 0 | yes | later that day, PR #27's five differing answers | yes | — |
| `live/pre-merge.sh` | V21–V23, V25 | adapted | runs the five steps above | the last step's | — | no | no | needs the two code copies checked first |
| `checks/a2_gabaritos.py`, `a4_compare.py`, `a5_chain.py` | V02, V08 | reconstructed | stdout | 0 | `a5_chain.py` orders runs by mtime | no | yes, in the image | `a4_compare.py` compares floats, not fractions |
| `checks/dump.py`, `walkcmp.py` | V19 | reconstructed | writes its output file | 0 | yes | no | yes | Go's and the other V19 checks not found |
| `checks/mutate.sh` | V20, V27 | reconstructed | a throwaway Neo4j; copies of the tree | `mcp-it.sh`'s | yes | no | yes | — |
| `recovery/recover.py`, `heredoc.py` | V29 | original, adapted | writes the rebuilt files | 0 | yes | on 2026-10-24 and 2026-10-26 | **no: the transcripts are not in the repository** | in-place edits are listed, not replayed |
| `probes/probe.py`, `tree.py` | V14 | original | stdout; in the image | 0 | yes | no | yes | — |
