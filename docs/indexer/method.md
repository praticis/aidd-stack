# Method: validating a change to the indexer

How a change is proven, step by step. Nothing here changes per PR. Where H5 stands and what comes next is in
[the H5 handoff](../handoffs/H5-indexer-refactor.md); how to judge a difference is in [judgment.md](judgment.md).

Paths starting with `scripts/` are under `indexer/`. `$C` is `~/.cache/aidd-corpus` (clones, runs, baselines, micro bases). `.local/` is git-ignored and holds private
outputs. The tools are listed with their arguments in [`indexer/scripts/README.md`](../../indexer/scripts/README.md).

## 1. The cycle of a change

| # | Step | How | Passes when |
|---|---|---|---|
| 0 | Design | the plan's section "Contracts, boundaries and proof" ([`docs/design.md`](../design.md) §4) | it names the contract it reads, the module that holds each piece of knowledge, the reference that proves it and what stays `Unknown`; the author approved it |
| 1 | Context | `git status`, `git worktree list`, `docker image inspect aidd-indexer:local` | branch, commit and image are the ones the run is meant to measure |
| 2 | Case first | a fixture case or test that fails without the rule (`indexer/tests`) | fails on `main`, passes on the tree |
| 3 | Tests, writer, shape | `scripts/test.sh`; `scripts/mcp-it.sh`; `scripts/protocol/shape.sh` | all pass; `0 new or worse over a target` |
| 4 | Corpus and hold-out | `scripts/protocol/protocol.sh LABEL` | a refactor: `0 repo(s) differ` on both. A change: every diff judged at the source |
| 5 | Micro graph | the same `protocol.sh`, through `micro-fresh.sh` | a refactor: identical. A change: judged by case |
| 6 | Judgment (changes only) | `scripts/judgment/` and [judgment.md](judgment.md) | no wrong item in any case |
| 7 | Time | `scripts/protocol/time-alone.sh MAIN_WORKTREE BRANCH_WORKTREE` | no worse than `main` unless justified. Judged, never a gate |
| 8 | PR and CI | the `gates` job | green; the labels `graph-change` and `holdout-measurement` only after judgment |
| 9 | Live, before the merge | `scripts/live/validate.sh before` (§4.7) | dry-runs identical outside the change; picture and golden answers the same |
| 10 | Merge, reinstall | the author only. `install.sh` copies the working tree, so `main` is checked out first | `install-check.sh` ends in "All checks passed" |
| 11 | Live, after | `scripts/live/validate.sh after` (§4.8) | as step 9, plus the graph holds the branch's dry-run |
| 12 | Record | the PR body (§4.17); a golden round; one line in `docs/history.md`; a row in `docs/decisions.md` if the change decides something; the H5 State and the ROADMAP's "Where we are" only when the state moved | each change supported by the evidence, each fact written once |

A change to the extractor adds, before step 4: corpus `--baseline`, judgment at the source, the expected lists
(`lists/expected_lists.py` edits them, `checks/expected_lists_diff.py` shows what changed; §4.10), and a new
baseline only after its diff was judged item by item.

What judgment finds that the change opens is fixed in the change when that is viable; what it finds, does not block and
the change cannot fix is registered as a debt (`docs/tech-debt.md`) with a strict xfail test, never as a note.

A refactor and a change of behavior never share a commit: one `refactor:` commit makes the whole PR strict.

## 2. Who authorizes what

Permission to read or document a procedure is not permission to run it. Each class needs its own authorization, per
task; approval in one task does not carry over.

The classes bind an agent; the author runs any of these tools without asking.

| Class | Examples | Authorization |
|---|---|---|
| 1. Read-only | `git status/log/show`, reading files, `docker image inspect`, `gh pr view`, `debts.py` | the task |
| 2. Offline analysis of saved artifacts | `judgment/` tools but `attribution.sh`, `gates.sh`, `checks/expected_lists_*.py`, `judgment/ts_vs_checker.py`, `live/dry_sections.py`, `live/graph_vs_dry.py`, `live/json_paths_diff.py`, `live/round.py` | the task says to run it |
| 3. Local files | editing docs or scripts; `lists/expected_lists.py` (edits the repository's expected lists); writes to `.local/` or `$C` | the task asks; `before/` pictures are never rewritten |
| 4. Corpus or indexer execution | `corpus.sh`, `micro.sh`, `protocol.sh`, `time-alone.sh`, `test.sh`, `mcp-it.sh`, `protocol/shape.sh`, `shape.py` on the host, `checks/mutate.sh`, `checks/mutants.sh`, `protocol/cost-pairs.sh`, `protocol/micro-fresh.sh`, `checks/dump.py`, `checks/python_scopes.py`, `checks/ts_scopes.py`, `checks/ts_heritage.py`, `checks/ts_modules.py`, `checks/ts_checker.js`, `checks/reference.sh`, `lib/test-image.sh`, `probes/`, `judgment/attribution.sh`; `protocol/resume-test.sh` (a headless `claude` session on the author's account) | explicit. One protocol at a time, in the background; never edit the mounted code during a run |
| 5. Live install | `live/validate.sh`, `graph-picture.sh`, `golden.py`, `dryrun-live.sh`, `pre-merge.sh`, `install-check.sh`, a refresh | explicit, per run. Install and reinstall are the author's alone |
| 6. Remote or git metadata | commits, pushes, PRs, labels, merges, branches, worktrees | the author's approval each time. Commits are one conventional line, signed |

Whatever the class: never run the code of a corpus repo (they belong to third parties; read and measure through the
indexer's container only), and never reinstall (the author's alone).

## 3. Where things live

| What | Where | In git |
|---|---|---|
| Procedures, tools, these docs | the repository | yes |
| Clones, runs, baselines, micro bases | `$C`, CI's cache | no (regenerable) |
| Live validation data: golden calls, pictures, dry-runs of live snapshots, answers | `.local/indexer/live/`: `golden-calls.json`, `inflight/` (the PR being validated), `merged/` (the last PR merged); layout in its README | never |
| What cannot be regenerated: the "before" picture of the PR in flight | `.local/indexer/live/inflight/before/` | no. Keep a second copy until the PR is validated: no backup policy exists |

Only two live pairs ever exist: the PR in flight and the last one merged. Extraction is deterministic, so an older
pair is not kept: a snapshot's sha and the indexer's commit (the build id) give the same dry-run again. The rest of
`.local/` is recycled the same way: nothing enters it without an end, and each PR's closing step (§4.9, step 6) clears
what its merge made obsolete, so the folder holds the PR in flight, the last one merged and the plans of the last three. Private data
reaches the repository only as counts, snapshot numbers and public repos. No tenant, client or private
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
- `http_corpus.py --reuse` (not a `corpus.sh` flag) rescores a saved run: it measures nothing about a change to the extractor.
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
python3 -I indexer/scripts/judgment/ts_vs_checker.py REPO BEFORE AFTER CHECKER.jsonl [--sample N [--seed S]]
python3 -I indexer/scripts/judgment/scorecard.py RUN_DIR [--base DIR] [--rows DIR] [--floors FILE] [--min-keyed PCT] [--write-floors]
python3 -I indexer/scripts/judgment/csharp_extensions.py sites|back|classes|this-kind|blocks ...
python3 -I indexer/scripts/judgment/attribution.py BEFORE AFTER OLD.jsonl NEW.jsonl N REPO... [--cases FILE] [--repos DIR] [--language LANG]
indexer/scripts/judgment/attribution.sh LANG OLD_TREE NEW_TREE BEFORE AFTER N REPO... [--cases FILE]
```

`BEFORE` and `AFTER` hold `<repo>.json.gz` dry-runs. `chain_diff` samples with a fixed seed over sorted sites, so the
same inputs give the same sample. Sizes used: `N` 6 to 12 per kind for each commit against the one before, 40 for
`main` against the tip. `attribution.py` is §4.12. `ts_vs_checker.py` is for a change to TS's resolution: it counts, for the typed edges the change adds and
the by-name edges it drops, what TypeScript's checker says about the callee at that site (`CHECKER.jsonl` is
`node checks/ts_checker.js --link /corpus/REPO` in the test image), with a `.d.ts` standing for the JS beside it as one
declaration, an edge to the type that owns a member with no symbol agreeing with the checker's declaration of that member,
an edge to what runs where the checker names the member of a declaration file neither agreeing nor contradicting, and
whether a dropped edge is replaced at its site or lost.
Each percentage it prints is over the sites the checker has a row for, and its line says how many edges that is. One
more line says how many of the TS calls of the two runs are in a file the checker has rows for (97.9 % in `ghost`);
below `--min-keyed` (a percent, 50 by default) it prints a WARNING, and with `--strict` it ends in 1. The comparator #84
first used compared a path with its extension to one without it and hid 11,145 of `ghost`'s 15,092 edges as "no site",
and the shares it printed looked fine. The rule is the general one: run an oracle on a case whose answer is known, and
count what it could not judge, before reading what it judged.

`scorecard.py` measures a whole tree, not one change. For a TS repo with the checker's rows it classes the edge of every call by
the checker's verdict: `confirmed` (it agrees, by the declaration, its `.d.ts` pair or the type that owns a member with no
symbol), `contradicted` (another declaration of the repo), `indirect` (the member of a declaration file, where the edge goes to
what runs: TD-061) and `undecided` (the checker has no opinion), and counts them by strategy. Two counts are gated, each with
a bound in `indexer/scripts/checks/reference_floors.txt` (`repo.strategy.confirmed :: >= N :: note`, `repo.strategy.contradicted
:: <= N :: note`): the confirmed typed edges may not fall and the contradicted ones may not rise. A count has no denominator,
so a call form the graph learns to read, which adds by-name edges, moves none of them, and the graph is deterministic, so
there is no tolerance (H5-D53). With `--base` it also lists the sites where the base has a confirmed typed edge and the tree has
none, a win lost, which a count cannot see when a change swaps one edge for another, and prints, with no bound, what reads the
graph without judging it: the typed share of every repo (a count of claims, not of correctness), recall, the by-name edges the
checker contradicts (the number SCIP must move) and the typed edges it does not decide or reads indirectly, each as the base,
the tree and the change. A count past its bound, one with no bound, a bound with no count and a repo whose calls are under
`--min-keyed` in files with rows all end in 1; wins lost alone end in 3. A bound is changed by editing its line in the diff of
the change, under the `graph-change` label (the label alone would free every change of the graph, and the line makes the
change a number the author reads). `--write-floors` prints the lines for a tree, and `--lowered BASE_FLOORS FLOORS` the bounds a change lowers: a floor that
falls, a ceiling that rises, a line that goes.

In CI the `micro` job runs it after the micro graph (`checks/reference.sh --base`, over the dry-runs of the branch and of its
base). The TS repos it makes the checker's rows for are the ones the micro set names (`micro.py --references`), not the ones
that have a bound, so a repo is not left out by deleting its lines. The rows depend on the clones, the checker and the test
image, not on the tree, so they are kept by content, and a push to main makes them (the `rows` job) for every pull request to
read from the cache; one that finds them missing makes them once. A run that did not finish (the image, the network, the
checker) fails the `micro` job, and never reaches the gates as a result. `gates.py` (`reference_gate.py`) fails the PR when a
count is past its bound, whatever the labels, and when it lowers a bound or loses a win without the `graph-change` label; a
refactor does neither. Locally: `micro.sh`, then `checks/reference.sh`.

### 4.5 Timing alone

`time-alone.sh` times the corpus on each side's worktree and then, for each of four repos (`AIDD_TIME_REPOS`), one dry-run per
side, alternating, with no other load. The rule is the median of three runs alone (H4.1); PRs #20 to #27 ran one per side. Run three when time matters.

A change to a pass over the TS files (the resolver's or the scanner's) is timed on ghost and mattermost, the two largest
TS repos of the corpus, with `protocol/cost-pairs.sh MAIN_TREE BRANCH_TREE [--pairs N] [--prefix NAME] REPO...`: pairs of
`corpus.sh --jobs 1 --no-expected` on `main`'s tree and on the branch's, one job at a time. The side that goes first flips
from one pair to the next, so a drift of the machine does not fall on one side. It prints, per repo, the change in time of
each pair, the median of the first three and of all of them, and the change in the median peak memory (`cost_pairs.py HOME
--main LABEL... --branch LABEL...` reads the same numbers from runs already made). The limit and the reading (the median of the
first three pairs, say) are written in the plan before the first run, and a fourth pair, if taken, is reported beside it. A repo that runs 12 to 24 s moves
by a second between runs: the small repos are reported and do not decide. To see where the time goes, profile a dry-run
in the image with `python -m cProfile -o` and `-w` on the mounted code (§6).

### 4.6 Equivalence of a representation

`checks/dump.py LANGUAGE OUT` (`csharp`, `go`, `python`, `typescript`, `tsx` or `javascript`) dumps every file's type
facts under `/corpus`, read as the extractor reads them, through the language's per-file index. The same dump from two
codes, compared with `cmp`, shows whether a refactor changed a fact; from one code twice, that the facts are values.

`checks/python_scopes.py [N]` compares Python's scope index with CPython's `symtable` over every Python file under
`/corpus`: each scope paired with symtable's, each name classified the same (local, global or free). It prints the
counts, the files it compared and those CPython 3.12 does not compile, and N samples of each difference. symtable only
compiles a file's symbols; no repository's code runs.

`checks/ts_scopes.py [N]` compares TS's scope index with TypeScript's own binder over every TS and JS file the indexer
extracts from `/corpus`: each name a file reads binds to the declarations of the file the checker's lookup through the
scopes finds, for what its place means (a value, a type or a namespace), and each `this` to the node that binds it.
`checks/ts_scopes.js` gives the binder's answers, a script bound alone. It prints the counts, the files tree-sitter
finds an error in and those the compiler does not parse, and N samples of each difference; code tree-sitter reads as
other code (`misread`) and a JS `require` the binder binds as an import in the function around it (`require`) are
counted apart. The compiler reads and binds the files; no repository's code runs.

`checks/ts_heritage.py [N]` compares TS's bases with TypeScript's own checker over every TS and JS file the indexer
extracts from `/corpus`: each type a heritage clause of a module's class or interface names is, in the type index, the
declaration the checker resolves it to, each file read with its config's `baseUrl` and `paths`, and where a class's
`extends` names a value, as a class a CommonJS module exports in an object literal, the checker's base type's
(`checks/ts_heritage.js`; `checks/ts_configs.js` chooses a file's `tsconfig.json` or `jsconfig.json` for every TS
oracle). It prints the count of each kind and N samples of each: the same declaration, none of the repo's on either
side, the index's `Unknown` by its reason, with a package's name the repo's `tsconfig.json` maps to its own file apart,
a declaration the index alone gives, and another one; a declaration in a function or a namespace, a name a module
declares twice, and a base a class expression declares, are counted apart. The compiler reads and types the files; no
repository's code runs. `checks/ts_runs.js` tells what JS runs on an instance of each class of a test's own case, which
it compiles and runs: it is for the tests only.

`checks/ts_modules.py [N]` compares TS's module resolution with TypeScript's own over every TS and JS file the indexer
extracts from `/corpus`: each import names, in the index, the file TypeScript resolves it to with the file's config
(`checks/ts_modules.js`). It prints the count of each kind and N samples of each: the same file, or a package the index
names where TypeScript resolves none; the checker's file where the index names a package, none or another file; a file
the index does not extract; the index's file where TypeScript resolves none, as a bundler's alias gives; and a package
of the repo's own workspace, which neither resolves without `node_modules`. The compiler reads the files; no
repository's code runs. `checks/ts_checker.js`, the declarations the checker resolves each method call to, reads each
file with its config too.

### 4.7 Live, before the merge (class 5)

```sh
indexer/scripts/live/validate.sh before BEFORE_COMMIT AFTER_COMMIT   # main before the merge, and the merge
```

It works in `.local/indexer/live/inflight`. It extracts both codes from git and checks every file against it, and
refuses unless the installed code is BEFORE_COMMIT's: the "before" is taken once, before the reinstall, never rewritten,
and afresh for each PR, not copied from `merged/after`, because the snapshots move as the workspace repos change. Then it
runs `pre-merge.sh`: the graph's picture (`graph-picture.sh`), the golden calls (`golden.py`, from
`.local/indexer/live/golden-calls.json`, the same file before and after and across PRs; `golden-calls.example.json`
shows its shape), the dry-runs of every live snapshot with both codes (`dryrun-live.sh`, with `-w` on the mounted code,
each snapshot copied at its sha to a folder no earlier run used and checked against it) and their comparison by section
(`dry_sections.py`, a record by its key and then the fields of a key both keep) and against the graph, which must
hold `main`'s dry-run: each symbol with every property the writer gives it, the calls' strategies, `virtual` and
`receivers`, and the hierarchy's edges (`graph_vs_dry.py` with the before only). It seals the folder in `SHA256SUMS` and prints counts.

### 4.8 Live, after the merge (class 5)

After the author's reinstall: `indexer/scripts/live/validate.sh after`. It refuses until the installed code is
AFTER_COMMIT's and, when the code that shapes the graph changed (the parts the build fingerprints), every snapshot's last
run since the before is ok and every snapshot holds a build other than the before's: an ok run of a refresh before the
reinstall is the old code's (the refresh runs every 15 min). When that code did not change, as in a PR of the MCP alone,
the build cannot tell the codes apart and the refresh re-indexes nothing: it refuses only a last run since the before
that is not ok, or a build that moved. A refusal writes no picture, so it runs again. It takes
the picture and the golden answers again, compares the graph with the dry-runs (`graph_vs_dry.py`) and each pair of
answers (`json_paths_diff.py`), seals `SHA256SUMS.after` and prints counts. Pass criteria: the picture is identical but
for the build and `IndexRun`; the graph holds the branch's dry-run on every snapshot; the answers are the same or differ
only in time and build fields. When the PR is validated, `validate.sh rotate --yes` makes `inflight/` the new `merged/` and
deletes the old one.

### 4.9 Running the live validation

A PR's pair lives in `.local/indexer/live/inflight`; `merged/` holds the last one. Each run of the agent's steps is
class 5: ask for it. The reinstall is the author's.

| # | Who | Command | Needs |
|---|---|---|---|
| 1 | agent | `indexer/scripts/live/validate.sh before BEFORE AFTER` | the install still on BEFORE's code; Docker and the stack up; `golden-calls.json` with its `SHA256SUMS` in `.local/indexer/live/`. About 2 min |
| 2 | author | `install.sh` from `main`, then `install-check.sh` | the PR merged, `main` checked out and up to date |
| 3 | agent | `indexer/scripts/live/validate.sh after` | the install on AFTER's code, and, when the build changed, every snapshot re-indexed (the refresh runs every 15 min) |
| 4 | agent | read the counts against §4.8; report numbers only | |
| 4b | agent | `indexer/scripts/live/round.py INFLIGHT --pr N --number K --date D --what "..." --merge SHA`: the draft of the golden round and of its history line, from the same folder | `after` done; the output is counts, snapshot numbers, list and tool names, never a label or a name; the sentence of what changed and the judgment ("what the round shows") are written by hand. The round is the block "the last round" of `docs/golden-questions.md` and replaces the previous one: its numbers stay in its history line and its text in git; only a round that found something adds an entry to the list of findings. |
| 5 | agent | `indexer/scripts/live/validate.sh rotate --yes` | `after/` taken, the PR's records done |
| 6 | agent | recycle `.local/` by the closing step of its README: the PR's body, the pending docs that merged, the oldest plans, the tools whose consumer merged | `rotate` done |

AFTER is the commit that merged the PR on `main` (`git log --oneline -1 main` once it is merged) and BEFORE its first
parent, `git rev-parse AFTER^1`, which is `main` before the merge, for a merge commit and for a squash alike.
`AIDD_LIVE` (default `.local/indexer/live`) and `AIDD_HOME` (default `~/.aidd`) move the two folders it uses; a trial in
a scratch folder sets both. The scripts print counts, never names: the live install's tenants, repositories and answers
stay out of chats, PRs and docs.

It refuses with exit code 2 and says why:

| It says | What to do |
|---|---|
| `inflight exists: the before is taken once` | the PR there is validated: `rotate --yes`; if not, ask the author |
| `the installed code is not X's: the before can only be taken before the reinstall` | the install already moved, so this PR has no "before": say so in the record and ask the author |
| `the golden calls file does not match SHA256SUMS` | ask the author; the file is private and never regenerated |
| `a container sees other files than the host's` | a folder recreated at one path is served stale: use another `AIDD_LIVE` |
| `the installed code is not X's: the author reinstalls from main first` | step 2 is not done: ask the author |
| `N snapshot(s) have no ok last run since the before` | wait for the refresh (up to 15 min) and run it again |
| `N snapshot(s) still hold the before's build` | wait for the refresh and run it again |
| `no before in <inflight>` | the before is taken first, with `validate.sh before`, before the reinstall |
| `after exists: the after is taken once` | it is taken: go to step 4 |

What the counts say. After `before`: the dry-runs of `main` and of the branch are identical in every snapshot except
where the change reaches, the graph has 0 mismatching snapshots against `main`'s dry-run, and one golden call is refused
(the Cypher write that must be refused). After `after`: the picture differs only in the build and the `IndexRun`
counts, 0 snapshots mismatch against the branch's dry-run, the answers differ only in time and build fields, and every
snapshot has an ok run. Anything else is a difference to judge as `judgment.md` says, never a pass.

### 4.10 Expected lists

`indexer/scripts/lists/expected_lists.py` edits `indexer/tests/corpus_expected/` (plain Python, no Docker; the
hold-out's lists only with `--holdout`, §4.11). A list is written back in the order it was read, so an edit is a small
diff, and a test keeps every real list identical through a read and a write. RUN is a label under `$C/runs`. After a
change to the extractor, with the branch's run:

1. `sync RUN` prints the `checked` items the run moved (`changed`), lost (`gone`) or gives more than one route for
   (`ambiguous`); `--apply` writes it. A moved item is right when the list has its route, and pending otherwise.
2. `pending` lists the items with no verdict. Read each at its evidence, as `judgment.md` says, then
   `judge NAME KIND DEFAULT [N=VERDICT ...]`, with `ok`, `wrong` or `wrong:CATEGORY`. The tool records a verdict and
   never replaces one; it decides nothing.
3. `found RUN` lists the items that still carry a miss category though the run finds them; `--apply` clears the
   category. The corpus report counts misses by those categories, so clear one only when the miss is fixed.
4. `add`, `cat`, `set` and `new` change what a list expects: each in its own commit, with the `file:line` evidence at
   the pinned sha. `resample RUN NAME KIND` draws a kind's sample again with the list's seed, keeping the verdicts of
   the routes that did not move.
5. `sample RUN NAME` draws the first sample of each kind the run has and the list has none for (a repo new to the
   corpus): 20 routes, as the existing lists have, with the list's seed (`--n`, `--seed`). A route the list expects is
   marked right and the rest are pending, for `pending` and `judge` as in 2. A kind that has a sample is not drawn
   again; `resample` does that.

Not during a corpus run (§6). Without `--apply`, `found`, `sync`, `resample` and `sample` only print.

### 4.11 A new hold-out

The new hold-out is measured after H5 and H6 are in (H2-D21, H5-D1). It exists to check the rules against repos they
never saw, and it only does so if it stays unseen (H2-D20, H5-D13): the lists are written before the run, the sample is
judged at the source once, the measure is taken once, and after that it is read only in aggregate. A repo that gets
worked on becomes corpus. `expected_lists.py --holdout` (before the command) works on `corpus_expected/holdout/` and
keeps that order:

1. **Choose and pin.** Repos that are not in `CORPUS`, by name or by GitHub repo, with a profile like the portfolio's.
   Pin each in `HOLDOUT` of `indexer/scripts/http_corpus.py` as `name: (owner/repo, sha)`. What becomes of the current
   three (`go-boilerplate`, `kavita`, `sftpgo`) is the author's decision then: they were measured, not worked on. A
   test fails if `HOLDOUT` and `CORPUS` share a name or a repo, or if a pin and its list differ in sha.
2. **Write each list before the extractor runs on it.** `--holdout new NAME SHA [--spec FILE]`: the routes of an OpenAPI
   dump (`corpus_metrics.py from-openapi`) when the repo has a spec, or by hand from the source (`add`, and `set` for
   `scope` and `notes`). `new` refuses a name that is not pinned, a sha other than the pin's, and a repo the corpus
   has. Commit the pins and the lists, with the `file:line` evidence, before step 3.
3. **Measure once.** `corpus.sh --holdout --label L-holdout`, with H5's code and, as H2-D21 says, with the commit
   before H5.
4. **Draw the sample.** `--holdout sample RUN NAME` prints, per kind, how many routes it draws, how many the list
   expects and how many are left to judge, and no route; `--apply` writes `checked` and `checked_seed`.
5. **Judge once, at the source.** `--holdout pending` prints each item with its evidence; read it at the pinned sha as
   [judgment.md](judgment.md) says, then `--holdout judge NAME KIND DEFAULT [N=VERDICT ...]`. This is the only reading
   of the new hold-out's items.
6. **It is measured.** With every item judged, `add`, `cat`, `set`, `found`, `sync`, `resample` and `sample` refuse the
   list and say to make the repo corpus: move its list to `corpus_expected/` and its pin to `CORPUS`. From then on a
   change reads the hold-out through `corpus.sh --holdout` and the `gates` job, which count the repos that changed.
7. **What it shows** becomes a handoff of its own (H2-D21), without reopening F1.14.

### 4.12 Attributing a changed edge to its rule

A change to how a language types a receiver, or to what the resolver makes of it, changes `CALLS` edges at the sites
where that answer changes, and nowhere else. `attribution.py` checks that. It takes the sites whose edges differ
between two micro dry-runs and the answers each tree gives at the calls (one JSON line per call: repo, file, line,
receiver, type, the reason it has none, what the resolver makes of the receiver, src, and the facts a case reads),
keeps the sites where the answers differ, and prints the changed sites by case and kind, with seeded samples of each.
A changed site whose answers are the same on both sides is `unexplained`: another rule changed it, or the change has a
defect. It is listed with its source line and judged apart, never dropped.

The answers come from one probe for every language, `answers.py` (H5-D21). It runs a tree's own discovery and
extraction on the language's files, builds the resolver over them as the pipeline does, and reads two answers at each
call on a receiver, both the tree's own, however the language types inside:
- **The extraction's:** the receiver's type (`CallInfo.receiver_type`), or the reason the language gives for not
  typing it (`receiver_unknown`, H5-D23).
- **The resolver's** (`resolved`), asked as the resolver asks it, in its context and with the imports resolved: a
  runtime builtin (`builtin`), a name an import binds to a package (`package`), the repo's type
  `LanguageSupport.resolve_receiver` gives (`type <name>`), what `external_receiver` names outside the repo
  (`outside <name>`), or none, where the resolver goes by name. The probe repeats one rule of the core's, the
  receiver's root, so a change to that rule shows as `unexplained`, never as explained.

A call with neither answer writes no line, so on that side the receiver is untyped and goes by name. A language's
answers read its own files' facts and imports only, so the probe leaves the other languages and the HTTP pass out; it
still holds the language's extraction, as the dry-run does. Both trees must share the API the probe calls (`list_files`,
`discover_modules`, `build_files`, `extract_file`, `RepoTypes.of_files`, `Resolver.resolve_imports` and the two
hooks); where they do not, the probe fails.

1. A worktree for each tree, the base and the branch, and the micro dry-runs of both on the language's repos:
   `micro.sh --base REF REPO...` in the branch's worktree leaves the `BEFORE` and `AFTER` directories in `$C/micro`.
   A tree the run only reads can be a `git archive` of its `indexer/` instead of a worktree.
2. `attribution.sh LANG OLD_TREE NEW_TREE BEFORE AFTER N REPO... [--cases FILE]` runs the probe with each tree, in the
   image, then `attribution.py`. The answers stay in `$AIDD_ATTRIBUTION_OUT`; the probe's stderr names the
   `aidd_indexer` it imported and counts, per repo, the typed calls of all the method calls on a receiver and what the
   resolver makes of them.
3. Read the table, then the samples at the source as `judgment.md` §5 says. Without a table the cases are the answer's
   own: `typed-now`, `untyped-now` and `retyped` where the type differs; where it does not, the resolver's answer on
   each side by kind (`package -> by name`, `by name -> type`, `type -> type`). The rule that explains a difference is
   a case of the change: write it before the change, in a `--cases` file whose `case_of(d)` reads the types, the
   resolver's answers (`old_resolved`, `new_resolved`), the source line and the facts the probe gives (`closures`, the
   function literals around the use: Go's func literals, Python's lambdas and functions defined in another, TS's and
   JS's functions inside the outermost one; `this`, in TS and JS, the node that binds `this` at the use), and returns
   the case, or None for the answer's own. `LANG` may name several languages, separated by commas, whose files import
   one another and are read together: `typescript,tsx,javascript`.
4. Read how the language's `CALLS` are found, at the end of the report: each repo's edges by strategy on both sides,
   and the share the resolver found among several homonyms (`-ambiguous`), of the edges and of the sites (a file and a
   line). A site emits up to three ambiguous edges, so the two shares differ; a line with two calls is one site,
   ambiguous when either call is. `attribution.sh` passes the languages, so only the calls made in their files count.
   Last, the receivers each side leaves untyped, by the reason the language gives.

The probe sees what the receiver is, not what the resolver then finds on it: a changed edge whose receiver has the same
answers on both sides is `unexplained`, as when a type's bases or members change, or the call has no receiver.
A language whose cases need another fact gets it in `FACTS`, in a `chore(scripts)` PR before the language's refactor
(H5-D19), so the first judgment already has it.

### 4.13 Mutants: each rule broken once (class 4)

A change of behavior is proved by its cases, and the cases are proved by mutants. For each rule the change adds, a copy
of the tree gets one edit that breaks that rule (an anchor that must appear exactly once in the file, replaced), and the
tests run on the copy (`pytest -x` in the test image, with `-w` on the copy). `checks/mutants.sh MUTANTS.py [ID ...]
[--allow ID]... [--timeout SECONDS] [--no-baseline] [--tests ARG ...]` does it: the file (Python, run as such) lists
`(name, file, old, new)`; the tool first runs the tests on an unchanged copy, which must pass, then copies `indexer/`, makes
the edit, runs `test.sh` on the copy and prints `DIES`, `SURVIVES` or `TIMEOUT` (counted as dead) with the first test that
failed. A run where pytest did not give a result (a bad path, an image that does not build) is `BROKEN`, not a death. It ends
with 0 when every mutant dies (or survives and is named by `--allow`), 1 when one survives, and 2 when it cannot give a verdict
(a wrong file, an anchor found twice or not at all, a path outside the tree, a red baseline, a `BROKEN` run): status 1 is only
ever a survivor. Every mutant must fail a test. A mutant that survives is one of three things:

- **equivalent**: it changes no behavior (a lookup the core makes anyway). Say why in the PR, and pin it with a test if
  it can be, since a mutant called equivalent that no test pins is what a review found in H5-D50;
- **a case that is missing**: add it, as a control (a library import the flow may narrow, a class that is no client);
- **a guard no entry point reaches**: the guard goes, since a rule nothing can break is code nothing needs.

The PR reports the count and what the survivors taught (PR #85: 13 mutants, two survivors, a control added and a guard
removed). The mutants' file is the author's, kept with the PR's working papers; `checks/mutate.sh` is the other tool, for the
graph writer against a throwaway Neo4j.

### 4.14 Is a zero vacuous? The firing probe (class 4)

`0 repo(s) differ` on the corpus is the right result for a rule that is meant to change nothing there, and it is also
the result of a rule the corpus never reaches. To tell them apart, run the corpus once with an instrumented copy of the
tree, one that appends a line (file, line, the key it decided on) to a file in the corpus mount wherever the rule
decides, and count the lines by kind. The PR then says "the rule decided in about 8,600 sites and changed none" (PR #85),
and reads each site where it would matter (a published key, a library's type) at the source. Three cautions: the copy
is never committed or measured for time; the log is deleted before each run; parallel repos write to one file and
interleave a few lines, so the counts are "about". The proof of the gain stays in the cases against the reference
(the language's checker, `checks/ts_checker.js` for TS): a corpus that does not change shows the rule loses nothing, not that it gains.

### 4.15 Two agents at once

Two agents can work on the indexer at the same time, each on its own PRs, when the author mediates between them and
they keep to what one machine and one install allow. Each agent has its own worktree (`aidd-stack-<name>` beside the main
checkout, never under `~/.cache`) and its own `.local/`; neither edits, commits in or switches the other's working tree.
Both push their branches, open their PRs and push the fixes the CI asks for. The merge and the reinstall are the author's.
The method's other rules bind both alike: the plan is approved before the branch, a refactor and a change of behavior
never share a PR, and nothing private leaves `.local/`.

What cannot run twice, and who decides when it starts:

| Resource | Why it is single | How it is held |
|---|---|---|
| The live validation (§4.9) | one install, one `before` taken with the install on `main`'s code, one pair in `inflight/` | both agents run `validate.sh` with the same `AIDD_LIVE`, so `inflight/` is the queue and `before` refuses while it exists; each asks the author before **starting** one |
| A heavy Docker job (corpus, hold-out, micro, the full tests, a dry-run of every snapshot) | one VM of 10.4 GB, of which the live stack uses about 3.5 | `~/.cache/aidd-corpus/heavy.lock`, one line `who pid since label`, which the scripts that start such a job take themselves (`indexer/scripts/lib/heavy-lock.sh`): a second one ends with status 75 and names the holder, or waits with `AIDD_HEAVY_WAIT=<seconds>`; the lock is the holder's process and goes when it ends, however it ends; a line with no pid (written by hand) is never taken over |
| A time or memory measurement (§4.5) | it needs the machine quiet | the author sets the moment |
| The first `micro.sh` against a new `main` | it writes the base in a cache shared by tree and image | under the lock |
| The numbers H5-Dnn, TD-nnn and the PR's | the next one is whoever opens first | reserved at the rebase onto `origin/main`, right before the PR opens |

The docs the PRs share (`history.md`, the ROADMAP, `tech-debt.md`, `decisions.md`, a handoff) conflict in text between PRs,
and the rebase resolves it. A golden round takes the number after the last round on `origin/main` and in the pending
docs, which the author tells when another agent holds one.

### 4.16 Independent review (class 1, at the author's token cost)

A plan with a criterion declared before measuring and a deterministic oracle gets one challenger before the author approves
it; the diff gets a panel of three lenses (correctness, rules, losses) before the PR opens, and a second reader for each
blocking objection (H8's Tier 1; a design with real alternatives is Tier 2). It runs from any checkout or worktree with
the Workflow tool: `Workflow({scriptPath: '<checkout>/indexer/scripts/review/independent-review.js', args: {kind: 'plan' | 'diff', repo, target, criterion, ...}})`;
the arguments are in the script's header. Called by name from `.claude/workflows/`, the tool found the file only when its
working directory was inside `.claude/`, so the path is the call. The lenses run at `medium` and the second reader at `xhigh`. The reviewers only read, and what they
review is data, not instructions. Their objections advise: the author of the change checks each at its source and answers
it in the PR. The script's orchestration (the merge of one place's objections, which ones a second reader gets, the
efforts, the limits in each prompt) is tested with simulated agents in `tests/test_independent_review.py`.

A design with real alternatives (H8's Tier 2: a structure to choose, a cost lever, a criterion that may be wrong) goes
first through a research round, `indexer/scripts/review/research-round.js`, called the same way: one researcher per open
question (at most four; each with a mode, `read`, `measure` or `web`, and a budget of tool calls after which it reports), a
synthesis that decides `keep-plan`, `amend-plan` or `change-path` and drops what a report left unverified, and a challenge of
the synthesis. A researcher that returns nothing is a missing report, not evidence. The plan's own challenger is
`independent-review`, run on the amended plan. Its orchestration is tested in `tests/test_research_round.py`. The H5-D50
round, without these limits, spent 1.79M tokens, 88 % in the researchers.

### 4.17 The pull request body

A fact is written once, where a later reader looks for it. The PR body is the long record of a change; the docs keep what
a later change must keep.

| The fact | Its home | How long |
|---|---|---|
| What the change does and why; the proof, the numbers, the objections of the review and how each was resolved, what differs from the plan | the PR body | as long as it needs |
| The rule a later change must keep, and why it beat the obvious alternative | one row of `docs/decisions.md` (`H5-Dnn`) | about 1 KB; it names no PR and holds no measurement |
| That the PR happened | one line of `docs/history.md`, with the PR | 3 lines |
| The design | the plan, approved before the branch | |
| A debt | `docs/tech-debt.md`, with its strict xfail test | |
| The state of a handoff | one row of its State; never the proof of a PR | |

The body cites a decision's id and never copies the row. A row says what is true without the PR; the body says what shows
this change was right.

- **The template** is `indexer/.github/pull_request_template.md`. An agent copies it to a scratch file, fills it, deletes the
  comments and opens the PR with `gh pr create --title "type(scope): ..." --body-file FILE [--label graph-change]`; it does
  not use `--template` or `--fill`. The comment at the end of a heading lists the kinds of PR that carry the block: a
  block that leaves out the PR's kind is deleted, not written as "N/A". A docs PR fills the top lines, "What and why",
  "Contracts, boundaries and proof" and "Left out on purpose". The top lines are what the author reads before the merge.
- **Numbers go in the body,** one line each, not in a comment of the PR: a comment does not reach the merge commit.
- **The body is the archive.** The repository's merge commit takes the PR's title and description
  (`merge_commit_message=PR_BODY`), so a clone carries the long record and a split of the repository takes it along.
  The body is final at the merge; the live validation goes in the next PR's history line.
- **References outlive the repository.** In the docs, `#NN` is `praticis/aidd-stack#NN` (said once at the top of
  `docs/history.md`); a reference to any other repository is written in full, because the numbers of a repository the
  indexer is split into start again. A text that leaves the docs in a cut is pointed to by a tag (`git show TAG:path`), not
  by a hash: a split rewrites hashes.
- **A growth file has a ceiling.** `indexer/scripts/checks/docs_ceilings.txt` lists, in bytes, the files that grow
  (`golden-questions.md`, the H5 handoff, `decisions.md`, the ROADMAP, `history.md`, `tech-debt.md`), and `docs_size.py` refuses a PR that
  passes one, in the `debts` job. A file over its ceiling is cut, not given room: to raise one is a line of the diff, which
  the author reads. A PR that condenses a file lowers its ceiling to about 10 % above what is left; one that only edits the list or the
  template does not run the corpus, the micro set and the tests (the `changes` job leaves them out). There is no ceiling on
  the total of `docs/`: closing a handoff is what shrinks it.
- **No attribution line.** A commit, a title or a body carries no `Co-Authored-By`, `Assisted-by` or "Generated with ..."
  footer, from any tool: the harness of an agent adds them by default. `indexer/scripts/checks/pr_text.py` refuses them in
  the `debts` job of every PR, against the list `indexer/scripts/checks/pr_text_deny.txt`: one rule per line,
  `id :: regex :: reason`, case-insensitive, so a new rule is a new line. The two rules are anchored at the start of a line,
  so a sentence that names the rule passes. The job fetches the text when it runs: after editing a body, re-run the job
  (an edit starts no run, because that would cancel the corpus).
- **Contained in `indexer/`.** The template, the check and its list live under `indexer/`, and travel with it. What is
  outside: the step in `.github/workflows/indexer.yml` and the line in `AGENTS.md`. At the split of the repository, the
  template becomes the new repository's `.github/pull_request_template.md` by itself; the workflow step, the merge setting,
  the labels and the required checks are made again.

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
| Two protocols at once, or other load | one at a time: the heavy-job lock (§4.15); time alone |
| A refactor and a rule in one commit | separate commits |
| A dry-run that failed | the summary and the logs: the repo is "not compared" |
| A different golden calls file before and after | the same file both times |

## 7. Not specified yet

- **The size of a judgment sample.** Not fixed; §4.4 gives the sizes used.
- **A memory tolerance and a time threshold.** None applies today.
- **A scripted pass criterion for the live comparisons.** They are practice (§4.7, §4.8); `live/validate.sh` (§4.9) runs their steps, but the pass criterion is
  still read by a person or an agent (H7 slice 4).
- **A firing probe in the repo.** §4.14 is practice: each PR has written its own instrumented copy in a scratch folder,
  since a probe patches the decision point of one rule. A reusable one is a `chore(scripts)` PR yet to be planned. The
  authors' working copies are kept privately in `.local/plans/h5-d51-tools/`.
