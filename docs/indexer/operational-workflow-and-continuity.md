# Operational workflow and continuity

> The fourth of five documents on how the indexer's changes are validated. It is the one to read first after an
> interruption. It says:
>
> - where H5's validation stands;
> - the order of its phases;
> - where each artifact lives, and what survives what;
> - which steps may run, and with whose authorization.
>
> The details are in the others:
>
> - **what** each procedure is: [the inventory](validation-inventory.md);
> - **where** its files came from: [the resource catalog](resource-catalog.md);
> - **how** it measures: [the benchmark protocols](benchmark-and-statistical-protocols.md);
> - **how** a difference becomes a verdict: [semantic judgment and regressions](semantic-judgment-and-regressions.md).
>
> **Written on 2026-10-26**, on `main` at `0725d47`. Nothing was executed to write it. The commands that ran were
> read-only:
>
> - `git status`, `log`, `rev-parse`, `show` and `worktree list`;
> - `gh pr list`, `gh release list` and `gh api` on the branches;
> - listings of `$C`;
> - `docker image inspect`, and `docker ps` as counts only;
> - `shasum -c` on `.local/indexer/pr27/`;
> - reading files.
>
> A `git ls-remote` failed for want of the SSH agent's signature, so the remote branches were read through the GitHub
> API. `$S`, `$C` and `$T` are defined in the inventory.
>
> **Its place in the series.** The inventory's §10 proposed "the refactor cycle, runbook and continuity" as the fifth
> document. This one was requested as the fourth, "operational workflow and continuity". It takes:
>
> - the continuity part: V29 and V30;
> - the authorization boundaries: V28, as they apply to running things;
> - the order of the phases.
>
> CI (V26) and the commit discipline are referred to, not detailed.
>
> **Labels.** As in [semantic judgment](semantic-judgment-and-regressions.md), §1: **[documented]** is written in a
> versioned file; **[practice]** was done before but written nowhere as a rule; **[recommendation]** is proposed
> here. Most of the safe-resumption procedure (§8) is a recommendation.

## 1. Where things stand on 2026-10-26

| Item | State | How it was checked |
|---|---|---|
| `main` | `0725d47`, PR #27's merge. The same on GitHub | `git log`; `gh api` |
| The recovery's files | **46 paths staged when this was written, none committed or pushed:** `.gitignore`, the scripts' README, six documents under `docs/indexer/`, and 38 files under `indexer/scripts/{checks,judgment,live,probes,protocol,recovery}/` (37 scripts and an example calls file). Later edits of the same day are unstaged, and later documents untracked, until the author stages them: read `git status` rather than this row. They exist only on this disk | `git status --porcelain` |
| Worktrees | only the main checkout. The worktrees of the past runs under `$S` are no longer listed | `git worktree list` |
| `h6/step1-proto` | `6ccf4a0`, locally and on GitHub. GitHub's other branches are `main` and `docs/h4.1-contributor-path` | `git rev-parse`; `gh api` |
| Pull requests after #27 | none: no docs PR for the eleventh round | `gh pr list` |
| The draft release `h6-step1-results` | present | `gh release list` |
| The image `aidd-indexer:local` | `f07550cbe2e2`, built on 2026-10-24 at 06:35:55 UTC by the reinstall. **Later that day the tag named `9e6dd3753826`,** built at the same second from the same layers, which differs only in compose's service label. How the tag moved is not known | `docker image inspect` |
| The image behind PR #27's micro base runs | `927f5b4115c5`, built on 2026-10-22 at 21:02 UTC, **untagged**. It is the only image with a base for the tree of `main` at `274d63b`; that PR #27 used it is inferred from that | `$C/micro`'s directory names; `docker image inspect` |
| The stack | 9 `aidd-*` containers; no corpus or micro run container (labels `aidd.corpus`, `aidd.micro`). **Later that day: `aidd-core-neo4j` in a restart loop** (§3.4), and so `aidd-mcp-atlas` unhealthy. The author then recreated it: healthy, with no restart | `docker ps`, counts only; `docker inspect`; `install-check.sh` |
| The live graph's build | `0.2.15+ccc54d86dbc7`, with no snapshot `outdated`, **as checked on 2026-10-24** through `atlas_status`. Not checked again: the `atlas` MCP did not connect, because the install's Neo4j was down. Checked again after the recreation: the same | the inventory, §3; §3.4; the PR #27 evidence, §9 |
| `$C` | both baselines present. A micro base for `main`'s tree with the current image was absent, and **was made later that day** (§5.3) | listings |
| `.local/indexer/pr27/` | 91 files, 89 of 89 hashes OK; no `after/`. Later that day it gained `after/` and `post-merge-2026-10-26/`, with a `SHA256SUMS` of their own; the 89 still check | `shasum -c` |
| PR #27's validation | **not complete** (§5.3). Later that day, the live steps passed; the docs PR is left | §5.3 |

## 2. The operational lifecycle

The order that PRs #17 to #27 followed is drawn in the inventory's §6, and it is the source for this one
**[practice]**. Each phase below says:

- what it needs;
- its canonical script or document;
- what it leaves;
- its risk class (§5);
- whether it is safe during a recovery that only documents;
- what it depends on.

| # | Phase | Needs | Canonical | Leaves | Risk class | Safe in a documentation-only task | Depends on |
|---|---|---|---|---|---|---|---|
| 1 | Establish the context: repository, branch, commit, code tree, image | the checkout | `git`, `docker image inspect` (§8) | notes | read-only | yes | — |
| 2 | Check the prerequisites and the artifacts | §1's items | [benchmark](benchmark-and-statistical-protocols.md) §3, §9; `.local/indexer/pr27/SHA256SUMS` | notes | read-only | yes | — |
| 3 | Prepare the corpus, the baseline and the hold-out | network for the pinned clones; the named baselines | [`corpus.sh`](../../indexer/scripts/corpus.sh) and [`micro.sh`](../../indexer/scripts/micro.sh) (they clone what is missing); [benchmark](benchmark-and-statistical-protocols.md) §6.1, §6.2 | `$C/repos`; a baseline only after judgment | local generation | no | the pins in `http_corpus.py` and `micro.py` |
| 4 | Generate the indexer's outputs | Docker; the image; a worktree per commit | `corpus.sh`, `micro.sh` (and `--base-only`), [`protocol/`](../../indexer/scripts/protocol/); [benchmark](benchmark-and-statistical-protocols.md) §4.1, §4.3, §4.4 | runs in `$C/runs`, `$C/micro`, `$C/micro-fresh` | corpus or indexer execution | no | the tree and the image; a micro base for both |
| 5 | Run the offline measurements and protocol checks | as phase 4 | [`test.sh`](../../indexer/scripts/test.sh), [`protocol/shape.sh`](../../indexer/scripts/protocol/shape.sh), [`gates.sh`](../../indexer/scripts/gates.sh), [`protocol/time-alone.sh`](../../indexer/scripts/protocol/time-alone.sh), [`mcp-it.sh`](../../indexer/scripts/mcp-it.sh) | reports on stdout and in `$C` | corpus or indexer execution | no | as phase 4; `shape.sh` installs ruff from the network |
| 6 | Compare against the right baseline | the runs of phase 4 | `micro.py --compare`, [`judgment/`](../../indexer/scripts/judgment/), `gates.py`, [`checks/`](../../indexer/scripts/checks/); [benchmark](benchmark-and-statistical-protocols.md) §4.2, §4.5, §4.6, §5 | counts, samples | offline analysis | only with authorization to execute | the same `(tree, image)` pairs on both sides |
| 7 | Judge where the evidence allows | the source at the pinned sha | [semantic judgment](semantic-judgment-and-regressions.md) §4, §7 | verdicts | read-only (reading), then local edits (recording) | reading, yes; recording verdicts is an edit | the clones; for live snapshots, the private source, locally |
| 8 | Record the outcomes, the limits and what stays open | the verdicts | the expected lists, the case tables, the handoff's results ([semantic judgment](semantic-judgment-and-regressions.md) §5.4) | commits | local edits, then remote | edits only if the task asks; commits need the author | — |
| 9 | Update the handoff and the validation state | the evidence | the H5 handoff, the ROADMAP, `docs/history.md`, `docs/golden-questions.md` | a docs PR | local edits, then remote | edits only if the task asks; the PR needs the author | evidence that supports each change |

**The live side** runs around the merge, in its own order (the inventory's V21 to V25 and its §7):

| Phase | Canonical | Risk class | Who |
|---|---|---|---|
| Before the merge: picture, golden answers, dry-runs per snapshot, sections, graph against dry-runs | [`live/pre-merge.sh`](../../indexer/scripts/live/pre-merge.sh); [benchmark](benchmark-and-statistical-protocols.md) §4.10, §4.11 | live (read-only queries, private outputs) | with the author's authorization |
| The merge | GitHub | remote | the author |
| The reinstall: `install.sh` copies the **working tree** into `~/.aidd`, so `main` is checked out first | [`setup/install.sh`](../../setup/install.sh) | live (mutates the install) | the author only |
| Post-install checks and the refresh | [`setup/install-check.sh`](../../setup/install-check.sh); `atlas_status` | live | with authorization |
| After: the picture, the golden answers, the comparisons | `foto.sh`, `golden.py`, `graph_vs_dry.py`, the typed commands ([benchmark](benchmark-and-statistical-protocols.md) §4.11) | live, then offline | with authorization |
| The records: the golden round, `history.md`, the states | a docs PR, as #21, #24 and #26 were | remote | with the author's approval; the author merges |

## 3. Continuity: resuming after an interruption

### 3.1 What survives what

"Yes" means the artifact survives that event as it is. Nothing here has a confirmed backup beyond GitHub.

| Artifact | Canonical place | Conversation or agent lost | Reboot | This disk lost |
|---|---|---|---|---|
| Committed code and docs | `main`, on GitHub | yes | yes | yes |
| **The recovery's files** (§1) | this working tree and its index: staged, uncommitted, unpushed. **Later on 2026-10-26:** the commit `21f9670`, on `docs/h5-validation-recovery` and the local `main`; still unpushed | yes | yes | **no** |
| The reference branch | `h6/step1-proto`, local and on GitHub | yes | yes | yes |
| The draft release `h6-step1-results` | GitHub | yes | yes | yes |
| CI's baselines and artifacts | the Actions cache (until evicted); artifacts for 14 days | yes | yes | yes, within those limits |
| Clones, runs, micro bases, H6's raw data | `$C` (`~/.cache/aidd-corpus`) | yes | yes | no |
| Images: the current one, and the untagged `927f5b4115c5` | Docker | yes | yes (unless pruned) | no |
| PR #27's private live data | `.local/indexer/pr27/` | yes | **yes: it survived the reboot of 2026-10-26, 89 of 89 hashes** | **no: no backup** |
| The transcripts (`$T` and later ones) | the agent's project folder, outside the repository | yes, as files | yes | no |
| The agent's memory files | outside the repository | yes | yes | no |
| **Scratchpads** | `/private/tmp/…` | the next session gets a new one | **no:** emptied on 2026-10-22 and 2026-10-26 | no |
| The live graph | the install's Neo4j | yes | yes | no; and the state of `main`'s build before the reinstall is gone for good |

**A scratchpad is never durable storage.** Anything worth keeping goes to the repository (non-sensitive), to `$C`
(derived data) or to `.local/` (private). **[practice]**: the memory "Scratchpad lost on reboot"; the inventory,
V29.

Surviving one reboot on one disk is not a backup. **No copy of `.local/indexer/pr27/` outside this disk was
checked, and none is claimed.** Being ignored by git keeps it out of the repository. It does not keep it anywhere
else.

### 3.2 Reconstructable, not regenerable, missing

**Reconstructable,** with the cost of a run and the right authorization:

- a corpus or hold-out run, from its commit and the pinned clones. In CI a baseline is recomputed on a miss (H7-D1);
- a micro base for a `(tree, image)` pair: `micro.sh --base-only`;
- a snapshot's export, with `git archive` of its sha, and the code copies, with `git archive` of a commit (the local
  README of `.local/indexer/pr27/`);
- a lost scratchpad script, from `$T`, with [`recovery/recover.py`](../../indexer/scripts/recovery/recover.py) or
  [`recovery/heredoc.py`](../../indexer/scripts/recovery/heredoc.py) (V29);
- the counts of a past micro judgment, from `$C/micro-fresh`. They were re-derived on 2026-10-24.

**Not regenerable as they were:**

- **The "before" picture and answers of PR #27:** the graph no longer holds `main`'s build. The only copy is
  `.local/indexer/pr27/`.
- **The judged samples:** a new draw gives other items (the benchmark protocols, §8, gap 6), and the `.view.txt` files
  were lost with `$S`.
- **The timings:** the noise is about 28 %, and the machine's state has moved on.
- **H6's measurements:** the image they ran on is not identified. An untagged image can be pruned, as
  `927f5b4115c5` could.
- **`why_a.py`'s attribution:** only in part in `$T`.

**Missing, or never created:**

- `live-check.sh` (H7 slice 4);
- PR #27's after picture and golden answers;
- the eleventh golden round;
- a file of verdicts (H7-D2);
- `install-check.sh`'s output for the reinstall of 2026-10-24;
- C#'s per-site attribution;
- the checks of Go's facts, of `tools/list` and of the ASTs (V19).

Each one's grounds are in the catalog's §5.

### 3.3 Which source to believe when they disagree — **[recommendation]**

The sources rank as follows. The ranking is proposed here, from the cases this recovery met; no document fixes it.

1. **The artifact itself, or the code at a named commit.** A file exists or it does not, and a script does what its
   code does. Example: the catalog said "17 scripts" on the H6 branch; `git ls-tree` shows 16 and a README.
2. **The versioned rules at `HEAD`,** for what the method requires: `AGENTS.md`, the decisions, the handoffs.
3. **Recorded outputs** for what ran and what it gave: CI's checks, the evidence documents, the golden rounds. They
   must say which tool produced them. "Identical in every section" rests on `dry_sections.py`'s keys for PR #27
   (semantic judgment, §6).
4. **The transcripts,** for what a session did, and with which command.
5. **A PR's description** is a claim, not evidence. PR #27's body ticks an after-merge item that does not exist (the
   inventory, §9, contradiction 10).

When two sources disagree, record both and the evidence for each. **Never reconcile them silently, and never rewrite
the historical one.** This document, too, leaves PR #27's body as it is.

### 3.4 After each kind of interruption

- **A lost conversation, or an interrupted agent:**
  - read this document, then §8;
  - check whether anything is still running. `corpus.sh`'s and `micro.sh`'s containers carry `aidd.corpus=<label>`
    and `aidd.micro=<label>`, but `micro-fresh.sh`'s and `time-alone.sh`'s carry no label (checked on 2026-10-26).
    So also list the containers of the image `aidd-indexer:local`, besides the stack's own;
  - an interrupted run leaves a partial folder, so it is never compared. Start it again under a new label: `corpus.sh`
    refuses a label that exists, and on Docker Desktop `micro.sh` cannot reuse its head's path
    ([benchmark](benchmark-and-statistical-protocols.md) §3).

  **[documented]** (the scripts; the H5 pitfalls)
- **A reboot:**
  - the scratchpad is gone; `$C`, `.local/`, the repository and the transcripts stay;
  - a script that lived only in the scratchpad is rebuilt from `$T` (V29);
  - a worktree that lived in the scratchpad is listed by git as prunable. Pruning it changes git's metadata, so it
    waits for authorization;
  - **check the stack, too.** After the reboot of 2026-10-26 the install's Neo4j looped on restart: its
    `neo4j.conf`, in the container's own layer rather than a volume, held 35 NUL bytes, and the image's entrypoint
    appended a setting again at each start until the setting was declared 164 times. The graph is in the
    `neo4j_data` volume. The cause of the NUL bytes is inferred, not proven: the reboot. Recreating the container
    is a change to the install, the author's to make. The author recreated it later that day. The volume kept the
    graph, and the new `neo4j.conf` declares the setting once. Before any live step, check that `atlas` is online
    and holds its snapshots, not only that the server started.

  **[practice]**
- **A lost scratchpad's outputs:**
  - the protocol's summaries and the judged samples cannot be recovered as files;
  - the evidence documents keep their summaries;
  - counts can be re-derived from `$C`, and samples cannot.
- **A lost disk:** everything not on GitHub goes with it. That is the recovery's files (committed later that day as
  `21f9670`, but not pushed), `.local/`, `$C`, the transcripts and the untagged image. **This is the largest
  continuity risk, and no backup policy exists for it (§4.3).**

## 4. Persistence and privacy

### 4.1 What goes where

| Class | Examples | Where | In git | Basis |
|---|---|---|---|---|
| Durable, non-sensitive procedures | the CI scripts; the local tools in `indexer/scripts/`; these documents | the repository | yes. The recovery's files are staged, not yet committed; later on 2026-10-26, committed as `21f9670`, not pushed | `AGENTS.md`; the catalog |
| Reconstructed scripts | `json_paths_diff.py`, `walkcmp.py`, `dump.py`, `mutate.sh`, the `checks/a*.py` | the repository, **only** with their provenance in the catalog (nature "reconstructed"), and in the file when the author asks, as `dump.py`'s docstring line | yes, staged | the author's conditions, 2026-10-24 and 2026-10-26 **[practice]** |
| Reconstructable tools not persisted | `why_a.py`, `go_graph_diff.py`, H2's verdict tools, `h6/measure.py` | `$T` | no; persisting one needs the author's authorization | the catalog, §4 |
| Private inputs and outputs | the golden calls, the live pictures, the dry-runs, the snapshot exports, the answers | `.local/` (ignored), or a folder outside the repository | **never** | `AGENTS.md`; the rule `/.local/` in `.gitignore`; the inventory, V31 |
| Derived, regenerable data | clones, corpus runs, baselines, micro bases | `$C`; CI's cache | no | H2-D3; H7-D1 |
| Historical evidence whose loss is irreversible | PR #27's before picture and answers; the transcripts; the past PRs' micro-fresh runs (the inputs of every re-derivation); H6's raw data | `.local/`, the agent's folder, `$C` | no | §3.2 |

What reaches the repository from private data is counts, snapshot numbers and public repos only:

- no private name: **[documented]** (`AGENTS.md`; the golden doc's header, "described in shape, not in content");
- snapshots by number: **[practice]** (the inventory, V31).

### 4.2 `.local/indexer/pr27/`

`.local/indexer/pr27/` is local evidence, ignored by git (`/.local/` in `.gitignore`), and private: mode 700 for the
folder, 600 for its files. It is described here only as far as its own `README.md` and `SHA256SUMS` describe it:

| Path | Purpose |
|---|---|
| `before/` | the 15 lists of the graph's picture, taken while the graph held `main`'s build |
| `before/golden/` | the 27 golden answers at the same time |
| `dry/` | the dry-runs of each snapshot by `main`'s code and the branch's, with their logs |
| `pre-merge/` | the logs of the read-only check before the merge |
| `original/` | the golden script as it ran |
| `golden-calls.json` | the 27 calls, in the shape `live/golden.py` reads |
| `SHA256SUMS` | 89 entries |
| `README.md` | how to check and use the folder, and the steps still to run |

Its rules:

- **Check it before using it:** `shasum -a 256 -c SHA256SUMS`, then the versioned manifest in
  [the PR #27 evidence](evidence/pr27-validation-state.md), §5.
- **Write every new output into a new folder there,** never into `before/`.

Nothing in it was moved, renamed or written by this task. Its fingerprint was the same before and after.

### 4.3 Decisions that are still open

Each of these is recorded here, not decided:

- **A backup of `.local/indexer/pr27/`:** where, encrypted or not, and who keeps it.
- **Committing the recovery's staged files,** in which commits and through which PR. The commits follow `AGENTS.md`.
- **Retention:**
  - of `$C/micro-fresh`, 6.9 GB, which holds the inputs of the re-derivations;
  - of the transcripts;
  - of the untagged image `927f5b4115c5`.
- **Persisting the reconstructable tools** listed in the catalog's §4.
- **H7-D2,** how verdicts are recorded.

## 5. Execution boundaries

### 5.1 Risk classes

**Permission to inspect or to document a procedure is not permission to run it.** Each class needs its own
authorization, given for the task at hand. Approval in one task does not carry over to the next. The rules below come
from the author's standing instructions, which the inventory's §3 records as "operating constraints", and from
`AGENTS.md`.

| Class | Examples | What it writes | Authorization |
|---|---|---|---|
| **1. Read-only inspection** | `git status`, `log`, `show`, `ls-tree`, `rev-parse`, `worktree list`; reading files; listings; `docker image inspect`, `docker ps`; `shasum -c`; `gh pr view`, `gh api` (GET) | nothing | allowed in a documentation task, as the request grants it |
| **2. Offline analysis of existing artifacts** | `chain_diff.py`, the `ext_*.py`, `dry_sections.py`, `graph_vs_dry.py`, `json_paths_diff.py` on saved data, with `python3 -I` | stdout, or a file chosen outside the repository; private outputs only into a new folder under `.local/` | the task must authorize running it |
| **3. Local generation or mutation of files** | editing docs or scripts; a new folder in `.local/`; a file in `$C` | the working tree, `.local/`, `$C` | docs edits when the task asks; `.local/` and `$C` writes when it says so. `before/` is never written |
| **4. Corpus or indexer execution** | `corpus.sh`, `micro.sh` (and `--base-only`), `micro-fresh.sh`, `protocol.sh`, `time-alone.sh`, `test.sh`, `mcp-it.sh`, `shape.sh`, `dump.py` in the image, H6's benches | `$C`; Docker images and containers; for `mcp-it.sh`, a throwaway Neo4j | an explicit authorization. Run in the background, one protocol at a time, and never edit the mounted code during a run |
| **5. Live install, refresh, or production-like operations** | `foto.sh`, `golden.py` (one of its calls is a write the MCP must refuse), `dryrun-live.sh`, `pre-merge.sh`, `install-check.sh` (it reads the install's `.env`), `install.sh`, a refresh | the install's state; private outputs | an explicit authorization for each run. **The install and the reinstall are the author's alone** |
| **6. External or remote changes** | commits, pushes, PRs and their bodies, labels, merges, CI re-runs, releases; also the git index, branches and worktrees | GitHub; git's metadata | the author's approval for each one. The author merges. Commits are one conventional line, signed |

### 5.2 Two notes on the boundaries

- **Read-only is not harmless.** Class 1 must not print private names into anything that leaves the machine.
  `dry_compare.py`'s output and `foto.sh`'s lists name the tenants, as their code shows (the inventory, V31).
- **A live check that only reads** (`foto.sh`, `golden.py`) still touches the install. It needs class 5's
  authorization. **[practice]**: "the live install is read-only for the agent".

### 5.3 PR #27: what is still pending (checked on 2026-10-26)

None of these steps was performed by this task.

| # | Step | State | Evidence | Class |
|---|---|---|---|---|
| 1 | The "after" picture | not taken: **blocked on 2026-10-26**, the install's Neo4j down (§3.4). **Taken later that day** | `.local/indexer/pr27/after/` | 5 |
| 2 | The golden answers after | not taken: blocked the same way. **Taken later that day** | `after/golden/` | 5 |
| 3 | The before/after comparison: the 15 lists, `graph_vs_dry.py` with both pictures, the answers | not done. **Done later that day, and it passes** | the PR #27 evidence, §9 | 2, after 1 and 2 |
| 4 | The eleventh round, and PR #27's line in `docs/history.md` | absent | the golden doc ends at the tenth round; `history.md` has no `#27`; no PR after #27 | 3, then 6 |
| 5 | The ROADMAP's and the H5 handoff's state | out of date. Corrected in the working tree later that day, uncommitted | ROADMAP: "is done and goes to review"; the handoff: "done on 2026-10-23, before its review" | 3, then 6 |
| 6 | The micro base for `main`'s tree (`ed46a54b…`) and the image `f07550cbe2e2`, before the next `micro.sh` or `protocol.sh` | **made on 2026-10-26**, with authorization: 12 of 12 | `$C/micro/base-ed46a54b…-f07550cbe2e2` | 4 |
| 7 | `install-check.sh`'s output for the reinstall of 2026-10-24 | **still unknown.** A run on 2026-10-26, with authorization, failed: 10 failures, all from the Neo4j loop. A run after the recreation passes | the PR #27 evidence, §8 and §9 | 5, or the author's own output |

Also unverified on 2026-10-26: the live graph's build and freshness, last read on 2026-10-24, since the `atlas` MCP
did not connect while the install's Neo4j was down.

**Later on 2026-10-26** the author recreated the Neo4j container and asked for steps 1 to 3 to be run. They pass, and
the build and freshness were read again: the same build, and no snapshot `outdated` (the PR #27 evidence, §9).

- **What is left:** steps 4 and 5, in one docs PR, and step 7's output of 2026-10-24.
- **Step 6's base no longer matches the tag.** It is keyed by `f07550cbe2e2`, and the tag now names `9e6dd3753826`,
  so the next `micro.sh` or `protocol.sh` makes a new base first.

## 6. Branch and version dependencies

### 6.1 `h6/step1-proto`

The branch is at `6ccf4a0`, locally and on GitHub, and is never to merge (H6). Only it holds:

- `indexer/scripts/h6-step1/`: 16 scripts and a README;
- its `results/`: 201 files;
- the prototype they measure: `core/pipeline.py` and `pipeline_pkg.py`.

Which scripts need the branch's code, and which only read results, is in
[the benchmark protocols](benchmark-and-statistical-protocols.md), §4.8.

**Why its numbers are not `main`'s:**

1. **The code is a prototype.** It replaces `extract_tree` with a map, a reduce and a cache that `main` does not have.
2. **The branch was cut from H5 at `374e243`** (the corpus report, "H6 step 1"). That is before H5's later steps, and
   its copies of `http_corpus.py`, `shape.py`, `mcp-it.sh` and `gates.py` are older (the catalog, §2).
3. **The image it ran on is not identified,** and a fresh run would use today's.
4. **Its correctness checks** compared it with `main` of that time, against `-28`, not `-29`.

So a result from the branch describes the prototype at its commit. It becomes a fact about `main` only once H6 is
plugged into `main` and measured there.

**How to work with it:**

- **To read it,** without switching anything: `git show h6/step1-proto:<path>`, `git ls-tree`, `git diff`, `git log`
  on the ref.
- **To run it,** a separate worktree (`git worktree add --detach <path> origin/h6/step1-proto`, the catalog, §2).
  Making a worktree changes git's metadata, so it needs class 6's authorization.
- **Never switch the main checkout's branch:** `install.sh` copies whatever is checked out.
- **No branch script is copied into `main`.**

### 6.2 Historical code versions on `main`

- **A measurement belongs to its `(code tree, image, baseline)`,** and is valid only for that triple. Examples:
  - PR #27's protocol measured each commit's worktree against `main` at `274d63b`, whose `aidd_indexer` tree is
    `b15e9385…`;
  - its micro base for that tree exists only with the image `927f5b4115c5`, which is now untagged.

  **[documented]** (`micro.sh`'s keys)
- **After a reinstall,** the image changes, and the old base runs serve the old image only (the H5 pitfalls).
- **A worktree of an older commit runs that commit's own `corpus.sh`.** Only the protocol scripts come from the
  checkout ([benchmark](benchmark-and-statistical-protocols.md) §4.4).
- **The local repository holds branches that GitHub does not,** such as `backup/h5-374e243` and the merged feature
  branches. They were not inspected for this document.

## 7. Discrepancies, and what each claim rests on

Six claims are kept apart:

- **described as done in a PR;**
- **present as an artifact;**
- **reproducible;**
- **executed;**
- **checked:** its output verified;
- **judged:** a semantic verdict backed by source evidence.

| Item | Described as done in a PR | Present as an artifact | Reproducible | Executed | Checked | Judged |
|---|---|---|---|---|---|---|
| PR #27's after picture and eleventh round | **yes, ticked** | no | needs the live install | no | no | no |
| PR #27's micro judgment | yes | the runs in `$C/micro-fresh` | the counts yes; the samples no | yes, historically | the counts, re-derived on 2026-10-24 | reported in prose; no item recorded |
| PR #27's live dry-runs, identical | yes | `.local/…/dry/` | the comparison, from saved data | yes, historically | re-derived on 2026-10-24 | not applicable; identical by `dry_sections.py`'s keys only |
| PR #27's golden answers before | — | `.local/…/before/golden/` | no: the graph has changed | yes | integrity only (`SHA256SUMS`, the manifest) | no |
| C#'s type facts equivalence (PR #23) | yes (the handoff) | `checks/dump.py`, reconstructed | with Docker and the two codes | yes, historically | `IDENTICAL` in `$T` | not applicable |
| H6's step 1 and 2 numbers | yes (the corpus report) | `results/` on the branch | partly (§6.1) | yes, historically | the branch's text results | not applicable |
| The `checked` sample's verdicts | — | the expected lists | as records | yes | — | yes, per item, without how each verdict was reached |

**The inventory's contradictions,** to read rather than to repeat (§9):

- 1, PR #27 merged while the docs say "to review";
- 3, sampling per case or per kind;
- 4, 12 repos against 23 or 25;
- 5 and 9, the times;
- 8, the micro base's conventions;
- 10, PR #27's body ticking an undone item.

None of them was reconciled by editing a PR or a historical record.

## 8. A checklist for resuming H5 — **[recommendation]**

These are read-only steps, in order. They grow out of the documented workflow, but the list itself is proposed here.
Every command reads only. Under zsh, keep separators free of `====`, and keep backticks out (V30).

1. **Read the series:**
   - [the inventory](validation-inventory.md): §1, §3 and §9;
   - [PR #27's evidence](evidence/pr27-validation-state.md);
   - this document's §1 and §5.3.
2. **Read the method:**
   - [the catalog](resource-catalog.md);
   - [the benchmark protocols](benchmark-and-statistical-protocols.md);
   - [semantic judgment](semantic-judgment-and-regressions.md);
   - the H5 handoff's state and "Pitfalls".
3. **Read git's state, and change nothing in it:** `git status --porcelain`, `git diff --cached --stat`,
   `git branch --show-current`, `git log --oneline -1`, `git worktree list`. Staged files are someone's work in
   progress: leave the index as it is.
4. **Check that what you will rely on exists:**
   - each script, by its path in the catalog;
   - `.local/indexer/pr27/` with `shasum -a 256 -c SHA256SUMS`, run inside it;
   - the baselines, with `ls ~/.cache/aidd-corpus/runs/2026-10-18-v2-baseline-29`.
5. **Pin the versions:**
   - the code tree: `git rev-parse <ref>:indexer/aidd_indexer`;
   - the image: `docker image inspect -f '{{.Id}}' aidd-indexer:local`;
   - whether a micro base exists for the pair: `ls ~/.cache/aidd-corpus/micro`;
   - the branch of any H6 script: `git ls-tree h6/step1-proto`.
6. **List what is missing,** and what cannot be regenerated (§3.2), before planning anything that needs it.
7. **Sort the next tasks by risk class** (§5.1), and ask for each class's authorization separately.
8. **Review PR #27's pending items** (§5.3) without running them, and check that each is still pending.
9. **Record every new finding with its provenance:** the source, the date, its evidence term and its label.
10. **Change a handoff, the ROADMAP or a history line only when the evidence supports it,** in a task that asks for
    it, with the commits and the PR left to the author.

## 9. References

- **The series:**
  - [the validation inventory](validation-inventory.md);
  - [the resource catalog](resource-catalog.md);
  - [the benchmark and statistical protocols](benchmark-and-statistical-protocols.md);
  - [semantic judgment and regressions](semantic-judgment-and-regressions.md);
  - [PR #27's validation state](evidence/pr27-validation-state.md);
  - [PR #5's validation plan](evidence/pr5-validation-plan.md).
- **The scripts:**
  - [the scripts' README](../../indexer/scripts/README.md);
  - [`protocol/`](../../indexer/scripts/protocol/), [`judgment/`](../../indexer/scripts/judgment/),
    [`checks/`](../../indexer/scripts/checks/), [`probes/`](../../indexer/scripts/probes/),
    [`live/`](../../indexer/scripts/live/), [`recovery/`](../../indexer/scripts/recovery/);
  - [`corpus.sh`](../../indexer/scripts/corpus.sh), [`micro.sh`](../../indexer/scripts/micro.sh),
    [`gates.sh`](../../indexer/scripts/gates.sh), [`test.sh`](../../indexer/scripts/test.sh),
    [`mcp-it.sh`](../../indexer/scripts/mcp-it.sh);
  - [`setup/install.sh`](../../setup/install.sh), [`setup/install-check.sh`](../../setup/install-check.sh).
- **The method:**
  - [`AGENTS.md`](../../AGENTS.md);
  - [the H5 handoff](../handoffs/H5-indexer-refactor.md);
  - [the H6 handoff](../handoffs/H6-extraction-pipeline.md);
  - [the H7 handoff](../handoffs/H7-regression-gates.md);
  - [the ROADMAP](../ROADMAP.md);
  - [the history](../history.md);
  - [the golden questions](../golden-questions.md);
  - [the corpus report](../corpus-report.md).
- **Outside the repository:**
  - `h6/step1-proto` and the draft release `h6-step1-results`;
  - `$C`;
  - the transcripts;
  - `.local/indexer/pr27/` (private, local, with no backup).
