# H5's validation and continuity: the entry point

> **Start here** to resume H5 safely. This page is an index and a synthesis. It says:
>
> - which document answers which question;
> - where H5 and PR #27 stand;
> - how sure each kind of statement is;
> - what may be lost;
> - what to check before doing anything.
>
> It replaces none of the detailed documents, and repeats none of their procedures.
>
> **Written on 2026-10-26**, on `main` at `0725d47`, after an audit of the seven documents below against the scripts,
> git, GitHub and the local evidence (§6). Nothing was executed to write it. The read-only commands were:
>
> - `git status`, `diff`, `log`, `show`, `ls-tree` and `worktree list`;
> - `gh pr view` and `gh pr checks` (#27), and `gh run view`;
> - listings of `$C`;
> - `docker image inspect`;
> - `shasum -c` on `.local/indexer/pr27/`;
> - reading files.
>
> `$S`, `$C` and `$T` are defined in [the inventory](validation-inventory.md).

## 1. Purpose and scope

H5 refactors the indexer, and step 5 changes its behavior on purpose, language by language. Every change is validated
in layers:

- the tests and their case tables;
- the corpus and the hold-out;
- the micro graph;
- the CI gates;
- a live install, before and after the merge.

The development session that ran H5 until PR #27 could not be continued. Its method had to be recovered from what it
left. These documents record:

- **the recovered method:** the procedures, the tools, the formulas and the rules of judgment;
- **its evidence,** with how sure each part is;
- **the state it left:** PR #27 merged, with its validation after the merge still open;
- **how to go on** without losing evidence or running what should not run.

## 2. The documents, and the question each answers

| Document | The question it answers |
|---|---|
| **This page** | Where do I start, what is the state, and what may I do? |
| [The validation inventory](validation-inventory.md) | Which validation procedures exist (V01–V31), how sure is each, and what is missing or contradictory (§9)? |
| [The resource catalog](resource-catalog.md) | Where does each script and document live, where did it come from, what does it need, and is it safe to version? |
| [The benchmark and statistical protocols](benchmark-and-statistical-protocols.md) | How is each thing measured and compared: the commands, the formulas, the thresholds, and what invalidates a run? |
| [Semantic judgment and regressions](semantic-judgment-and-regressions.md) | How does a difference become a verdict: gains, losses, FP, FN, regressions, and what evidence a verdict needs? |
| [Operational workflow and continuity](operational-workflow-and-continuity.md) | In what order do the phases run, what survives an interruption, and who may run what? |
| [PR #27's validation state](evidence/pr27-validation-state.md) | What ran for PR #27, what it gave, and what is still open? |
| [H5-D18's validation state](evidence/h5-d18-validation-state.md) | What ran for H5-D18, the fix of the wrong edge PR #27 exposed, what it gave, and what is still open? |
| [PR #5's validation plan](evidence/pr5-validation-plan.md) | Where did the two-phase validation, offline then live, come from? |

**The reading order for a newcomer:**

1. this page;
2. the operational workflow, §1 and §5;
3. PR #27's state;
4. the inventory, §1, §3 and §9;
5. the catalog;
6. the benchmark protocols, and semantic judgment, on the procedures the task touches;
7. PR #5's plan, for the origin.

The method's own documents come next: `AGENTS.md`, the H5 handoff, the corpus report and the golden questions.

## 3. How sure each statement is

The documents use one set of evidence terms ([the benchmark protocols](benchmark-and-statistical-protocols.md), §1):

| Term | Meaning | The inventory's class |
|---|---|---|
| **Confirmed** | a versioned file, a CI run, or a read-only check, dated | C |
| **Reconstructed** | an artifact rebuilt from the transcript, not an original file | the catalog's nature "reconstructed" |
| **Partially confirmed** | the implementation exists, but its execution or evidence is incomplete | P |
| **Historical only** | known only from historical notes or outputs | R |
| **Not found, or never recorded** | in no recovered source; or a decision or verdict nobody wrote down | U; the catalog's §5 |

Three claims stay apart: **available, reproducible, executed.** A script in the repository is not a run.

A **re-derivation**, which the catalog calls "reproduced", runs a script again on saved inputs. It checks the script,
and measures nothing again. A **fresh** run measures again, and none was made during the recovery.

Rules carry a label in the later documents:

- **[documented]**: written in a versioned file;
- **[practice]**: done before, but written nowhere as a rule;
- **[recommendation]**: proposed, never used.

## 4. Where things stand on 2026-10-26

### 4.1 The recovery: done, but not committed

| Work | State |
|---|---|
| The inventory, the catalog, the two evidence documents, the four detailed documents and this page | written in `docs/indexer/` |
| 38 files under `indexer/scripts/{checks,judgment,live,probes,protocol,recovery}/`: 37 scripts and an example calls file, each with its provenance in the catalog | written |
| The scripts' README and `.gitignore`'s `/.local/` rule | edited |
| PR #27's private live data | copied to `.local/indexer/pr27/` on 2026-10-24; 89 of 89 hashes OK on 2026-10-26 |

**None of it is committed or pushed.** The earlier files are staged, and the later edits are unstaged or untracked
until the author stages them; `git status` gives the current split. The recovery exists only on this disk (§7).
**Later on 2026-10-26:** the documents, the 38 files, the README and `.gitignore` were committed as `21f9670`, signed,
on `docs/h5-validation-recovery` and on the local `main`. It is not pushed and no PR holds it, so it still exists only
on this disk (§13). `.local/` stays out of git by design.

### 4.2 PR #27: five kinds of status

PR #27 is merged, and its live validation after the merge passed later on 2026-10-26 (§11). **Its record is not
complete: the eleventh golden round and the line in `docs/history.md` are still unwritten. H5 is not done either.**
**Later on 2026-10-26:** both were written in the working tree, not yet committed (§13).

| Kind | What |
|---|---|
| **1. Historical PR and CI facts** (confirmed on 2026-10-26 with `gh`) | merged on 2026-10-24 at 06:34:33 UTC as `0725d47`, with the `graph-change` label and 31 commits; checks `changes`, `tests`, `shape`, `corpus`, `micro` and `gates` all passing; the push to `main`, run `40070748413`, successful |
| **2. Recovered and verified artifacts** | the before picture, the golden answers, the dry-runs, the pre-merge logs and the golden calls in `.local/indexer/pr27/` (hashes OK on 2026-10-26; the manifest matched on 2026-10-24); PR #27's micro runs in `$C/micro-fresh` (85 entries `csn-n*`); the persisted scripts; three re-derivations on 2026-10-24: `chain_diff.py`'s counts, `dry_sections.py`'s and `graph_vs_dry.py`'s pre-merge outputs. **On 2026-10-26** (§10): the same three again, the last two from the local copies; the dry-runs identical record by record in every list; `main` against the baselines and its micro base, all identical |
| **3. Documented, not executed again** | the protocol on each of the 17 fix commits; the micro judgment by case on seeded samples; the timing alone; the read-only live check before the merge. Their results are in [the evidence](evidence/pr27-validation-state.md), §2 to §5 |
| **4. Pending** | the eleventh golden round and PR #27's line in `docs/history.md`, in a docs PR (no PR after #27 exists); `install-check.sh`'s output of 2026-10-24. Done on 2026-10-26: the micro base for `main`; the ROADMAP's and the H5 handoff's state, corrected in the working tree, uncommitted. **Done later that day:** the after picture, the golden answers after and the before/after comparisons, which pass (§11). They had been blocked since the reboot by the install's Neo4j looping on restart, until the author recreated the container. The table, with each item's risk class, is in [the operational workflow](operational-workflow-and-continuity.md), §5.3 |
| **5. Not reconfirmed** | whether `install-check.sh` passed on 2026-10-24. On 2026-10-26 it failed on the Neo4j loop, and passed after the container was recreated. The live graph's build and freshness, and that the install's code equals `main`'s, were reconfirmed later on 2026-10-26 (§11) |

**A claim that disagrees with the artifacts.** PR #27's body ticks "After the merge: the graph's picture after, and
the eleventh golden round". Neither exists (the inventory's contradiction 10). The PR was left as it is. Later on
2026-10-26 the picture after was taken; the eleventh round still does not exist.

## 5. Coverage matrix

The status column uses the terms of §3. "Detailed in" points at a document and its section.

| Area | Inventory ids | Canonical implementation or evidence | Detailed in | Status | Open gap or prerequisite |
|---|---|---|---|---|---|
| Corpus and hold-out | V01–V04, V07 | [`corpus.sh`](../../indexer/scripts/corpus.sh), [`http_corpus.py`](../../indexer/scripts/http_corpus.py), [`corpus_metrics.py`](../../indexer/scripts/corpus_metrics.py); baselines `-29`, `-26` in `$C` | benchmark §4.1, §6 | Confirmed (CI on PR #27; local runs historical) | baselines unpublished (H4.1-D1); the hold-out's lists are public (H4.1-D2) |
| Gates and offline checks | V08, V09, V27 | [`gates.py`](../../indexer/scripts/gates.py); [`checks/a2_gabaritos.py`](../../indexer/scripts/checks/a2_gabaritos.py), [`a4_compare.py`](../../indexer/scripts/checks/a4_compare.py), [`a5_chain.py`](../../indexer/scripts/checks/a5_chain.py) | benchmark §4.2, §5.5; semantic §5.3 | Confirmed (gates); Reconstructed (A2, A4, A5, not run since 2026-10-19) | the gates "one cause per commit" and "every item judged" are not built (H7 slice 2) |
| The micro graph and its baselines | V10, V03 | [`micro.sh`](../../indexer/scripts/micro.sh), [`micro.py`](../../indexer/scripts/micro.py), [`protocol/micro-fresh.sh`](../../indexer/scripts/protocol/micro-fresh.sh); bases in `$C/micro` | benchmark §4.3, §5.6 | Confirmed (CI); `micro-fresh.sh` ran from the repository on 2026-10-26 | a base for `main`'s tree and the current image exists since 2026-10-26; three base conventions (contradiction 8); `micro-fresh.sh`'s containers carry no label |
| The protocol per commit | V13 | [`protocol/protocol.sh`](../../indexer/scripts/protocol/protocol.sh) | benchmark §4.4; operational §2 | Partially confirmed (adapted; never run from the repository) | the micro base; one protocol at a time |
| The micro judgment and the extension-loss analysis | V11, V12 | [`judgment/chain_diff.py`](../../indexer/scripts/judgment/chain_diff.py), [`ext_loss.py`](../../indexer/scripts/judgment/ext_loss.py), [`lost_ext.py`](../../indexer/scripts/judgment/lost_ext.py), the `ext_*.py` | benchmark §4.5, §4.6, §5.7, §5.8; semantic §3, §6 | Partially confirmed (counts re-derived again on 2026-10-26) | the past judged samples lost for good; new samples reproduce since the sorting fix of 2026-10-26; `why_a.py` missing; the scripts' definitions differ |
| Structural graph comparisons | V10, V21, V23 | `micro.py`; [`live/graph_vs_dry.py`](../../indexer/scripts/live/graph_vs_dry.py); [`live/foto.sh`](../../indexer/scripts/live/foto.sh) and typed commands | benchmark §4.10, §4.11, §5.9 | Partially confirmed | no script for the picture's 14 other lists; `go_graph_diff.py` not persisted |
| Semantic judgments and regressions | V05, V09, V11, V12, V25 | the expected lists' `checked` verdicts; the case tables; the fixtures; the handoffs' and PR bodies' results | semantic | Confirmed (rules, lists, cases); **not recorded** (diff verdicts, judged samples) | H7-D2, the verdict format, undecided |
| The live dry-run comparison | V21, V22 | [`live/dryrun-live.sh`](../../indexer/scripts/live/dryrun-live.sh), [`dry_sections.py`](../../indexer/scripts/live/dry_sections.py), [`dry_compare.py`](../../indexer/scripts/live/dry_compare.py), [`pre-merge.sh`](../../indexer/scripts/live/pre-merge.sh) | benchmark §4.10; operational §2 | Partially confirmed (historical runs; two re-derived; PR #27's dry-runs identical record by record on 2026-10-26) | `dry_sections.py` keyed endpoints by a missing field until 2026-10-26; `graph_vs_dry.py` exited 0 on a mismatch until then; `live-check.sh` never built |
| H6's procedures | V18 | `h6/step1-proto:indexer/scripts/h6-step1/` (16 scripts, `results/`) | benchmark §4.8; operational §6 | Partially confirmed (on the branch only) | the image not identified; never to merge; not `main`'s numbers |
| PR #27's before and after | V21, V23, V25 | `.local/indexer/pr27/`; [the PR #27 evidence](evidence/pr27-validation-state.md) | the evidence; operational §5.3 | the before side preserved and verified; the after side taken on 2026-10-26, and it passes | the eleventh round unwritten (§4.2, kind 4) |
| Time | V17 | [`protocol/time-alone.sh`](../../indexer/scripts/protocol/time-alone.sh) | benchmark §4.7, §5.10 | Partially confirmed (one run per side) | the median of 3 not practiced (contradiction 9) |
| Historical equivalence checks | V19 | [`checks/dump.py`](../../indexer/scripts/checks/dump.py), [`checks/walkcmp.py`](../../indexer/scripts/checks/walkcmp.py) | benchmark §4.9 | Historical only; the scripts Reconstructed | Go's facts, `tools/list`'s and the ASTs' checks not found |
| Tests, shape, the writer, CI | V06, V15, V16, V20, V26 | [`test.sh`](../../indexer/scripts/test.sh), [`shape.py`](../../indexer/scripts/shape.py), [`mcp-it.sh`](../../indexer/scripts/mcp-it.sh), [`indexer.yml`](../../.github/workflows/indexer.yml) | inventory | Confirmed | H7's slices 1b and 2 to 6 open |
| Continuity and recovery | V29, V30, V31 | [`recovery/recover.py`](../../indexer/scripts/recovery/recover.py), [`heredoc.py`](../../indexer/scripts/recovery/heredoc.py); `.local/`; `$C` | operational §3, §4 | Partially confirmed | no backup; the recovery uncommitted (committed later that day as `21f9670`, not pushed); an untagged image (§7) |

The classes agree across the documents. The inventory counts 13 Confirmed, 16 Partially confirmed and 2 Historical
only, and the benchmark protocols' overview gives each procedure the same class.

## 6. The audit of 2026-10-26

### 6.1 What was checked, and how

| Check | Method | Result |
|---|---|---|
| Scripts said to exist | every script path the seven documents name (208), against the tree, the H6 branch and the catalog's §4 and §5 | 121 in `indexer/scripts/`. Of the other 87: 37 in other folders of the repository, 17 only on `h6/step1-proto`, and 33 recorded as not persisted, renamed, not found or never built. **None unexplained** |
| Scripts present but undocumented | each file of the six local folders against the catalog | 38 of 38 in the catalog |
| Counts quoted | listings | 29 Python files ✓; H6's 16 scripts ✓; "38 scripts" **corrected** to 38 files, 37 scripts and an example |
| Cross-references between the documents | every `§N` reference to another document (90) | all resolve; one self-reference made explicit |
| Relative links | every link of the eight documents | none broken (§9) |
| Machine-specific paths | a search for user paths and ids | a scratchpad path with the local user's id, in the inventory and the catalog: **corrected** to `claude-<uid>` |
| Private names | the snapshot list and the golden calls of `.local`, against every document (counts only) | none. Some hits were common English words that happen to equal a snapshot's name, used with their ordinary meaning |
| Statements in the present tense about `$S` | a search | five said files "are in" `$S`, or were "still volatile" there, though a reboot emptied it on 2026-10-26: **corrected** in the inventory (2), the catalog (2) and the PR #27 evidence (1) |
| A dated check presented as current | reading | the inventory's "Confirmed now" (2026-10-24) said the working tree was clean: **dated**. The live build is dated in every document |
| A structural difference called a confirmed regression | reading | none found |
| A PR checklist against its artifacts | `gh pr view` | PR #27's ticked after-merge item: recorded, not edited (contradiction 10) |
| H6 numbers attributed to `main` | reading | none found |
| Terms | reading | the catalog's "reproduced" is the later documents' "re-derived": **mapped** in the catalog |
| The inventory's contradiction 6 (`test_mcp_neo4j.py`, "14 cases" against 12 functions) | a static count at three commits | **resolved:** 14 cases at `849b2cd`, 15 since `7268642`. This is a count by reading, not a pytest collection |

### 6.2 What stays unresolved

Each was left as recorded. The evidence for it, and what is unknown, are in the place cited.

| Claim in conflict | Best evidence | Unknown | Where |
|---|---|---|---|
| The ROADMAP and the handoff said PR #27 "goes to review" | merged, per GitHub | — : corrected in the working tree on 2026-10-26, uncommitted | inventory §9, 1 |
| The guide's §5 and §6 are out of date | the code at `HEAD` | — (H4 phase 0b) | inventory §9, 2 |
| H5-D14 and PR #25's body say "per case and repo"; the tool sampled per kind | the tool's code | whether any C# sample was ever drawn per case | inventory §9, 3; semantic §6 |
| H5's protocol names 12 repos; step 5 judged 23 or 25 | the evidence documents | — | inventory §9, 4 |
| Summed and wall times mixed; the median of 3 against single runs | the corpus report; the evidence | the run-to-run range of single runs | inventory §9, 5, 9 |
| H7's planned gates against `gates.py`'s five | the code | — (H7 slice 2) | inventory §9, 7 |
| Three conventions for the micro base | the scripts | which to use when: a decision | inventory §9, 8 |
| PR #27's body ticks an undone item | the artifacts are absent | — | inventory §9, 10 |
| The golden rounds 9 and 10 say "identical in every section" | `dry_compare.py` for PR #23; `dry_sections.py` for #27 | which tool PR #25 used | semantic §6 |
| The H6 README's `evaluate.py --typed-only` | the code reads no such flag | how `replay-eval-typed.txt` was made | benchmark §4.8 |
| PR #27's run n1 is `f043452` | inferred: its line holds no sha | the sha | the PR #27 evidence, §2 |

## 7. Continuity risks, and decisions still open

These are risks, not actions. **Each remedy, whether a backup, a commit, a push, a tag or a cleanup, needs its own
authorization.**

| Risk | Evidence on 2026-10-26 |
|---|---|
| **The recovery is uncommitted.** The documents and the 38 files exist only in this working tree and its index. A lost disk loses them, and so would any operation that discards the index or the working tree. **Later on 2026-10-26:** committed as `21f9670`, not pushed. A lost disk still loses it | `git status`: staged, plus later unstaged and untracked edits; no commit after `0725d47` |
| **PR #27's private evidence has one copy.** `.local/indexer/pr27/` survived the reboot of 2026-10-26, but a file that survives a reboot on one disk is not a backup. **No independent backup is confirmed,** of it or of anything else outside GitHub | `shasum -c`: 89 of 89; no other copy checked |
| **The before picture cannot be retaken.** The graph no longer holds `main`'s build of 2026-10-23 | the reinstall of 2026-10-24 |
| **The images behind the micro bases are untagged.** `927f5b4115c5` is still present, but a prune would remove it. Later on 2026-10-26, `f07550cbe2e2`, the image of the base made that day, lost its tag to a twin with the same layers (§11) | `docker image inspect`, 2026-10-26 |
| **`$C`, the transcripts and the agent's memory** are on this disk only. `$C/micro-fresh` (6.9 GB) holds the inputs of every re-derivation | listings |
| **Missing scripts:** `why_a.py` (only in part in `$T`), `live-check.sh` (never built), a before/after comparator (only typed commands) | the catalog, §4 and §5 |
| **Unreproducible past samples:** they were drawn in a set's order; since 2026-10-26 the draw is sorted, so new samples reproduce, but the past ones are lost | the benchmark protocols, §8, gap 6 |
| **The live install was down:** its Neo4j looped on restart after the reboot of 2026-10-26, and no live step could run. **Resolved later that day:** the author recreated the container, the volume kept the graph, and `install-check.sh` passes | §10, §11 |
| **Judgments never recorded item by item:** the diff verdicts, the micro and loss samples, the live differences | semantic §5.1, §9 |
| **A scratchpad is not storage.** Two reboots emptied one | the inventory, the header |

**Decisions still open,** each the author's:

- a backup of `.local/indexer/pr27/`;
- how to commit the recovery, and through which PR;
- the retention of `$C/micro-fresh`, the transcripts and the untagged image;
- whether to persist the reconstructable tools of the catalog's §4;
- H7-D2, how verdicts are recorded;
- when, and by whom, PR #27's docs PR is written: the eleventh round and the history line.

## 8. A safe resumption checklist — **[recommendation]**

Steps 1 to 6 only read. Steps 7 and 8 need an authorization for each risk class
([the operational workflow](operational-workflow-and-continuity.md), §5.1). The longer version, with the commands, is
the operational workflow's §8.

1. **Read only:** check git's state, and change nothing in it: `git status --porcelain`, `git diff --cached --stat`,
   `git branch --show-current`, `git log --oneline -1`, `git worktree list`. Staged and unstaged files are work in
   progress: leave them as found.
2. **Read only:** read this page, then the documents in §2's order.
3. **Read only:** check that what the task needs exists: the scripts by their catalog paths; the baselines in `$C`;
   for an H6 script, the branch, with `git ls-tree`.
4. **Read only:** pin the versions: the code tree (`git rev-parse <ref>:indexer/aidd_indexer`), the image's id, and
   whether a micro base exists for that pair.
5. **Read only:** find the private local evidence, and check it without opening it into anything shared: `shasum -a 256
   -c SHA256SUMS` inside `.local/indexer/pr27/`. Never copy its contents into the repository or a PR.
6. **Read only:** review PR #27's pending steps (§4.2), and confirm each is still pending.
7. **With authorization:** separate the task's documentation from its execution, and ask for each class: offline
   analysis, corpus and indexer runs, live checks, remote changes. Inspection or documentation is never permission to
   run.
8. **With the author's approval:** record new findings with their provenance, and change a handoff, the ROADMAP or a
   history line only when the evidence supports it, through commits and a PR the author approves.

## 9. Canonical scripts and evidence

- **The method's CI scripts:** [`corpus.sh`](../../indexer/scripts/corpus.sh),
  [`micro.sh`](../../indexer/scripts/micro.sh), [`gates.sh`](../../indexer/scripts/gates.sh),
  [`shape.py`](../../indexer/scripts/shape.py), [`test.sh`](../../indexer/scripts/test.sh),
  [`mcp-it.sh`](../../indexer/scripts/mcp-it.sh), and [their README](../../indexer/scripts/README.md).
- **The local tools:** [`protocol/`](../../indexer/scripts/protocol/), [`judgment/`](../../indexer/scripts/judgment/),
  [`checks/`](../../indexer/scripts/checks/), [`probes/`](../../indexer/scripts/probes/),
  [`live/`](../../indexer/scripts/live/), [`recovery/`](../../indexer/scripts/recovery/).
- **The evidence:**
  - [PR #27's validation state](evidence/pr27-validation-state.md);
  - [PR #5's validation plan](evidence/pr5-validation-plan.md);
  - the expected lists, in [`corpus_expected/`](../../indexer/tests/corpus_expected/);
  - the [golden questions](../golden-questions.md);
  - the [corpus report](../corpus-report.md).
- **The method:**
  - [`AGENTS.md`](../../AGENTS.md);
  - the [H5](../handoffs/H5-indexer-refactor.md), [H6](../handoffs/H6-extraction-pipeline.md) and
    [H7](../handoffs/H7-regression-gates.md) handoffs;
  - the [decisions](../decisions.md);
  - the [ROADMAP](../ROADMAP.md);
  - the [history](../history.md).
- **Outside the repository:**
  - `h6/step1-proto` and the draft release `h6-step1-results`;
  - `$C`;
  - the transcripts;
  - `.local/indexer/pr27/`, private, local and with no backup.

## 10. The process audit of 2026-10-26, after running it

The author authorized four kinds of run: offline analyses of saved data, the indexer in Docker, read-only live
checks, and `install-check.sh`. The documents were then checked against what the scripts did, and against the
evidence. The runs and their results are in [the PR #27 evidence](evidence/pr27-validation-state.md), §8, and each
script's audit is in [the catalog](resource-catalog.md), §8.

### 10.1 Four separate verdicts

| Dimension | Verdict | Evidence |
|---|---|---|
| **Runtime correctness of `main`** | consistent with the baselines offline; **not verified on the live install**. Later that day, verified there too (§11) | corpus `0 repo(s) differ` against `-29`, hold-out `0` against `-26`, micro identical to `main`'s base; CI green on PR #27; the live after side blocked. Later: the after picture and answers as the dry-runs said |
| **The validation process's correctness** | **five defects found,** that could give a false pass or a judgment no one can re-check; all five fixed and verified; three behaviors documented rather than changed | `graph_vs_dry.py` and `golden.py` exited 0 on failure; `dry_sections.py` keyed endpoints by a missing field; `chain_diff.py` and `ext_judge.py` drew samples in a set's order. Documented: `dryrun-live.sh` exits 0 whatever its runs give; `pre-merge.sh` returns its last step's code; `micro-fresh.sh`'s containers carry no label |
| **Documentation fidelity** | the documents matched what ran, with six corrections | the image build a fork can use; the containers' labels; the scope of "identical"; `golden.py` "never run"; the samples; PR #27's stale state in the ROADMAP and the handoff |
| **Continuity readiness** | **ready on this machine for the offline work; not ready from a fresh clone** | §10.3 |

Passing the runtime checks does not make the process reproducible. Reproducible scripts do not make a judgment right.
Complete documents do not make the code right.

### 10.2 The documents and procedures, audited

**The columns:**

- "Provenance" is the catalog's nature.
- "Fidelity" compares the artifact with the historical practice.
- "Fork" says whether a fresh clone, with Docker and the network and no private data, can use or run it.
- "Done" means the remediation was made and verified.

| Artifact or procedure | Purpose | Provenance | Evidence | Status on 2026-10-26 | Fidelity | Fork | Defects or missing knowledge | Remediation | Done |
|---|---|---|---|---|---|---|---|---|---|
| This page | the entry point | newly authored | the audit above | current | — | once committed | — | `AGENTS.md` now points to it | yes, uncommitted |
| [The inventory](validation-inventory.md) | procedures, evidence, gaps | newly authored, derived | its §2 sources | corrected | its R items rest on `$T` | once committed | R claims that no one can re-run | dated, corrected, gaps 10 and 11 added | yes |
| [The catalog](resource-catalog.md) | provenance | newly authored | git, hashes, `$T` | §8 added | — | once committed | — | the script audit | yes |
| [The benchmark protocols](benchmark-and-statistical-protocols.md) | how things are measured | newly authored | the code, `$T`'s commands | corrected | its commands are the ones that ran | the offline part | the fork's image build | passages on the fixed scripts and the build | yes |
| [Semantic judgment](semantic-judgment-and-regressions.md) | how a verdict is made | newly authored | the docs, the code, PR bodies | tried on five items | keeps the sources' terms | with the public clones | the verdict format (H7-D2) is undecided | §4.6 added | yes |
| [The operational workflow](operational-workflow-and-continuity.md) | the order, continuity, authorizations | newly authored | the scripts, the practice | corrected | — | yes | the containers' labels; the Neo4j loop after a reboot | both written down | yes |
| [PR #27's evidence](evidence/pr27-validation-state.md) | what ran for PR #27 | derived from `$S`, now gone | the summaries, CI | §8 added | — | as history | the judged samples lost | — | — |
| [PR #5's plan](evidence/pr5-validation-plan.md) | the method's origin | reconstructed, translated | `$T` | unchanged | the plan's items kept | as history | — | — | — |
| `AGENTS.md`, the scripts' README, the ROADMAP, the H5 handoff | the repository's entry points | versioned | git | edited | — | once committed | no pointer to `docs/indexer/`; the compose build needs `.env`; PR #27's state stale | a pointer, the fork's build, the state | yes, uncommitted |
| V07, V04: corpus and hold-out | the HTTP items against the baselines | original (CI) | the runs of 2026-10-26 | `0 repo(s) differ` on both | as practiced | yes; a run of `0725d47` stands for the unpublished baselines | — | — | — |
| V10, V13: micro, `micro-fresh.sh`, `protocol.sh` | the micro graph, per commit | original; adapted | the runs of 2026-10-26 | identical; the base made | as practiced | yes | unlabelled containers; three base conventions | documented | yes |
| V11: `chain_diff.py` | changed edges by kind and class | adapted | runs before and after the fix | counts equal the history | yes, for the counts | yes | the samples were not reproducible | sorted draw | yes |
| V12: the loss scripts | lost extension edges | original; adapted | `ext_judge.py`'s runs | as documented | yes | yes | definitions differ; key order in `ext_loss.py`'s output | `ext_judge.py`'s draw sorted; the rest documented | partly |
| V21: `graph_vs_dry.py` | the graph against the dry-runs | adapted | re-derived; synthetic | as documented | yes | given pictures | exit code | exit 1 on a mismatch | yes |
| V22: `dry_sections.py`, `dryrun-live.sh` | the live dry-runs | adapted; original | re-derived; synthetic; a full comparison | PR #27's dry-runs identical | yes | no (private install) | a key field that does not exist; `dryrun-live.sh`'s exit code; its workspace layout | the key fixed; the rest documented | partly |
| V23: `foto.sh` and the comparison | the picture before and after | original; typed commands | — | **blocked**; later that day, run: identical but for the build and `IndexRun` (§11) | as practiced | no | no script for 14 lists | — | yes, later |
| V25: `golden.py` | the golden calls | new (a rewrite) | a local stand-in; a closed port; later, the live MCP | logic equal to the original's; live, 22 of 27 identical, 5 in time and build fields | yes | no (private calls) | exit code | exit 1 when a call never reached the MCP | yes |
| V24: `install-check.sh` | the install's health | original, versioned | a run; later, a second | **FAIL**, from the Neo4j loop; after the recreation, "All checks passed" | — | no | the output of 2026-10-24 unknown | the author recreated the container | yes, later |
| V19: `dump.py`, `walkcmp.py` | equivalence of a representation | reconstructed | `$T` | not run | — | yes | Go's and the other checks not found | — | — |
| V18: H6's scripts | the pipeline's design | on the branch | the branch's results | not run | — | partly | the image not identified | — | — |
| V29: `recover.py`, `heredoc.py` | rebuilding lost files | original; adapted | runs of 2026-10-24 and 2026-10-26 | — | — | **no:** the transcripts are not in the repository | — | — | — |

### 10.3 The fresh-fork handoff, audited statically

**The setup:** a contributor or an agent starts from the committed repository alone, with no conversation, no
`.local/`, no `$C`, no transcripts and no agent memory. Nothing was deleted or reset to simulate this. The audit reads
what a clone holds, and what each instruction needs.

| What they need | From a fresh clone | Gap |
|---|---|---|
| The entry point | `AGENTS.md` → this page | **none of `docs/indexer/` and none of the local tools is committed yet.** Until the author commits them, a clone has neither this page nor the pointer to it. **Later on 2026-10-26:** committed as `21f9670`, not pushed, so a clone of GitHub still has neither |
| The project's state, and where H5 stands | the ROADMAP and the H5 handoff | their correction for PR #27 is uncommitted too. **Later on 2026-10-26:** committed in `21f9670`, not pushed |
| The decisions and their reasons | `docs/decisions.md`, the ADRs, the handoffs | none found |
| The procedures and their acceptance criteria | `AGENTS.md`, the scripts' README, `docs/indexer/` | once committed |
| Telling confirmed from reconstructed or proposed | the evidence terms (§3) and the labels | once committed |
| The environment, with no private path | Docker; the image built as CI builds it; the pinned public clones; `micro.sh --base-only` for a micro base | the named baselines are on one disk: a run of `0725d47` reproduces them item for item (§10.1). The scripts' error message points at `docker compose build`, which needs a private `.env` |
| Running a validation and keeping its evidence | the offline layers: tests, corpus, hold-out, micro, gates, judgment scripts | **the live layer needs the private install and the private calls file.** No public stand-in exists: the demo tenant (H4.1-D4, H7 slice 4) is not built |
| Judging a change | semantic judgment, with the public clones | the verdict format is undecided (H7-D2) |
| Knowing what cannot be reproduced, and why | the catalog's §4 and §5, the benchmark protocols' §8 | none |
| The next step | §10.4 | none |

**Knowledge that lives only on this machine:**

- **PR #27's before side,** in `.local/indexer/pr27/`. It cannot be versioned, since it is private, nor retaken,
  since the graph has moved on.
- **The runs in `$C`,** among them the inputs of every re-derivation.
- **The transcripts,** which hold the reconstructable tools of the catalog's §4 and the commands not quoted here.
- **The untagged image.**
- **The live install itself.**

The agent's memory holds operating rules: the approvals, that the live install is read-only for the agent, and that
only the author reinstalls. These now also stand in the operational workflow's §5.

### 10.4 The next steps, in the order their dependencies impose

1. **The author commits the recovery,** in commits and a PR they choose. Every later step, for anyone but this
   session, depends on it. **Committed later on 2026-10-26** as `21f9670`; its push and PR are still to come.
2. **The author repairs the install's Neo4j,** for instance by recreating its container (the graph is in the
   `neo4j_data` volume), then checks `install-check.sh` until it passes. **Done later on 2026-10-26** (§11).
3. **With authorization, PR #27's after side:**
   - the picture;
   - the golden answers;
   - the comparisons with the before side, where identical is expected but for the build and `IndexRun`.

   **Done later on 2026-10-26, and it passes** (§11). Left: the eleventh round and the `history.md` line, in a docs
   PR.
4. **The author decides on the new wrong edge** of §8 of the PR #27 evidence: a case for a later PR, or a gap left as
   it is. **Decided later that day:** H5-D18 (§12).
5. **A backup of `.local/indexer/pr27/`,** at least until the eleventh round is written: it holds the only before
   side, and now the after side too.
6. **Then H5 step 5 for Python** (the ROADMAP), with the protocol on each commit. The micro base made on 2026-10-26
   serves while the image stays `f07550cbe2e2`. The tag has since moved to `9e6dd3753826` (§11), so the next
   `micro.sh` makes a new base first.

## 11. PR #27's after side, later on 2026-10-26

The author deleted and recreated the install's Neo4j container, and asked for the blocked steps to be resumed. They
ran read-only, and every one passes by the inventory's criteria. The numbers are in
[the PR #27 evidence](evidence/pr27-validation-state.md), §9, and the private outputs in `.local/indexer/pr27/after/`
and `post-merge-2026-10-26/`.

| Validation | Result | Kind |
|---|---|---|
| The data survived the recreation | `atlas` online and the default; 10 snapshots; 16,030 nodes, which is the before picture's 16,020 plus one `IndexRun` per snapshot | fresh, read-only |
| V24: the install | `install-check.sh` rc 0, "All checks passed". The code equals `main`'s. Each snapshot was re-indexed once, on 2026-10-24, and 10 refresher cycles have changed none since | fresh, read-only |
| V23: the picture after | 13 of 15 lists byte-identical. `snapshots` differs only in the build, at the same 10 shas, and `labels` in one `IndexRun` per snapshot | fresh, read-only |
| V21: the graph against the dry-runs | `graph_vs_dry.py`: before holds `main`'s dry-run and after holds the branch's on all 10 snapshots; "mismatching snapshots: 0" | fresh, read-only |
| V25: the golden answers after | 27 of 27 calls reached the MCP. 22 are byte for byte the same, and the other 5 differ only in time and build fields. The write is refused, and no snapshot is `outdated` | fresh, read-only |

**What it does not change:**

- PR #27's live graph equals the before one, but for the build, because these snapshots' code has none of the calls
  the change reaches. This checks the install, not the change. The change was judged on the corpus.
- The eleventh round and the `history.md` line are still unwritten; they go in a docs PR. **Later that day:** written
  in the working tree (§13).
- §8's new wrong edge still waits for the author. **Later that day:** its fix is H5-D18 (§12).
- `install-check.sh`'s output of 2026-10-24 stays unknown.

**One operational change was found.** The tag `aidd-indexer:local` now names `9e6dd3753826`, not `f07550cbe2e2`.
Both images were built at the same second from the same layers, and they differ only in compose's service label. How
the tag moved is not known. `micro.sh` keys its base by the tagged image's id, so it will make a new base on its next
run.

## 12. H5-D18, later on 2026-10-26

The wrong edge of [the PR #27 evidence](evidence/pr27-validation-state.md), §8 and §10, has a fix: H5-D18, decided by
the author, implemented in the working tree and not committed. Its record is
[H5-D18's evidence](evidence/h5-d18-validation-state.md); the live outputs are in a folder outside the repository.

| Validation | Result | Kind |
|---|---|---|
| The tests, `mcp-it.sh` and the shape ratchet | all pass; "0 new or worse over a target" | fresh |
| The corpus and the hold-out | 0 repos differ from `-29` and from `-26` | fresh |
| The micro graph, 23 repos | 17 identical; 6 C# repos differ, −815 and +97 edges. The real diff equals the diagnosis's measure item for item. Each class read at the source, with no right edge found lost, by the agent that wrote the change: a proposal for the author's review | fresh |
| V21, V22, V25: the live check before a merge | the two codes' dry-runs identical on all 10 snapshots; the graph holds `main`'s; the picture equals PR #27's after one; the 27 calls of a recovered list answer as expected, with 22 inferred, not compared, against the eleventh round. An unplanned early run of the same calls happened (its evidence, §7) | fresh, read-only |

**On 2026-10-27,** an AI agent independent of the change, not a person, judged a seeded sample of 189 items by
reading the source. Nothing was compiled.

- It found no wrong item among the 106 changed edges. Among `main`'s untouched edges it found 15 inherited wrong
  ones, each traced to its cause.
- The author accepted it that day as complementary engineering evidence. It is not a human review, so the method's
  check by a person is not literally met.
- Two groups of inherited defects, `EvaluateAsync` and `List<T>.AsReadOnly()`, are non-blocking debt candidates for
  F1.2, by the author's decision. The other ten are not classified as non-blocking: seven fall under H5-D16 or
  H5-D17, and three are unresolved.
- These decisions are recorded in [the decisions](../decisions.md), H5-D18.
- The count of type arguments is a separate follow-up, kept out of H5-D18.

They are in its evidence, §5.3, §6.2, §6.4 and §8.

**What it does not change:**

- **The semantic gate stays open** until the criteria of its evidence, §8, are met. Nothing is committed, and nothing
  merged.
- The live snapshots hold none of the calls H5-D18 reaches, so the live check shows the install, not the change.
- What H5-D18 inherits from `main`, and what it leaves out, is in its evidence, §6.

## 13. What changed after §4 to §11, later on 2026-10-26

§4 to §11 record what held when they were written. They stay as they were, but for "Later" pointers in §4.1, §4.2,
§5, §7, §10.3, §10.4 and §11.

**The recovery is committed:** `21f9670`, signed, on 2026-10-26 at 16:18.

- It is on `docs/h5-validation-recovery`, and on the local `main`, which is one commit ahead of `origin/main`.
- It is not pushed, and no PR holds it.

**Since then, in the working tree, not yet committed:**

- **The eleventh golden round** is written in [the golden questions](../golden-questions.md), and **PR #27's line** in
  `docs/history.md`. The ROADMAP's and the H5 handoff's states say so.
- **§8's wrong edge** of the PR #27 evidence has a fix, H5-D18 (§12), which is not merged and not accepted.
- **Other documents** still say the eleventh round is unwritten: the inventory, the operational workflow, the benchmark
  protocols, the semantic judgment and the PR #27 evidence, §7. They are records of 2026-10-26 too, and are left as
  they were.
- **The twelfth golden round** records H5-D18's live check before a merge.
- **A continuity test** is prepared, not executed: [continuity-test.md](continuity-test.md).
  - It can run only from a clean clone, once the recovery and its follow-ups are pushed.
  - It is left out of §2's reading list, because a session under test should not read the criteria it is judged by.
