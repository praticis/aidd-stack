# The Atlas's stable interface

What a consumer outside this repository may rely on. A tool, an argument, a field or a key may be added in any
release. Nothing this page promises is removed, renamed or given another meaning except in an incompatible version
(H11-D1), whose section of `CHANGELOG.md` says so. No test holds this page to the code yet (F1.21): a pull request that
changes a name listed here changes this page in the same diff. An install from `main` between releases gets no such
promise.

## The server

- **Name and transport:** an MCP server named `atlas`, over streamable HTTP, stateless, answering JSON at `/mcp`.
- **Address:** `http://localhost:3005/mcp`. The gateway publishes it on `AIDD_BIND_ADDRESS` (`127.0.0.1` by default);
  the port 3005 and the path are fixed. Only a client that reaches it as `localhost`, `127.0.0.1` or `[::1]` is served,
  whatever `AIDD_BIND_ADDRESS` is: the gateway answers 403 to another `Host`, and to a browser `Origin` from another
  host. The port the server listens on inside its container is not part of the interface.
- **Health:** `GET /healthz`, at the same host and port, answers 200 with `status` `ok` when Neo4j answers, and 503
  with `status` `degraded` when it does not. The body also has `neo4j`, `tenant` (null in multi-tenant mode) and
  `version`, the indexer's version.

## `tenant`

Every tool takes an optional `tenant`. `AIDD_TENANT` sets the server's mode:

- **fixed** (`AIDD_TENANT=<name>`): the server serves that tenant only. `tenant` may be left out, and another value is
  an error.
- **multi-tenant** (`AIDD_TENANT=auto`): the workspace is laid out as `<workspace>/<tenant>/<repo>`, and a repository's
  tenant is the folder right below the workspace. Left out, `tenant` is the only tenant in the graph, or the call fails
  and lists the tenants; `atlas_status` without it lists every tenant.

The tenant's and the repository's names that `atlas_status` lists are the keys the other tools take.

## The tools

Ten tools are promised, by name. Given a `repo`, a `ref` left out is its default branch, and a repository or `ref` that
is not indexed is a tool error whose text lists what is; its wording is not promised. Without `repo`, `find_symbol` and
the tools that take a `symbol` search every snapshot that is not `ephemeral` (a feature branch), an ephemeral one only
when its `ref` is named, and a `ref` is not checked: `find_symbol` answers an empty list, and a `symbol` is not found.
`who_consumes` does not check `repo`. `symbol` takes an id, a qualified name, its `Type.Method` tail or a bare name; one
that matches more than one symbol is an error listing their ids. Pass an `id` back as given: its shape is not promised.

The fields below are the ones a consumer reads; an answer may carry others, which are not promised. Required arguments
are in bold.

| Tool | Arguments | Fields |
|---|---|---|
| `atlas_status` | `tenant` | `mode`, `tenant`, `indexer_version`, `indexer_build`, `refresh` (`stale`, `last_rc`); `repos[]`: `repo`, `default_ref`, `remote.ok`, and `snapshots[]`: `ref`, `sha`, `ephemeral`, `indexed_at`, `outdated`. In multi-tenant mode with no `tenant`, `tenants[]`, each with `tenant`, `refresh` and `repos`, instead of `tenant`, `refresh` and `repos` |
| `repo_map` | **`repo`**, `ref`, `max_entry_points`, `tenant` | `repo`, `ref`, `sha`, `indexed_at`, `stack`, `area`, `architecture`, `conventions`, `modules[]` (`name`, `path`), `entry_points[]` (`id`, `qualified_name`, `file`, `line`), `external_packages[]`, `roles[]` (`role`, `count`, `examples`), `layers[]` (`layer`, `files`, `violations`), `depends_on[]` and `depended_by[]` (`service`, `packages`) |
| `find_symbol` | **`query`**, `match` (`fuzzy`, `word`, `exact` or `regex`), `repo`, `ref`, `kind`, `role`, `limit`, `tenant` | a list: `id`, `repo`, `ref`, `kind`, `name`, `qualified_name`, `file`, `line`, `signature`, `entry_point`, `role` |
| `who_calls` | **`symbol`**, `repo`, `ref`, `limit`, `tenant` | `symbol` (`id`, `qualified_name`, `file`, `line_start`), `callers[]` (`id`, `qualified_name`, `file`, `line`, `strategy`), `dispatched_callers[]` (the same, and `via`), `overrides[]`, `overridden_by[]` |
| `symbol_context` | **`symbol`**, `repo`, `ref`, `limit`, `tenant` | `symbol` (as in `who_calls`), `parent`, `members[]`, `calls[]` and `called_by[]` (`id`, `qualified_name`, `file`, `line`, `strategy`), `file_imports[]` |
| `http_map` | **`repo`**, `ref`, `tenant` | `exposes[]` (`method`, `path`, `framework`, `app`, `handler`, `consumer_repos`), `outbound_calls[]` (`method`, `path`, `caller`, `target_hint`, `env_hints`, `linked_to`: the endpoint it links to, with `service`, `method`, `path` and `confidence`, or null; and `also_linked_to` when it links to more than one) |
| `who_consumes` | **`path`**, `method`, `repo`, `tenant` | `endpoints[]`: `service`, `app`, `method`, `path`, `handlers`, `consumers[]` (`repo`, `caller`, `evidence`, `confidence`, `refs`), `consumer_repos`, `possible_consumers[]` |
| `impact_of` | **`symbol`**, `repo`, `ref`, `max_depth`, `tenant` | `symbol` (as in `who_calls`), `internal_callers[]` (`id`, `qualified_name`, `file`, `hops`, `test`, `via_ambiguous`, `via_dispatch`), `exposed_through[]` (`endpoint_id`, `service`, `method`, `path`, `handler`), `consumers[]` (`service`, `method`, `path`, `repo`, `caller`), `consumer_repos` |
| `ref_diff` | **`repo`**, **`ref`**, `base` (the default branch when left out), `limit`, `tenant` | `snapshots` (each ref's `sha`), `endpoints_added`, `endpoints_removed`, `entry_points_added`, `entry_points_removed`, `http_calls_added`, `http_calls_removed`, `symbols_added`, `symbols_removed`, `symbols_changed`, `summary` |
| `violations` | **`repo`**, `ref`, `severity`, `rule`, `layer`, `limit`, `tenant` | `checked`, `conventions`, `total`, `summary[]` (`convention`, `rule`, `severity`, `n`), `violations[]` (`convention`, `rule`, `severity`, `message`, `file`, `layer`, `line`, `symbol`) |

The values of `strategy` are not promised.

**Limits.** Lists stop at their `limit`, and at 200 where the tool caps it, without saying so; a count beside a list
(`caller_count`, `internal_caller_count`, `production_caller_count`, `test_caller_count`) counts what the list holds.
`violations.total`, `violations.summary` and `ref_diff.summary` count everything. `find_symbol`, `who_calls` and
`symbol_context` stop at `limit`, and at 200; `overrides`, `overridden_by` and `internal_callers` at 200; `repo_map` at
`max_entry_points` entry points and 40 external packages; `who_consumes` at 50 endpoints, each with 3 `handlers` and 20
`possible_consumers`; `impact_of` walks at most 10 hops; `ref_diff` at `limit` for each `symbols_*` list; `violations`
at `limit`.

**How fresh the graph is.** `atlas_status` has no "stale" per repository and ref; it has three signals:

- `refresh.stale`, per tenant: `true` when no refresh of the tenant has finished for more than two refresh intervals,
  so the graph may lag behind the remotes; `null` when none is recorded, as for a tenant indexed on demand. `false` says
  that a refresh finished, not that it succeeded: `refresh.last_rc` is its exit status;
- `remote.ok`, per repository: `false` when the last refresh could not fetch the repository's remote, so its snapshots
  follow the developer's own fetches. `remote` is `null` until a refresh has checked it;
- `outdated`, per snapshot: `true` when another build of the indexer wrote it. The next refresh re-indexes it.

`sha` is the first 10 characters of the indexed commit: compare it with a full hash as a prefix. A repository with no
snapshot is listed with one entry in `snapshots` whose `ref` is `null`, and which has no `outdated`.

**The version.** `indexer_version` is the indexer's version. `indexer_build` is that version and a fingerprint of the
code that shapes the graph; it is what `outdated` compares. Which release is installed is not answered yet (SO19).

**`checked`.** `violations` answers `checked: false` when no convention applied to the snapshot: its list is then empty
and says nothing about the code, and a `note` says so.

## A convention as a file

A convention is a YAML file that a tenant names by path in `atlas.yaml`, which is `~/.aidd/atlas.yaml` on the host:

```yaml
tenants:
  <tenant>:
    conventions:
      - path: /workspace/<tenant>/conventions/orders.yaml
        repos: ["orders-*"]                  # optional globs; every repository when left out
        options: {architecture: <name>}      # optional: one of the file's architectures, instead of detecting it
```

A `conventions` key outside a tenant is ignored.

- **The path is any YAML file inside the workspace, as the indexer sees it:** the indexer runs in a container that
  mounts the workspace, read-only, at `/workspace`, so the path starts there. Environment variables in the path are
  expanded in the container's environment: `$WORKSPACE_PATH` is `/workspace`, and `$HOME` is not the host's.
- **The refresh does not see a change to the file:** it re-indexes a snapshot only when the repository's commit or the
  indexer's build changes (F1.23).
- **The keys:** `id`; `roles`, each with at least one of `extends`, `name` and `declares`, and an optional `layer`;
  `layers`; `architectures`, each with `layers` and an optional `detect` (`together` or `modules`), the one without
  `detect` being the default; `targets`; `dispatch` (`calls`, `handlers`, `method`); `entry_points`
  (`signature_contains`, `members_of` with `signature_contains` and `names`, `roles`); `rules`, each with an `id`, one
  of `forbid_import` (`from`, `to`), `endpoints_only_in`, `http_calls_only_in` or `roles_in`, and a `severity` of
  `error`, `warning` or `info`. The keys and what they select by are promised; the exact declaration text a substring is
  matched against is not. An unknown key is ignored, except under `dispatch`, where it is an error. `route_patterns` and
  `client_patterns` are read too, and are not promised: they will extend the catalog of frameworks (ADR-006).
- **Names come back as written:** the convention's `id`, the names of its roles, layers and architectures, and the ids
  of its rules. In `violations`: `convention`, `rule`, `layer`, `summary[].rule`, `conventions`, and the `rule` and
  `layer` filters; in `repo_map`: `roles[].role`, `layers[].layer`, `architecture` and `conventions`; in `find_symbol`:
  `role` and its filter. `conventions` lists each convention that applied as its `id`, followed by `[<architecture>]`
  when an architecture was picked.
- **Defaults are not promised:** write the file's `id`, each rule's `id` and `severity`, and each `dispatch` entry's
  `method`. A missing `id` is derived (the file's folder, or `rule<n>` by the rule's position), and a missing `method`
  is `Handle`.

## Commands on the host

No consumer program calls these: a person, or an agent at a terminal, runs them by hand. They run the indexer in a
container through `~/.aidd/aidd`, which the installer also links as `~/.local/bin/aidd` when that folder exists and is
writable. Their rename to `aidd atlas …` (N13) arrives with a release.

| Command | What it does |
|---|---|
| `aidd bootstrap --tenant <tenant> --repos <a,b> --yes` | indexes every snapshot the plan of `atlas.yaml` lists for those repositories, without asking |
| `aidd refresh --tenant <tenant> --repos <repo> --wait <seconds>` | re-indexes the snapshots whose commit changed, or that another build of the indexer wrote; `--wait` waits that long for a refresh that is running instead of skipping. With `--repos` it does not update `atlas_status`'s `refresh`, collects no ephemeral snapshot, and exits 75 when a running refresh still holds the lock after `--wait` |
| `aidd index <repo> [--ref <branch>] --ephemeral` | indexes a branch as an ephemeral snapshot, which a full refresh drops once the plan no longer lists it and it is older than `gc_ephemeral_after_days` (30 by default). Without `--ref`, or with the checked-out branch, it indexes the working tree as it is, uncommitted changes included, under `HEAD`'s sha |
| `aidd index <repo> --dry-run --out <file>` | extracts and resolves without writing the graph, and writes the payload as JSON to `<file>`, a path in the container: one under `/var/lib/aidd/state` lands in `~/.aidd/state` |

## Not part of this interface

- `cypher_readonly`, an eleventh tool: it runs read-only Cypher, and the graph's schema (`neo4j/SCHEMA.md`) is not
  promised. In multi-tenant mode, `ATLAS_RAW_CYPHER=off` withdraws it.
- `inherited` callers, which the description of `who_calls` names and its answer does not carry.
- The installer's handling of a repository's `.mcp.json`: today it replaces the whole file, other servers' entries
  included (SO16).
- A convention written in Python, as a class registered as an entry point and named by `id` in `atlas.yaml`.
- The MCP prompt that teaches the graph enters this page with F1.22.
