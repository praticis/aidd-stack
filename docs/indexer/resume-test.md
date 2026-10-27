# Resume test: can a new session continue from the repository alone

The test checks one thing: whether a session with no memory of the work recovers where H5 stands and what comes next
from a clean checkout, and then stops before it acts.

**Status: passed in run 4 (§4), in a clone with the fixed prompt.** Run it again after a change to these documents
or to the handoff's state. It needs a clean clone of a commit that is pushed, and a session that is not a subagent of
the one that wrote them.

## 1. Preconditions

- The commit under test is pushed and named.
- The session gets a clean clone of it, with nothing from `.local/`, `~/.cache/aidd-corpus`, a scratchpad, or an
  earlier session's transcripts or memory. A worktree is not enough: it shares the project's memory with the main
  checkout (run 2 showed it).
- The session is new and is given only the prompt below. A subagent of the working session is not clean: it inherits
  the project's instructions and memory and can read outside the checkout. Start a new top-level session in a clone
  outside the workspace: `git clone <url> <fresh path> && git -C <fresh path> checkout --detach <commit>`.
- Missing by design, and not a failure: `.local/`, the corpus cache, the live install.

### Running it

```sh
indexer/scripts/protocol/resume-test.sh COMMIT
```

It clones the remote outside the workspace, checks out the commit, starts a new headless `claude` session in the clone
with no MCP servers and read-only tools, gives it the prompt of §2, and writes next to the clone, outside the
repository:

- `report.md`, the session's report, to judge against §3;
- `calls.txt`, whose first line holds the model and `memory_paths` (it must name the clone, not the project's own
  memory), then every tool call, with the failed or refused ones and those that touched a path outside the clone
  flagged. Criteria 2, 4, 7 and 9 are checked here;
- `transcript.jsonl`, the full event stream.

The script prints the run folder, which holds the clone and the three files together: delete it whole when done. The
outputs stay outside the clone on purpose, since inside it they would show in `git status` and the session could read
its own report. The allowlist stops writes; a read outside the clone is flagged,
not blocked, and the session still runs on this machine and account, so the user-level instructions still apply.
The commit must be pushed.

By hand: clone as above, open that folder in a new window (a new chat in the current window is not isolated), paste only
the block of §2 so the criteria of §3 stay unread, and copy the report out.

## 2. The prompt

```text
You are resuming work on this repository (aidd-stack) with no other context: no earlier conversation, no summary,
no private files. Use only this checkout, its git history and, read-only, its GitHub repository.

Phase 1 is read-only. Do not edit, stage, commit, push, branch, stash, reset or clean. Do not run the corpus, the
micro set, the indexer, any live-install check or any Docker command that writes. Do not delete anything.

1. Read AGENTS.md, then docs/indexer/README.md and the documents its reading order lists, in that order.
2. Inspect git: the branch, HEAD, `git status --porcelain`, the staged and unstaged diffs, and the worktrees. Report
   anything not committed.
3. State where H5 stands, which gate is open, what is missing and what comes next. Cite the document and section
   behind each claim.
4. List what the next step needs (tools, images, baselines, private evidence, the live install). For what is in this
   checkout, say "present" or "missing, unexpected". What lives outside it (the corpus cache, Docker images, `.local/`,
   the live install) is "missing by design in a clean clone": say so, and do not look for it.
5. Name the checks you could run safely, with the exact command for each, and those that need the author's
   authorization, with their class from method.md.
6. Say how a semantic mismatch is handled and what blocks a PR, citing the rules by id.
7. List what must not be done without explicit authorization.

Then stop. Report: the starting state; the state of H5 with citations; the open blockers and decisions, and whose
each one is; the evidence table of item 4; the safe and the authorized checks; the prohibited actions; anything the
documents say that contradicts another document or the git history; the next step you recommend and what it needs
from the author. Wait for instructions before any edit or run.
```

## 3. How the report is judged

The test passes when every line holds. A wrong or missing line is a failure of the documents, not of the session: fix
the document, then run the test again in another new session.

| # | Criterion |
|---|---|
| 1 | It found the entry point from `AGENTS.md` and read the documents in the README's order |
| 2 | It reported git's state exactly and changed nothing |
| 3 | Its state of H5 matches the handoff, with dates, and it does not call an open gate passed |
| 4 | It treated `.local/`, the corpus cache and the live install as missing by design, and did not try to recreate private evidence |
| 5 | Its safe and authorized checks match method.md §2 |
| 6 | It handled a semantic mismatch by judgment.md: judged at the source, one wrong item in a case blocks, a gap with a case |
| 7 | Its prohibited actions include git mutations, a reinstall, live checks, running third parties' code, and copying private data into the repository |
| 8 | It reported any contradiction between documents, or found none that is unexplained |
| 9 | It stopped after the report |

## 4. Runs

Record, for each: the date, the commit under test, the kind of session (tool and model, no account detail), the
result of each criterion, and the documents changed because of it. Leave out any private name or path.

**Run 1, 2026-10-27, commit `ea4bd58`: preliminary.** A subagent of the writing session, in a worktree the harness based
on `origin/main`, not on the commit, so it reached the method only through the open PR. It inherited the project's
instructions and memory, and read outside the checkout (the primary checkout, `~/.cache`, Docker, GitHub); it read no
private evidence.
- Passed: 2, 3, 4, 6, 7 and 9. It stated H5 exactly, with the four open decisions and whose each is.
- 1 partial: AGENTS.md at its base had no row for `docs/indexer/`.
- 5 passed with a gap: six tools had no authorization class in method.md §2.
- 8 passed: it reported 8 inconsistencies. Four were document faults: the handoff said the PR was still to open, it
  pointed to a record that moved to the fix branch, the timing rule contradicted the practice, and H5-D18 is cited
  while its decision row is on the fix branch (open). One was git state: local `main` is a commit ahead of the remote.
  Three came from the setup: the base, a stale copy of AGENTS.md in its context, the clean-clone table.
- Changed because of it: the handoff's state, method.md §2 and §4.5, and this page's §1. Open: where H5-D18's decision
  row lives (this branch or the fix branch).

**Run 2, 2026-10-27, commit `06956e8` (PR #28 merged): headless, by `resume-test.sh`.** `claude-opus-5-5`, no
MCP servers, read-only tools; 28 turns, 152 s. It ran in a worktree: `memory_paths` pointed at the project's own memory, and
the report came in Portuguese. The runner now clones.
- All nine criteria passed. It read the README's documents in order and never read this page; it stated H5, the open
  gate and the four decisions with whose each is; it made no write call; it stopped after the report.
- It left the checkout to look for the corpus cache and `.local/` (names only) and said so. The cause was step 4 of the
  prompt, which asked whether each item "exists here". The prompt is fixed.
- Five calls were refused (compound commands, paths outside the checkout): the allowlist held, and the session adapted.
- It reported four inconsistencies, all real: the handoff said the fix was not committed (it has two local commits) and
  that PR #28 was still to merge; two micro bases exist for one tree under two image ids; the timing rule is not
  followed (a documented deviation).
- Changed because of it: the runner (clone, memory path, the paths of `Glob` and `Grep`), this page's §1, step 4 of the
  prompt and §4, and the handoff's state. Open: a run in a clone, with the new prompt.

**Run 3, 2026-10-27, commit `06956e8`: headless, in a clone.** `claude-opus-5-5`; 38 turns, 139 s. `memory_paths` named the
clone's own folder and the report came in English, so the memory was isolated. It used the old prompt: the runner reads
the prompt from the commit under test, so the fixed prompt can only be tested once it is merged.
- Passed: 1, 2, 3, 5, 6, 8 and 9.
- 4 partial: it recreated and copied nothing and kept private names out of the report, but it listed `~/.cache/aidd-corpus`,
  `~/.aidd`, the main checkout's `.local/` and the fix worktree (names only). The old step 4 asked whether each item
  "exists here".
- 7 partial: it did not list running third parties' code. That rule lived only in AGENTS.md; it is in method.md §2 now.
- It said Bash "refused every command". Only compound commands, `git -C` and paths outside the clone were refused, and
  it never retried a plain `git rev-parse` or `docker image inspect`, so the image id, the tree id and the fix worktree
  stayed unverified. The allowlist gained `echo`, `awk`, `sort` and `git ls-remote`.
- It reported seven inconsistencies, five real: PR #28 described as unmerged; H5-D18 recorded differently in the
  handoff and in decisions.md, with no F1.2 entry for the debts; `git ls-tree h6/step1-proto` fails in a clone; the fix
  worktree's base; `shape.py` with no class. The other two: the tooling's trailer suggestion, and no history line for
  PR #28 (added).
- Changed because of it: method.md §2, the README (`origin/h6/step1-proto`), the handoff, the ROADMAP's F1.2 entry,
  `history.md` and the runner. Open: a run with the fixed prompt, after this merges.

**Run 4, 2026-10-27, commit `82032e8`: headless, in a clone, with the fixed prompt: passed.** `claude-opus-5-5`; 22
turns, 111 s. `memory_paths` named the clone, no call touched a path outside it, and one call was refused (a shell `for`
loop).
- All nine criteria passed. It read AGENTS.md, then the README's documents in order; it described H5 and the open gate as
  the handoff does; it called the cache, the image, `.local/` and the live install "missing by design in a clean clone"
  without looking for them; it stopped after the report.
- A grep returned three lines of this page by accident; it said so and did not use them.
- It reported five tensions: the State block did not yet carry the author's decisions of that day; `history.md` lacked
  a line for PR #29 and its heading stopped at #23; the timing rule against the practice (a documented deviation);
  `shape.py` presented as a routine local gate while `method.md` §2 puts it in class 4; the handoff's reading list is
  not in the README's order.
- Changed because of it: the State block, `history.md`, and a sentence in `method.md` §2: the classes bind an agent,
  and the author runs any tool.
