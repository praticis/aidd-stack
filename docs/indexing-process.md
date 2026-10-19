# The atlas indexing process — proposal (under discussion)

> Status: **decided and implemented for the `local` source** (2026-09-11, F0.3.5). Remote providers and the scheduler
> wait for F1. D9 solved without mirrors: refs are materialized with `git archive` from the remote-tracking refs of
> the dev's clone. D11 simplified: optional `areas` in the manifest. Context: F0.3 validated (`aidd index <repo>`
> works), but indexing is today a manual command, repo by repo, over whatever branch is checked out. It has to become
> a process.

## 1. The problem

Three questions were left open after F0.3:

1. **How the tenant's whole portfolio gets into the atlas** at install time (bootstrap), without depending on what
   each dev has cloned.
2. **Which branches to index**: today it is "the one checked out"; we want `main`, `develop` and only the branches
   with recent activity — never all of them.
3. **How to keep it current** until pipeline triggers exist (Phase 3).

## 2. Principle: separate the *source* from the *workspace*

The dev's workspace (`WORKSPACE_PATH`) is volatile — a checked-out branch, dirty files, only the repos they cloned.
It does not serve as the source for the tenant's atlas. The proposal is for the atlas to have **its own source**: a
mirror of repositories under aidd's control.

```
~/.aidd/_docker/mirror/<tenant>/<repo>.git     ← bare clones, updated by `aidd sync`
~/.aidd/atlas.yaml                              ← manifest: sources, selection, ref policy
```

With mirrors, `aidd index <repo> --ref develop` does a temporary `git worktree add` of the requested ref, indexes it
and discards it — independent of what the dev has open. The dev's workspace still serves the **ephemeral** case:
indexing the card's branch in `refine-tech`.

## 3. The `atlas.yaml` manifest (per install, sections per tenant)

```yaml
tenants:
  <tenant>:
    sources:
      - type: local            # repos already cloned in the dev's workspace (fast bootstrap, no network)
        path: ${WORKSPACE_PATH}/<tenant>
      - type: github           # or gitlab | azure-devops | bitbucket — each tenant picks its own
        org: <github-org>
        token_env: GITHUB_TOKEN_<TENANT>   # the env var's name, never the value
        include: ["*"]         # globs over the repo name
        exclude: ["*-archive", "poc-*"]
        skip_archived: true
    refs:
      always: ["main", "master", "develop"]     # indexes the ones that exist
      patterns: ["release/*"]                    # optional
      active:
        max_age_days: 14       # branches with a commit in the last N days…
        max_per_repo: 5        # …limited to K per repo, marked ephemeral: true
        exclude: ["dependabot/*", "renovate/*", "docs/*", "ci/*", "cd/*", "pipeline/*"]
      gc_ephemeral_after_days: 30
      overrides:             # optional: a per-repo policy (exact name or glob; overrides only what it declares)
        <project>:
          always: ["main"]   # e.g. `develop` abandoned in this repo — it leaves the policy without touching the tenant
        "legacy-*":
          always: ["master"]
          active: false      # no active branches for these
    schedule: "0 */6 * * *"    # automatic refresh (aidd sync + index --changed) until Phase 3
```

Rules: no implicit default tenant (D7); tokens only by reference to an env var; `local` and remote sources may
coexist (the remote is the source of truth when both have the same repo).

## 4. Commands

| command | does |
|---|---|
| `aidd sync [--tenant T]` | lists the repos in the sources (provider API), creates/updates bare mirrors (`git fetch --prune`), writes `Repo` with `url`, `default_ref`, `archived`, `last_activity` |
| `aidd plan [--tenant T]` | shows what **would** be indexed: repos × refs by the policy, with a reason (`always`, `active: 3 commits/9d`) — without touching the graph |
| `aidd bootstrap [--tenant T] [--all \| --repos a,b,c]` | `sync` + `index` of everything `plan` listed; idempotent; resumable |
| `aidd index <repo> [--ref R] [--ephemeral]` | already exists; starts accepting a real `--ref` (a worktree of the mirror) besides the workspace |
| `aidd refresh` | only what changed: compares the mirror's `commit_sha` with the `Snapshot`; re-indexes the differences; GC of expired ephemeral snapshots |
| `aidd status` | already exists; gains a `stale` column (mirror ahead of the snapshot) |

## 5. Where it goes in `install.sh`

After the infra step (compose up) and before distributing `.mcp.json`:

```
=== 4. Atlas bootstrap ===
  1) Index the local workspace now (repos already cloned)          ← default
  2) Configure a remote source (GitHub/GitLab/Azure DevOps) and index the portfolio
  3) Skip (run `aidd bootstrap` later)
```

Option 2 asks for the provider, the org/group and the name of the token's env var, writes them to `atlas.yaml`, runs
`aidd plan` and asks for confirmation ("42 repos × 2.3 refs on average ≈ 97 snapshots — index all, or choose?").
`install.sh` is still the **upgrade** command too: re-running it syncs `~/.aidd`, re-applies the schema and rebuilds
the images (including the `tools` profile).

## 6. Phases

| when | what |
|---|---|
| **F0.3.5 (now)** | `atlas.yaml` + the `local` source + ref policy + `aidd plan/bootstrap/refresh` + an option in `install.sh` + a real `--ref` through a worktree |
| F1 | remote providers (GitHub first; GitLab/Azure DevOps next), bare mirrors, `aidd sync`, a scheduler in the compose file |
| F2 | governance: read `catalog-info.yaml` (Backstage) / CODEOWNERS → `Domain`, `System`, `Team` nodes, an `OWNS` edge; optionally integrate with Backstage or Atlassian Compass as the catalog source |
| F3 | pipeline triggers (a push to a protected branch → `aidd index`), the central server replaces the scheduler |

## 7. Decisions

- D8 **Open** — the providers in use per tenant; needed only in F1.
- D9 **Replaced by D15 (2026-10-12)** — the refresher keeps a bare mirror per repo for the `local` source too and
  mounts the workspace read-only (see the ROADMAP, the "Security and operations" track). Original text: no mirrors
  for the `local` source: the indexer does `git fetch --all --prune` (SSH credentials/.gitconfig mounted as in
  `mcp-git`) and materializes refs with `git archive <sha>`; the working tree is never touched. Bare mirrors only
  with remote providers (F1).
- D10 **Solved** — defaults `14 days / 5 per repo / GC 30 days`, editable in `atlas.yaml`.
- D11 **Simplified** — optional `areas:` in the manifest (name → repos/globs), used by `aidd plan` to group and
  written to `Repo.area`. `Domain`/`System`/`Team` nodes and Backstage/Compass wait for F2.
