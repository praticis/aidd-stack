# ADR-005 — One type service for the resolver and the scanners

**Status:** proposed · **Date:** 2026-10-20 · **Phase:** 1 (H5 step 5, built toward H6) · **Records:** ADR-002's
addendum (`needs-resolver`); the H5 handoff's target architecture, item 3; ADR-004 (where it is built)

## Context

The indexer answers "what is the type of this value" in two places, each in its own way:

- **The micro resolver** works from each language's `file_facts`, with indexes built in `resolve_setup`: types by
  name, Go's files by directory and method sets (PR #9).
- **The HTTP scanners** have their own answers:
  - Go: `_value_type` and `_field_type`, which runs over every file's facts in the directory;
  - C#: `_declared_type` and `_reaches_fast`;
  - Python: `_router_class`;
  - TS: `_client_of`;
  - the repo view: `classes_named`.

  Go's `_declared_type` (the resolver's) and `_value_type` (the scanner's) read the same receivers, parameters and
  composite literals twice.

SCIP (F1.2) is going to answer this question, and today it would have to come in at about ten places.

ADR-004 adds two constraints:

- **The type facts travel.** They are made in map 1, from one file. They are joined in the reduce, from every file's
  summary. They are read in map 2, by a scan whose cache key must cover what it read.
- **A broad read makes the cache coarse.** A scan that reads every file's facts in its directory depends on all of
  them. Step 1 found that this is what drives D's tail on Go's large packages: adding a method anywhere in the package
  re-runs every scan in it.

## Decision

### 1. Two levels of answer

- **Inside a file, in the map:** the per-file index answers local questions, such as a local's type from its
  assignment, a receiver or a parameter. It is the same code for the resolver's call receivers and for the scanners.
- **Across files, the `TypeIndex`:** built once per repo in the reduce, from the type facts of every summary. It is
  read-only, and the resolver and map 2's scans use the same instance.

### 2. The type facts

Each language's `file_facts` become typed, serializable values with no tree node:

| Language | Facts |
|---|---|
| Go | struct fields and embeds, interfaces, method sets, function signatures, import aliases |
| C# | types with their bases and members' types, namespaces |
| TS | classes, the clients a file creates |
| Python | classes with their bases |

A fact names types as the file wrote them. The `TypeIndex` resolves the names, with the file's imports, package or
namespace.

### 3. The questions

The `TypeIndex` answers these questions:

- `type_named(name, from_file)`: the type a name means, seen from a file;
- `field(type, name)` and `method(type, name)`;
- `bases(type)` and `implementers(interface)`;
- `return_type(function)`, when it is declared.

Each answer is a value or `Unknown`, with a reason. `Unknown` is what `needs-resolver` is today (ADR-002's
addendum), and the gap stays recorded, with no heuristic.

### 4. A question is a dependency

When a scan in map 2 asks the `TypeIndex` a question, the question and its answer are recorded with the scan's entry,
like the questions to the repo's structure (ADR-004). The entry is a hit only while each answer still holds.

The scan then depends on, for example, the type of the field `Server.Router`, and no longer on every struct of its
directory. Every file's facts leave the directory's context digest.

### 5. SCIP

In F1.2, a SCIP implementation answers the same questions for a repo that has an index. The index's digest joins the
cache's namespace. The recognizers (ADR-006) and the resolver do not change.

## Consequences

- **One implementation per language** of "declared type", shared by `CALLS` and HTTP. H5 step 5 replaces Go's
  `_value_type` and `_field_type`, C#'s `_declared_type` and `_reaches_fast`, Python's `_router_class`, TS's
  `_client_of` and `classes_named` with questions.
- **D's tail shrinks.** Measured on the step 1 replay of mattermost, with no key missing a change:

  | Directory context | Scans a push re-runs, median / p90 |
  |---|---|
  | Every fact of every file (D per package, as built) | 40 / 438 |
  | Cut to the facts a scanner reads: Go's struct fields | 10 / 300 |
  | Every lookup recorded as a question, with its answer (C) | 8 / 108 |

  - Most of what is left in the cut row comes from the functions by name. A function added anywhere in a package
    changes its directory's context.
  - Recording that lookup as a question too, "the function named X in this directory", brings D to C's level. It
    adds no read tracking beyond the questions' API.
- **The resolver's indexes from PR #9 move into the `TypeIndex`,** and stay built once per repo.
- **Cost:**
  - every question is recorded in map 2, as the view's are. Step 1 measured a median of 2–3 recorded questions per
    scan;
  - a facts schema per language, versioned with the build.

## Alternatives considered

| Alternative | Why not |
|---|---|
| **Keep two type systems** | Two answers to one question drift, and SCIP would come in at about ten places |
| **The `TypeIndex` in each worker, built from the files a scan needs** | The worker would need other files' facts in any case, and the reduce builds them once |
| **Scans read every fact of their directory, as today** | It is what makes D's key coarse on large packages |
