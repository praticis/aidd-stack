# Design a change: contracts, boundaries and proof

How a refactor or a new implementation is designed anywhere in this repository: the indexer, the MCP, the skills,
the setup. The design comes before the plan, and the plan shows it. How a change to the indexer is then proven is in
[`indexer/method.md`](indexer/method.md); how a difference is judged, in [`indexer/judgment.md`](indexer/judgment.md).

The design starts with one question: is there a level above the one the work is about to be written at? Three signs
that the work sits one level too low:
- a list of cases;
- a tool per language;
- a rule copied into a second module.

Each one usually re-implements something the system, or the language itself, already answers. The answer is found in
three places: the **contracts** the change reads and keeps, the **boundaries** that say where each piece of knowledge
lives, and the **proof** that it is right. A reviewer asks the same questions of a plan or a diff. "None" is an
answer, with its reason.

## 1. Contracts

1. **What are the questions, really?** Split the change into independent questions and answer each one once.
   - Too low: one table of cases mixes two questions, so one of them gets answered by enumeration.
2. **Who already answers them?** Look for a contract the system keeps between its stages: a model record, a hook's
   output, an index. Look also for a reference outside the system: the language's reference implementation, a
   specification, a standard library.
   - Too low: a new answer written next to one that exists, or a tool that calls another module's internals.
3. **What does it couple to?** The narrowest stable contract. When two sides must agree (two versions of the code,
   the resolver and the scanner), they read the same contract.
   - Too low: depending on how another module works inside, which its next refactor breaks.

A module reads another one's records (`CallInfo`, a `TypeIndex` answer), never its private functions. A tool that
compares two versions of the code reads the contract both of them keep, so a refactor of either side does not break
it.

## 2. Boundaries

4. **Where does each piece of knowledge belong?** What depends on a language, a framework or a convention lives in
   that one's module.
   - Too low: a core function that lists a language's syntax or a framework's names, or the same rule in two language
     modules.

The core is universal: it names no language, framework, convention, tenant or project. It reads each of them through
a hook or a contract (ADR-003). What is specific lives at the edge that owns it: a language's module, a convention, a
skill.
- When two language modules need the same rule, it becomes a hook in the core, with one answer per language. The core
  asks; each language answers.
- A core function that holds one language's node kinds, or a framework's names, holds a rule that belongs to an edge.
  A test counts the core's names that only one language's grammars have (TD-023, `docs/tech-debt.md`).

## 3. Proof

5. **What proves it?** An independent reference, over all of the real data.
   - Too low: only examples chosen by whoever wrote the change.
6. **What does it leave unknown?** An answer is a value, or `Unknown` with its reason.
   - Too low: a guess where the facts in sight do not decide.

A design is proven against something that did not come from the same reasoning:
- **a parity:** the output of the code or tool it replaces, on the same real inputs;
- **an oracle:** the reference implementation of what it models, such as a language's own compiler or standard
  library;
- **a measured corpus:** with its expected lists.

Run the proof over all of the real data where that is feasible, not over a sample, and write the reference's known
deviations next to the check. When the ADRs keep a reference out of the product (a second parser, or a runtime the
graph would depend on), it stays in the checks.

When the facts in sight do not decide, the answer is `Unknown` with a reason, never a guess (ADR-002's
`needs-resolver`, ADR-005). The reasons are counted, and the counts say what the next investment is worth: F1.2's
SCIP, or a new rule.

## 4. In the plan

Every plan for a refactor or a new implementation has a section called "Contracts, boundaries and proof", which
answers the six questions:
- the questions;
- the contract or reference it uses, and what it couples to;
- where each piece of knowledge lives;
- how it is proven;
- what stays unknown;
- the alternative one level up that was considered, and why it was taken or not.

The author approves the plan before a branch is created. A choice that sets the direction is recorded as a decision
(`docs/decisions.md`).

## 5. Two examples

**The attribution probe (H5-D21).**
- The plan: one probe per language, each calling its language's typing function.
- The contract: the extractor's record of each call (`CallInfo.receiver_type`) is the contract between extraction and
  resolution, the same in every language. One probe reads it for all of them, and a refactor of a language's typing
  cannot break it.
- The proof, a parity: on Go's change of local typing, it printed the same output as the Go probe it replaced, byte
  for byte.

**Python's types (H5-D22).**
- The plan: a table of cases (`self`, `x = C()`, an annotated parameter, a closure).
- What was wrong with it: the table mixed two questions, which binding a name refers to and what type that binding
  declares, and answered the first by enumeration. The core's generic scopes already got that question wrong in
  Python: they bound a comprehension's variable to an assignment outside it.
- The boundary: Python's scoping is modeled once, in Python's module, and shared by the resolver and the scanner. A
  small table of declaration forms sits on top, and modules and classes are both namespaces, reached through one hook
  in the core.
- The proof, an oracle: CPython's `symtable`, over every Python file of the corpus, kept in the checks.
