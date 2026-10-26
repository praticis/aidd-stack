# The indexer's benchmark and statistical protocols

> The second of five documents on how the indexer's changes are validated; the first is
> [the inventory](validation-inventory.md). This one covers what is measured and how it is counted: the runs that
> produce numbers, the scripts that compare them, the formulas they apply, and the thresholds a result is held to. It
> is written for a developer, or a coding agent, resuming H5.
>
> **Written on 2026-10-26**, on `main` at `0725d47`. The sources are:
>
> - the scripts in this working tree;
> - the reference branch `h6/step1-proto`, read with `git show` and never checked out;
> - the versioned docs;
> - the previous session's transcript (`$T`).
>
> `$S`, `$C` and `$T` are defined in the inventory. **Nothing was measured to write it:** no benchmark, no protocol and
> no live check ran. The commands that did run were read-only:
>
> - listings of `$C`;
> - `git show` on the branch;
> - the integrity check of `.local/indexer/pr27/` (89 of 89 hashes OK);
> - the extraction of past commands from `$T`;
> - a check of Python's set order on synthetic data (§8, gap 6).
>
> **Its place in the series.** The inventory's §10 proposed "reference sets and runs" as the second document and
> "judgment and statistics" as the third. This one was requested as "benchmark and statistical protocols", and covers
> the measured part of both. What it leaves to the later documents:
>
> - preparing the clones and the expected lists (V01, V02);
> - the decision rules of a judgment, beyond their counts (V05, V09);
> - the live install's operation (V24).
>
> Each resource's origin and safety are in [the resource catalog](resource-catalog.md).

## 1. Scope and evidence terminology

### What this document covers

| Inventory id | Procedure | Here |
|---|---|---|
| V07 | The corpus and the hold-out against their baselines | §4.1 |
| V08 | Precision, recall and the gates; PR #5's offline checks | §4.2 |
| V10 | The micro graph, compared record by record | §4.3 |
| V13 | The protocol per commit | §4.4 |
| V11 | The micro graph's changes by kind and class | §4.5 |
| V12 | The loss analysis | §4.6 |
| V17 | Timing alone | §4.7 |
| V18 | H6's benchmarks and replay | §4.8 |
| V19 | The equivalence of a representation | §4.9 |
| V21, V22 | The live graph against the dry-runs; the dry-runs per snapshot | §4.10 |
| V23, V25 | Two pictures of the graph and two sets of golden answers, compared | §4.11 |
| V03, V04 | The baselines and the hold-out, as inputs and as rules | §6 |

Out of scope: V01, V02, V05, V06, V09 (their counts are here, not their rules), V14, V15, V16 (one threshold row in
§5.12), V20, V24 and V26–V31.

### Evidence terms

The classes are the inventory's; this document only names them in words. Where it found a discrepancy with the
inventory or the catalog, it says so (§8, and the final report of the step that wrote it).

| Term | Meaning | In the inventory and the catalog |
|---|---|---|
| **Confirmed** | read in a versioned file at `0725d47`, or on the reference branch at `6ccf4a0`; a CI run; or a read-only check made on 2026-10-26 | class **C** |
| **Reconstructed** | an artifact rebuilt from `$T`, not an original file that survived | nature "reconstructed" |
| **Partially confirmed** | the implementation exists, but its complete execution sequence or its historical evidence is incomplete | class **P** |
| **Historical only** | supported only by historical notes or output: `$T`, the lost `$S`, or the handoffs' prose about a run | class **R** |
| **Not found** | in no recovered source | class **U**; the catalog's §5 |
| **Inferred** | concluded from code or context, and not checked by a run | class **I** |

### Three separate claims

For each procedure, §4 answers three questions, each with its own evidence:

1. **Available:** the implementation exists, and where it is.
2. **Reproducible:** the inputs and the environment it needs exist now. This was checked read-only on 2026-10-26,
   unless stated otherwise.
3. **Executed:** a run was made and its result checked. Each run has a kind:
   - **CI:** a GitHub Actions run, confirmed with `gh`;
   - **historical:** a run whose output survives only in `$T`, a handoff or the evidence documents;
   - **re-derived:** a persisted script run again on 2026-10-24 over saved inputs, which gave the saved output byte for
     byte. A re-derivation checks the script and its arithmetic, not the measurement: it reads the same dry-runs and
     measures nothing again;
   - **fresh:** a new measurement from the code and the clones. None was made during the recovery.

A script in the repository is not a run, and a recovered output is not a fresh reproduction.

### Measured, derived, interpreted

- **Measured:** what a run records. That is a dry-run's records, a corpus run's ids, a container's wall seconds and
  peak memory, or a live list's rows.
- **Derived:** what a script computes from measured data. That is precision and recall, the `N repo(s) differ` line,
  the sites by kind, or a median with its range.
- **Interpreted:** what a person concludes, such as "judged right", "within the noise", "a gain" or "a gap with a
  case". No script decides an interpretation, and H7 rules that an LLM never decides a verdict a gate reads.

## 2. Benchmark overview

"Fresh" means a run that measures code on clones or on the live install. "Artifacts" means a script over saved runs.

| Procedure | Measures or compares | Fresh or artifacts | Implementation | Runs in | Class |
|---|---|---|---|---|---|
| V07 corpus and hold-out | HTTP ids against a saved baseline; P/R against the lists | fresh, then a report over the saved runs | [`corpus.sh`](../../indexer/scripts/corpus.sh), [`http_corpus.py`](../../indexer/scripts/http_corpus.py), [`corpus_metrics.py`](../../indexer/scripts/corpus_metrics.py) | the image; `$C` | Confirmed |
| V08 gates | two corpus runs scored against the branch's lists; five gates and the micro verdict | artifacts | [`gates.sh`](../../indexer/scripts/gates.sh), [`gates.py`](../../indexer/scripts/gates.py); offline [`checks/a2_gabaritos.py`](../../indexer/scripts/checks/a2_gabaritos.py), [`a4_compare.py`](../../indexer/scripts/checks/a4_compare.py), [`a5_chain.py`](../../indexer/scripts/checks/a5_chain.py) | the image | Confirmed (gates); Reconstructed (offline) |
| V10 micro graph | full dry-runs, record by record | fresh | [`micro.sh`](../../indexer/scripts/micro.sh), [`micro.py`](../../indexer/scripts/micro.py); [`protocol/micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh) | the image; `$C` | Confirmed (`micro.sh`); Partially confirmed (`micro-fresh.sh`) |
| V13 protocol per commit | V07 and V10 on one commit's worktree | fresh | [`protocol/protocol.sh`](../../indexer/scripts/protocol/protocol.sh) | the image; `$C`; a worktree | Partially confirmed |
| V11 judgment by kind and class | the `CALLS` sites and edges that changed | artifacts | [`judgment/chain_diff.py`](../../indexer/scripts/judgment/chain_diff.py) and its viewers | host Python | Partially confirmed |
| V12 loss analysis | the edges to extension methods that went away | artifacts, plus the clones for source lines | [`judgment/`](../../indexer/scripts/judgment/): `ext_*.py`, `ext_loss.py`, `lost_ext.py`, `this_kind.py` | host Python | Partially confirmed |
| V17 timing alone | the corpus's wall time and four full dry-runs, on two codes | fresh | [`protocol/time-alone.sh`](../../indexer/scripts/protocol/time-alone.sh) | the image; `$C`; two worktrees | Partially confirmed |
| V18 H6 benches and replay | time, memory, the cache's misses per policy | fresh on the prototype; artifacts for their aggregates | `h6/step1-proto:indexer/scripts/h6-step1/` | a worktree of the branch | Partially confirmed |
| V19 equivalence | one representation against another, byte for byte | fresh | [`checks/dump.py`](../../indexer/scripts/checks/dump.py), [`checks/walkcmp.py`](../../indexer/scripts/checks/walkcmp.py) | the image | Historical only; scripts Reconstructed |
| V21, V22 live graph and dry-runs | the graph's `CALLS` and the dry-runs, by merge key; the two dry-runs, by section | fresh on the live install; artifacts for the comparisons | [`live/`](../../indexer/scripts/live/): `dryrun-live.sh`, `dry_sections.py`, `graph_vs_dry.py`, `dry_compare.py`, `pre-merge.sh` | the live install; host Python | Partially confirmed |
| V23, V25 pictures and golden answers | 15 lists and 27 answers, before and after | artifacts (two pictures) | [`live/foto.sh`](../../indexer/scripts/live/foto.sh), [`live/golden.py`](../../indexer/scripts/live/golden.py), [`live/json_paths_diff.py`](../../indexer/scripts/live/json_paths_diff.py); the comparison itself is typed commands | the live install; host Python | Partially confirmed |

How they chain in a PR of step 5, as PRs #20 to #27 ran them:

```
each code commit:   V13 = V07 (corpus, hold-out) + V10 (micro, through micro-fresh.sh)
a change of behavior: V11 on each commit against the one before, and on main against the tip; V12 on the losses
the PR:             V17 (main's worktree, then the tip's) · CI: V07, V10, then V08's gates
before the merge:   V22 dry-runs per snapshot · V21 with the "before" picture on both sides · V23, V25 "before"
after the merge:    V23 "after" and the diff · V21 with both pictures · V25 "after" and the diff
```

## 3. Prerequisites and artifact layout

### The environment

- **Docker,** with the indexer's image `aidd-indexer:local`. A missing image stops every script with "build the
  stack's indexer image first (docker compose build at the repo root)".
  - That command needs the installed `.env`: without it, compose stops on its required variables (checked on
    2026-10-26 with `docker compose config`).
  - CI builds the same image from `indexer/` alone, `docker build -t aidd-indexer:local indexer`, which a fresh fork can
    run. It was not run here: on this machine the tag is the live install's image.
  - The image's id keys the micro base runs: its first 12 hex digits locally (`micro.sh`), and 16 in CI
    (`AIDD_MICRO_IMAGE_KEY`).
  - On 2026-10-26 the id is `f07550cbe2e2`, the image built by the reinstall of 2026-10-24.
- **Docker's memory sets how many containers run at once:**
  - `corpus.sh` runs 3 from 9 GiB, 2 from 7 GiB, and 1 below that, at 3g each;
  - `micro.sh` runs 2 from 9 GiB, and 1 below that, at 5g each, since grafana's dry-run peaks at 4.4 GiB;
  - `micro-fresh.sh` runs 2 at once and `time-alone.sh` 1, at 5g each.
- **git,** for worktrees and `git archive`.
- **Host Python 3,** always with `-I`, and only on our own outputs. The `judgment/` and `live/` comparison scripts use
  the standard library only. The `checks/` scripts and `gates.py` import `corpus_metrics` and `aidd_indexer`, so
  they run in the image.
- **macOS:** the past chains ran under `caffeinate -i`, to keep the machine awake. No script requires it.
- **The working directory** is the repository's root for every command below, unless stated otherwise.
  - The shell scripts find their paths from their own location.
  - The `judgment/` scripts are the exception: they find `edges_lib.py` from `sys.argv[0]`. Call them by a path that
    includes their folder, such as `indexer/scripts/judgment/chain_diff.py`, since `python3 -I` does not put the
    script's folder on `sys.path`.

### The data outside the repository

| Path | What it holds | Written by | Durable | State on 2026-10-26 |
|---|---|---|---|---|
| `$C/repos/<repo>` | the clones at their pins | `http_corpus.py` and `micro.py --prepare`, through `corpus.sh` and `micro.sh` | yes | present |
| `$C/runs/<label>/<repo>.json`, `$C/runs/<label>.logs/` | corpus runs: the items, each container's log, `summary.txt`, `report.txt` | `corpus.sh` | yes | `2026-10-18-v2-baseline-29` (55 run files) and `2026-10-18-v2-holdout-26` (3) present |
| `$C/micro/code-<tree>/`, `base-<tree>-<image>/`, `<label>/`, `<label>.summary.txt`, `<label>.report.txt` | the base's code, the base's and the head's dry-runs (`<repo>.json.gz`, `<repo>.log`) | `micro.sh` | yes | 7 base directories; **none for `main`'s tree `ed46a54b…` with the image `f07550cbe2e2`** |
| `$C/micro-fresh/<label>-<HHMMSS>` with `-copy` and `-base`, plus `.summary.txt` and `.report.txt` | the head's dry-runs, then copies of the head's and the base's on fresh paths. The judgment reads the `-copy` and `-base` folders | `micro-fresh.sh` | yes | 6.9 GB in all, including PR #27's runs (85 entries `csn-n*`, among them `csn-n17-183358`, `-base` and `-copy`), PR #25's (41 entries `csb-*`) and Go's (30 entries `*h5-go*`) |
| `$C/protocol/<label>/` | `protocol.sh`'s outputs, at its adapted default | `protocol/protocol.sh` | yes | absent: the persisted copy has never run |
| `$C/h6/` | H6's raw runs, caches, replay windows and code copies | the H6 scripts | yes | present (`step1`, `replay`, `cache`, `code`, `grafana`, `history`, `storebench`) |
| `h6/step1-proto:indexer/scripts/h6-step1/results/` | H6's results as text | committed on the branch | yes | 201 files |
| The draft release `h6-step1-results` | the replay's records (107 MB) | — | yes | not downloaded |
| `.local/indexer/pr27/` | PR #27's private live data (§7) | copied from `$S/livecsn` on 2026-10-24 | on this disk only, with no backup | 89 of 89 hashes OK |
| `$S/…` | the previous session's scratchpad: the protocol's summaries, the judgment's outputs and judged samples, the live data | — | no | **emptied by the reboot of 2026-10-26** |

### Labels and fresh paths

Docker Desktop on macOS breaks the bind mount of a folder deleted and made again at the same path, and can serve a
file another container has just written cut short (the H5 handoff, "Pitfalls"). So every run needs a new path:

- `corpus.sh` refuses a label that exists ("the run … exists already: pick another --label"). Its default label is
  `<date>-<short sha>`, plus `-dirty` with local changes and `-holdout` for the hold-out.
- `micro.sh` names the head's runs `<date>-<short sha>[-dirty]`, and deletes and remakes that folder on every run. A
  second run on the same tree state therefore fails every head dry-run on Docker Desktop.
- `micro-fresh.sh` adds the time (`<label>-<HHMMSS>`), and copies both sides to new paths before comparing them.
- `protocol.sh` hands its label to `corpus.sh` (`LABEL` and `LABEL-holdout`) and to `micro-fresh.sh`. So a label
  serves one run only.

## 4. The procedures

### 4.1 V07 — The corpus and the hold-out against their baselines

**Purpose:** prove that the HTTP extraction did not change, or show exactly which items did.

**Commands.** From `corpus.sh`'s usage and `AGENTS.md`; `protocol.sh` runs the same two:

```sh
indexer/scripts/corpus.sh --label <new-label> --baseline 2026-10-18-v2-baseline-29
indexer/scripts/corpus.sh --holdout --label <new-label>-holdout --baseline 2026-10-18-v2-holdout-26
```

Other options are `--jobs N`, `--memory SIZE`, `--show N`, `--no-expected` and a list of repos. The clones and runs
live in `$AIDD_CORPUS_HOME`, by default `~/.cache/aidd-corpus`, and the image is `$AIDD_INDEXER_IMAGE`.

**Outputs:**

- `$C/runs/<label>/<repo>.json`, which holds `repo`, `sha`, `endpoints`, `calls` and `warnings`;
- `$C/runs/<label>.logs/`:
  - one log per container, ending in `peak_memory_bytes=…`;
  - `summary.txt`, one line per repo, `<repo> <ok|failed(rc)> <seconds>s <peak bytes>`;
  - `report.txt`.

The report gives, per repo:

- `baseline: identical`, or the counts per kind (`endpoints -a +b ~c | calls -a +b ~c`) with the items behind them;
- `expected <kind> (<source>): P … R … | extracted … expected … fp … fn …`;
- `checked <kind>: P … (ok/judged, … pending, … stale)`.

It ends with:

- `baseline <dir>: N repo(s) differ — <repos>`;
- the per-language table;
- the table of miss categories.

`corpus.sh` then prints `run <label>: <s>s wall, <jobs> at once under <memory> each` and the three largest peaks. It
exits 1 when a repo failed, and the report leaves that repo out. It exits 2 on a missing image, a missing baseline or
a label that exists.

**Fresh or artifacts.** It is a fresh extraction. `http_corpus.py --reuse runs/<run> --expected` only rescores a saved
run, and its help says: "never for measuring an extractor change".

**In CI** the base is not `-29`. The base's own worktree runs `corpus.sh --label base-<indexer tree> --no-expected
--show 0`, and the head runs `--label head`, both cached by the base's `indexer` tree (H7-D1,
[`indexer.yml`](../../.github/workflows/indexer.yml)).

| Claim | State | Evidence |
|---|---|---|
| Available | Confirmed | the three scripts on `main` |
| Reproducible | Confirmed for its inputs: both baselines and the clones are in `$C`, and the image exists | the listing of 2026-10-26; nothing run |
| Executed | CI and historical | CI `corpus` on PR #27, 7m18s, passing; 17 local runs for PR #27 ([the PR #27 evidence](evidence/pr27-validation-state.md), §2); the corpus report's tables |

### 4.2 V08 — Precision, recall and the gates

**The gates, as CI runs them** (the [scripts' README](../../indexer/scripts/README.md)), over two runs labelled with
`--label` on both sides:

```sh
indexer/scripts/micro.sh; micro=$?
git log --format=%s origin/main..HEAD \
  | indexer/scripts/gates.sh --base runs/<base> --head runs/<branch> \
      --holdout-base runs/<base>-holdout --holdout-head runs/<branch>-holdout \
      --branch="$(git branch --show-current)" --commits - --micro-rc "$micro"
```

`gates.sh` maps each `runs/…` argument to `/corpus/runs/…` in the image. With no `--micro-rc`, `gates.py` gives no
micro verdict, and that gate passes. The report is Markdown, and the script exits 1 when a gate fails.

**PR #5's offline checks** (phase A, reconstructed). They ran on 2026-10-19 from `$S/val/`, as recorded in `$T`. The
persisted copies are in `indexer/scripts/checks/`, which the `/src` mount below already holds as `/src/scripts/checks/`.
No run was made from there. The A4 command, as it ran:

```sh
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src:/src/scripts -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD/indexer":/src:ro -v "$S":/val -v ~/.cache/aidd-corpus:/corpus:ro --entrypoint python aidd-indexer:local \
  /val/val/a4_compare.py /corpus/runs/2026-10-18-validate-main /corpus/runs/2026-10-18-validate-head \
  /src/tests/corpus_expected
```

The same day, with the same `docker run` prefix:

- **A4 on the hold-out:** the `-holdout` runs, followed by `--holdout`;
- **A5:** `/val/val/a5_chain.py /corpus/runs /src/tests/corpus_expected 2026-10-18-v2-baseline-27
  2026-10-18-v2-holdout-26`;
- **A2:** `/val/val/a2_gabaritos.py /val/main-pristine/indexer/tests/corpus_expected /src/tests/corpus_expected
  /corpus/runs/2026-10-18-v2-baseline-27`, where `main-pristine` was a copy of `main`'s tree in `$S`.

| Claim | State | Evidence |
|---|---|---|
| Available | Confirmed (gates); Reconstructed (A2, A4, A5) | `gates.py`, `test_gates.py`; the catalog, §2 |
| Reproducible | gates: yes, given two labelled runs. A2/A4/A5: their inputs are corpus runs in `$C/runs`, but the `validate-*` runs named above were not checked | — |
| Executed | CI (`gates`, 35 s on PR #27); historical (A2, A4, A5 for PR #5, the plan's "what came of it") | [PR #5's plan](evidence/pr5-validation-plan.md) |

### 4.3 V10 — The micro graph, record by record

**Commands.** From `micro.sh`'s usage:

```sh
indexer/scripts/micro.sh                         # the 12 repos, the base at main's tip
indexer/scripts/micro.sh --base-only             # only the base's dry-runs, kept for later runs
indexer/scripts/micro.sh --base REF [repo ...]   # another base; or only some repos
```

The extended set's base, as it ran on 2026-10-23 (from `$T`; the lines are wrapped):

```sh
caffeinate -i indexer/scripts/micro.sh --base-only eshop jellyfin btcpayserver umbraco vikunja gitea mattermost \
  grafana dispatch netbox ghost outline ardalis-clean-arch azure-saas bitwarden clean-arch-dotnet eshop-on-web \
  eshop-support notifo radarr rapid-blazor elsa smartstore
```

Through fresh paths ([`micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh)'s usage): `AIDD_REPO=<worktree>
indexer/scripts/protocol/micro-fresh.sh LABEL REPO...`, where `AIDD_REPO` defaults to this checkout.

**The base, in three conventions** (the inventory's contradiction 8):

| Who | The base | Source |
|---|---|---|
| `micro.sh` | `--base REF`, by default `main`, which is its tip | the script |
| `micro-fresh.sh` | `git merge-base main HEAD` of the measured tree: "main may have moved on with code the dry-runs do not run" | the script |
| CI | the merge commit's first parent (`HEAD^1`), passed as `micro.sh --base "$BASE"` | `indexer.yml` |

A base run is reused only by the same `aidd_indexer` tree **and** the same image key. `micro-fresh.sh` makes no base
runs, and stops with "no base run for: …" (exit 2) when one is missing.

**Outputs and the report:**

- `micro.sh` writes `micro/<label>.report.txt`, and prints it.
- Each repo is `identical` or `DIFFERS (files=… symbols=… calls=… imports=…)`, with the counts taken from the base.
- Each list that differs gets `-gone +new`, with up to `--show` records on each side.
- The report ends with `N repo(s) differ: <repos>`. `not compared: …` goes to stderr.
- Exit codes: 0 identical, 1 a repo differs or was not compared, 3 a dry-run failed, 2 usage.

`micro-fresh.sh` writes `<label>-<HHMMSS>/`, its `-copy` and `-base`, `.summary.txt` and `.report.txt` under
`$HOME/.cache/aidd-corpus/micro-fresh/`. It exits 3 when a dry-run failed, and otherwise with `micro.py`'s code.

Unlike `micro.sh`, it fixes:

- the home, `$HOME/.cache/aidd-corpus`;
- the image, `aidd-indexer:local`;
- 2 jobs at 5g.

It ignores `AIDD_CORPUS_HOME`, `AIDD_INDEXER_IMAGE` and `AIDD_CORPUS_JOBS`.

| Claim | State | Evidence |
|---|---|---|
| Available | Confirmed (`micro.sh`, `micro.py`); Partially confirmed (`micro-fresh.sh`: an adapted copy, syntax checked, never run from the repo) | the catalog, §2 |
| Reproducible | **Not yet:** no base exists for `main`'s tree and the current image, so `micro.sh --base-only` (with the repos to compare) comes first. PR #27's past runs are in `$C/micro-fresh` | the listing of 2026-10-26 |
| Executed | CI (`micro`, 6m35s on PR #27); historical (17 local runs on 23 repos for PR #27; 25 repos for Go's PRs) | [the PR #27 evidence](evidence/pr27-validation-state.md), §2 |

### 4.4 V13 — The protocol per commit, in worktrees

**Commands:**

```sh
git worktree add --detach <worktree> <commit>
AIDD_REPO=<worktree> indexer/scripts/protocol/protocol.sh <label> [REPO...]
```

`protocol.sh` runs three steps:

1. it moves into `$AIDD_REPO` and runs that tree's own `corpus.sh` against `AIDD_BASELINE` (by default `-29`);
2. it runs the hold-out against `AIDD_HOLDOUT_BASELINE` (by default `-26`);
3. it runs the copy of `micro-fresh.sh` next to itself, on the 12 repos and any given after the label.

The measuring code is therefore the commit's own. Only the two protocol scripts come from this checkout, and
`micro-fresh.sh` inherits `AIDD_REPO`.

**As it ran for PR #27** (2026-10-23, from `$T`). One worktree per commit, made with `git worktree add -q --detach
"$wt" <sha>`. Then a loop, `csn-chain.sh`, run as `caffeinate -i bash $S/h5/csn-chain.sh n5 n6 n7 n8 n9`. Its body:

```sh
CS=$(cat $S/h5/cs-extra.txt)      # the 11 C# repos of the extended set
for n in "$@"; do
  wt=$(cat $S/h5/csn-$n-wt.txt)
  AIDD_REPO=$wt $S/h5/protocol.sh "csn-$n" $CS
done
```

**Outputs:** `$AIDD_PROTOCOL_RUNS/<label>/{corpus,holdout,micro}.txt`, by default `~/.cache/aidd-corpus/protocol`.
These were originally in `$S/h5/runs/<label>/`. On stdout it prints `corpus rc=… <N repo(s) differ line> <time>`, the
same line for `holdout`, the micro report's lines, and `micro rc=…`.

| Claim | State | Evidence |
|---|---|---|
| Available | Partially confirmed: an adapted copy (the catalog, §7), syntax checked, never run from the repo | — |
| Reproducible | needs the micro base for the merge base's tree and the current image (§4.3); the baselines are present | the listing of 2026-10-26 |
| Executed | historical: `csn-n1`…`csn-n17` on 2026-10-23, and Go's `2026-10-21-h5-go-*` | [the PR #27 evidence](evidence/pr27-validation-state.md), §2; the 85 `csn-n*` entries in `$C/micro-fresh` |

### 4.5 V11 — The micro graph's changes by kind and class

**Commands.** From the scripts' docstrings:

```sh
python3 -I indexer/scripts/judgment/chain_diff.py BEFORE_DIR AFTER_DIR N REPO... > OUT.txt 2> SAMPLES.jsonl
python3 -I indexer/scripts/judgment/samples_view.py SAMPLES.jsonl ~/.cache/aidd-corpus/repos > VIEW.txt
python3 -I indexer/scripts/judgment/show.py ~/.cache/aidd-corpus/repos < SAMPLES.jsonl
python3 -I indexer/scripts/judgment/site_edges.py REPO FILE_SUFFIX:LINE[,...] DIR...
```

`BEFORE_DIR` and `AFTER_DIR` hold `<repo>.json.gz` dry-runs, as `micro.sh` and `micro-fresh.sh` leave them.

**As it ran for PR #27** (2026-10-23 21:40, from `$T`; the lines are wrapped):

```sh
M=~/.cache/aidd-corpus/micro-fresh
R="eshop jellyfin btcpayserver umbraco ardalis-clean-arch azure-saas bitwarden eshop-on-web eshop-support notifo radarr elsa smartstore"
python3 -I $S/h5/why/chain_diff.py $(ls -d $M/csn-n16-*-copy | tail -1) $(ls -d $M/csn-n17-*-copy | tail -1) 12 $R \
  > $S/h5/why/out/n17.txt 2> $S/h5/why/out/n17.jsonl
python3 -I $S/h5/why/chain_diff.py $(ls -d $M/csn-n17-*-base | tail -1) $(ls -d $M/csn-n17-*-copy | tail -1) 40 $R \
  > $S/h5/why/out/main-n17.txt 2> $S/h5/why/out/main-n17.jsonl
```

`main` against the tip reads micro-fresh's `-base` copy, which is `main`'s run, and the tip's `-copy`. Each commit
against the one before reads two `-copy` folders. The 13 repos are the C# repos that changed. `samples_view.py`
then turned each samples file into a `.view.txt` with the source lines (21:26, for `main-n16`).

**The sample sizes used** (`N` per kind, from every call in `$T`):

| PR | Each commit against the one before | `main` against the tip |
|---|---|---|
| #20 (Go) | 4 to 6 | none found among the recorded calls |
| #25 (C#) | 6 to 8 | 6 |
| #27 (C#) | 6 to 12 | 40 (at n9, n16 and n17) |

Once, between n11 and n12, `N` was 100 (`n12-all.jsonl`), to read the `dropped` sites. That shows at most 100 of
them, not every one.

**The per-case tools** need the per-site attribution file that `why_a.py` wrote (`WHY.jsonl`), which is not persisted
(the catalog, §4). The tools are [`edges_join.py`](../../indexer/scripts/judgment/edges_join.py) and
[`kinds.py`](../../indexer/scripts/judgment/kinds.py) (`BASE HEAD WHY.jsonl SAMPLE REPO...`),
[`cases.py`](../../indexer/scripts/judgment/cases.py) (`WHY.jsonl`) and
[`view.py`](../../indexer/scripts/judgment/view.py) (JSON lines on stdin, in the image with `/code` and `/repos`
mounted). They cannot run without that file.

| Claim | State | Evidence |
|---|---|---|
| Available | Partially confirmed: `chain_diff.py` and the viewers persisted (originals); the per-case tools persisted, but without their input | the catalog, §2 |
| Reproducible | the counts: yes, from existing artifacts (PR #27's `-base` and `-copy` folders are in `$C/micro-fresh`). The historical samples: **no**, they cannot be drawn again (§8 gap 6). Since 2026-10-26 the script sorts the sites before drawing, so a new sample reproduces | the runs of 2026-10-26 (§8, gap 6) |
| Executed | historical (PRs #20, #25, #27); **re-derived** on 2026-10-24: the persisted script, with stderr discarded, printed `n17.txt` and `main-n17.txt` byte for byte. The samples were not compared | this recovery's transcript; [the PR #27 evidence](evidence/pr27-validation-state.md), §3 |

### 4.6 V12 — The loss analysis

**Commands.** From each docstring, all run as `python3 -I indexer/scripts/judgment/<script>`:

| Script | Arguments | Output |
|---|---|---|
| [`ext_loss.py`](../../indexer/scripts/judgment/ext_loss.py) | `BEFORE AFTER REPO...` | per repo, the sites that lost an edge to an extension method, by what they have now; then `all:` |
| [`lost_ext.py`](../../indexer/scripts/judgment/lost_ext.py) | `BEFORE AFTER REPOS_DIR REPO...` | per repo, the sites that lose an edge into a file with C# 14 `extension(…)` blocks, and how many keep none |
| [`ext_sites.py`](../../indexer/scripts/judgment/ext_sites.py) | `BEFORE AFTER OUT.jsonl REPO...` | one row per lost edge; counts by old strategy and kind of `this` |
| [`ext_back.py`](../../indexer/scripts/judgment/ext_back.py) | `LOST.jsonl AFTER_DIR OUT.jsonl` | for `ext_sites.py`'s rows, which a later run has again |
| [`ext_judge.py`](../../indexer/scripts/judgment/ext_judge.py) | `BEFORE AFTER REPOS_DIR N SEED REPO...` | the changed sites by class of extension gained, with `N` seeded samples per class and their source lines |
| [`this_kind.py`](../../indexer/scripts/judgment/this_kind.py) | `BEFORE AFTER REPOS REPO...` | each `unique-name` edge gained to an extension: whether its `this` takes any value |

**As they ran** (from `$T`):

- PR #27, 2026-10-23 21:40: `lost_ext.py <csn-n17 -base> <csn-n17 -copy> ~/.cache/aidd-corpus/repos bitwarden elsa
  smartstore`.
- PR #25, 2026-10-22:
  - `ext_loss.py "$c3" "$c4" $R | tail -1`, and the same from `main`'s base to c6;
  - `ext_back.py $S/h5/ext/main-c6.jsonl <csb-c7 -copy> $S/h5/ext/back-c7.jsonl`;
  - `ext_judge.py <before> <after> ~/.cache/aidd-corpus/repos N SEED <repos>`, with N 10, 20, 24 and 14 and seeds 7,
    7, 3 and 5. **The seed was not `20261021`.**

  `R` was the 12 C# repos of that PR.

| Claim | State | Evidence |
|---|---|---|
| Available | Partially confirmed: persisted, originals or adapted (the import path only) | the catalog, §2 and §7 |
| Reproducible | from existing artifacts: PR #27's and PR #25's micro-fresh folders are in `$C` (85 and 41 entries), and the clones too. `ext_judge.py`'s past samples cannot be drawn again; since 2026-10-26 it sorts the sites, and two runs give the same output (§8 gap 6) | the runs of 2026-10-26 |
| Executed | historical: 188 extension edges lost in PR #25 (the H5 handoff; which script printed the number is not established); 45 sites lost to extension blocks in PR #27, and eshop's one site, gap 7. `ext_sites.py` was smoke-tested on 2026-10-24 on two repos | the inventory, V12 |

### 4.7 V17 — Timing alone

**Command.** From the script's usage:

```sh
indexer/scripts/protocol/time-alone.sh MAIN_WORKTREE BRANCH_WORKTREE
```

It takes `AIDD_BASELINE` (by default `-29`) and `AIDD_TIME_REPOS` (by default `umbraco elsa bitwarden smartstore`).
It runs:

1. each side's corpus, with that side's `corpus.sh`, under the label `<date>-<HHMMSS>-time-<folder>` in `$C/runs`.
   Only the lines matching `repo(s) differ|wall` are kept;
2. one full dry-run at a time of each repo, `main` then the branch, in a temporary folder under
   `$C/micro-fresh/time-XXXXXX` that it deletes. It prints `<repo> <side>: <s>s total; [resolve] …`.

Its output is stdout only.

**As it ran for PR #27:** as `time-csn.sh`, the same steps with fixed labels, on 2026-10-23, on `main`'s worktree
(`274d63b`) and n17's. The numbers are in [the PR #27 evidence](evidence/pr27-validation-state.md), §4: one run per
side.

| Claim | State | Evidence |
|---|---|---|
| Available | Partially confirmed: an adapted copy, never run from the repo | the catalog, §7 |
| Reproducible | needs two worktrees, the baseline, and a machine with no other load; nothing checks the load | — |
| Executed | historical (PR #27, PR #25 and earlier, in the corpus report's "H5 steps") | [corpus report](../corpus-report.md) |

### 4.8 V18 — H6's benchmarks and replay (reference branch only)

**Where:** `h6/step1-proto` at `6ccf4a0`, local and on `origin`, never to merge. Its 16 scripts and README are in
`indexer/scripts/h6-step1/`, beside `results/`. None is in this checkout.

- **Reading them** needs nothing: `git show origin/h6/step1-proto:indexer/scripts/h6-step1/<script>`.
- **Running them** needs a worktree of the branch, which leaves the main checkout's branch as it is: `git worktree add
  --detach <path> origin/h6/step1-proto` (the catalog, §2).

**The code-version dependency:**

- `bench.sh` mounts `AIDD_H6_CODE`, by default the worktree's own `indexer/`, at `/code`, and sets `AIDD_PIPELINE`
  and `AIDD_WORKERS`. Only the prototype's `core/pipeline.py` reads those.
- `replay.py` imports `aidd_indexer.core.pipeline`, which `main` does not have.
- The chains call the branch's own `scripts/corpus.sh`, `micro.sh` and `test.sh`.
- So these scripts need the branch's code. On `main` they would measure nothing of what they were written for.
- `aggregate.py`, `evaluate.py`, `same.py` and `store_bench.py` read results only, and run anywhere on their inputs.
  `store_bench.py` runs in the image.
- **Inferred:** the image gives the grammars and the Python. Today's `aidd-indexer:local` was built from `main` on
  2026-10-24, not the image H6 measured with. A fresh run would not be comparable with the recorded numbers.

**Commands.** From the branch's README and scripts. Paths are relative to the worktree's
`indexer/scripts/h6-step1/`:

| Script | Usage | As it ran |
|---|---|---|
| `fetch.sh` | `NAME SLUG SHA` | the windows vikunja `82b5cb3131ee` and mattermost `2de97aee85bc`, 40 first-parent commits each |
| `replay.py` | in the image: `python /step1/replay.py /hist --name NAME --out /out --commits 40 --workers 4` | `chain.sh`, for vikunja and mattermost |
| `evaluate.py` | `OUT_DIR [OUT_DIR ...]` | its output has the shape of `results/replay-eval.txt`; the call is not recorded |
| `bench.sh` | `LABEL SRC_DIR OUT_DIR PIPELINE WORKERS [CACHE_DIR]` | through `run_bench.sh` and `push_bench.sh` |
| `run_bench.sh` | `ROUNDS REPO...`, under `caffeinate -i` | `run_bench.sh 3 vikunja mattermost`; `run_bench.sh 1 grafana`; `AIDD_BENCH_OUT=bench2 run_bench.sh 3 vikunja mattermost grafana` |
| `push_bench.sh` | `REPO K...` | `push_bench.sh vikunja 12 28 38`; `push_bench.sh mattermost 19 25 30` |
| `batch_run.sh` | `CODE LABEL SRC OUT PIPELINE BATCH WORKERS [FREEZE]` | through the two package chains |
| `packages_chain.sh` | `MICRO_BASE`, `main`'s micro dry-runs | step 2, batches by package |
| `packages_2w_chain.sh` | — | step 2, 2 workers, with `gc_patch.py` |
| `aggregate.py` | `BENCH_DIR` | the medians of the step 2 tables |
| `same.py` | `A.json.gz B.json.gz` | after every prototype run, against today's |
| `store_bench.py` | in the image: `python store_bench.py /cache-entries /target --rounds 3` | the cache store table |
| `count_reads.py` | in the container, against `/repo` | the step 2 counts of reads |

Their outputs go to `$AIDD_H6_OUT`, by default `~/.cache/aidd-corpus/h6/step1`. The bench's lines go to
`<out>/bench/summary.txt`, and the pushes' to `push/summary.txt`. `packages_chain.sh` edits its copy of the code with
BSD `sed -i ''`, which is macOS's.

**Two discrepancies on the branch,** recorded here and left unedited:

- The README gives `evaluate.py` a `--typed-only` flag. The code reads every argument as a directory, and takes the
  typed digests from `*.typed.json` files when they exist. How `replay-eval-typed.txt` was made is not established.
- The README also says only round 1 of `results/bench-round1/` is valid: "a loop bug ran rounds 2 and 3 on no repo".

| Claim | State | Evidence |
|---|---|---|
| Available | Confirmed on the branch (read on 2026-10-26); none on `main` | `git ls-tree`, `git show` |
| Reproducible | **partly:** the text results are in git (201 files), the raw runs in `$C/h6`, and the replay's records in the draft release. A fresh bench needs the branch's worktree, a quiet machine and, for comparability, the image H6 used, which is not identified | — |
| Executed | historical: the corpus report's "H6 baseline", "H6 step 1" and its step 2 sections, and the branch's `results/` | [corpus report](../corpus-report.md) |

### 4.9 V19 — The equivalence of a representation

**C#'s type facts (PR #23).** As it ran on 2026-10-22 (from `$T`, and recorded in the catalog), once with each
code, then compared:

```sh
docker run --rm -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 -v "<code>/indexer":/src:ro \
  -v ~/.cache/aidd-corpus/repos:/corpus:ro -v "<scripts>":/scripts:ro -v "<out>":/out \
  --entrypoint python aidd-indexer:local /scripts/dump.py /out/<main|head>.tsv
cmp <out>/main.tsv <out>/head.tsv && echo IDENTICAL
```

**The walk (H5 step 2).** [`walkcmp.py`](../../indexer/scripts/checks/walkcmp.py) reads a file and a language
(`walkcmp.py FILE LANG`, from its code), in the image. How it was invoked is not established.

| Claim | State | Evidence |
|---|---|---|
| Available | Reconstructed (`dump.py`, `walkcmp.py`); Go's facts check, `tools/list`'s and the ASTs' **not found** | the catalog, §2 and §5 |
| Reproducible | `dump.py`: the clones are in `$C/repos`; the two codes come from `git` | — |
| Executed | historical: 35,255 C# files on each side, `IDENTICAL` (2026-10-22). Nothing since | the inventory, V19 |

### 4.10 V21, V22 — The live graph and the dry-runs

**Before the merge, read-only** ([`pre-merge.sh`](../../indexer/scripts/live/pre-merge.sh)'s usage):

```sh
indexer/scripts/live/pre-merge.sh LIVE_DIR GOLDEN_CALLS_JSON
```

`LIVE_DIR` must hold `main_src/indexer` and `head_src/indexer`, copies of the two codes. Before the run, each copy is
checked against `git ls-files` with `shasum` (the catalog, `pre-merge.sh`'s row). The script runs, in order:

1. `foto.sh LIVE_DIR/before`;
2. `golden.py` into `before/golden`;
3. `dryrun-live.sh LIVE_DIR LIVE_DIR/head_src/indexer LIVE_DIR/main_src/indexer LIVE_DIR`, whose first argument is
   not used;
4. `dry_sections.py LIVE_DIR/dry`;
5. `graph_vs_dry.py LIVE_DIR/before LIVE_DIR/before LIVE_DIR/dry`.

`dryrun-live.sh` reads:

- the snapshot list from `before/snapshots.txt`;
- the clones at `$HOME/workspace/<tenant>/<repo>`;
- `~/.aidd/atlas.yaml`.

It writes:

- `LIVE_DIR/snap/`;
- `LIVE_DIR/dry/<tenant>__<repo>__<ref>__{main,head}.json`, each with a `.log`.

Every output names the install's tenants, so `LIVE_DIR` lies outside the repository.

**After the merge** (inventory V21; PR #20's run of 2026-10-21 was `graph_vs_dry.py $S/livego/before $S/livego/after
$S/livego/dry`):

```sh
python3 -I indexer/scripts/live/graph_vs_dry.py <before> <after> <dry>
```

**Its exit code.** Until 2026-10-26 `graph_vs_dry.py` exited 0 whatever it found, and `pre-merge.sh` prints that code
as `graph rc=…`. It now exits 1 when any snapshot mismatches. A synthetic case and PR #27's data checked both codes.

**Reading the pre-merge run.** With the "before" picture on both sides, only the check "before = main" says something.
The other four hold only when `main`'s and the branch's dry-runs are equal. When they differ, "after = head" fails by
construction. On 2026-10-22 at 13:04, a check of this kind on `$S/livecs` filtered its output with `grep -vE
"MISMATCH: after|^$"` for that reason. By its folder's name and date it was PR #23's: an inference.

[`dry_compare.py`](../../indexer/scripts/live/dry_compare.py) `DRY_DIR BEFORE_DIR` compares more sections, but prints
tenant and repo names. Its output is for local use only.

| Claim | State | Evidence |
|---|---|---|
| Available | Partially confirmed: `graph_vs_dry.py`, `dry_sections.py`, `dryrun-live.sh` (originals); `pre-merge.sh`, `dry_compare.py` (adapted) | the catalog, §2 |
| Reproducible | the live runs need the install and the author's authorization. PR #27's dry-runs and before picture are in `.local/indexer/pr27/` (§7) | — |
| Executed | historical: the dry-runs for PRs #20, #23, #25 and #27 (the inventory, V22); `graph_vs_dry.py` for PR #20, before and after, for PR #27, before only, and on `$S/livecs`, before only (PR #23, inferred). **Re-derived** on 2026-10-24: `dry_sections.py` and `graph_vs_dry.py` on PR #27's saved data, byte for byte. **Fresh** on 2026-10-26: `graph_vs_dry.py` on PR #27's before and after pictures, 0 mismatching | `$T`; [the PR #27 evidence](evidence/pr27-validation-state.md), §5 |

### 4.11 V23, V25 — Two pictures and two sets of golden answers

**The picture** (the script's usage): `indexer/scripts/live/foto.sh OUT_DIR`. It runs read-only Cypher through
`docker exec` on `aidd-core-neo4j`, writes 15 lists sorted with `LC_ALL=C sort`, and prints each list's row count.

**The golden answers** (the script's usage): `python3 -I indexer/scripts/live/golden.py CALLS_JSON OUT_DIR [--url
URL]`. The default URL is `http://localhost:3005/mcp`. Before, the original script with its calls inside it ran as
`python3 -I $S/val/golden.py <out>/golden`.

- **The rewrite had not run against the live MCP** when this was first written: on 2026-10-26 the MCP was down
  (§7). Later that day, after the Neo4j container was recreated, it ran against the live MCP: rc 0, 27 of 27 calls
  reached.
- **It ran against a local stand-in for the MCP's HTTP,** with the example calls file. It read JSON, SSE, text and
  error answers as the original's code does. Two runs gave byte-identical files.
- **Its exit code:** since 2026-10-26 it is 1 when a call never reached the MCP. Before, both the original and the
  rewrite exited 0 with every call failed. An answer with `isError`, as the refused write, still counts as an answer.

**No script compares two pictures, or two sets of answers.** These commands ran by hand, recorded in `$T`, with the
lines wrapped:

PR #20, 2026-10-21 21:28, run in the folder that holds `before/` and `after/`:

```sh
for f in before/*.txt; do n=$(basename $f)
  if cmp -s $f after/$n; then echo "$n same"
  else echo "$n DIFFERS: -$(comm -23 $f after/$n | wc -l | tr -d ' ') +$(comm -13 $f after/$n | wc -l | tr -d ' ')"; fi
done
```

PR #25, 2026-10-22 18:46: the tenant masked in `labels`, the build masked in `snapshots`, and each golden answer
diffed with ISO timestamps masked. The loop named five calls by label; some labels name private repositories, so they
are written `<label>` here.

```sh
diff before/labels.txt after/labels.txt | sed -E 's/^([<>]) "[^"]*"/\1 T/'
diff <(sed -E 's/"0\.2\.15\+[0-9a-f]+"/BUILD/' before/snapshots.txt) \
     <(sed -E 's/"0\.2\.15\+[0-9a-f]+"/BUILD/' after/snapshots.txt)
for n in <label> ...; do diff <(python3 -I -m json.tool before/golden/$n.json) \
    <(python3 -I -m json.tool after/golden/$n.json) | grep '^[<>]' \
  | sed -E 's/"[0-9]{4}-[0-9]{2}-[0-9]{2}T[^"]*"/TS/g' | sort | uniq -c | head -12; done
```

For an answer that differs, `python3 -I indexer/scripts/live/json_paths_diff.py A B` lists the leaf paths that
differ, with values only for numbers and a few keys.

| Claim | State | Evidence |
|---|---|---|
| Available | Partially confirmed: `foto.sh` (original), `golden.py` (a sanitized rewrite, run on 2026-10-26 against a stand-in, then the live MCP), `json_paths_diff.py` (reconstructed); the comparisons exist only as the commands above | the catalog, §2 and §5 |
| Reproducible | the "after" side needs the live install and the author's authorization. For PR #27 the "before" side is local and private (§7) | — |
| Executed | historical: PR #20 and PR #25, before and after; PR #27, before. Fresh: PR #27's after side, on 2026-10-26 | the golden rounds; [the PR #27 evidence](evidence/pr27-validation-state.md), §5 |

## 5. Statistical formulas and thresholds

Each formula gives its source:

- **code:** a file on `main` at `0725d47`, or on the branch at `6ccf4a0`;
- **doc:** a versioned document;
- **output:** a historical output;
- **reconstructed:** recovered from `$T`.

### 5.1 A corpus item, and a corpus diff (code: `corpus_metrics.py`, `http_corpus.py`)

- An item's id is `(METHOD, path_key(normalize_path(path)), evidence)`, where `evidence` is `repo:file:line`
  (`run_ids`).
- For each kind (`endpoints`, `calls`), the diff of two runs has three parts:
  - `removed`: the base's ids minus the head's;
  - `added`: the head's ids minus the base's;
  - `resolution`: the shared ids whose `handler_id` (endpoints) or `caller_id` (calls) changed.
- **A repo differs** when any kind has an item in any of the three. `N repo(s) differ` counts those repos.
  - In `http_corpus.py`'s report, a repo with no file in the baseline counts as differing ("baseline: none for …").
  - `gates.py` instead fails a repo missing on the branch, under "Every repo measured".
- When a run's `sha` differs from the baseline's, the report says "ids may differ for that reason alone"; a pin moved.

### 5.2 Precision and recall against an expected list (code: `corpus_metrics.score`)

- **Pairs:** `X` is the set of distinct `(METHOD, path_key)` pairs extracted inside the list's scope, and `E` the
  set of distinct expected pairs.
  - The scope is `scope`, file prefixes, and `scope_paths`, path prefixes. `/v1` covers `/v1/x`, but not `/v10`.
  - Both may be global or per kind.
- **A match:** the same `path_key`, with compatible methods (`ANY` matches any). For the frameworks in
  `CASE_INSENSITIVE` (`aspnet`, `aspnet-minimal`, `fastendpoints`), the paths are compared without case.
- **The two sets of errors:** `FP` = the pairs of `X` that match no pair of `E`; `FN` = the pairs of `E` that no pair
  of `X` matches.
- **The formulas:** `P = (|X| − |FP|) / |X|` and `R = (|E| − |FN|) / |E|`. Each is undefined when its denominator is
  0, and printed as `—`.
- **A kind absent from the list** is not measured. A kind present and empty means nothing is expected there.

### 5.3 Precision on the checked sample (code: `corpus_metrics`; doc: the corpus report; H2-D6)

- **The sample:** `random.Random(f"{seed}:{repo}:{kind}")` draws `min(n, len)` items from the run's items, which are
  first sorted by `(evidence, METHOD, normalized path)`. It is deterministic for a given run, seed and repo. The corpus
  report fixes 20 routes and 20 calls per repo (`--sample 20 --seed <n>`).
- **The counts:**
  - `judged`: the sampled items with a verdict;
  - `pending`: those without one;
  - `stale`: judged items the run no longer has (re-sample);
  - `wrong`: judged `ok: false`.
- **The formula:** `P_checked = ok / judged`.
- **Recall** is measured only against a list: sampling what was extracted never shows a miss (H2-D6).

### 5.4 Pooled per language (code: `http_corpus.py`, `gates.py`)

- **`http_corpus.py`'s table:**
  - `P checked = Σ ok / Σ judged`, where each sampled item counts in the language of its own file, by extension;
  - `P gabarito = Σ TP_X / Σ |X|`;
  - `R gabarito = Σ TP_E / Σ |E|`.

  A list's `language` field moves a kind to another language, such as a Go server's UI calls.
- **`gates.py`'s pool,** per language and kind, is `Σ (|X| − |FP|)` and `Σ |X|` on each side. The sums are over the
  repos (micro-averaged), not an average of the repos' ratios.

### 5.5 The gates (code: `gates.py`; doc: the H7 handoff, `AGENTS.md`)

Both runs are scored against **the branch's** expected lists.

| Gate | Fails when |
|---|---|
| Precision ratchet | for a repo and kind, or a language pooled, both sides extracted something and `Fraction(TP_head, X_head) < Fraction(TP_base, X_base)`. Exact fractions, so no rounding. Recall is not ratcheted |
| No win lost | an expected pair the base found is missed on the branch (`FN_head − FN_base`), or a `checked` item judged right is stale on the branch and was not stale on the base |
| Hold-out untouched | `changed > 0` without the `holdout-measurement` label. `changed` is the number of hold-out repos missing on one side or with any diff (§5.1) |
| A refactor changes nothing | under `refactor`, any corpus repo differs or `changed > 0` |
| Every repo measured | a repo of the base's runs has no run on the branch |

**The `refactor` label** is added when the branch name matches `refact(or)?/` or a commit subject matches
`refact(or)?(\([^)]*\))?!?:`.

**The micro verdict** (`--micro-rc`):

- 0 passes;
- 1 fails under `refactor`, passes under `graph-change`, and fails otherwise;
- any other code fails.

**Not gates:** `gains` are added items whose pair the branch now finds. Every other added, removed or re-resolved item
is listed "to judge at the source", with a link to its line at the pinned sha.

### 5.6 The micro graph's comparison (code: `micro.py`; `same.py` on the branch, the same rule)

- **The lists compared:** every top-level list of a dry-run, except `repo` and `counts`, which are the run's metadata.
- **Each list is a multiset** of whole records, each serialized as `json.dumps(record, sort_keys=True, default=str)`.
  So a field that changes anywhere shows, and so does a record that appears once more.
- **A repo differs** when any list's multiset differs.
- **The `-gone +new` counts** are the sizes of the multiset differences, `base − head` and `head − base`.
- **No tolerance:** identical or not.

### 5.7 The judgment's counts and samples (code: `chain_diff.py`, `edges_lib.py`)

- **A site** is `(caller's file path, line)`. A call made from a file rather than a symbol uses the file's path.
- **A site's edges** are the set of `(callee's qualified name, strategy)`. A callee that is not a symbol keeps its id.
- **A site changed** when its edge set differs between the two runs.
- **Its kind,** from the callee sets `cw` (before) and `cn` (after), with the strategies set aside:

  | Kind | When |
  |---|---|
  | `strategy` | `cw = cn` |
  | `added` | `cw` is empty |
  | `dropped` | `cn` is empty |
  | `widened` | `cw ⊂ cn` (strict) |
  | `narrowed` | `cn ⊂ cw` |
  | `changed` | otherwise |

- **An edge's class,** from its strategy:
  - `typed`: it starts with `receiver-type`, which includes `receiver-type-impl`;
  - `inherited`: it starts with `inherited`, which includes `inherited-impl`;
  - `name`: every other strategy. That is `same-file`, `same-module`, `unique-name`, **and `dispatch`**, a
    mediator's resolution, which is not a name match ([`SCHEMA.md`](../../neo4j/SCHEMA.md));
  - `~amb` is appended when the strategy contains `ambiguous`.
- **The counts:**
  - sites per kind;
  - edges per `(added | removed, class)`, over the set differences `now − was` and `was − now`.

  A callee whose strategy changes counts once as removed, in its old class, and once as added, in its new one. So
  "added" and "removed" are not net changes of callees.
- **A derived row:** the H5 handoff's "found by name" is `name + name~amb`
  ([the PR #27 evidence](evidence/pr27-validation-state.md), §3).
- **The samples:**
  - for each kind but `strategy`, in sorted order, `min(N, count)` sites are drawn by **one**
    `random.Random(20261021)`. So the draws of a kind also depend on the sizes of the kinds before it;
  - until 2026-10-26, the sites were drawn from a list built in the iteration order of a Python `set`. **That order
    changes from one process to the next under `python3 -I`** (§8, gap 6). The seed fixed the draw over a given
    order, not the order. Since 2026-10-26 the sites are sorted first, so the same inputs give the same samples.

### 5.8 The loss analysis (code: the `judgment/` scripts)

The scripts do not share definitions, so their numbers are not interchangeable. They differ in two places.

**What an extension method is:**

| Script | Its definition |
|---|---|
| `ext_loss.py`, `ext_sites.py` | a symbol of kind `method` whose signature contains `(this `, taken from both runs' symbols |
| `ext_judge.py` | a symbol of kind `method` from the after run's symbols, whose signature matches `\(\s*(\[[^\]]*\]\s*)*this\s`, **or contains ` static `**: wider, since it also takes static methods |
| `lost_ext.py` | the callee's file contains an `extension(…)` block (`^\s*extension(<[^>]*>)?\s*\(`). A call whose caller or callee is not a symbol is skipped |
| `this_kind.py` | a `unique-name` edge gained to a symbol of the after run; its `this` is read from the source, and is `any` when it is a type parameter of the method, or `object` |

**What a site has now:**

| Script | Its rule |
|---|---|
| `ext_loss.py`, `ext_back.py` | `nothing`; else `inherited` only when **every** strategy left is exactly `inherited`; else `typed` when any starts with `receiver-type`; else `name`. So a site left with `inherited-impl` counts as `name` |
| `ext_judge.py` | the site before: `inherited` when every strategy starts with `inherited` |
| `chain_diff.py` | prefix classes (§5.7) |

**A lost edge** (`ext_loss.py`, `ext_sites.py`) is a callee that is an extension method in `was − now`, and is not
among the site's callees now, under any strategy.

### 5.9 The live comparisons (code: the `live/` scripts)

- **`graph_vs_dry.py`** keys `CALLS` by `(caller id, callee id, line)`, the writer's merge key.
  - The graph's snapshot comes from the caller id's prefix, before `/sym/` or `/file/`.
  - The dry-run's snapshot comes from its file name.
  - Per snapshot it runs five set checks: before = main; after = head; removed = main − head; added = head − main;
    the strategies after = head's, on the keys both share.
  - `mismatching snapshots` counts the snapshots that fail any check.
  - A dry-run may count more `CALLS` than the graph, which merges an edge by its key. Counted by those keys, the two
    match (the inventory, V21).
- **`dry_sections.py`** compares each snapshot's two dry-runs as multisets of key tuples, per section:

  | Section | Key |
  |---|---|
  | `files` | `path` |
  | `symbols` | `id` |
  | `calls` | `caller_id, callee_id, line, strategy` |
  | `imports` | `file_id, target_id, spec` |
  | `endpoints`, `http_calls` | `method, path, file_id, line` (until 2026-10-26: `file`) |

  It prints `-x +y` per section that differs, and the change in `CALLS` per strategy. Two limits followed from the code:
  - **The dry-run's endpoints and HTTP calls carry `file_id`, not `file`** (`core/model.py`, `asdict` in
    `cli.py`). Until 2026-10-26 the key named `file`, so that part was always empty, and a route that moved to
    another file at the same line showed as identical. A synthetic case showed it. The key now names `file_id`;
  - **It compares six sections, by those keys only.** It leaves out `modules`, `packages`, `violations`, `provides`
    and `requires`, and every field outside the key, such as a symbol's lines, a call's `resolved`, or an endpoint's
    `handler_id`.

  So "identical on all 10 snapshots" (PR #27, before the merge) meant identical by these keys, not record by record.
  On 2026-10-26 a record-by-record comparison of the preserved dry-runs, in every list, found all 10 identical
  ([the PR #27 evidence](evidence/pr27-validation-state.md), §8).
- **`dry_compare.py`** compares the non-HTTP sections as canonical JSON. The sections are `modules`, `files`,
  `symbols`, `calls`, `imports`, `packages`, `violations`, `provides` and `requires`. For endpoints and HTTP calls it
  uses key sets, and it also compares `main`'s dry-run counts with the picture's. It prints names.
- **Pictures:** each list is diffed whole (`cmp`), and the rows gone and new are counted with `comm` (§4.11).
  - **Expected** (the inventory, V23): identical, but for the build in `snapshots` and one more `IndexRun` per
    snapshot in `labels`, and except what the dry-runs said.
  - **The masks:** the build mask matches `0.2.15+<hex>` only, so a new version number would escape it. The tenant
    mask replaces the first quoted field.
- **Golden answers** (the inventory, V25):
  - **Expected:** byte for byte the same (`cmp`), or different only in time and build fields.
  - **Diffing an answer:** pretty-printed JSON, with ISO timestamps masked, then counted with `sort | uniq -c`.

### 5.10 Time (doc: the H6 and H5 handoffs, the corpus report, H7)

- **The design rule** (H6, "How it is measured"):
  - each measurement runs alone on the machine, one container per run;
  - at least 3 runs, interleaved across the repos;
  - the report gives the median and the range (min–max).

  The H5 handoff's pitfall says the same: "Measure alone, three times, and use the median".
- **The decision rule:** two options are compared only when their difference is larger than the run-to-run range
  (H6).
- **The known noise:** the corpus's summed time moved 28 % between two runs of the same code (the corpus report,
  "H5 steps"). So a small effect is measured with a microbenchmark on the same trees (H6). Configurations are
  compared interleaved within one run of the bench, never across runs (the H6 pitfalls).
- **Time never gates CI** (H7). The nightly trend, H7's slice 3, is not built.
- **Wall time** is `corpus.sh`'s `run …: <s>s wall`. **Summed time** is the sum of the per-repo seconds in
  `summary.txt`. That is **inferred**: no script or recorded command that sums them was found. The two are not
  comparable: they depend on the jobs at once (the inventory's contradiction 5).
- **As practiced in PRs #23 to #27:** one run per side, alone, on one image, read as "within the noise" or "the
  same". That is not the median of three (the inventory's contradiction 9).

### 5.11 H6's statistics (code, on the branch)

- **Medians:** `statistics.median`, which averages the two middle values when the count is even. The range is
  `min–max`. Used by `aggregate.py` (per configuration) and `store_bench.py` (per store and scenario).
- **Percentiles:**
  - `evaluate.py` computes `q(xs, f) = sorted(xs)[min(n − 1, ⌊f·n⌋)]`, a nearest-rank-style index with no
    interpolation. It reports the median, `q(·, 0.9)` and the maximum;
  - `count_reads.py` computes its p90 as `sorted(xs)[⌊0.9·n⌋]`.
- **A key that missed a change** (`evaluate.py`): a scanned file whose policy says "hit", but whose scan digest
  differs between the two commits. A policy that cannot decide counts as a re-run, and as "unknown".
- **Correctness:** `same.py` applies §5.6's rule: `same`, or `DIFFERS` with `-x+y` per list, and exit 1.

### 5.12 Thresholds and acceptance criteria

| Criterion | Threshold | Source | Status |
|---|---|---|---|
| A refactor's corpus and hold-out | `0 repo(s) differ` on both sets | `AGENTS.md`; `gates.py` | gate |
| A refactor's micro graph | identical (rc 0) | `AGENTS.md`; `gates.py` | gate |
| List precision | never lower, per repo and kind and per language pooled, as exact fractions | `gates.py`; H2-D11 | gate |
| Wins | no expected pair, and no `checked` item judged right, lost | `gates.py` | gate |
| Hold-out | no change without `holdout-measurement`. In a change of behavior, read only in aggregate, and the author decides the label | `gates.py`; H5-D13; H2-D20 | gate, then judged |
| Every repo measured | no repo of the base missing on the branch | `gates.py` | gate |
| A change of behavior's micro graph | judged by case. "One wrong item in a case blocks the PR"; `graph-change` after the judgment | H5-D14 | judged; no number |
| A change of behavior's cases | every xfail gained and no guard lost | H5-D10 | tests |
| A corpus diff | each item judged at the source; a rule that raises recall and drops precision in any repo does not go in | H2-D11; the guide §5 | judged |
| A loss | a wrong guess the receiver's type disproves, or a gap with its case named. A loss of the same kind as the PR's goes in the PR | H5-D15, D16, D17 (widened on 2026-10-23) | judged; no number |
| PR #5's A4 | per repo and kind, the list's P **and R** on the head ≥ `main`'s; no expected pair or `checked` item lost. Stricter than CI, which does not ratchet recall | the plan (reconstructed) | not in CI |
| PR #5's A5 | no expected pair any earlier baseline found is missed at the end, or each one explained | the plan (reconstructed) | not in CI |
| Live dry-runs | identical outside the change; inside it, each difference judged | PR #5's B2 (reconstructed); the inventory, V22. `AGENTS.md` and the decisions require the run, not this criterion | judged |
| Live graph | `mismatching snapshots: 0` | the inventory, V21 | historical practice |
| Picture | identical but for the build and `IndexRun`, and what the dry-runs said | the inventory, V23; PR #5's B5 | historical practice |
| Golden answers | the same, or different only in time and build fields; Q1–Q5 ✅ | the inventory, V25; the golden rounds | historical practice |
| Time | "no worse than the previous one, unless justified" | the H5 protocol, item 5 | judged; never a gate |
| H5 step 9 | the summed time ≤ 60 % of step 0's (≤ ~870 s of 1,449 s) | the corpus report, "H5 baseline" | met at 54 %; that step only |
| H5 step 3 | vikunja's profile: `walk` < 20 % | the H5 handoff, the steps' table | met at 18 %; that step only |
| H6's cache | warm equals cold; no key misses a change | the H6 handoff, "The incremental cache" | the prototype's runs; a gate after H6 (H7 slice 5) |
| Shape | no function over complexity 9, and no module over 300 lines, new or grown | `shape.py`; H5-D9 | gate (V15, out of scope here) |
| An equivalence check | equal (`cmp`) | the inventory, V19 | historical practice |

### 5.13 Criteria that are not specified

- **The sample size of the micro judgment.** No document fixes `N`. The values used are in §4.5. H5-D14 asks for "a
  seeded sample per case and repo", while `chain_diff.py` samples per kind across repos (the inventory's
  contradiction 3).
- **How a judged sample is recorded,** and what share of wrong items blocks. "One wrong item in a case blocks", but
  the verdicts have no format (H7-D2 is open).
- **A memory tolerance.** H7-D4 recommends about 10 %, from a 2–4 % spread of container peaks in H6's step 0. It is a
  decision still to make: no threshold applies today.
- **A time threshold.** No number. "Within the noise" is a judgment, and the run-to-run range of a single run per side
  is not measured.
- **The live comparisons' pass criteria** are practice from the golden rounds, not a written rule with a script that
  enforces it. `live-check.sh` (H7 slice 4) was never built.

## 6. Baselines, the hold-out and the validity of a run

### 6.1 The baselines (V03)

- **The current baselines:** `2026-10-18-v2-baseline-29` (corpus, 55 repos) and `2026-10-18-v2-holdout-26` (the
  hold-out's three repos: Kavita, go-boilerplate and sftpgo). Both are in `$C/runs` on 2026-10-26.
- **Promotion:** "a new baseline is saved only after its diff against the previous one was judged item by item" (the
  corpus report). A refactor never promotes one. A change of behavior promotes one only when the corpus changed
  (H5-D12): Go's did (`-29`), and C#'s three PRs kept `-29`.
- **Locally, a baseline is a named directory on one machine.** In CI it is derived from the base's code, keyed by its
  `indexer` tree, and recomputed on a miss (H7-D1). So a local `-29` and CI's base are not the same object, though a
  refactor must give `0 differ` against both.
- **They are not published** (H4.1-D1), so an outsider cannot reproduce the quoted numbers from the repository alone.

### 6.2 The hold-out (V04)

- **Its rules** (H2-D20):
  - its lists are written before the extractor runs on it;
  - its sample is seeded and judged at the source;
  - it is measured once, and no rule is tuned on it;
  - a hold-out repo that gets worked on becomes corpus.
- **In a change of behavior** it is read only in aggregate, as the repos that changed and P/R against its lists. Its
  items are not opened, and the author decides `holdout-measurement` (H5-D13).
- **CI moves only the count** between jobs (`gates.py --holdout-count`), so no artifact carries its items.
- **The next hold-out** is measured once, on H5's code and on the commit before H5 (H2-D21, H5-D12).

### 6.3 What makes a run invalid, or two runs incomparable

| Condition | Effect | Guard | Source |
|---|---|---|---|
| A pin changed between the two runs | ids may differ for that reason alone | the report's and `gates.py`'s note | code |
| A list read at another sha than the run | P/R not to be trusted | the report's note: "re-check it before trusting P/R" | code |
| `--reuse` used to measure a change to the extractor | nothing measured: it rescores a saved run | its help text | code |
| A micro base from another `aidd_indexer` tree or another image | not the same grammars or code | the base's directory name; after a reinstall, `micro.sh --base-only` | code; the H5 pitfalls |
| `python -m` in the image without `-w` on the mounted code | the image's code runs, not the tree's | `-w`, and the log's first line | the H5 pitfalls; `dryrun-live.sh` |
| A folder deleted and made again at one path (Docker Desktop) | the container sees no folder or an I/O error; `FileNotFoundError` on every head dry-run | a new label per run; `micro-fresh.sh`'s fresh paths | the H5 pitfalls |
| A file another container just wrote, read through another mount | read cut short | copy to a fresh path before comparing | the H5 pitfalls; `micro-fresh.sh` |
| The indexer's code edited during a run | the containers import the mounted modules | no edits during a run | `AGENTS.md`; the H5 pitfalls |
| Two protocols at once, or other load | timings invalid; memory pressure, and the OOM killer may pick a stack container | one protocol at a time; time alone | the inventory, V13, V17; `corpus.sh`'s comment |
| A refactor and a rule in one commit, or the extractor and the lists in one commit | "0 repos differ" stops proving anything; a gate passes anything | separate commits (not checked: H7 slice 2) | the H5 pitfalls; H7 |
| Timings from different runs, or a wall time against a summed time | not comparable | interleave within one run; one kind of time | H6; the inventory's contradiction 5 |
| A dry-run that failed | the repo is "not compared"; rc 3 | the summary and the logs | code |
| The "before" picture taken after the reinstall | it no longer holds `main`'s graph, and cannot be retaken | take it before; for PR #27 it is kept in `.local` | the inventory, V23 |
| Code copies for the live dry-runs served stale | the wrong code dry-runs | check each copy against `git ls-files` with `shasum` | the catalog (`pre-merge.sh`) |
| A different golden calls file before and after | answers not comparable | the same file. PR #27's is frozen in `.local`; one argument was edited in place on 2026-10-22 | the inventory, V25 |
| A hold-out item opened | it becomes corpus | read only in aggregate | H2-D20, H5-D13 |
| A sample drawn again with `chain_diff.py` or `ext_judge.py` | other items than the recorded ones | none (§8, gap 6) | code; the check of 2026-10-26 |

## 7. PR #27: the context and what is still open

PR #27 (`fix(csharp)`, H5-D17) merged into `main` as `0725d47` on 2026-10-24, with the `graph-change` label and CI
green. **Its validation is not complete.** This document does not close it, and nothing of it was run here. The full
state is in [the PR #27 evidence](evidence/pr27-validation-state.md).

### What is available

| What | Where | Kind |
|---|---|---|
| The protocol on each of the 17 fix commits, with corpus, hold-out and micro set | the evidence, §2 | a summary of historical outputs (`$S` was emptied on 2026-10-26) |
| The judgment from `main` to the tip, by kind and class (N 40, seed `20261021`) | the evidence, §3 | historical; the counts were re-derived on 2026-10-24 |
| The micro dry-runs behind it | `$C/micro-fresh/csn-n*` (85 entries) | durable artifacts |
| The time, alone | the evidence, §4 | historical, one run per side |
| The live check before the merge: dry-runs, sections, graph against dry-runs, picture, golden calls | the evidence, §5 | historical; two outputs re-derived on 2026-10-24 |
| The "before" picture's manifest (15 lists' rows and digests, one digest of the 27 answers) | the evidence, §5 | versioned |
| The private live data | `.local/indexer/pr27/` | local copies, checked on 2026-10-26 |

**The local layout**, by file count only, since the contents and most of the names are private:

| Path | Files |
|---|---|
| `before/` | the 15 lists of `foto.sh` |
| `before/golden/` | 27 answers, one per call |
| `dry/` | 40: a JSON and a log for each of the 10 snapshots × `main` and the branch, named `<tenant>__<repo>__<ref>__{main,head}.json` |
| `pre-merge/` | 5 logs of the pre-merge check |
| `original/` | 1: the golden script as it ran |
| `golden-calls.json` | the 27 calls, for `live/golden.py` |
| `SHA256SUMS` | 89 entries |
| `README.md` | how to check and use the folder |

**There is no backup.** Being ignored by git is not one, and no other copy was checked. The folder must never be
copied into `docs/`, a PR or an issue. Use it from the repository's root:

1. **Check it first:** `cd .local/indexer/pr27 && shasum -a 256 -c SHA256SUMS`, then the versioned manifest.
2. **Write every new output into a new folder there,** never into `before/`.

### What is still open (checked again on 2026-10-26)

| # | Item | State on 2026-10-26 | How (§4) |
|---|---|---|---|
| 1 | The "after" picture | absent: no `.local/indexer/pr27/after/`. **Taken later that day** | `foto.sh` (§4.11), with the author's authorization |
| 2 | The pictures compared | not done; no script for the 14 lists other than `CALLS`. **Done later that day,** with the commands: identical but for the build and `IndexRun` | the commands of §4.11, then `graph_vs_dry.py` with `before/`, `after/` and `dry/` (§4.10) |
| 3 | The golden answers after, compared | not taken. **Done later that day:** 22 of 27 identical, 5 only in time and build fields | `golden.py` with `golden-calls.json`; `cmp`; `json_paths_diff.py` (§4.11) |
| 4 | The eleventh golden round | absent: `docs/golden-questions.md` ends at the tenth | a docs PR |
| 5 | PR #27's line in `docs/history.md` | absent | the same docs PR |
| 6 | The ROADMAP's and the H5 handoff's state | both still say H5-D17 "goes to review" at `0725d47`. Corrected in the working tree, uncommitted | the same docs PR |
| 7 | The micro base for `main`'s tree and the current image | **made on 2026-10-26**: 12 of 12 base runs, `$C/micro/base-ed46a54b…-f07550cbe2e2`. The tag has since moved to `9e6dd3753826`, the same layers, so the next run makes a new base | `micro.sh --base-only` (§4.3) |
| 8 | `install-check.sh`'s output for the reinstall | the output of 2026-10-24 is still unknown. **A run on 2026-10-26 failed:** the install's Neo4j is in a restart loop, which also blocks items 1 to 3. After the author recreated the container, a run passes | [the PR #27 evidence](evidence/pr27-validation-state.md), §8 |

The expected results of items 1 to 3 are the inventory's criteria, as this document's §5.12 collects them:

- the lists identical but for the build and `IndexRun`, since the 10 dry-runs were identical by `dry_sections.py`'s
  keys (§5.9);
- `mismatching snapshots: 0`, with the graph after holding the branch's dry-run;
- the answers equal, or different only in time and build fields.

These are expectations, not results. Later on 2026-10-26 they were met: see
[the PR #27 evidence](evidence/pr27-validation-state.md), §9.

## 8. Known gaps and reproducibility limitations

Each was checked against the repository and the evidence on 2026-10-26.

1. **The before/after comparator is only partly recovered.** Still true.
   - `graph_vs_dry.py` covers `CALLS`, and `dry_compare.py` covers `main`'s dry-run against one picture's counts.
   - The other 14 lists and the golden answers were compared with typed commands, recovered from `$T` for PRs #20 and
     #25 (§4.11). No script holds them.
   - The recovered `comm` does not set a locale, while `foto.sh` sorts with `LC_ALL=C`. Whether that ever changed a
     count is not established.
2. **The item-by-item judgments were not recorded.** Still true: H7-D2 is open.
   - The judged samples (`$S/h5/why/out/*.view.txt`, `$S/h5/n*/`) were lost with `$S` on 2026-10-26.
   - Gap 6 means they cannot be drawn again as they were.
   - What survives is prose and totals in the handoffs, the PR bodies and the evidence documents.
3. **H6's procedures and measurements depend on `h6/step1-proto`.** Still true (§4.8).
   - Running them needs a worktree of the branch.
   - The image they used is not identified.
   - The README's `--typed-only` does not match `evaluate.py`.
4. **The live checks and PR #27's validation after the merge are pending.** Still true (§7). `install-check.sh`'s
   output is unknown. Later that day the live checks ran and passed. The eleventh round, the history line and the
   2026-10-24 output are left.
5. **A recovered output is not a fresh reproduction.** Still true. Since the recovery, only re-derivations ran, on
   saved inputs:
   - `chain_diff.py`'s counts;
   - `dry_sections.py` and `graph_vs_dry.py` on PR #27's data.

   No benchmark, protocol, micro run or timing was made again. Later on 2026-10-26 the protocol ran on `main`, with
   a new micro base, and PR #27's live after side was taken (§7).
6. **Seeded samples over a `set` do not reproduce.** *New finding.*
   - `chain_diff.py` iterates `set(b) | set(h)`, and `ext_judge.py` `ea.keys() | eb.keys()`. Both then draw with
     `random.Random(seed).sample` from a list in that order.
   - The sites are tuples of strings, whose hashes Python randomizes per process. `python3 -I` ignores
     `PYTHONHASHSEED` (`sys.flags.ignore_environment` is 1).
   - Checked on 2026-10-26 on synthetic tuples, not on the project's runs:
     - six runs under `python3 -I` drew six different samples with seed `20261021`;
     - three runs with `PYTHONHASHSEED=0` and without `-I` drew the same one.
   - The counts on stdout are sorted, and so do reproduce.
   - `edges_join.py`, `kinds.py` and `corpus_metrics.sample` sort before drawing, so they are not affected.
   - **Checked on real data on 2026-10-26:** two runs of `chain_diff.py` from `main` to n17 (N 40) gave the same
     counts, equal to the evidence's §3, and samples that shared 8 of 200 items.
   - **Fixed on 2026-10-26:** `chain_diff.py` and `ext_judge.py` sort the sites before drawing. After the fix, two
     runs of each gave byte-identical output, and `chain_diff.py`'s counts did not change. The past samples stay
     unrecoverable: they were drawn in an order no one can replay.
7. **The live dry-runs' "identical" was by `dry_sections.py`'s keys.** Six sections, by their keys, with an
   endpoint's `file` always empty (§5.9). The key was fixed on 2026-10-26. For PR #27, a record-by-record comparison
   of every list found the 10 snapshots identical on that day.
8. **The loss scripts' definitions differ** (§5.8). *New finding.* Their numbers are not interchangeable.
   - `chain_diff.py`'s class `name` holds `dispatch` edges. Whether PR #27's counts held any is not established.
9. **The base of a micro comparison has three conventions** (§4.3). `micro-fresh.sh` also ignores `AIDD_CORPUS_HOME`
   and the image and jobs settings.
10. **The per-case attribution is missing.** `why_a.py` is not persisted, so `edges_join.py`, `kinds.py`, `cases.py`
    and `view.py` cannot run (the catalog, §4).
11. **`a5_chain.py` orders runs by their directory's mtime.** It also selects them by name (`v2-baseline|holdout`, no
    `validate`). Copying `$C/runs` elsewhere could change the order it reports. *Inferred from the code.*
12. **The summed corpus time** has no recovered script (§5.10).
13. **V19's other checks were not found:** Go's facts, `tools/list` and the ASTs.

## 9. Reproduction checklist

Each step says what to check before it, not what it gives.

**Before any run:**

- [ ] `docker image inspect aidd-indexer:local` works. Note its id's first 12 hex digits.
- [ ] `$C/runs/2026-10-18-v2-baseline-29` and `$C/runs/2026-10-18-v2-holdout-26` exist.
- [ ] A micro base exists for the base's `aidd_indexer` tree and this image (`$C/micro/base-<tree>-<image>/`), for
  every repo to compare. Otherwise run `micro.sh --base-only [--base REF] [repo ...]`.
- [ ] Nothing else runs on the machine, and no code under `indexer/` is being edited.
- [ ] Every label is new.

**A code commit of a PR (§4.4):**

- [ ] A worktree of the commit.
- [ ] `AIDD_REPO=<worktree> indexer/scripts/protocol/protocol.sh <label> [extended set]`, one commit at a time.
- [ ] Read `corpus rc`, `holdout rc` and `micro rc`, and each `N repo(s) differ`.

**A change of behavior (§4.5, §4.6):**

- [ ] `chain_diff.py` on each commit against the one before, and on `main` (micro-fresh's `-base`) against the tip
  (`-copy`), over the repos that differ.
- [ ] Keep `OUT.txt` and `SAMPLES.jsonl` outside `$S`, which a reboot empties. The samples cannot be drawn again
  (§8, gap 6).
- [ ] The loss scripts on the same folders. Read each script's own definitions (§5.8).
- [ ] Record the judgment's totals with their `N` and seed.

**The PR (§4.7, §4.2):**

- [ ] `time-alone.sh` on `main`'s worktree and the tip's, alone. Say how many runs per side.
- [ ] The gates locally, as CI runs them, with `--micro-rc`.

**Before the merge, with the author's authorization (§4.10, §4.11):**

- [ ] Copies of the two codes, checked against `git ls-files` with `shasum`.
- [ ] `pre-merge.sh LIVE_DIR <calls file>`, with `LIVE_DIR` outside the repository.
- [ ] Keep `LIVE_DIR/before` somewhere durable and private before any reinstall.

**After the merge and the author's reinstall (§4.10, §4.11, §7):**

- [ ] Check the "before" copy (`SHA256SUMS`, the manifest).
- [ ] `foto.sh` into a new `after/`.
- [ ] The lists compared, with the masks.
- [ ] `graph_vs_dry.py before after dry`.
- [ ] `golden.py` with the same calls file into a new folder, then `cmp` and `json_paths_diff.py`.
- [ ] Only counts, snapshot numbers and public repos go into a docs PR.

**H6 (§4.8):**

- [ ] A worktree of `origin/h6/step1-proto`.
- [ ] At least 3 rounds, interleaved, alone.
- [ ] Note the image's id.
- [ ] Never compare with the recorded numbers across images or runs.

## 10. References

- **The series:**
  - [The validation inventory](validation-inventory.md): V03, V04, V07, V08, V10–V13, V17–V19, V21–V25; §9's gaps and
    contradictions.
  - [The resource catalog](resource-catalog.md): each script's origin, nature, state, edits and safety.
  - [PR #27's validation state](evidence/pr27-validation-state.md).
  - [PR #5's validation plan](evidence/pr5-validation-plan.md).
- **The scripts:**
  - CI's: [`corpus.sh`](../../indexer/scripts/corpus.sh), [`http_corpus.py`](../../indexer/scripts/http_corpus.py),
    [`corpus_metrics.py`](../../indexer/scripts/corpus_metrics.py), [`micro.sh`](../../indexer/scripts/micro.sh),
    [`micro.py`](../../indexer/scripts/micro.py), [`gates.sh`](../../indexer/scripts/gates.sh),
    [`gates.py`](../../indexer/scripts/gates.py);
  - the local ones: [`protocol/`](../../indexer/scripts/protocol/), [`judgment/`](../../indexer/scripts/judgment/),
    [`live/`](../../indexer/scripts/live/), [`checks/`](../../indexer/scripts/checks/);
  - [the scripts' README](../../indexer/scripts/README.md);
  - [the CI workflow](../../.github/workflows/indexer.yml).
- **The method's documents:**
  - [`AGENTS.md`](../../AGENTS.md);
  - [the H5 handoff](../handoffs/H5-indexer-refactor.md): the regression protocol, H5-D10…D17, the pitfalls;
  - [the H6 handoff](../handoffs/H6-extraction-pipeline.md): "How it is measured", the cache's guarantees;
  - [the H7 handoff](../handoffs/H7-regression-gates.md): the gates, H7-D2, H7-D4;
  - [the corpus report](../corpus-report.md): the method, the baselines, "H5 baseline", "H5 steps", "H6 baseline",
    "H6 step 1";
  - [the decisions](../decisions.md): H2-D4…D21, H5-D12, H5-D13, H7-D1;
  - [the golden questions](../golden-questions.md);
  - [the graph's schema](../../neo4j/SCHEMA.md): the `CALLS` strategies.
- **Outside the repository:**
  - the reference branch `h6/step1-proto` (`indexer/scripts/h6-step1/`) and the draft release `h6-step1-results`;
  - `$C` (`~/.cache/aidd-corpus`);
  - `$T`, the previous session's transcript;
  - `.local/indexer/pr27/`, private and local.
