# The indexer's validation method: entry point

How a change to the indexer is proven, and how to resume that work from the repository alone. This folder holds the
method, which does not change per PR. **State does not live here:** where H5 stands, what is missing and what comes
next are in the status block of [the H5 handoff](../handoffs/H5-indexer-refactor.md) and in the ROADMAP's "Where we
are".

## Reading order

| # | Read | For |
|---|---|---|
| 1 | [`AGENTS.md`](../../AGENTS.md) | the project, the principles, the gates |
| 2 | the status block of [the H5 handoff](../handoffs/H5-indexer-refactor.md) | where we are, what is open, what is next |
| 3 | [method.md](method.md) | the cycle of a change, its commands and criteria, who authorizes what |
| 4 | [judgment.md](judgment.md) | how a difference becomes a verdict |
| 5 | [`indexer/scripts/README.md`](../../indexer/scripts/README.md) | every tool, what it answers and how it runs |

[resume-test.md](resume-test.md) is the test of these documents. A session under test should not read it first.

## Resuming

Steps 1 to 5 only read.

1. **Git's state, changing nothing:** `git status --porcelain`, `git diff --cached --stat`,
   `git branch --show-current`, `git log --oneline -1`, `git worktree list`. Staged and unstaged files are work in
   progress: leave them as found.
2. **The state:** the H5 handoff's status block, then the ROADMAP.
3. **The method:** method.md and judgment.md.
4. **What the task needs exists:**
   - the tools, by their paths in `indexer/scripts/README.md`;
   - the baselines: `ls ~/.cache/aidd-corpus/runs/2026-10-18-v2-baseline-29`;
   - private live evidence in `.local/indexer/live/`, checked as its README says, never copied out;
   - an H6 script's branch: `git ls-tree origin/h6/step1-proto`.
5. **Pin the versions:** the code tree (`git rev-parse <ref>:indexer/aidd_indexer`), the image
   (`docker image inspect -f '{{.Id}}' aidd-indexer:local`) and whether a micro base exists for that pair
   (`ls ~/.cache/aidd-corpus/micro`).
6. **Sort the next tasks by authorization class** (method.md §2) and ask for each class separately. Reading or
   documenting a procedure is never permission to run it.
7. **Record what you find** with its source and date. Change a handoff, the ROADMAP or a history line only where the
   evidence supports it. Commits, pushes and PRs are the author's to approve.

A shell note: under zsh, a separator such as `echo ====` fails with "not found"; use plain text.

## What a clean clone lacks, by design

| Missing | Why |
|---|---|
| `.local/` | private evidence (live pictures, golden calls); never in git |
| `~/.cache/aidd-corpus` | clones, runs, baselines and micro bases are regenerable; baselines are not published |
| the live install (`~/.aidd`, its Neo4j and MCP) | its checks need the author's authorization |
| the H6 branch's files | they are on `origin/h6/step1-proto`, read with `git ls-tree`, never merged |

A missing item here is not a failed check. Private evidence is never recreated.
