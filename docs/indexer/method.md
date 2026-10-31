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
| 12 | Record | a golden round, `docs/history.md`, the H5 handoff, the ROADMAP | each change supported by the evidence |

A change to the extractor adds, before step 4: corpus `--baseline`, judgment at the source, the expected lists
(`lists/expected_lists.py` edits them, `checks/expected_lists_diff.py` shows what changed; §4.10), and a new
baseline only after its diff was judged item by item.

What judgment finds and does not block is registered as a debt (`docs/tech-debt.md`) with a strict xfail test, never
as a note.

A refactor and a change of behavior never share a commit: one `refactor:` commit makes the whole PR strict.

## 2. Who authorizes what

Permission to read or document a procedure is not permission to run it. Each class needs its own authorization, per
task; approval in one task does not carry over.

The classes bind an agent; the author runs any of these tools without asking.

| Class | Examples | Authorization |
|---|---|---|
| 1. Read-only | `git status/log/show`, reading files, `docker image inspect`, `gh pr view`, `debts.py` | the task |
| 2. Offline analysis of saved artifacts | `judgment/` tools but `attribution.sh`, `gates.sh`, `checks/expected_lists_*.py`, `live/dry_sections.py`, `live/graph_vs_dry.py` | the task says to run it |
| 3. Local files | editing docs or scripts; `lists/expected_lists.py` (edits the repository's expected lists); writes to `.local/` or `$C` | the task asks; `before/` pictures are never rewritten |
| 4. Corpus or indexer execution | `corpus.sh`, `micro.sh`, `protocol.sh`, `time-alone.sh`, `test.sh`, `mcp-it.sh`, `protocol/shape.sh`, `shape.py` on the host, `checks/mutate.sh`, `checks/dump.py`, `checks/python_scopes.py`, `probes/`, `judgment/attribution.sh`; `protocol/resume-test.sh` (a headless `claude` session on the author's account) | explicit. One protocol at a time, in the background; never edit the mounted code during a run |
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
pair is not kept: a snapshot's sha and the indexer's commit (the build id) give the same dry-run again. Private data
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
python3 -I indexer/scripts/judgment/attribution.py BEFORE AFTER OLD.jsonl NEW.jsonl N REPO... [--cases FILE] [--repos DIR] [--language LANG]
indexer/scripts/judgment/attribution.sh LANG OLD_TREE NEW_TREE BEFORE AFTER N REPO... [--cases FILE]
```

`BEFORE` and `AFTER` hold `<repo>.json.gz` dry-runs. `chain_diff` samples with a fixed seed over sorted sites, so the
same inputs give the same sample. Sizes used: `N` 6 to 12 per kind for each commit against the one before, 40 for
`main` against the tip. `attribution.py` is §4.12.

### 4.5 Timing alone

`time-alone.sh` runs the corpus's wall time and four full dry-runs on `main`'s worktree, then the branch's, with no
other load. The rule is the median of three runs alone (H4.1); PRs #20 to #27 ran one per side. Run three when time matters.

### 4.6 Equivalence of a representation

`checks/dump.py LANGUAGE OUT` (`csharp`, `go` or `python`) dumps every file's type facts under `/corpus`, read as the
extractor reads them, through the language's per-file index. The same dump from two codes, compared with `cmp`, shows
whether a refactor changed a fact.

`checks/python_scopes.py [N]` compares Python's scope index with CPython's `symtable` over every Python file under
`/corpus`: each scope paired with symtable's, each name classified the same (local, global or free). It prints the
counts, the files it compared and those CPython 3.12 does not compile, and N samples of each difference. symtable only
compiles a file's symbols; no repository's code runs.

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
(`dry_sections.py`) and against the graph, which must hold `main`'s dry-run, the strategies, `virtual` and the
hierarchy's edges included (`graph_vs_dry.py` with the before only). It seals the folder in `SHA256SUMS` and prints counts.

### 4.8 Live, after the merge (class 5)

After the author's reinstall: `indexer/scripts/live/validate.sh after`. It refuses until the installed code is
AFTER_COMMIT's, every snapshot's last run since the before is ok and, when the code that shapes the graph changed (the
parts the build fingerprints), every snapshot holds a build other than the before's: an ok run of a refresh before the
reinstall is the old code's (the refresh runs every 15 min). A refusal writes no picture, so it runs again. It takes
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
| 3 | agent | `indexer/scripts/live/validate.sh after` | the install on AFTER's code, and every snapshot re-indexed (the refresh runs every 15 min) |
| 4 | agent | read the counts against §4.8; report numbers only | |
| 5 | agent | `indexer/scripts/live/validate.sh rotate --yes` | `after/` taken, the PR's records done |

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
| `N snapshot(s) have no ok run since the before` | wait for the refresh (up to 15 min) and run it again |
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
   function literals around the use: Go's func literals, Python's lambdas and functions defined in another), and
   returns the case, or None for the answer's own.
4. Read how the language's `CALLS` are found, at the end of the report: each repo's edges by strategy on both sides,
   and the share the resolver found among several homonyms (`-ambiguous`), of the edges and of the sites (a file and a
   line). A site emits up to three ambiguous edges, so the two shares differ; a line with two calls is one site,
   ambiguous when either call is. `attribution.sh` passes the language, so only the calls made in its files count.
   Last, the receivers each side leaves untyped, by the reason the language gives.

The probe sees what the receiver is, not what the resolver then finds on it: a changed edge whose receiver has the same
answers on both sides is `unexplained`, as when a type's bases or members change, or the call has no receiver.
A language whose cases need another fact gets it in `FACTS`, in a `chore(scripts)` PR before the language's refactor
(H5-D19), so the first judgment already has it.

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

- **The size of a judgment sample.** Not fixed; §4.4 gives the sizes used.
- **A memory tolerance and a time threshold.** None applies today.
- **A scripted pass criterion for the live comparisons.** They are practice (§4.7, §4.8); `live-check.sh` (H7 slice 4)
  was never built.
