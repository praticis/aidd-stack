# Resume test: can a new session continue from the repository alone

The test checks one thing: whether a session with no memory of the work recovers where H5 stands and what comes next
from a clean checkout, and then stops before it acts.

**Status: one preliminary run (§4); a clean run is still to do.** It needs a clean clone of a commit that is pushed,
and a session that is not a subagent of the one that wrote these documents.

## 1. Preconditions

- The commit under test is pushed and named.
- The session gets a clean clone or worktree of it, with nothing from `.local/`, `~/.cache/aidd-corpus`, a
  scratchpad, or an earlier session's transcripts or memory.
- The session is new and is given only the prompt below. A subagent of the working session is not clean: it inherits
  the project's instructions and memory and can read outside the checkout. Start a new top-level session in a detached
  worktree outside the workspace: `git worktree add --detach <fresh path> <commit>`.
- Missing by design, and not a failure: `.local/`, the corpus cache, the live install.

### Running it

```sh
indexer/scripts/protocol/resume-test.sh COMMIT
```

It makes a detached worktree outside the workspace, starts a new headless `claude` session in it with no memory, no
MCP servers and read-only tools, gives it the prompt of §2, and writes next to the worktree, outside the repository:

- `report.md`, the session's report, to judge against §3;
- `calls.txt`, every tool call it made, with the failed or refused ones and those that touched a path outside the
  checkout flagged. Criteria 2, 4, 7 and 9 are checked here;
- `transcript.jsonl`, the full event stream.

The script prints the folder and removes the worktree (`--keep` leaves it). The allowlist stops writes; a read outside
the checkout is flagged, not blocked, and the session still runs on this machine and account.

By hand: `git worktree add --detach <fresh path> <commit>`, open that folder in a new window (a new chat in the current
window is not isolated), paste only the block of §2 so the criteria of §3 stay unread, copy the report out, then
`git worktree remove <path>`.

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
4. List what the next step needs (tools, images, baselines, private evidence, the live install) and check whether each
   exists here: "present", "missing by design in a clean clone" or "missing, unexpected".
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
