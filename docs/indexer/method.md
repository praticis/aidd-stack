# Method: validating a change to the indexer

How a change is proven, step by step. Nothing here changes per PR. Where H5 stands and what comes next is in
[the H5 handoff](../handoffs/H5-indexer-refactor.md); how to judge a difference is in [judgment.md](judgment.md).

Paths starting with `scripts/` are under `indexer/`. `$C` is `~/.cache/aidd-corpus` (clones, runs, baselines, micro bases). `.local/` is git-ignored and holds private
outputs. The tools are listed with their arguments in [`indexer/scripts/README.md`](../../indexer/scripts/README.md).

## 1. The cycle of a change

| # | Step | How | Passes when |
|---|---|---|---|
| 1 | Context | `git status`, `git worktree list`, `docker image inspect aidd-indexer:local` | branch, commit and image are the ones the run is meant to measure |
| 2 | Case first | a fixture case or test that fails without the rule (`indexer/tests`) | fails on `main`, passes on the tree |
| 3 | Tests, writer, shape | `scripts/test.sh`; `scripts/mcp-it.sh`; `scripts/protocol/shape.sh` | all pass; `0 new or worse over a target` |
| 4 | Corpus and hold-out | `scripts/protocol/protocol.sh LABEL` | a refactor: `0 repo(s) differ` on both. A change: every diff judged at the source |
| 5 | Micro graph | the same `protocol.sh`, through `micro-fresh.sh` | a refactor: identical. A change: judged by case |
| 6 | Judgment (changes only) | `scripts/judgment/` and [judgment.md](judgment.md) | no wrong item in any case |
| 7 | Time | `scripts/protocol/time-alone.sh MAIN_WORKTREE BRANCH_WORKTREE` | no worse than `main` unless justified. Judged, never a gate |
| 8 | PR and CI | the `gates` job | green; the labels `graph-change` and `holdout-measurement` only after judgment |
| 9 | Live, before the merge | `scripts/live/pre-merge.sh` (§4.7) | dry-runs identical outside the change; picture and golden answers the same |
| 10 | Merge, reinstall | the author only. `install.sh` copies the working tree, so `main` is checked out first | `install-check.sh` ends in "All checks passed" |
| 11 | Live, after | picture, golden answers, graph against dry-runs (§4.8) | as step 9, plus the graph holds the branch's dry-run |
| 12 | Record | a golden round, `docs/history.md`, the H5 handoff, the ROADMAP | each change supported by the evidence |

A change to the extractor adds, before step 4: corpus `--baseline`, judgment at the source, the expected lists
(`checks/expected_lists_diff.py`), and a new baseline only after its diff was judged item by item.

A refactor and a change of behavior never share a commit: one `refactor:` commit makes the whole PR strict.

## 2. Who authorizes what

Permission to read or document a procedure is not permission to run it. Each class needs its own authorization, per
task; approval in one task does not carry over.

| Class | Examples | Authorization |
|---|---|---|
| 1. Read-only | `git status/log/show`, reading files, `docker image inspect`, `gh pr view` | the task |
| 2. Offline analysis of saved artifacts | `judgment/` tools, `live/dry_sections.py`, `live/graph_vs_dry.py` | the task says to run it |
| 3. Local files | editing docs or scripts; writes to `.local/` or `$C` | the task asks; `before/` pictures are never rewritten |
| 4. Corpus or indexer execution | `corpus.sh`, `micro.sh`, `protocol.sh`, `time-alone.sh`, `test.sh`, `mcp-it.sh`, `dump.py` | explicit. One protocol at a time, in the background; never edit the mounted code during a run |
| 5. Live install | `graph-picture.sh`, `golden.py`, `dryrun-live.sh`, `pre-merge.sh`, `install-check.sh`, a refresh | explicit, per run. Install and reinstall are the author's alone |
| 6. Remote or git metadata | commits, pushes, PRs, labels, merges, branches, worktrees | the author's approval each time. Commits are one conventional line, signed |

## 3. Where things live

| What | Where | In git |
|---|---|---|
| Procedures, tools, these docs | the repository | yes |
| Clones, runs, baselines, micro bases | `$C`, CI's cache | no (regenerable) |
| Golden calls, live pictures, dry-runs of live snapshots, answers | `.local/` or a folder outside the repo | never |
| Evidence that cannot be regenerated (a "before" picture, the past PRs' micro runs) | `.local/`, `$C` | no. Keep a second copy: no backup policy exists |

Private data reaches the repository only as counts, snapshot numbers and public repos. No tenant, client or private
repo name appears in code, docs or tests: the repository is public. A read-only tool can still leak: the live
scripts print snapshots by number, and their raw outputs name tenants.

## 4. Procedures

### 4.1 Corpus and hold-out

```sh
indexer/scripts/corpus.sh --label L --baseline 2026-10-18-v2-baseline-29
indexer/scripts/corpus.sh --holdout --label L-holdout --baseline 2026-10-18-v2-holdout-26
```

- Baselines are named directories in `$C/runs`; in CI they are derived from the base's code. They are not published.
- A new baseline is saved only after its diff was judged item by item. A refactor never promotes one.
- `--reuse` rescores a saved run: it measures nothing about a change to the extractor.
- The hold-out's lists are written before the extractor runs on it, it is measured once, and no rule is tuned on it.
  In a change of behavior it is read only in aggregate; an item opened becomes corpus.
- Gates (`gates.sh`): precision never lower (per repo and kind, and pooled per language); no expected pair and no
  `checked` item lost; hold-out untouched; every repo measured; a refactor changes nothing.
- Offline, not in CI: `checks/expected_lists_chain.py` (no win reverted across the saved runs) and
  `checks/expected_lists_diff.py` (what changed between two sets of expected lists). Both run in the image with
  `PYTHONPATH=/src:/src/scripts`.

### 4.2 Micro graph

`micro.sh` dry-runs the 12 repos of `MICRO` (`scripts/micro.py`) with `main` and with the tree and compares record by
record. The base is keyed by the `aidd_indexer` tree and the image; after a reinstall run `micro.sh --base-only`.

`protocol/micro-fresh.sh LABEL REPO...` does the same through paths no container mounted before: Docker Desktop breaks
the bind mount of a folder deleted and recreated at one path, and can serve a file just written cut short. The base
is the merge-base with `$AIDD_BASE_REF` (default `origin/main`).

### 4.3 Protocol per commit

One worktree per commit, so each is measured with its own code:

```sh
AIDD_REPO=<worktree> indexer/scripts/protocol/protocol.sh LABEL [REPO...]
```

It runs the corpus, the hold-out and the micro set (plus any repos given) and prints the verdicts. Compare each
commit with the one before (`-copy` against `-copy`) and `main` with the tip (`-base` against `-copy`).

### 4.4 Judgment tools

```sh
python3 -I indexer/scripts/judgment/chain_diff.py BEFORE AFTER N REPO... > out.txt 2> samples.jsonl
python3 -I indexer/scripts/judgment/show.py $C/repos [--short] < samples.jsonl
python3 -I indexer/scripts/judgment/site_edges.py REPO FILE_SUFFIX:LINE[,...] DIR...
python3 -I indexer/scripts/judgment/csharp_extensions.py sites|back|classes|this-kind|blocks ...
```

`BEFORE` and `AFTER` hold `<repo>.json.gz` dry-runs. `chain_diff` samples with a fixed seed over sorted sites, so the
same inputs give the same sample. Sizes used: `N` 6 to 12 per kind for each commit against the one before, 40 for
`main` against the tip.

### 4.5 Timing alone

`time-alone.sh` runs the corpus's wall time and four full dry-runs on `main`'s worktree, then the branch's, with no
other load. One run per side: the median of three is not practiced.

### 4.6 Equivalence of a representation

`checks/dump.py LANGUAGE OUT` (`csharp` or `go`) dumps every file's type facts under `/corpus`. The same dump from two
codes, compared with `cmp`, shows whether a refactor changed a fact.

### 4.7 Live, before the merge (class 5)

`LIVE_DIR` holds `main_src/indexer` and `head_src/indexer`, copies of the two codes (check each copy against
`git ls-files` with `shasum`: copies get served stale). The golden calls file is private; use
`live/golden-calls.example.json` for its shape.

```sh
indexer/scripts/live/pre-merge.sh LIVE_DIR GOLDEN_CALLS_JSON
```

It takes the graph's picture (`graph-picture.sh`), runs the golden calls, dry-runs every live snapshot with both
codes (`dryrun-live.sh`, with `-w` on the mounted code), then compares them by section (`dry_sections.py`) and
against the graph by merge key (`graph_vs_dry.py`). Take the "before" picture before the reinstall: afterwards it
cannot be retaken.

### 4.8 Live, after the merge (class 5)

After the author's reinstall: `graph-picture.sh LIVE_DIR/after`, `golden.py CALLS LIVE_DIR/after/golden` with the same
calls file as before, `graph_vs_dry.py BEFORE AFTER DRY`, and `json_paths_diff.py A B` for each pair of answers. Pass
criteria: the picture is identical but for the build and `IndexRun`; the graph holds the branch's dry-run on every
snapshot; the answers are the same or differ only in time and build fields.

## 5. Criteria

| Criterion | Rule | Kind |
|---|---|---|
| Refactor | corpus and hold-out `0 repo(s) differ`; micro identical | gate |
| Precision, wins, hold-out, coverage | as §4.1 | gate |
| Shape | no function above complexity 9, no module above 300 lines, new or grown | gate |
| Change of behavior, micro graph | judged by case; one wrong item in a case blocks | judged |
| Change of behavior, cases | every xfail gained, no guard lost | tests |
| A loss | a wrong guess the receiver's type disproves, or a gap with its case named; a loss of the PR's own kind goes in the PR | judged |
| Time | no worse than the previous unless justified | judged |
| Live | as §4.7 and §4.8 | practice |

## 6. What makes a run invalid

| Condition | Guard |
|---|---|
| A pin changed between two runs, or a list read at another sha | the report's note |
| A micro base from another tree or image | the base's directory name; `--base-only` after a reinstall |
| `python -m` in the image without `-w` on the mounted code | `-w`, and the log's first line |
| A folder deleted and recreated at one path (Docker Desktop) | a new label per run; `micro-fresh.sh` |
| A file just written by another container, read through another mount | copy to a fresh path first |
| The indexer's code or the expected lists edited during a run | no edits during a run |
| Two protocols at once, or other load | one at a time; time alone |
| A refactor and a rule in one commit | separate commits |
| A dry-run that failed | the summary and the logs: the repo is "not compared" |
| A different golden calls file before and after | the same file both times |

## 7. Not specified yet

- **Per-site attribution for judgment.** Judging "by case" needs each changed call site tied to the rule that explains
  it. The tool that did it for Go (`why_a.py`) is not in the repository and needs a module that was not recovered; C#
  was judged with `csharp_extensions.py`; Python and TS have nothing. Design one before the Python step.
- **The size of a judgment sample.** Not fixed; §4.4 gives the sizes used.
- **A memory tolerance and a time threshold.** None applies today.
- **A scripted pass criterion for the live comparisons.** They are practice (§4.7, §4.8); `live-check.sh` (H7 slice 4)
  was never built.
