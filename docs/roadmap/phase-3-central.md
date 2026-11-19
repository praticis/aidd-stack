# Phase 3 — Central and continuous (the end goal)

> The Atlas served to a team from one central server, kept current by each repository's CI, with authentication per
> tenant. The fields are H10-D2's; the map of the roadmap is `docs/ROADMAP.md`.

- [ ] F3.1 A central server (Neo4j and the `atlas` MCP) with backup; a compose "server profile"
  - **Sketch:** missing what makes it a server: its address, who reaches it, how a backup is taken while it serves
    (Neo4j Community dumps a stopped database), and whether a restore beats indexing the same commits again; first step:
    a dump of the graph of the repositories `mcp-it` indexes, loaded into an empty Neo4j, timed against indexing them
    again, and the two graphs compared
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** nothing
  - **Not to do:** serve it beyond the machine before each client authenticates and is held to the tenants its token
    grants
- [ ] F3.2 A CI job per repo: on every merge to `main`/`develop` → `aidd index` → push to the central server (a
  self-hosted runner with a SCIP cache)
  - **Sketch:** missing what is pushed (the graph, or the dry-run artifact the server loads), the runner's contract, and
    the credential the push uses; first step: a loader that writes one repository's dry-run artifact (`aidd index
    --dry-run --out`) into an empty graph, and the graph it leaves compared, record by record, with a direct index of
    the same commit
  - **Verified by:** the author (the CI and the self-hosted runner are his)
  - **Depends on:** F3.1
- [ ] F3.3 A scheduled/event-driven linker on the central server; a report of new edges and divergences
  - **Sketch:** missing the report's form and what a divergence is: the linker already runs after an index, a bootstrap,
    a refresh that changed something and `aidd link`, and `ref_diff` already lists the endpoints a branch adds or
    removes; first step: the links one refresh added and removed, counted by comparing the tenant's links before and
    after the linker rebuilds them
  - **Verified by:** anyone
  - **Depends on:** F3.1
- [ ] F3.4 MCP auth per tenant (a token per dev/team behind a reverse proxy); the tenant filter injected, never
  trusted to the client
  - **Sketch:** missing where the proxy lives, how a token is issued and revoked, what it grants, what the server's
    address and the `Host` check, which `docs/atlas-interface.md` promises for the local server, become on a central
    one, and what a token's holder sees of the tenants it does not grant: `atlas_status`'s list, an error that lists
    tenants, and `cypher_readonly`, which `$tenant` does not bound; first step: what a token grants (one tenant, or
    several), how a tool's `tenant` argument is checked against it, and what a call that leaves it out answers
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** F3.1
  - **Not to do:** change what the `tenant` argument means: a tenant the token does not grant is refused, never replaced
    by another; list, or answer from, a tenant the token does not grant
- [ ] F3.5 A coverage/freshness dashboard: indexed repos, index age, % of macro edges by confidence
  - **Sketch:** missing where it is shown, and what it adds to `atlas_status` and `aidd status`, which already give the
    indexed repositories and their age; first step: the share of macro edges by confidence, per tenant, counted on the
    graph of the repositories `mcp-it` indexes
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] F3.6 Retention: the runs kept per `(repo, ref)` are bounded, and a persistent snapshot whose ref is gone is
  collected, as an ephemeral one is
  - **Sketch:** missing how many runs to keep, and how long a persistent snapshot outlives its ref: today a refresh
    keeps it, names it while its repository is in the workspace, and `aidd wipe` removes it; first step: what a dead ref
    is: a branch deleted from its repository, one the ref policy no longer lists, or a repository that left the
    manifest, whose `Repo` node not even `aidd wipe` removes
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** collect a snapshot of a repository the refresh could not read
- [ ] F3.7 The installer points the `atlas` entry of a repository's MCP configuration at the central server when
  configured; local stays as the offline fallback
  - **Sketch:** missing how the central and the local server share the one name `atlas`, how the installer changes an
    `atlas` entry that holds another address, which SO16 keeps, and where a client's credential lives, since it cannot
    go in a repository's MCP configuration; first step: the one `atlas` entry, whose address the installer writes from a
    setting, and what a client does when the central server does not answer
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** F3.1, F3.4, SO16
  - **Not to do:** write a credential into a repository's MCP configuration; write a second `atlas` entry
