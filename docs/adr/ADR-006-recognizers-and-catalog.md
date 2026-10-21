# ADR-006 — HTTP rules as recognizers, and the framework catalog as data

**Status:** accepted on 2026-10-20, amended on 2026-10-21 (§3: the facts are `NamedTuple`s, as H5 step 7 built
them) · **Date:** 2026-10-20 · **Phase:** 1 (H5 step 6, built toward H6) · **Records:** H5-D2; the H5 handoff's
target architecture, items 5–7; ADR-004 (where the recognizers run)

## Context

Each language's HTTP scanner decides everything in one flow of `if`s: `_call` in Go, `_read_call` in TS,
`_invocation` and `_controller` in C#. That one flow decides whether a call is a route, a mount, a router handed on,
a generated client or an outbound call:

- a new rule is one more `if`, and the order between the rules is implicit;
- the functions are far past complexity 9, and the modules past 300 lines.

The knowledge about frameworks sits in loose constants per scanner (`GO_REGISTRARS`, `CS_MAP`, `FE_VERBS`,
`TS_ROUTER_VERBS`, `CLIENT_RECEIVER`, …). The facts and pending items that cross files are keyed by text (about 35
keys, such as `"cs.fe-group"`), and their values are positional tuples unpacked far from where they were made.

ADR-004 runs the scanners in the map's workers: early, in map 1, with the package's context, or in map 2. That has
two consequences:

- a scan sees one file's tree, a read-only context and the repo's questions;
- its result is cached under a key that must cover everything the scan reads, and an early scan is accepted only if
  each read gets the same answer from the whole repo.

So the rules need a contract for what they read, not only a shape.

## Decision

### 1. A recognizer per rule

A recognizer is a small object with three members:

- **`kinds`:** the node types it looks at;
- **`callees`:** the callee names it looks at, or none for any callee. Together, `kinds` and `callees` are its cheap
  precondition;
- **`apply(node, scan) -> bool`:** True when the recognizer claims the node.

Each language's scanner becomes a dispatcher over an explicit, ordered list of recognizers:

- it indexes the list by node type and callee name, so a node only meets the recognizers that can match it;
- for each node, it tries the matching recognizers in the list's order;
- the first one that claims the node ends it. That is today's precedence, made visible.

Each recognizer matches one line of the guide's table of rules, and has its fixture case and its unit test.

### 2. What a recognizer may read

This is the contract that keeps ADR-004's cache and early scans sound. A recognizer may read:

- the file's tree and its per-file index;
- the file's directory context, read-only;
- the repo view's questions: an import's target, a manifest's directory, the files under a directory, another
  directory's constants, the directories that define a class, the functions of a name that return a parameter;
- the type service's questions (ADR-005);
- the catalog.

Nothing else is allowed:

- no environment variable, no clock;
- no file read from disk;
- no other file's tree;
- no loop over the directories' contexts. A lookup across the repo is a question, so its answer is recorded. Step 2
  found a Go lookup that looped, which step 1's key did not cover (ADR-004, "What keeps it right").

Each question to the view or to the type service goes through an API that records it with its answer. That record is
what map 2's cache key is made of.

### 3. What a recognizer may write

- **Into the scan's result:** endpoints, calls and warnings.
- **Typed facts and pending items, for compose:** one `NamedTuple` per kind (for example `FeGroup(prefix, parent)`,
  published under the group's name), serializable, with no tree node inside. The text keys and the positional tuples
  go away.
  - A `NamedTuple` keeps a tuple's equality, which let H5 step 7 change no result.
  - So two kinds with equal values compare equal. Facts are kept apart by kind, and a digest encodes the kind's name
    (ADR-004).

Each language's `compose` becomes an ordered list of steps that consume typed facts.

### 4. The framework catalog as data

One YAML file per language, `languages/<lang>/frameworks.yaml`. For each framework it holds:

- the name written on routes;
- the verbs, the registrars and the prefix carriers;
- the app and router constructors;
- the client receivers.

Rules for the catalog:

- **A schema is checked at load time.** An invalid catalog fails loudly in the tests and degrades with a warning
  during indexing, as the conventions do.
- **The conventions' YAML (F0.4.5) extends the same catalog.**
- **The catalog's digest is part of the cache namespace,** because it is extraction config (ADR-004).
- **`built_bundle`'s thresholds become named parameters.**

The catalog holds data, the recognizers hold logic. A rule that needs a scope, a type or a lookup stays in code.

### 5. The layout

`languages/<lang>/http/` is a package with:

- one module per group of recognizers: routes by attribute, routes by call, mounts, clients;
- `facts.py`, the typed facts and pending items;
- `compose.py`.

No function goes past complexity 9, and no module past 300 lines.

### 6. The migration

The migration is H5 step 6:

- **one language per commit**, from the worst to the smallest: C#, Go, TS, Python;
- **each commit is a `refactor:`,** so the gates require `0 repo(s) differ` on the corpus, the hold-out and the micro
  set (H5's protocol, H7's refactor gate);
- **the order of the recognizers reproduces today's order** of the `if`s, and a difference in the corpus is a
  migration defect, not a judgment.

## Consequences

- **Adding a rule** is a recognizer, a catalog entry if it is about a framework, a fixture case and a test. The cycle
  of a change stays the same: fixture, corpus, judgment, expected lists, baseline.
- **The precedence is the list's order,** which can be read, tested and diffed.
- **The dispatcher's index** saves trying every rule on every node.
- **The cache can trust a scan,** because what it reads goes through recorded questions. A recognizer that reads
  something else is a defect, and the cold-equals-warm gate catches it.
- **SCIP (F1.2) changes no recognizer:** it answers the type service's questions (ADR-005).
- **Cost:** a large mechanical move, which has to keep today's order exactly. It is done one language at a time,
  under the refactor gate.

## Alternatives considered

| Alternative | Why not |
|---|---|
| **Keep the methods and their `if`s** | It is what led to the complexity, the implicit order and the rules that cannot be tested alone |
| **Tree-sitter queries alone** | Queries match shapes. They cannot follow a scope, a declared type or another file's constant, which most rules need |
| **Whole rules in YAML** | The logic would become a small language of its own, with no types and no tests. The catalog keeps data and the code keeps logic |
