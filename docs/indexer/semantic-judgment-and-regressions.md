# Semantic judgment and regressions

> The third of five documents on how the indexer's changes are validated. [The inventory](validation-inventory.md)
> lists the procedures, and [the benchmark protocols](benchmark-and-statistical-protocols.md) say how they measure
> and compare. This one says how a difference becomes a verdict: what counts as a gain, a loss, a false positive, a
> false negative, an ambiguous case or a regression, and what evidence a verdict needs. It is written for a
> developer, or a coding agent, resuming H5.
>
> **Written on 2026-10-26**, on `main` at `0725d47`. The sources are:
>
> - the versioned docs, the tests and the scripts in this working tree;
> - the bodies of PRs #25 and #27, read with `gh` (no edit);
> - the previous session's transcript (`$T`), read for the tools that recorded verdicts.
>
> **Nothing was judged to write it,** and no comparison was run. The read-only commands were:
>
> - counts over the expected lists and the fixtures;
> - `git show`;
> - `gh pr view`;
> - searches of `$T`.
>
> **The terms.** The evidence terms (Confirmed, Reconstructed, Partially confirmed, Historical only, Not found,
> Inferred) are the benchmark protocols' §1. `$S`, `$C` and `$T` are defined in the inventory.
>
> **Its place in the series.** The inventory's §10 proposed "judgment and statistics" as the third document. The
> benchmark protocols took its measured part, and this one takes the rest: the decision rules of V05, V09, V11 and
> V12, the golden round's verdicts (V25), and how a case or a regression is recorded.

## 1. Scope and labels

| Inventory id | What this document takes from it |
|---|---|
| V05 | cases first: fixtures, case tables, strict xfails, as the records of an expectation |
| V09 | judging a corpus diff at the source |
| V11 | judging the micro graph by case |
| V12 | judging a loss |
| V25 | what a golden answer's comparison can and cannot say |
| V02, V08 | the `checked` verdicts and the gates' classification, as recorded judgments and as their starting point |

Each rule below carries one of three labels:

| Label | Meaning |
|---|---|
| **[documented]** | written in a versioned document, a test or a script; the source is named |
| **[practice]** | done in past PRs, as `$T`, the handoffs' prose or a PR body shows, but written nowhere as a rule |
| **[recommendation]** | proposed here, for later H5 work; it was never used, and nothing records it as history |

## 2. A difference is not a verdict

Every comparison tool shows **what** changed. None of them says **whether it is right.**

The sources say so in several places:

- "CI classifies the diff the way a judgment starts" (the H7 handoff, "What stays judgment"). **[documented]**
- "Judging an item at its source is what keeps the expected lists evidence, and an LLM does not decide it" (H7).
  **[documented]**
- An LLM does not judge its own result (H3; the H4.1 handoff, "The acceptance test"). **[documented]**
- The guide (§5, step 4, in Portuguese) asks for the diff to be judged item by item at the source. Each item that
  leaves must have been wrong before, and each that enters must be right. "A change the rule does not explain is a
  defect of the rule, even with P/R rising." **[documented]**
- A fixture's `expected.json` is regenerated only after each line was checked at the source, "never from the
  extractor's output without review" (the guide, §5). **[documented]**
- "A `checked` item whose `evidence` moved to another line is checked again, not copied" (the guide, §5, step 5).
  **[documented]**

| Layer | The observable difference, and the tool that shows it | What the tool cannot say | Where the verdict is made |
|---|---|---|---|
| HTTP corpus | ids added, removed or re-resolved (`http_corpus.py --baseline`; `gates.py`'s "to judge") | whether the item is a route the code serves, or a call it makes | at the item's evidence line, at the pinned sha |
| Against a list | FP and FN, precision and recall (`corpus_metrics.py`) | whether the list is right; a list is corrected with evidence (H2-D15) | at the source; the list's edit in its own commit |
| Micro graph | records gone and new (`micro.py`); sites by kind, edges by class (`chain_diff.py`) | whether the callee the site reaches now is the one the code calls | at the sample's source line, by case (H5-D14) |
| Losses | the edges to extension methods that went away (`ext_*.py`, `lost_ext.py`) | whether the lost edge was right, or a guess `main` made by luck | the receiver's declared type, at the source |
| Live dry-runs | differences per section (`dry_compare.py`; later `dry_sections.py`) | the same as the micro graph, on private code | at the source, locally; reported by snapshot number |
| Live graph | whether the graph holds a dry-run (`graph_vs_dry.py`) | nothing semantic: it checks the writer, not the extractor | — |
| Golden answers | byte equality, or a difference only in time and build fields (`cmp`, `json.tool`, `json_paths_diff.py`) | whether the answer is right | "the MCP's answer and the Cypher's agree **and** a sample was checked at the source" (the golden questions' header) |

## 3. The terms the sources use

The sources have no single taxonomy. Each layer has its own words, and this section keeps them. The six categories
of this document are a mapping onto those words, not a historical scheme. **[documented]** where a source is named,
**[practice]** where only prose shows it.

### 3.1 Gains

- **"Gain" in the gates:** a new corpus item whose pair the branch now finds in the expected list, `FN_base −
  FN_head` (`gates.py`; H7: "a new item that is in the expected list. Nothing to judge"). It is automatic, and as
  good as the list it reads. **[documented]**
- **"Gain every xfail":** a change of behavior must make each strict xfail of the language's cases pass, and lose no
  guard (H5-D10). **[documented]**
- **"Only real gains":** the author's request for step 5 (H5-D10, the handoff). The micro graph has no automatic gain:
  an added edge is a gain only once it is judged right. **[documented]**
- **In the handoffs' prose,** a change of behavior's gains are listed as judged examples, by case, with public repos'
  sites: "smartstore's `_db.SaveChangesAsync()` reaches `HookingDbContext`". **[practice]**
- **"A difference in the corpus is a defect of the step, not a gain"** (the H5 protocol; H4.1, part 6). Under a
  refactor, nothing is a gain. **[documented]**

### 3.2 Losses

- **"No win lost"** (`gates.py`; H7). An expected pair the base found and the branch misses, or a `checked` item
  judged right that the branch no longer extracts. A gate fails: H7 calls it a "regression". **[documented]**
- **"Gone":** an item outside the list that went missing is listed "to judge", "probably a false positive removed"
  (H7). **[documented]**
- **The micro graph's kinds** `dropped`, `narrowed` and `changed` are observable, not verdicts (`chain_diff.py`).
  **[documented]**
- **"Found by luck":** an edge `main` had for a wrong reason, which a correct answer loses. H5-D15 and H5-D16 close
  such gaps in the same PR, with their cases first. **[documented]**
- **"What stays lost":** the losses a PR accepts, each with its reason, such as Go's interface receivers and C#'s 188
  extension edges (the H5 handoff; PR #25's body). **[documented]** as a record; the reasons are judgments.
- **The author's rule of 2026-10-23:** a loss of the same kind as the PR's goes in the PR. Another kind is recorded
  in detail (H5-D17, widened). **[documented]**

### 3.3 False positives

- **Against a list:** `false_positives`, the extracted pairs that match no expected pair (`corpus_metrics.py`).
  **[documented]**
- **In the `checked` sample:** an item with `ok: false`, and a `category` that says why. **[documented]**
- **H2-D12:** a route or call that lost a prefix the code holds is an error. A prefix from config or the environment
  is not, since it belongs to the linker. **[documented]**
- **H2-D14:** an item wrong only because it inherits a defect already categorized counts, but does not block the rule.
  **[documented]**
- **H2-D11, precision before recall:** a rule that raises recall and drops precision in any repo does not go in.
  **[documented]**
- **In the micro graph** there is no FP label. The step 5 tables say a wrong answer is "a `CALLS` edge to the wrong
  method, or one found by name instead of by type". The handoffs list "the guesses by name that go were wrong".
  **[documented]** (the tables), **[practice]** (the lists)

### 3.4 False negatives

- **Against a list:** `false_negatives`, the expected pairs no extracted pair matches. Each carries a `category`
  that says why it is missed (`corpus_metrics.py`). **[documented]**
  - H2-D16: one category per miss, the most specific one.
  - H2-D5: a call is expected only when its path is a literal or a template.
- **In a fixture:** `gaps`, "links known to be missing — xfail until they appear, then the test fails asking to move
  them to `edges`" (`test_fixtures.py`). **[documented]**
- **In a case table:** a strict xfail on the side that is wrong, whose reason is "what that side gives today when it
  is wrong" (`e74bc41`, `test_cs_names.py`). **[documented]**
- **"What stays out":** the gaps a PR leaves, each "with a case to start from", such as H5-D17's thirteen (the H5
  handoff). **[documented]**

### 3.5 Ambiguous cases

**No source has an "ambiguous" verdict.** What the sources have instead:

| Term | What it is | Source |
|---|---|---|
| `ok: null` in `checked` | a sampled item with no verdict yet, counted as `pending`. The lists hold none today (§5.1) | `corpus_metrics.py` |
| `needs-resolver`, `Unknown` with its reason | **an extraction outcome, not a verdict.** A decision that needs a type not declared in sight is not guessed | `AGENTS.md`; H5 step 5; H4.1, rule 8: "A limitation is recorded, not estimated" |
| A strategy's `-ambiguous` suffix, and `~amb` in `chain_diff.py` | the resolver found several candidates by name. **A property of the edge, not of a judgment** | `neo4j/SCHEMA.md` |
| "Which one applies … is a question of their types" | a choice tree-sitter cannot make: it stays out of the rule, as a gap, until SCIP | the H5 handoff, "C#'s change of behavior"; H5-D16; the guide §8, the boundary with SCIP |

So the sources' handling of a case that cannot be decided is to leave it out of the rule and record it as a gap with
a case. It is not given a verdict either way. **[documented]** (H5-D15 to D17; H4.1, rule 8)

### 3.6 Regressions

| Use of the word | Meaning | Source |
|---|---|---|
| "regression" in CI's classification | an expected item that went missing; the gate fails | H7, "What stays judgment" |
| "No repo may regress" | no repo's precision drops | the guide §5, step 4; H2-D11 |
| "Regression protocol" | the checks every H5 step runs | the H5 handoff |
| "An H5 regression" | a difference on the new hold-out between H5's code and the commit before H5, not explained by a judged case of step 5 | H2-D21 as amended by H5-D12 |
| "Regression" in the golden questions | repeat all five after any change to what the graph holds | `docs/golden-questions.md` |
| "Golden-file regression" | the fixtures' test | `test_fixtures.py` |
| "A defect of the step" | any corpus difference under a refactor | the H5 protocol |
| "A defect of the rule" | a change the rule does not explain, even with P/R rising | the guide §5 |
| "What blocks the merge" | a difference outside the change without an explanation; an expected pair or a `checked` item lost; a link lost in the graph; an `install-check` FAIL | PR #5's plan (reconstructed) |

**"Confirmed regression" does not appear in the sources.** §5.3 maps it.

### 3.7 The mapping, in one table

| This document's category | The sources' words | Observable signal | What makes it a verdict |
|---|---|---|---|
| Gain | "gain" (gates), xfail gained, the handoffs' judged examples | a new id that matches the list; an added edge; a case that passes | a list that is evidence; a judged sample; a case |
| Loss | "win lost", "gone", "found by luck", "what stays lost" | a missing id or record; `dropped` or `narrowed` sites | judged at the source as a right item lost, or as a wrong one removed |
| False positive | `false_positives`, `ok: false` with a category, "a wrong edge", "a wrong guess" | an extracted pair outside the list; an edge | judged at the evidence line |
| False negative | `false_negatives` with a category, `gaps`, xfail, "what stays out" | an expected pair not extracted; a gap fixture | the list or the case says it should exist |
| Ambiguous | none. The nearest are `pending`, `needs-resolver`, gaps left to SCIP | — | not decided; recorded as a gap |
| Regression | "regression" (H7), "win lost", "defect of the step or rule", "an H5 regression", "what blocks the merge" | a gate failure; an unexplained difference | §5.3 |

## 4. The evidence a judgment rests on

### 4.1 What each kind of record keeps

| Record | Fields kept per item | Where | What it does not keep |
|---|---|---|---|
| A `checked` entry of an expected list | `evidence` (`repo:file:line`), `method`, `path`, `raw` (most), `ok`, `category` | `indexer/tests/corpus_expected/`, with `checked_seed` in 54 of the 57 lists | how the verdict was reached, by whom, when, or why |
| An expected pair | `method`, `path`, a `category` when missed; the list's `source`, `sha`, `spec`, `scope`, `notes` | the same | the rationale per pair |
| A gates "to judge" line | the repo, the kind, `METHOD path`, a link to the line at the pinned sha, and a tag (`new` or `gone`; "another place of an expected pair", "outside the list" or "no list"; or `handler_id`/`caller_id` changed) | the job summary (artifacts kept 14 days) | any verdict |
| A `chain_diff.py` sample | `kind`, `repo`, `file`, `line`, `was`, `now`; `samples_view.py` adds the source line | `SAMPLES.jsonl`, outside the repository | the case (only Go had a per-site case, from `why_a.py`), and any verdict |
| A per-site attribution row | its readers read `repo`, `file`, `line`, `case`, `src`, `old`, `new` and `way` | `WHY.jsonl`, written by `why_a.py`: **not persisted** | — |
| A case table entry | the code, each side's expectation, and a strict xfail whose reason is what the wrong side gives | `indexer/tests/test_*.py` | which corpus sites the case explains |
| A fixture's `gaps` | `from`, `to`, `why` | `fixtures/*/expected.json` | — |
| A handoff's results | judged examples by case, with public repos' sites; totals; "what stays lost or out" | `docs/handoffs/H5-indexer-refactor.md` | the sample sizes, the items judged, the verdicts one by one |
| A PR body's "Judged" section | the same, per PR | GitHub (#25, #27) | the same |
| A golden round | Q1–Q5 as ✅, ⚠️ or ❌; the 27 calls as counts ("22 are byte for byte the same, and the other 5 differ only in their time and build fields"); what changed; what the round caught | `docs/golden-questions.md` | the answers themselves (private) |

### 4.2 What the sources require before a verdict

- **The evidence line.** A corpus item is judged at its `repo:file:line`, at the pinned sha, "against what the
  application serves or requests" (the corpus report, "How it is measured"). `gates.py` links each item to that
  line. **[documented]**
- **Both sides' code versions.** The baseline is named, as `-29` or `-26`, or derived from the base's tree in CI. A
  micro base is keyed by its `aidd_indexer` tree and the image (the benchmark protocols, §4.3, §6.3). **[documented]**
- **The language's rule.** A micro difference is explained by "a case of the language's table" (H5-D14). The rule is
  the handoff's statement of the language's semantics, such as "a name is what its nearest declaration in scope
  makes it" for C#, and the boundary with SCIP: "Only a declared type counts". **[documented]**
- **The list's own rules,** for a corpus item: H2-D4, D5, D12, D14, D15, D16 and D17. **[documented]**
- **Judged by a person, or an agent reading the source,** never an LLM's verdict that a gate reads (H7), and never an
  LLM judging its own result (H3, H4.1). **[documented]**
- **For the hold-out, no item at all:** it is read only in aggregate (H5-D13, H2-D20). **[documented]**

### 4.3 What was never defined

- **No mandatory set of fields for a verdict.** H7-D2 recommends "a file committed with the PR, one verdict and one
  reason per 'to judge' item, checked by CI", but it is a decision still to make.
- **No confidence level.**
  - The golden rounds' ✅, ⚠️ and ❌ are outcomes of a question, not a confidence in a verdict.
  - The graph's `confidence` on macro edges (`exact`, …) is a property of a link, not of a judgment.
- **No record of how a `checked` verdict was made.** The first hold-out's tools, in `$T` on 2026-10-17, show three
  ways in one sample:
  - a sampled item that matched the expected list was marked right automatically (`prep.py`, "an item that matches
    the repo's expected list … is right");
  - the others were shown for judging at the source, and `verdict.py` took a default verdict for the unlisted ones,
    with exceptions by index;
  - a `categorize.py` set the misses' categories "one cause per repo, read at the source".

  H2b's `gab.py judge` (2026-10-15) wrote one verdict per item. The lists do not say which way each verdict came.
  **[practice]**, Historical only.
- **No sample size, and no share of wrong items that blocks,** beyond "one wrong item in a case blocks the PR"
  (H5-D14). The benchmark protocols' §5.13 has the details.

### 4.4 When the source or the artifacts are missing

| What is missing | What can still be concluded | What cannot |
|---|---|---|
| The judged micro samples (`$S/h5/why/out/*.view.txt`, emptied on 2026-10-26) | that the handoffs and PR bodies report a judgment, with its totals and examples; the counts, re-derived from `$C/micro-fresh` | which items were judged, and how; a new draw does not give the same items (the benchmark protocols, §8, gap 6) |
| `why_a.py`'s attribution (Go) | the per-case totals as the handoff reports them | any per-case count or sample again |
| The rationale of a past verdict | the verdict, where a list or a case records it | why, beyond the category or the xfail's reason |
| The private source of a live snapshot | locally, with the clone: everything | nothing of it may go into the repository; only counts and snapshot numbers |
| A hold-out item | the aggregate | the item itself: the rule forbids opening it |
| The CI artifacts of an old PR (kept 14 days) | the check's verdict on GitHub | the "to judge" list, unless the runs are made again |

A historical result whose inputs, code version or rationale are missing is evidence that the result was **reported**.
It is not evidence that it **would reproduce**, nor of **why** each item was judged as it was.

### 4.5 A verdict record — **[recommendation]**

This is not a historical rule. It follows H7-D2's recommendation, which is still undecided. One row per item judged,
and one per item left unjudged:

| Field | Content |
|---|---|
| `item` | the observable difference: the layer, the repo (a public one, or a snapshot number), `file:line`, and the record before and after |
| `sides` | each side's code (sha and tree), the baseline or base-run label, and the image id |
| `source` | what was read: the line, and its link at the pinned sha |
| `rule` | the language's or the list's rule that decides it, by its id (H2-D12, H5-D17 …) or its case |
| `verdict` | one of `right`, `wrong`, `undecided` (§3.5), or `unjudged` |
| `class` | the sources' term (§3.7): gain, a win lost, FP and its category, FN and its category, a gap, a defect |
| `basis` | `source-read`, `automatic` (such as a list match), `historical-note` or `inferred` |
| `by`, `date` | who judged, and when |
| `record` | the test, fixture, list commit or gap entry that holds it, if any |

**A hypothetical example.** It is invented, and is no historical case. The repo `example-api` and its line are
fictional:

| Field | Value |
|---|---|
| `item` | micro graph, `example-api`, `src/Orders/OrdersService.cs:42`: `{(Repo.Save, unique-name)}` → `{(IOrderRepo.Save, receiver-type)}` |
| `sides` | `main` `<sha>`, tree `<tree>`; branch `<sha>`; micro base `base-<tree>-<image>` |
| `source` | line 42 calls `_repo.Save(order)`; `_repo` is a field declared `IOrderRepo _repo` |
| `rule` | "a name is what its nearest declaration in scope makes it" (the H5 handoff, C#) |
| `verdict` | `right` |
| `class` | gain; a wrong guess by name removed |
| `basis` | `source-read` |
| `by`, `date` | `<name>`, `<date>` |
| `record` | the case `a-field` in `test_cs_types.py` |

### 4.6 The process tried on real items, on 2026-10-26

To test whether this document is enough to judge with, five items were judged by it on 2026-10-26. **They are a new
judgment, not PR #27's historical one.** They come from `chain_diff.py`, run from `main` to n17 after its sorting fix,
with seed `20261021` and N 40, taking the first sample of each kind. Each was judged by reading the declaration that
decides the receiver's type, in the public repo at its pin. The full rows are in
[the PR #27 evidence](evidence/pr27-validation-state.md), §8.

| Kind | Repo | Verdict | The sources' term | Rule |
|---|---|---|---|---|
| `added` | elsa | **wrong** | a guess by name (FP): `x` of `x => …` is an `ExpressionExecutionContext`, and the call is that type's `GetInput<T>(InputDefinition)` | a typeless lambda parameter goes by name (H5-D16, "what stays lost"), and it now reaches an extension block's method |
| `changed` | elsa | right | a wrong guess by name removed | a capitalized member is that member (H5-D17) |
| `dropped` | smartstore | right | wrong guesses by name removed | an array is no value of its element's type (H5-D17) |
| `narrowed` | bitwarden | right | wrong `inherited` edges removed | the same |
| `widened` | umbraco | right | a static call on a homonym class replaced by the member's interface and its one implementation | a capitalized member, declared on a base that another part of the `partial` class names (H5-D17) |

**What it showed:**

- The terms (§3), the evidence a verdict needs (§4.2) and the record (§4.5) were enough to judge and record each item.
- **One wrong item is new evidence.** `main` had no edge at that site, and the branch added a wrong one. By H5-D14 a
  wrong item in a case blocks a PR; here it comes from a gap the PR left out on purpose, as H2-D14 treats an
  inherited defect. Whether it would have blocked PR #27, or calls for a case in a later PR, is **the author's
  decision**. It was not taken here.
- Why the resolver chose that method among the repo's `GetInput`s was not traced. The verdict rests on the source,
  not on the mechanism.
- **Traced later that day** (the PR #27 evidence, §10).
  - PR #27's last fix commit gave an extension block's methods their extension facts, which C# calls for. An older
    filter then kept `ActivityExtensions.GetInput` for a receiver of unknown type, because its `this` is an interface.
  - No code checked that a call written with type arguments needs a method that declares type parameters.
  - That missing check was categorized nowhere, so H2-D14 did not apply, and the semantic gate stood blocked.
  - The author chose to fix it by C#'s rule: H5-D18, a call written with type arguments reaches only a method that
    declares type parameters. Its judgment widened it to what C# proves an extension cannot take. The fix, its
    validation and what stays out are in [H5-D18's evidence](evidence/h5-d18-validation-state.md).

## 5. Cases, golden questions and regression records

### 5.1 The kinds of record, and what each one is

| Kind | Where | Is it a judgment? | Automated once written? | Counts on 2026-10-26 |
|---|---|---|---|---|
| **A test fixture** | `indexer/tests/fixtures/<name>/` with `expected.json` | its expected values were checked at the source when written; synthetic, controlled code | yes, `test_fixtures.py`; P and R must be 100 % | 17 fixtures, 3 with `gaps` |
| **A case table** | `test_go_types.py`, `test_go_declared_types.py`, `test_cs_types.py`, `test_cs_declared_types.py`, `test_cs_extension_methods.py`, `test_cs_names.py` | each case is a written expectation, a guard or a strict xfail with its reason | yes | `test_cs_names.py`: 42 cases; no xfail mark in use in the Go and C# tables after their fixes |
| **An expected list** | `indexer/tests/corpus_expected/` and `holdout/` | its pairs and categories, and its `checked` verdicts, are recorded judgments of the corpus | scored automatically | 57 lists; 35 miss categories; `checked`: 1,435 verdicts, 1,323 right, 112 wrong, 0 pending |
| **The gates' classification** | the job summary | no: it is where a judgment starts | yes | — |
| **A historical example** | the handoffs' results, PR bodies' "Judged" | a judged item, reported in prose | no | not exhaustive; not re-checkable when its sample is lost |
| **A golden round** | `docs/golden-questions.md` | the questions' outcomes, and a summary of the calls' comparison | no | rounds 1 to 10; no eleventh |
| **An automated regression test** | the suite (`test.sh`), `test_gates.py`, the Neo4j tests (`mcp-it.sh`) | no: it checks a recorded expectation | yes | CI on every PR |

**Recorded item-by-item judgments do exist, for one layer only.** The expected lists' `checked` samples are verdicts
per item, judged at the source, with no record of how each was made (§4.3).

What was **not** recorded item by item:

- the verdicts on the "to judge" items of a corpus diff (V09);
- the micro graph's judged samples (V11);
- the loss analysis's samples (V12);
- the live differences.

These survive only as prose and totals (the inventory, §9, gap 5).

### 5.2 Golden questions and calls

- **Where:** `docs/golden-questions.md` holds Q1–Q5, each with its MCP tool, its Cypher, what is expected and what
  was obtained, and the rounds. **[documented]**
- **Privacy.** The doc uses placeholders (`<project-a>`) and describes results "in shape, not in content".
  - The live install's 27 calls name its tenants and repos, so they are kept out of the repository. For PR #27 they
    are `.local/indexer/pr27/golden-calls.json`, local, private, and with no backup.
  - [`live/golden.py`](../../indexer/scripts/live/golden.py) reads a calls file. The repository holds only
    [`golden-calls.example.json`](../../indexer/scripts/live/golden-calls.example.json), with neutral names.
  - The answers are written outside the repository.

  **[documented]** (`AGENTS.md`, the golden doc's header); **[practice]** (the local folder)
- **"Answered":** a question counts as answered when "the MCP's answer and the Cypher's agree **and** a sample was
  checked at the source" (the golden doc's header). **[documented]**
- **The comparison:** each answer byte for byte (`cmp`), else a diff of pretty-printed JSON with ISO timestamps masked,
  and `json_paths_diff.py` for the leaf paths. Expected: the same, or different only in time and build fields. The
  commands are in the benchmark protocols' §4.11. **[practice]**
- **What a round can claim.** An equal answer says the graph answers as before. It does not say the answer is right,
  unless the question's own check (the Cypher, and a sample at the source) was made. A round's ✅ records that check.
  The rounds give no per-call semantic judgment of the 27 calls, and none is claimed here.

### 5.3 A confirmed regression, and a candidate

The sources do not use these two terms. Mapped onto what they do say:

| Situation | Status | Source |
|---|---|---|
| Any corpus, hold-out or micro difference under a refactor | **confirmed** as a defect of the step, with no semantic judgment needed: the rule is identity. A real bug the refactor reveals is recorded, fixed in a separate commit with a fixture, and enters the baseline by explicit decision | the H5 protocol; `gates.py` |
| A gate failure: precision lower, a win lost, the hold-out changed without its label, the micro graph different without `graph-change` | **the PR fails.** Whether the extractor regressed, or the list is wrong, is judged: a list is corrected with evidence, in its own commit (H2-D15) | `gates.py`; H2-D15; H4.1 |
| An item "to judge" in a corpus diff | **candidate,** until it is judged at its evidence line | H7; the guide §5 |
| A micro difference in a change of behavior | **candidate,** until judged by case. **One sampled item judged wrong in a case blocks the PR** | H5-D14 |
| A loss of the PR's own kind | **fixed in the PR**; another kind is a gap with a case | H5-D17 (widened) |
| A live difference outside the change | **blocks unless explained** | PR #5's plan |
| A new hold-out difference between H5's code and the commit before | **an H5 regression,** unless a judged case of step 5 explains it | H2-D21, H5-D12 |
| A golden answer that differs beyond time and build fields | **candidate,** judged against the dry-runs and the question's check | the golden rounds (practice) |

**[recommendation]:** use "confirmed regression" only for a candidate judged wrong at the source, or for any
difference under a refactor. Use "candidate" for everything not yet judged.

### 5.4 Recording a new case without passing it off as history

- **The documented path:**
  1. a `test(<lang>)` commit with the case and its counterexample, a strict xfail with its reason on the wrong side,
     before the fix (V05; the guide §5, step 1; H4.1's cycle);
  2. a fixture's `gaps` entry, with its `why`;
  3. an expected-list edit with `file:line` evidence, in its own commit (H2-D15; H4.1);
  4. a gap under "What stays out", "with a case to start from" (H5-D17).

  **[documented]**
- **[recommendation]:**
  - a new case says when it was written, and from what: a fresh judgment, or a historical note;
  - a historical example from a handoff becomes a test only by being written as one;
  - a sample drawn now from a past diff is a new judgment, dated now, never the past one (§4.4);
  - nothing private goes into a case: public corpus repos, or synthetic code.

## 6. What the comparisons' limits mean for a judgment

The comparisons themselves are in [the benchmark protocols](benchmark-and-statistical-protocols.md). Each limit
below was checked again on 2026-10-26, and each is followed by what it means here.

1. **A structural diff is not a verdict** (§2). A count of added typed edges does not say how many are right. A
   "0 differ" says nothing changed, not that anything is right.
2. **`chain_diff.py`'s counts reproduce, but its past samples do not** (benchmark, §5.7, §8 gap 6). A past sample
   cannot be judged again as it was. Since 2026-10-26 the script sorts the sites before drawing, so a new sample
   reproduces from the same runs and seed. It is still a new judgment, never the past one.
3. **`graph_vs_dry.py` covers `CALLS` only** (benchmark, §4.10, §5.9). It checks that the graph holds the dry-run.
   That is the writer's correctness, not the extractor's. The other 14 lists of a picture have no script.
4. **The live "identical" is by `dry_sections.py`'s keys:** six sections, and an endpoint's `file` always empty
   (benchmark, §5.9).
   - It must not be read as identity of fields or sections it does not compare.
   - `dry_sections.py` was written on 2026-10-22 at 17:47 (`$T`). The live checks `$T` records before it, from
     2026-10-19 to 2026-10-22 at 13:04, ran `dry_compare.py`, which compares more. These are the folders of PRs #5 to
     #23, by their names and dates: an inference.
   - The ninth and tenth golden rounds say "identical in every section". For PR #23, `$T` shows a `dry_compare.py`
     output. For PR #25 the tool is not established.
   - For PR #27, before the merge, it was `dry_sections.py`. On 2026-10-26 a record-by-record comparison of the
     preserved dry-runs, in every list, found the 10 snapshots identical. The eleventh round can cite that. Since that
     day `dry_sections.py` also keys an endpoint by its `file_id`.
5. **The before/after comparator is not fully recovered.** What exists:
   - the commands typed for PRs #20 and #25;
   - `graph_vs_dry.py`;
   - `go_graph_diff.py`, one repo's `CALLS` before and after by merge key. It was found in `$T` (2026-10-21, PR #20)
     and is not persisted (the catalog, §4).
6. **The per-site case attribution is missing** (`why_a.py`, Go only). No C# attribution file was found. For C#, a
   commit's diff stood for its case (the inventory, an inference). So no recorded "per case and repo" sample exists,
   though H5-D14 and PR #25's body describe one.
7. **H6's procedures depend on `h6/step1-proto`** (benchmark, §4.8). For judgment, their correctness checks (`same.py`:
   identical or not) need no semantic verdict.
8. **PR #27's validation is not complete** (§7).

## 7. A judgment protocol

The steps follow the request's order. Each one gives its historical basis, and what is only recommended. No command
is new: those that exist are in the benchmark protocols.

| # | Step | Historical basis | **[recommendation]** |
|---|---|---|---|
| 1 | Identify each changed, added or missing record | **[documented]** the corpus report's per-repo `-a +b ~c` items; `gates.py`'s "to judge" list; `micro.py`'s report. **[practice]** `chain_diff.py`'s kinds and samples; the live dry-runs per section | keep the full list of items, not only the counts, outside `$S` |
| 2 | Establish each side's baseline and code | **[documented]** the named baselines; CI's base; the micro base by tree and image. **[practice]** each commit against the one before, and `main` against the tip | write both shas, the tree, the image id and the run labels next to the judgment |
| 3 | Find the source evidence | **[documented]** the evidence line at the pinned sha; the gates' links. **[practice]** `samples_view.py` and `show.py` print the source lines; `view.py` for Go, which needs `why_a.py`'s file | for live snapshots, read the private source locally and record only numbers |
| 4 | Decide whether the change is right | **[documented]** H2-D11, D12, D14, D15; H5-D10 to D17; the language's rule; "only a declared type counts"; judged by a person or an agent reading the source, not an LLM grading its own work | when the source cannot decide it, say `undecided` and record a gap with a case (§3.5) |
| 5 | Classify it in the sources' terms | **[documented]** §3 | use §3.7's mapping, and keep the source's own word |
| 6 | Record the evidence and the reason | **[documented]** list edits (`ok`, `category`) in their own commit; cases as tests; the handoff's results and "what stays lost or out". **[practice]** the PR body's "Judged"; totals by class | one row per item (§4.5), as H7-D2 recommends |
| 7 | Decide its status | **[documented]** blocks (H5-D14; PR #5's plan); fix in this PR (same kind); a gap with a case (another kind); explained | name it: confirmed regression, expected change, undecided, or unresolved candidate (§5.3) |
| 8 | Link it to its test or record | **[documented]** the `test(<lang>)` commit before the fix; a fixture's `gaps`; the handoff's gap list | put the test's id or the commit in the row |
| 9 | Report the unjudged apart | **[documented]** the gates count "To judge (N)"; `checked` counts `pending`. **[practice]** the PR test plans tick "every intermediate difference judged" | give judged and unjudged counts, and the sample sizes, separately. Tick a test plan item only when it is done: PR #27's body ticks an after-merge item that was never done (§7) |

None of these steps was run for this document.

## 8. PR #27 and H5: four different things

Four separate claims, each with its own state. Neither PR #27's validation nor H5 is complete. The details are in
[the PR #27 evidence](evidence/pr27-validation-state.md) and the inventory's §3.

| Claim | State on 2026-10-26 |
|---|---|
| **The inputs and tools for a judgment are recovered** | in part. Persisted: the scripts (the catalog, §2). Kept: the micro dry-runs in `$C/micro-fresh`, and the pre-merge live data in `.local/indexer/pr27/`, with no backup. **Lost:** the judged samples, and `why_a.py`'s attribution |
| **The judgment was performed** | historically, before the merge, for the corpus's two intermediate differences and for the micro graph by case on seeded samples, as the handoff and the PR body report. **Not re-performed.** The comparisons after the merge were never made, so nothing after the merge was judged. Later that day they were made, and found nothing to judge: the live graph differs only in the build and `IndexRun` (the PR #27 evidence, §9) |
| **An automated comparison was reproduced** | **re-derived on saved inputs**, not measured again: `chain_diff.py`'s counts, `dry_sections.py`'s and `graph_vs_dry.py`'s pre-merge outputs (2026-10-24). The after side cannot be compared until it is taken. It was taken and compared later on 2026-10-26: 0 mismatching |
| **PR #27's validation is complete and accepted** | **no.** Open: the after picture and its comparison, the golden answers after, the eleventh round, `docs/history.md`, the ROADMAP's and the handoff's state, the micro base, `install-check.sh`'s output. Acceptance is the author's. **Later that day:** the after side, its comparisons and the micro base were done; a new `install-check.sh` passes. The ROADMAP's and the handoff's state are corrected in the working tree. Still open: the eleventh round, `docs/history.md`, the 2026-10-24 output, and the author's acceptance |

**A discrepancy, recorded and not edited.** PR #27's body, on GitHub, has its test plan's last item ticked: "[x] After
the merge: the graph's picture after, and the eleventh golden round". Neither exists: no `after/` picture, and
`docs/golden-questions.md` ends at the tenth round. The inventory's §9 records this as a contradiction. Later on
2026-10-26 the picture after was taken, privately in `.local/`; the eleventh round still does not exist.

## 9. Provenance and gaps

| Class | What |
|---|---|
| **Confirmed artifacts** | the expected lists with their `checked` verdicts and categories; the fixtures and case tables; `gates.py`'s classification; `chain_diff.py` and the loss scripts (persisted copies of originals); the handoffs' rules and results; the golden rounds; the PR bodies (#25, #27) |
| **Reconstructed** | `json_paths_diff.py`; PR #5's plan, whose blockers define "what blocks the merge"; PR #5's A2, A4 and A5 checks |
| **Partially confirmed** | judging the micro graph by case: the rule is documented, the tools exist, and the totals are reported, but the samples and the per-case attribution are lost. The live comparisons: scripts for part, typed commands for the rest |
| **Historical only, with no implementation to recover** | `why_a.py` (only in part in `$T`); C#'s per-case attribution (not found); the first hold-out's and H2b's verdict tools (`prep.py`, `verdict.py`, `categorize.py`, `gab.py`, in `$T` only, not persisted); `go_graph_diff.py` (in `$T`, not persisted) |
| **Never recorded** | the verdict of each "to judge" item of a corpus diff (V09); each judged micro or loss sample (V11, V12); a reason per verdict, anywhere; how each `checked` verdict was reached; which golden answers were checked at the source in each round, beyond the questions' ✅ |

Three of the known gaps stay open:

- the item-by-item semantic judgments of diffs were not recorded (H7-D2 is open);
- the repository holds no file of verdicts besides the expected lists;
- `$T` holds no such file. The `.view.txt` files it names are samples with their source lines, not verdicts, and
  they are lost.

## 10. References

- **The series:**
  - [the validation inventory](validation-inventory.md): V02, V05, V08, V09, V11, V12, V25, and §9;
  - [the resource catalog](resource-catalog.md): each tool's provenance; §4 lists the verdict tools found in `$T`;
  - [the benchmark and statistical protocols](benchmark-and-statistical-protocols.md): the comparisons, their formulas
    and limits;
  - [PR #27's validation state](evidence/pr27-validation-state.md);
  - [PR #5's validation plan](evidence/pr5-validation-plan.md).
- **The scripts:**
  - [`judgment/`](../../indexer/scripts/judgment/), especially
    [`chain_diff.py`](../../indexer/scripts/judgment/chain_diff.py),
    [`samples_view.py`](../../indexer/scripts/judgment/samples_view.py),
    [`edges_join.py`](../../indexer/scripts/judgment/edges_join.py) and
    [`kinds.py`](../../indexer/scripts/judgment/kinds.py);
  - [`live/graph_vs_dry.py`](../../indexer/scripts/live/graph_vs_dry.py),
    [`live/dry_sections.py`](../../indexer/scripts/live/dry_sections.py),
    [`live/dry_compare.py`](../../indexer/scripts/live/dry_compare.py),
    [`live/json_paths_diff.py`](../../indexer/scripts/live/json_paths_diff.py),
    [`live/golden.py`](../../indexer/scripts/live/golden.py);
  - [`gates.py`](../../indexer/scripts/gates.py), [`corpus_metrics.py`](../../indexer/scripts/corpus_metrics.py);
  - [the scripts' README](../../indexer/scripts/README.md).
- **The tests:**
  - [`test_fixtures.py`](../../indexer/tests/test_fixtures.py), [`fixtures/`](../../indexer/tests/fixtures/);
  - [`test_cs_names.py`](../../indexer/tests/test_cs_names.py);
  - [`corpus_expected/`](../../indexer/tests/corpus_expected/);
  - [`test_gates.py`](../../indexer/tests/test_gates.py).
- **The method:**
  - [`AGENTS.md`](../../AGENTS.md);
  - [the decisions](../decisions.md): H2-D4…D21, H5-D10…D17, H7;
  - [the H5 handoff](../handoffs/H5-indexer-refactor.md): the step 5 tables, the results, "What stays lost" and
    "What stays out";
  - [the H7 handoff](../handoffs/H7-regression-gates.md): "What stays judgment", H7-D2;
  - [the H4.1 handoff](../handoffs/H4.1-contributor-path.md): the failure modes, the acceptance test;
  - [the guide](../indexer-evolution.md) §5, in Portuguese;
  - [the corpus report](../corpus-report.md), "How it is measured";
  - [the golden questions](../golden-questions.md);
  - [the graph's schema](../../neo4j/SCHEMA.md).
- **Outside the repository:**
  - PRs #25 and #27 on GitHub;
  - `$T`;
  - `$C/micro-fresh`;
  - `.local/indexer/pr27/`, private and local.
