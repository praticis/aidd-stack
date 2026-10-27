# Resume test: can a new session continue from the repository alone

The test checks one thing: whether a session with no memory of the work recovers where H5 stands and what comes next
from a clean checkout, and then stops before it acts.

**Status: prepared, not executed.** It can run only on a clean clone of a commit that is pushed; until then it would
test a working tree, not the repository.

## 1. Preconditions

- The commit under test is pushed and named.
- The session gets a clean clone or worktree of it, with nothing from `.local/`, `~/.cache/aidd-corpus`, a
  scratchpad, or an earlier session's transcripts or memory.
- The session is new and is given only the prompt below.
- Missing by design, and not a failure: `.local/`, the corpus cache, the live install.

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

None yet. Record, for each: the date, the commit under test, the kind of session (tool and model, no account detail),
the result of each criterion, and the documents changed because of it. Leave out any private name or path.
