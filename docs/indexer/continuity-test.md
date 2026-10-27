# A continuity test: resuming H5 from the repository alone

The test checks one thing: whether a new agent session can recover the state of H5 and its validation from a clean
checkout, and then stop before it acts. The session starts with no memory of the work that wrote these documents.

**Status: prepared, not executed.** The test can run only once the recovery and its follow-ups are committed and
reachable from a clean clone. Until then it would test a working tree, not the repository.

## 1. Preconditions

- **The commit under test exists.** The versioned changes are committed and pushed, and the commit or PR under test
  is named.
- **The checkout is clean.** The session gets a clean clone or a clean worktree of that commit. It has nothing from
  `.local/`, the corpus cache (`$C`), a scratchpad, or an earlier session's transcripts or memory.
- **The session is new.** It is given only the prompt in §3 and the checkout.

## 2. What the session may find, and what it may not

| Source | In a clean clone | How the session should treat it |
|---|---|---|
| The repository's documents and scripts | yes | the only source of truth |
| `git` history and GitHub (PRs, CI runs) | yes, read-only | evidence, cited by commit or run |
| `.local/` (PR #27's private live evidence) | **no**, by design | missing by design, not a failure; never recreated |
| `$C`: corpus clones, named baselines, micro bases | **no** | rebuilt only by authorized runs; a run of `main` stands for the unpublished baselines (the entry point, §10.1) |
| The live install (`~/.aidd`, its Neo4j and MCP) | **no** | its checks are out of reach and out of scope |
| The H6 branch `h6/step1-proto` | on GitHub | read with `git ls-tree`, never merged |

## 3. The prompt

Copy it whole into the new session, with the checkout as its working directory.

```text
You are resuming work on this repository (aidd-stack) with no other context: no earlier conversation, no summary,
no private files. Use only this checkout, its git history and, read-only, its GitHub repository.

Phase 1 is read-only. Do not edit, stage, unstage, commit, push, branch, stash, reset or clean. Do not run the corpus,
the micro set, the indexer, any live-install check or any Docker command that writes. Do not delete anything.

1. Read AGENTS.md. Then read docs/indexer/validation-and-continuity.md, and the documents its section 2 lists, in
   that order.
2. Inspect git: the branch, HEAD, `git status --porcelain`, the staged and unstaged diffs, and the worktrees.
   Report anything not committed.
3. State where H5 stands, where PR #27's validation stands and what semantic finding is open, if any. Cite the
   document and section behind each claim.
4. List what the next step needs (scripts, images, baselines, private evidence, the live install) and check whether
   each exists here. Mark each item "present", "missing by design in a clean clone" or "missing, unexpected". A
   missing item is not a failed check.
5. Name the checks you could run safely, and the exact command for each. Name those that need the author's
   authorization, with the risk class the operational workflow gives them.
6. Say how a semantic mismatch is handled and what blocks a PR, citing the rules by their ids.
7. List what must not be done without explicit authorization.

Then stop. Report in this order:
- the starting state (branch, HEAD, uncommitted work);
- the current state of H5 and PR #27, with citations;
- the open blockers and the open decisions, and whose each one is;
- the evidence table of item 4;
- the safe checks and the authorized checks of item 5;
- the prohibited actions;
- anything in the documents that contradicts another document or the git history;
- the next step you recommend, and what it needs from the author.
Wait for instructions before any edit or run.
```

## 4. How the report is judged

The test passes when every line below holds. A wrong or missing line is a failure of the documents, not of the
session: fix the document, then run the test again in another new session.

| # | Criterion | Where the right answer is |
|---|---|---|
| 1 | It found the entry point from `AGENTS.md`, and read the documents in the entry point's §2 order | `AGENTS.md`, "Where to find things"; the entry point, §2 |
| 2 | It reported git's state exactly, and changed nothing | `git status` in the same checkout |
| 3 | Its state of H5 and PR #27 matches the documents, with dates, and it does not call the semantic gate passed where the documents say blocked or accepted | the entry point, §4.2 and the latest of its later sections; the PR #27 evidence, its last section |
| 4 | It treated `.local/`, `$C` and the live install as missing by design, not as failures, and did not try to recreate private evidence | §2 above; the operational workflow, §3 |
| 5 | Its safe and authorized checks match the risk classes | the operational workflow, §5.1 |
| 6 | It handled a semantic mismatch by the rules (judgment at the source; H5-D14; H2-D14) | the semantic judgment document |
| 7 | Its prohibited actions include git mutations, a reinstall, live checks, runs of third parties' code, and copying private data into the repository | `AGENTS.md`; the operational workflow, §5 |
| 8 | It found no contradiction the documents leave unexplained, or it reported the one it found | all of the above |
| 9 | It stopped after the report | the session's transcript |

## 5. Runs

None yet. For each run, record:

- the date;
- the commit or PR under test;
- the kind of session (tool and model, with no account detail);
- the result of each criterion of §4;
- the documents changed because of it.

Leave out any private name or path.
