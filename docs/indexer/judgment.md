# Judgment: deciding whether a difference is right

Every comparison shows what changed; none says whether it is right. This page is how a difference becomes a verdict.
The commands that produce the differences are in [method.md](method.md).

## 1. Who judges

- A person, or an agent reading the source. Never a verdict an LLM grades on its own result, and never one a gate
  reads.
- The agent that wrote the change does not judge it: its reading is a proposal. An agent that did not write it may
  judge by reading the source, and the author decides whether that is enough to open a gate.
- For the hold-out, no item at all: it is read only in aggregate.

## 2. Where the verdict is made

| Layer | The tool shows | The verdict is made |
|---|---|---|
| HTTP corpus | ids added, removed or re-resolved (`corpus.sh`, `gates.py` "to judge") | at the item's evidence line, at the pinned sha |
| Against a list | false positives and negatives, precision and recall | at the source; a list is corrected with evidence, in its own commit |
| Micro graph | records gone and new (`micro.py`); sites by kind (`chain_diff.py`) | at the sample's source line, by case |
| Losses | edges to extension methods that went away (`csharp_extensions.py`) | by the receiver's declared type, at the source |
| Live dry-runs | differences per section (`dry_sections.py`) | at the source, locally; reported by snapshot number |
| Live graph | whether the graph holds a dry-run (`graph_vs_dry.py`) | nowhere: it checks the writer, not the extractor |
| Golden answers | equal, or different only in time and build fields | the MCP's answer and the Cypher's agree, and a sample was checked at the source |

## 3. What a verdict needs

- **The evidence line:** `repo:file:line` at the pinned sha, read against what the application serves or requests.
- **Both sides' code:** each side's sha and tree, the baseline or micro base, and the image id.
- **The rule that decides it:** the language's (for C#, "a name is what its nearest declaration in scope makes it";
  "only a declared type counts") or the list's.
- **Never a guess.** What needs a type not declared in sight is `needs-resolver`: left out of the rule, recorded as a
  gap with a case, and left to SCIP.

## 4. The terms

| Term | Meaning |
|---|---|
| Gain | a new item that is right: matches the list, or a case that passes |
| Loss | an item gone: judged as a right one lost, or a wrong one removed |
| False positive, false negative | an extracted item outside the list; an expected item not extracted. Each has a category |
| Ambiguous | no verdict exists. `-ambiguous` (and `~amb`) is a property of an edge: the resolver found several candidates by name |
| Candidate | a difference not yet judged |
| Regression | what blocks (below) |

What blocks or passes:

| Situation | Status |
|---|---|
| Any difference under a refactor | a defect of the step. No judgment needed: the rule is identity |
| A gate fails (precision lower, a win lost, hold-out changed, micro changed without `graph-change`) | the PR fails; then judged whether the extractor regressed or the list is wrong |
| A corpus item "to judge" | candidate until judged at its evidence line |
| A micro difference in a change of behavior | candidate until judged by case. **One wrong item in a case blocks the PR** |
| A loss of the PR's own kind | fixed in the PR. Another kind is a gap with a case |
| A live difference outside the change | blocks unless explained |
| A new hold-out difference between H5's code and the commit before | an H5 regression, unless a judged case explains it |

## 5. The protocol

1. **List every changed record,** not only the counts, outside the scratchpad.
2. **Fix both sides:** shas, tree, image id, run labels. Write them next to the judgment.
3. **Read the source.** `show.py` prints the sampled sites' lines. For live snapshots read the private source locally
   and record only numbers.
4. **Sample.** A seeded sample per case and repo, drawn from sorted sites. `chain_diff.py` draws `N` per kind across the
   repos it is given: give it one repo at a time for a sample per repo. Sizes are in method.md §4.4.
5. **Decide.** `right`, `wrong` or `undecided`. When the source cannot decide, `undecided`, and a gap with a case.
6. **Record.**
   - a list edit, with `file:line` evidence, in its own commit;
   - a case as a test: a strict xfail with its reason on the wrong side, before the fix;
   - a gap under "What stays out", with a case to start from.
7. **Give it a status:** blocks, fixed in this PR, a debt that does not block (registered in `docs/tech-debt.md` with a
   strict xfail test), a gap with a case, or explained.
8. **Report judged and unjudged apart,** with the sample sizes. Tick a test-plan item only when it is done.

A sample drawn now from a past diff is a new judgment, dated now, never the past one. A new case says when it was
written and from what. Nothing private goes into a case: public corpus repos, or synthetic code.

## 6. The verdict record

Not yet decided (H7-D2); recommended. One row per item judged, one per item left unjudged:

| Field | Content |
|---|---|
| `item` | the layer, the repo (public, or a snapshot number), `file:line`, the record before and after |
| `sides` | each side's sha and tree, the baseline or base label, the image id |
| `source` | what was read: the line, with its link at the pinned sha |
| `rule` | the language's or the list's rule, by id or by case |
| `verdict` | `right`, `wrong`, `undecided` or `unjudged` |
| `class` | gain, win lost, false positive or negative with its category, gap, defect |
| `basis` | `source-read`, `automatic` (a list match), `historical-note` or `inferred` |
| `by`, `date` | who judged, and when |
| `record` | the test, fixture, list commit or gap entry that holds it |

## 7. What a comparison cannot tell you

- A count of added typed edges does not say how many are right. "0 differ" says nothing changed, not that anything
  is right.
- `graph_vs_dry.py` covers `CALLS` only and checks the writer. The other 14 lists of a picture have no script.
- `dry_sections.py` compares six sections (`files`, `symbols`, `calls`, `imports`, `endpoints`, `http_calls`) by a few
  keys each: "identical" means identical in those, by those keys. Modules, packages and violations are not compared.
- A historical result whose inputs are missing is evidence that it was reported, not that it would reproduce.
- The per-site attribution that ties a changed site to the rule that explains it does not exist in the repository
  (method.md §7). Until it does, a case is read from the rule and the commit.
