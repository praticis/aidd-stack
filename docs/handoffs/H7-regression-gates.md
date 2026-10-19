# Handoff H7 — Regression gates in CI: the method as checks

> Paste this file (or ask for `docs/handoffs/H7-regression-gates.md` to be read) at the start of a new chat. Before
> anything else, the chat should read:
> - `AGENTS.md`, the entry point;
> - `docs/decisions.md`: H2-D4…D21, the method's decisions;
> - `docs/corpus-report.md`: "How it is measured" and the baselines table;
> - `docs/handoffs/H5-indexer-refactor.md`: the regression protocol every step follows;
> - `docs/handoffs/H6-extraction-pipeline.md`: the cache, and "How it is measured";
> - `docs/handoffs/H4.1-contributor-path.md`: the contributors these gates serve. H4.1-D5 (the corpus in CI) is
>   absorbed here;
> - the fifth round of `docs/golden-questions.md`: how PR #5 was validated on a live install.
>
> **State (2026-10-19):** registered by the author, not started. Proposed slot: the first slice lands before H5's
> steps 4 to 7 resume, so that every following step of H5 and H6 is proved by CI and not by hand (H7-D5).

## Context in one paragraph

Today the method's checks run by hand: the corpus against a baseline, every diff item judged at the source, the
hold-out identical, `0 repo(s) differ` for a refactor, no win lost, the live install before a merge. They work
because the author and one agent run them every time. A contributor, or their AI, may not. H7 turns what is
mechanical in the method into CI gates that fail a PR, and shrinks what needs judgment to a short list, each item
shown with its source line. The gates use only deterministic measures, so they do not flake, and they protect what
H2 and F1.14 achieved from any PR, the author's included.

## What becomes a gate

| Gate | From | Fails when |
|---|---|---|
| **Precision ratchet** | H2-D11 | the list precision of any repo or language is lower on the branch than on the baseline |
| **No win lost** | PR #5's validation | an expected pair the baseline found is missing on the branch, or an item of the `checked` sample judged right is no longer extracted |
| **Hold-out untouched** | H2-D20, H2-D21 | the hold-out's ids change in a PR without the `holdout-measurement` label |
| **A refactor changes nothing** | H5 | a PR with the `refactor` label changes any id of the corpus or the hold-out |
| **One cause per commit** | H5's pitfalls | one commit touches both the extractor (`indexer/aidd_indexer/`) and `indexer/tests/corpus_expected/` |
| **Every diff item judged** | the cycle of a change | an item the classifier marks "to judge" has no verdict (H7-D2) |
| **Cold equals warm** | H6, once the cache is in | a run with the cache gives a different result from one without it |
| **Memory** | F1.13, H6 | a repo's peak memory grows past a tolerance set from H6's measured spread (H7-D4) |
| Tests, hygiene, shape | they exist | as today; the shape report starts blocking when the author decides (H5-D3) |

Time never gates: shared runners are noisy, and the corpus already varies about 28 % between runs on one machine.
Time is a nightly trend instead.

## What stays judgment, and how CI shrinks it

Judging an item at its source is what keeps the expected lists evidence, and an LLM does not decide it. CI
classifies the diff the way a judgment starts:

- **gain:** a new item that is in the expected list. Nothing to judge;
- **regression:** an expected item that went missing. The gate fails;
- **to judge:**
  - a new item outside the expected list: a false positive, or a real route the list lacks (H2-D15);
  - an item outside the list that went missing: probably a false positive removed;
  - any change outside a list's scope.

The PR comment lists the "to judge" items, each with a link to its `file:line` on GitHub at the pinned SHA and a few
lines of context, so a reviewer, or their AI, judges each one in seconds. The verdicts are recorded (H7-D2), and the
PR does not merge with an item unjudged.

## The pipeline

```
 every push to a PR (minutes)
   tests and fixtures · code hygiene · shape report · docs links and repo paths · the MCP against an ephemeral Neo4j

 a PR that touches indexer/** (to be measured; likely 15–25 min)
   the corpus of the branch vs the baseline of the merge base  ──►  gates + the classified diff, as a PR comment
   the hold-out of the branch vs its baseline                   ──►  gate

 a merge to main
   the corpus and the hold-out run, and the runs are published as the new baselines, named by the commit (H7-D1);
   the corpus report's numbers come from them, not typed by hand

 nightly, on main
   corpus + hold-out, three times: the medians of time and memory per repo as a trend, with an alert past the noise
```

## On GitHub's runners

- **Capacity:** a public repo's standard runners are free, with 4 vCPU and 16 GB, enough for 3 to 4 corpus repos at
  once (the largest peak is mattermost's, 2.2 GiB). The clones are 3.6 GB, cached between runs and keyed by the pins
  in `CORPUS`. `http_corpus.py` already clones each repo at its SHA.
- **The baseline is the merge base's,** not the tip of `main`; otherwise a PR inherits another PR's diff. When the
  merge base has no published baseline, the job runs it first.
- **Forks:** the corpus job runs on `pull_request`, with a read-only token and no secrets. It uploads the report as an
  artifact, and a second workflow (`workflow_run`), which never checks out the PR's code, posts the comment. Never
  `pull_request_target` with the PR's code checked out.
- **Third-party code never runs:** the job parses the corpus repos and builds or tests none of them.

## The live validation

The portfolio's install cannot move to GitHub: its repos are private, and a self-hosted runner on a public repo runs
code from any fork's PR. So it has two parts:

- **Local, for the maintainer:** `indexer/scripts/live-check.sh` automates what PR #5 did by hand: a dry-run of `main`
  and of the branch on each snapshot at its SHA (with `-w` on the mounted code), pictures of the graph before and
  after the reinstall, the MCP's answers recorded through HTTP, and their diff. Its output stays on the machine.
- **In CI, on a demo tenant of public repos** (H4.1-D4): the compose stack starts in the runner, indexes the demo with
  `main`'s image, takes a picture, re-indexes with the branch's image, takes another, and runs golden questions
  written for the demo.

## Slices

| # | Slice | Done when |
|---|---|---|
| 1 | Baselines published on merge to `main`; the corpus and the hold-out on a PR; the gates of precision, no win lost, hold-out and refactor; the classified diff as a comment | PR #7's refactor commits get a comment that says `0 repo(s) differ`, and a test PR that drops a route fails |
| 2 | One cause per commit, `CODEOWNERS` on the expected lists, the verdicts recorded and checked | a PR with an unjudged item cannot merge |
| 3 | The nightly trend of time and memory | a week of medians with their spread |
| 4 | `live-check.sh`, and the demo tenant in CI | the demo tenant's golden questions in a PR's checks |
| 5 | After H6: the cold-equals-warm gate, and the PR corpus run only on the files the PR changed | a PR's corpus job takes a fraction of a cold run |
| 6 | The shape report blocks (H5-D3) | the author turns it on |

## Decisions to make with the author

| # | Decision | Recommendation | Why |
|---|---|---|---|
| H7-D1 | Where the baselines live | An OCI artifact on GHCR per baseline, tagged by the commit (`oras push`); release assets as the alternative | Actions artifacts expire; GHCR is already where the indexer's image goes (H4-D10); a data branch would grow the history |
| H7-D2 | How verdicts are recorded | A file committed with the PR, one verdict and one reason per "to judge" item, checked by CI to cover them all | A checkbox can be ticked without judging; the file is also the record of why a baseline changed |
| H7-D3 | When the corpus job runs | On every PR that touches `indexer/**`, once its time is measured; a label reruns it | A gate that runs only when someone remembers is not a gate |
| H7-D4 | The memory tolerance | From the spread H6's step 0 measures across runs | A tolerance below the noise flakes; one far above it catches nothing |
| H7-D5 | The slot | The first slice before H5's steps 4 to 7 resume | Those steps move the heart of the extractor; with the gates, each push proves `0 differ` |

## Pitfalls

- **A flaky gate gets switched off.** Only deterministic measures gate: ids, precision and recall, the hold-out's ids.
- **Changing the ruler and the measured thing together passes any gate.** That is why one commit never touches both
  the extractor and the expected lists, and why the lists have code owners.
- **The wrong baseline.** The merge base's, always.
- **Disk on the runner:** clones, the image and Docker's layers. Measure the free space and prune.
- **A pin that changes** re-fetches its clone; the cache key includes the pins.
- **The comment on a fork's PR** needs the two-workflow pattern; a token with write access never meets the PR's code.

## How H7 relates to the others

- **H4.1:** H7 is the "checks in CI" part of the contributor path. H4.1-D4 (the demo tenant) and H4.1-D6 (code owners)
  are shared; H4.1-D5 is replaced by H7.
- **H5:** H7 runs H5's regression protocol on every push.
- **H6:** the cache makes the PR corpus run cheap, and adds the cold-equals-warm gate.

## Constraints and conventions

- Everything in the repo is in English; one-line conventional commits, with no body and no attribution.
- New code meets the shape targets: complexity ≤ 9, modules ≤ 300 lines.
- No real tenant or private project names, in the code, the workflows or the comments the bot posts.
- An LLM is never the parser, and never the judge of a gate.

## Expected deliverables

- The workflows (PR checks, the corpus job, the comment, the baseline publishing, the nightly trend).
- The diff classifier, next to `scripts/corpus_metrics.py`, with tests.
- `indexer/scripts/live-check.sh`, and the demo tenant's setup and golden questions.
- `CONTRIBUTING.md`'s part on what the bot's comment means and how to record verdicts (with H4.1).
- The decisions H7-D1…D5 in `docs/decisions.md`.
