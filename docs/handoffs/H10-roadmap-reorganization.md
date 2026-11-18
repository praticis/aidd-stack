# Handoff H10 — Reorganize the roadmap

> Paste this file (or ask for `docs/handoffs/H10-roadmap-reorganization.md` to be read) at the start of a new chat. Before
> anything else, the chat should read, in this order:
> - `AGENTS.md`, the entry point;
> - `docs/ROADMAP.md`, whole;
> - `docs/handoffs/`: the list, and the opening of H5 and H8;
> - `docs/decisions.md`, `docs/history.md` and the rules at the top of `docs/tech-debt.md`;
> - `docs/indexer/README.md` and `docs/indexer/resume-test.md`;
> - `docs/indexer/method.md` §4.17, `indexer/scripts/checks/docs_ceilings.txt` and `docs_size.py`, and
>   `indexer/scripts/debts.py`.
>
> The author has a **private appendix** for this handoff, with material that cannot live in a public repository. Ask for
> it before planning, and do not copy any line of it into `docs/`, a PR or an issue.
>
> **State (2026-11-18):** judged. The plan it asked for lives outside the repository, with the private appendix, and
> runs as ten pull requests; until the last one merges, no other pull request enters `main`. What it waits for is in
> `docs/handoffs/README.md`.

## What is asked

1. The author organized another, larger roadmap with a structure he liked a lot: items with a fixed shape, a map, a script
   that checks them, execution cards whose state can be resumed, and an index of handoffs with states. He sees it as the
   **evolution of concepts that exist here mixed together** (section 4).
2. He wants this chat to **understand that structure** (section 3), **see what this repository has today** (section 4) and
   **propose how to reorganize `docs/ROADMAP.md`** (section 5), taking him the decisions that are his (section 6).
   **The reorganized roadmap is the roadmap of the Atlas only** (section 1): two of its tracks leave it, and the work of
   taking the other pieces out of this repository enters it as items.
3. The proposal **keeps what already works** here (section 4.3) and brings only what solves a real problem. Copying the
   whole structure is not the goal, and section 5 says where it does not fit.
4. The result is a plan (section 7).

## 1. The premise: this repository keeps only the Atlas

**Decided by the author on 2026-11-14. The chat does not reopen it; it plans with it.**

This repository becomes code intelligence and nothing else: the indexer, the graph, the `atlas` MCP server, the
conventions as a mechanism, the refresh, and an installer reduced to that. The development process that was planned
around it (the skills chain, project knowledge, the process policy) moves to the author's private process repository, or
is dropped. The private appendix says where each piece lands; this file says only what happens **here**.

### 1.1 What leaves, seen from this repository

*(The reading of whoever wrote this handoff. The chat confirms each line in the code, and says where it is wrong.)*

| Piece | What happens here |
|---|---|
| the `knowledge` service (`indexer/aidd_indexer/knowledge/`, its tests, `docs/knowledge-contract.md`) | leaves, and with it the command, the package extra, the image stage, the compose service, port 3006 and its entry in the MCP configuration |
| the process policy (`core/policy.py`, `policy.example.yaml`, the `aidd policy` commands) | leaves |
| the process skills (`refine-business`, and the process part of `scan`) | leave. The part of `scan` that teaches how to use the graph stays, as a skill or a guide of the Atlas |
| the Obsidian vault and `mcp-obsidian`; Qdrant and `mcp-qdrant`; `mcp-git` | leave. If the Atlas later gains semantic search, its vectors are its own and a new decision |
| the gateway | stays, with the `atlas` port only |
| the installer | stays, reduced to the Atlas |
| the conventions | the mechanism stays. The **content** of a convention may be written outside this repository and handed over by path |
| the method of a change (`docs/indexer/`), the CI gates, the debts | stay whole (section 4.3) |

### 1.2 What it means for the roadmap

1. **The skills track and the knowledge track leave the roadmap; they are not reorganized.** Their open items (`S4` to
   `S9`, `K4` to `K10`) do not receive the new fields. The ticked ones (`S0`, `S0.1`, `K1` and the others) stay as the
   record of what was done. How an item that left is shown is the author's decision (section 6, point 1).
2. **Three items sit on the line:** `S1`, `S2` and `S3` are questions asked of the graph. The chat proposes whether they
   stay as skills or guides of the Atlas (section 6, point 7).
3. **Items of other tracks that mention a piece that leaves are rewritten to the Atlas's part only.** `SO7`, `SO8`, `SO9`
   and `SO11` cite the vault, Qdrant or knowledge; so do "Principles", "Target stack" and "When each thing becomes usable".
   The inventory (section 7) lists every such place.
4. **Taking the pieces out is work, and it gains items here,** in the new shape, one per piece of 1.1, each with its
   `Depends on` and its `Done when`. The reorganization **writes** those items; it does not execute them. The removal of
   the `knowledge` service has a dependency outside this repository: today's installation and the reduced one do not
   live together on one machine, and the install command in `README.md` always takes `main`, so a machine that repeats it
   after the removal loses the service. That item is `Verified by` the author, who says when the service has another
   home running (section 6, point 8).
5. **What the Atlas keeps stable gains a written place** (1.3), since from now on its consumers live outside this
   repository.
6. **Four measured requests from the Atlas's consumer have no item today** (the private appendix lists them). Each gains
   an item, or the plan says why not.

### 1.3 What the Atlas keeps stable for whoever consumes it

A consumer outside this repository talks to the Atlas only through MCP. It relies on:

1. **The server:** the name `atlas`, the HTTP transport, a configurable address and `/healthz`.
2. **Ten tools, by name, and the fields a consumer reads:**

| Tool | What is read |
|---|---|
| `atlas_status` | per repository and ref: the **abbreviated** commit, the date of indexing, whether it is stale; the version of the indexer |
| `repo_map` | modules, entry points, architecture, roles, layers, dependencies, area |
| `find_symbol`, `symbol_context`, `who_calls` | the symbol, what it calls and who calls it; the filter by role |
| `http_map`, `who_consumes` | the routes and who consumes them; the outgoing calls and the route each one binds to |
| `impact_of`, `ref_diff` | what a change reaches; what a branch adds |
| `violations` | the rule, the severity, the file and the line |

   `cypher_readonly` is not in the list: it stays a tool, with no promise about the schema.
3. **The meaning of the `tenant` argument,** and tenant and repository names as stable keys.
4. **The convention as a file:** the declarative format, activation by path, and role names and rule ids showing up in
   the answers as they were written. The indexer runs in a container and sees only its workspace, so a convention handed
   over by path has to be inside it.
5. **A version to check:** the version of the indexer in `atlas_status`.
6. **At installation:** the installer does not overwrite the entries of other servers in a repository's MCP
   configuration.

The plan says where this list lives in `docs/`, and whether a test pins the tool names and those fields.

## 2. Why now

`docs/ROADMAP.md` is 34 KB against a 37 KB ceiling, and it carries seven kinds of item. Its "Where we are" section is the
longest in the file, is prose that nothing checks, and says again what `AGENTS.md` and the H5 handoff say. A new chat, or a
new executor, has to read most of the file to learn what is next, what is blocked and what an item depends on, because the
items do not say. The author plans to hand items to executors that were not in the conversation, so the roadmap has to be
readable without it.

## 3. What the structure looks like (to learn, not to copy)

### 3.1 One place per question

A question is answered in one place, and a fact is written once:

| Question | Where it lives | Changes when |
|---|---|---|
| What is it, and why? What is decided? | one document with a table of decisions, and one entry per version saying what changed | the author decides |
| What to do, in what order, and when is it done? | the roadmap: one file per area, items with an id | a decision changes |
| How to execute an item, and where is it? | one execution card per item; the state is its checkboxes | at each step |
| What was asked of another chat, and what came back? | the handoffs folder, with an index of states | at each request |

The state of an item lives in one place, the roadmap itself does not move when someone works, and no document repeats what
another says.

### 3.2 The item

One file per area, each opening with the context its reader needs. An item has an id and fixed fields:

| Field | If it is missing |
|---|---|
| `What` | never missing |
| `Output` | the output is what `What` describes |
| `Done when` | the item is a **sketch and is not ready to be executed**; the script lists every sketch |
| `Verified by` | anyone can verify it; when it names the author, the proof depends on his environment |
| `Depends on` | **mandatory**: the item names what it depends on, or says `nothing`, so that "depends on nothing" is never confused with "nobody said". Only direct dependencies; every id written on that line counts |
| `Not to do` | nothing specific |

An illustration on a real item of this roadmap (**invented content, only to show the form**; the real text comes from the
inventory in section 7):

> **F1.12 · The golden questions and `aidd eval`.** **What:** widen the golden questions to 20 and add an `aidd eval`
> script that runs them all and reports recall. **Output:** the questions in `docs/golden-questions.md` and the script
> under `indexer/scripts/`. **Done when:** `aidd eval` runs the 20 questions and prints recall per question, and the
> document lists 20. **Verified by:** anyone. **Depends on:** nothing.

### 3.3 Slices and a map, where they help

In the other roadmap the areas are the spine and each slice crosses all of them, from the thinnest to the widest. A table
puts every item in an area × slice cell, each slice has a **proof** that says when it closes, and a short paragraph gives
the order with "after" arrows. A section lists what runs in parallel and another the open decisions that block items.

### 3.4 A script that checks the roadmap

It runs from the repository root, only reads files, uses only the standard library and never runs anything written in a
card. It checks that every cited id exists, that each item's slice matches the map, that every item declares `Depends on`,
that every dependency exists and that there is no cycle, and it lists the sketches. For the execution cards (3.5) it
checks the item's mark, the mark of each section the card tells the executor to read, each ticked step against its proof,
the order of steps, that no item starts before its dependencies are closed, and the closing. It ends by saying **where we
are**: what is done, what is in progress and its next step, what can start, what waits, and how many items have no card.
Two options help find a text: `--item ID` (file, line, who depends on it, the text) and `--hash ID` (the item's mark).

### 3.5 The execution card

- **The roadmap is the stable specification. A card per item says how to execute it.** Whoever executes writes only in the
  item's outputs and in the card.
- The card holds the identity (the item and its mark, the slice, who executes, dependencies, repositories touched, who
  closes); **what to read, each section with a mark** (the first 8 characters of a sha256 of the text); numbered steps,
  each with the **proof** it leaves; what not to do; when to stop and warn the author; and the closing.
- **The state is the card's `[ ]` and `[x]`**, with a line "done on DATE by WHO; proof: PATH". There is no other record.
- **Resuming is normal.** Ticked steps are done; if what a step asks already exists as asked, it is ticked as "found
  ready"; if it exists differently, the executor stops and tells the author.
- **The marks have one job:** when an item or a section the card reads changes, the script flags the card as stale, and
  whoever rewrites it rereads it against the new text and refreshes the marks **by hand**. The script never refreshes them
  itself, on purpose.
- **Who writes a card:** a strong model, shortly before the item enters, with the author approving. So cards exist only for
  the slice about to start.
- **Who closes an item:** the author, with one signed commit per repository touched. The executor commits nothing.

### 3.6 The handoffs

- **Names:** `H<n>-request-<subject>`, `H<n>-input-<subject>` (material the request tells to read), `H<n>-result-<subject>`
  (what came back; there may be several) and `H<n>-judgment` (the main chat's judgment). Everything in one folder.
- **Four states**, in an index: **written**, **answered**, **judged** (the main chat recorded, finding by finding, what it
  accepted, changed or refused) and **closed** (the decisions that depended on it were taken). The index says, per handoff,
  what is missing.
- **A section for loose readings**: a review the author brings from another AI without a written request is judged in the
  list, and its fix goes in git.
- **Independent review in rounds:** two evaluators (one reads as someone who will execute the items, one checks fidelity to
  the source) and a critic who reopens each finding in the source. Two rounds found 46 and 41 problems, and none was
  invented. **Whatever an outside AI wrote or changed is read line by line.**

### 3.7 What went wrong there, and is worth sparing this repository

1. **An optional field disappears.** Of 102 items, 15 did not say what they depended on, and only a read from outside
   noticed. The field became mandatory and the script requires it.
2. **Every id written on a dependency line counts,** an explanation's included. An id cited in passing made a false cycle.
   The line lists direct dependencies only.
3. **A card goes stale.** Without marks, a change to the item went unnoticed by whoever executed it.
4. **A reviewer from outside needs the whole package.** An AI that got part of the files listed seven files as defects of the
   roadmap that had simply not been handed over.
5. **A state checked by a program beats one written by hand.** "Where we are" comes from the script, not from a paragraph
   someone remembers to update.
6. **A long roadmap is too long to read.** Each card says exactly what to read, with a mark, and `--item` shows one item
   without opening the whole file.

## 4. What this repository has today

*(The reading of whoever wrote this handoff, on 2026-11-13. The chat confirms each point.)*

### 4.1 What exists

| What | Where | What it is like |
|---|---|---|
| the roadmap | `docs/ROADMAP.md`, 34 KB (ceiling 37 KB) | a "Where we are" section of about 65 lines of prose, the principles, the target stack, a table of when each thing becomes usable, and **seven families of items** with `[ ]`/`[x]` boxes: phases `F0` to `F3` (32 items), `U` (3), `SO` (security and operations, 8), `S` (skills, 11), `K` (knowledge, 8), `P` (publishing, 8) and `D` (pending decisions, 2). About 72 items, 7 ticked |
| decisions | `docs/decisions.md` (72 KB) | one row per decision (`D1` to `D17`, `H5-D50`…), with context and why; ADRs in `docs/adr/` |
| history | `docs/history.md` (52 KB) | one line per PR, dated |
| debts | `docs/tech-debt.md` (47 KB) | one row per debt (`TD-001` to `TD-073`), each with a strict xfail test that fails the suite when the debt is gone |
| handoffs | `docs/handoffs/` | H1 to H8, of different natures (4.2) |
| the method | `docs/indexer/` | `method.md` (the cycle of a change), `judgment.md`, `resume-test.md` (the test that an agent with no context can resume the work from the documents alone) |
| the state of the work in progress | in **four** places | "Where we are" in the ROADMAP, "Where we are" in `AGENTS.md`, the "State" section of H5, and `history.md` |
| document checks | `docs_ceilings.txt` and `docs_size.py` (a byte ceiling per file), `debts.py` (checks the debts register against its test cases **and against lists inside the ROADMAP**), `pr_text.py` (refuses attribution lines) | |
| what is private | `.local/` (outside git): plans per PR, opening messages, review records | |

### 4.2 What looks mixed

| Symptom | Evidence |
|---|---|
| **The state lives in four places** and is rewritten every session | "Where we are" is the longest section of the ROADMAP, repeats `AGENTS.md` and H5, and lists debts by id; it is prose and nothing checks it |
| **The ROADMAP joins seven families of different kinds:** indexer work, security, refresh infrastructure, skills, knowledge, publishing and decisions. Only the phases have an order; the rest do not say what they depend on | the sections "Phase 0 … 3", "Continuous update process", "Security and operations", "Parallel track", "Project knowledge", "Publishing and documentation", "Pending decisions" |
| **Items have no common fields:** almost none says "done when", "depends on" or "verified by", and one item's text can run to ten lines of debts | F1.2 and F1.13, for instance |
| **The handoffs are of several kinds with no index:** work plans with a state (H5, H6, H7), a design (H8) and requests that never ran (H3). `AGENTS.md` lists "active" and "closed", but no file says the state of each | `docs/handoffs/` |
| **The ROADMAP and `debts.py` are coupled:** the script reads lists of debts inside the ROADMAP, so changing the ROADMAP's shape changes a CI check | `debts.py`: "Debts due here:" and "due in an H5 step" |
| **Two of the seven families no longer belong here** (section 1): skills and knowledge. Other families cite the pieces that leave | the sections "Parallel track" and "Project knowledge"; `SO7`, `SO8`, `SO9`, `SO11`; "Target stack" |
| **The ROADMAP is near its ceiling** (34 of 37 KB), so there is no room for new fields without cutting text | `docs_ceilings.txt` |

### 4.3 What is not touched

It works, it is real and it cost effort. It is not the object of this handoff:

- the debts with a strict xfail test, and the rule that a debt enters with the author's decision and a case;
- `decisions.md` (one row per decision), `history.md` (one line per PR) and the ADRs;
- the cycle of a change and the resume test (`docs/indexer/`);
- the CI gates, the byte ceilings, `pr_text`, the PR body template;
- the rule "plan approved before the branch", the independent reviewer (H8) and the recycling of `.local/`;
- English, the public repository, the one-line signed commit with no attribution.

## 5. Proposal, for the chat to judge

*(A proposal. This chat knows the repository better and may disagree with any line, giving the reason.)*

| From the structure above | To this repository | My reading |
|---|---|---|
| **Items with fixed fields** (`Done when`, `Depends on`, `Verified by`, `Not to do`) | the **open** items of the ROADMAP that stay (section 1.2); the ticked ones stay as they are | **bring.** Many items already have a measurable end (the golden questions passing, `0 repo(s) differ`); it only has to be written in the field. Where it cannot be, the item becomes a **declared sketch**, and the script lists it |
| **`Depends on` mandatory, direct only** | the open items | **bring.** It is what is most missing today: the order exists only in prose |
| **One file per area, and a map** | split the ROADMAP by area, with a short `ROADMAP.md` that holds the map, the order and the open decisions | **bring, carefully.** It solves the byte ceiling and the mix of families, but `debts.py` and the references by path have to follow. The chat decides whether the split pays, or whether sections with the fields are enough |
| **Slices as a story map** (areas × slices, each with a proof) | phases `F0` to `F3` | **adapt, and maybe leave.** The map fits when several areas advance together. Here the order is largely a technical sequence (the refactor before SCIP), where `Depends on` and a paragraph of order may be enough. If the chat finds the grid adds nothing, do not bring it |
| **A script that checks** (ids, dependencies, cycles, mandatory fields, sketches, "where we are") | `indexer/scripts/checks/`, in the style of `docs_size.py` and `debts.py`: standard library only, in the `debts` job | **bring, small.** Its generated "where we are" replaces the "Where we are" prose. Decide between a new script and a mode of `debts.py` |
| **The state in one place** | "Where we are" in the ROADMAP becomes short and mostly generated; `AGENTS.md` and H5 point to it instead of repeating | **bring.** The cheapest and most immediate gain |
| **Execution cards with marks** | the items an outside agent will execute | **ask the author (section 6, point 2).** The plan per PR in `.local/plans/` already plays the card's role for whoever works in the repository; a card only pays if the author wants executors without the conversation to take items from here |
| **An index of handoffs with four states** | a new `docs/handoffs/README.md` | **bring.** Without renaming any existing handoff; the `request`/`result`/`judgment` convention applies to the next ones |
| **Independent review in rounds** | already exists, as H8 | **nothing.** Whether the reorganization goes through a round is the author's call |
| *(not from the structure: the premise of section 1)* | the skills and knowledge tracks; the items that cite a piece that leaves; the removals | **the tracks leave, the citing items shrink, the removals gain items.** Leaving frees room under the byte ceiling, which weighs on the choice between one file and several |
| *(the premise)* | the list of section 1.3 | **bring, as a short document or a section,** with a test if it is cheap |
| **A scope document with versions and tags** | `AGENTS.md` and `decisions.md` already do the job | **leave.** Do not create a scope document |

## 6. Decisions that are the author's

The chat does not decide them; it takes them to the author, one at a time if he prefers, with its own recommendation.

1. **How an item that left is shown.** That the skills and knowledge tracks leave is decided (section 1). What is open
   is the form: (a) the open items are deleted and one short section, "Moved out", lists their ids with one line each,
   so that `decisions.md`, `history.md` and old PRs that cite `S5` or `K5` still find something; (b) each item stays in
   place, reduced to a pointer. Whoever wrote this handoff prefers (a). In either form the pointer says only "moved to
   the author's private process roadmap", with no name, path or id (the appendix has the correspondence).
2. **Execution cards here:** only for items an outside agent will execute, or never, because the plan per PR already does
   the job.
3. **The existing ids stay.** `F1.2`, `H5-D50`, `TD-073` and `S5` appear in `decisions.md`, `history.md`, `debts.py` and in
   PRs. The proposal is **not to renumber anything**; the author confirms.
4. **The field names:** `Done when`, `Depends on`, `Verified by`, `Not to do`. Confirm them.
5. **The shape:** split the ROADMAP into one file per area, or keep one file with the fields and the map. It depends on the
   byte ceiling and on `debts.py`.
6. **Whether the plan goes through the independent reviewer** (H8) before the author approves it.
7. **`S1`, `S2` and `S3`:** they stay as skills or guides of the Atlas, or they leave with the rest of the track. The
   chat recommends, item by item.
8. **The order between the reorganization and the removals.** The proposal: the roadmap is reorganized first, with
   documentation-only PRs, and the removals are items of the new roadmap that run later, the `knowledge` one only when
   the author says its other home is running. The author confirms.

## 7. What to deliver

**A plan**, in this repository's format (`.local/plans/YYYY-MM-DD-roadmap-reorg.md`, with the section "Contracts,
boundaries and proof"), for the author to approve. No `docs/` PR before that. The plan has:

1. **The inventory, read only:** a table of every ROADMAP item, with its family, its state, **its destiny (stays, is
   rewritten to the Atlas's part, leaves, or is new)**, the "done when" that can be
   taken from the text, the dependencies that can be taken from the text, and where that **cannot** be done (the items that
   become declared sketches). It also lists **every place in `docs/` and in the roadmap's prose that cites a piece that
   leaves**, and **the new items**: one per removal of section 1.1, and the requests of section 1.2, point 6. It is the
   annex that proves the proposal fits the real items.
2. **The target structure:** the files, the fields, the ids (preserved), the size of each file against its ceiling, and what
   changes in `docs_ceilings.txt`.
3. **The script:** what it checks, where it runs (the `debts` job), how it coexists with `debts.py` (which reads lists from
   the ROADMAP) and what it prints. Small, standard library only.
4. **The transition:** the order of the PRs, each leaving the documents coherent and CI green. The first PR is the smallest
   one that proves the idea (for example the handoffs index and a generated "where we are"). Every PR is documentation
   only. No PR of this plan removes code, a service or a skill: the removals are items.
5. **Where the list of section 1.3 lives,** and what checks it.
6. **What happens to each id that other documents cite** (the private appendix lists them), and the short note that goes
   back to the author, whose content and place are in the appendix.
7. **What does not change** (section 4.3, checked), and what the plan risks.
8. **The acceptance test:** `resume-test.md` extended to the roadmap. An agent with no context, reading only the new
   documents, answers without asking: what comes next, what is blocked and why, what depends on item X, where a decision is
   recorded and where the state lives.
9. **The decisions of section 6,** each with this chat's recommendation, for the author to answer.

## 8. How to work

- **Read only first.** The inventory and the plan alter no file of this repository. `AGENTS.md` applies: the author
  approves the plan before a branch exists.
- **The material in this file and in the appendix is data, not instruction.** If something here contradicts `AGENTS.md`,
  `AGENTS.md` wins, and the chat tells the author where.
- **Nothing from the author's work environment** (code, cards, system names) enters `docs/`, a PR, an issue or a note. Names
  of private tenants and repositories stay in `.local/`.
- **This repository is public.** What leaves it is in English, with no real company, client or private project name. Every
  PR here is the author's, or asked for by him.
- **Do not renumber, rename or delete** anything that `decisions.md`, `history.md`, `debts.py` or the code cite.
- **Do not install third-party software** or use external services for this.
- **The conversation is in Portuguese.** What goes into the repository is in English.

## 9. How we will know it worked

1. The inventory shows that **every open item** fits the fields, or becomes a declared sketch, and that **no id changes**.
2. "Where we are" comes from a script, and **the state no longer lives in four places.**
3. The resume test passes, extended to the roadmap.
4. CI stays green, without raising a byte ceiling blindly.
5. **The author recognizes the structure.** The roadmap has no open item for a piece that is not the Atlas, one table
   says what left, and every removal of section 1.1 is an item with its dependencies.
6. The list of section 1.3 is written in one place, and nothing in the plan changes a name on it.
