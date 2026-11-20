# Operations — roadmap

> How the Atlas is kept current, kept safe, installed and released: the continuous update (`U`), and security,
> operations, installation and release (`SO`). Security is a prerequisite for adoption by organizations. The fields
> are H10-D2's; the map of the roadmap is `docs/ROADMAP.md`.

## Continuous update

- [x] U1 **Service credential** (D13): a **read-only** PAT in `~/.aidd/secrets/git-token` (600), collected in step 6
  of `install.sh`; the wrapper uses it through `GIT_ASKPASS` and rewrites ssh→https remotes only for the fetch. Your
  personal key stays out of the scheduler. Validated: `fetch: ok (service)` on the 6 repos. Note: fine-grained needs
  admin approval in the org — classic (scope `repo`, short expiry) works as a bridge; a **GitHub App** is the target
  for the server (F1)
- [ ] U4 **Event trigger (F3)**: a webhook/CI on a push to a protected branch → `aidd index <repo> --ref <branch>`;
  replaces the refresher's polling on the central server
  - **Sketch:** missing what receives the event (an endpoint of the central server, or a step of each repository's own
    CI), how the event proves where it comes from, whether the refresher's polling stays as a fallback for a missed
    push, and what `atlas_status`'s `refresh.stale`, which counts refresh intervals, says when no polling runs; first
    step: a function that maps a push event's repository address and branch to a repository the manifest's sources
    select and a ref its ref policy lists, by each repository's `origin`, tested on the payload GitHub documents for a
    push
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** F3.1
  - **Not to do:** index a repository the manifest does not select, or a ref its ref policy does not list, because an
    event names it
- [x] U5 **In-container fetch**: became the default path with the refresher (D15) — a mirror per repo, the PAT as a
  file through `git-askpass.sh`. Validated with a local remote in the e2e; **still to validate against GitHub with a
  real PAT**

## Security and operations

- [ ] SO7 **Strong isolation between tenants**: today one Neo4j holds every tenant (Community has no RBAC and no
  multiple databases) and every `atlas` tool accepts `tenant`. For whoever serves several organizations on the same
  machine: one Atlas stack per tenant (a compose project with its own ports) or, on the server (F3.4), the tenant
  injected by the token
  - **Sketch:** missing the route, and, for a stack per tenant, the port and the names of a second stack:
    `docs/atlas-interface.md` fixes the port 3005, and the compose file fixes its project's and its containers' names;
    first step: what a second Atlas stack on one machine shares or clashes with in the first (the compose project's
    `name:`, each `container_name`, each published port, the volumes, the install folder, the `atlas` entry the
    installer writes), each with whether `docs/atlas-interface.md` promises it
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** F3.4
  - **Not to do:** change the address or the name of the server that `docs/atlas-interface.md` promises, outside an
    incompatible version
- [ ] SO8 **Authentication on the `atlas` MCP** (a per-dev token at the gateway; today the defense is localhost +
  Host/Origin) — ties in with F3.4; careful: the token cannot go in the MCP configuration the installer writes into
  the repos
  - **Sketch:** missing where the token lives on a developer's machine, how each client sends it, and whether the
    gateway requires it, which refuses a client it serves today and so comes only in an incompatible version, or only
    where an install sets one; first step: for each client whose configuration the repository ships (`setup/.mcp.json`,
    `antigravity/mcp_config.json`), whether it can send a header whose value it reads from the environment
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** F3.4
  - **Not to do:** write the token into a repository, the graph or a log: only the name of the variable that holds it
- [ ] SO9 **Prompt injection through the graph's answers**: third-party code reaches the agent as text it did not
  write (a symbol's `doc` and `signature`, a violation's `message`, the docstrings `find_symbol` matches). Name the
  answer fields that carry code text, so a consumer treats them as data; never filter or rewrite that text by heuristic
  - **Sketch:** missing whether those fields are named in `docs/atlas-interface.md` or marked in each answer, and which
    they are beyond the three the text names: a name, a path and a route are written in the code too; first step: index
    a fixture whose docstrings, signatures, string literals and names carry one marker, call every tool on it, and list
    the answer fields the marker reaches
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] SO10 **Pinned supply chain**: digests (`@sha256`) on the images, a lock with hashes (Python `--require-hashes`);
  the indexer's `pyproject.toml` dependencies are still ranges
  - **Done when:** the third-party images and the base images are pinned by digest, each at the version its tag names
    today, and the Python dependencies of each image the compose file builds install from a lock with hashes; a test
    fails on an image, a base image or a dependency that is not pinned
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** move an image with a volume to another version in the pull request that pins it
- [ ] SO11 **What is disposable**: once only Neo4j and the mirrors hold state, everything the Atlas keeps is rebuilt
  from the repositories; say so, and say what the host must keep (`atlas.yaml`, `.env`, the read-only token)
  - **Done when:** a page of `docs/` says what `docker compose down -v` deletes, what the host must keep, and what a
    refresh does not rebuild (a snapshot indexed by hand outside the ref policy, one whose branch is gone, the history
    of runs); on an install made for the check, after `down -v` and one refresh, `atlas_status` lists every snapshot the
    plan listed before, at the same `sha`, with no push to those repositories in between
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N7, N8
- [ ] SO12 **Scale with N devs**: N laptops × M repos every 15 min hit GitHub's secondary rate limit; backoff on a
  fetch failure; a central server (F3) for larger organizations. Mirrors double the repos' disk — GC of mirrors of
  repos that left the workspace
  - **Sketch:** missing the delay after a failed fetch and its bound, how long a mirror of a repository that left the
    workspace is kept before it is removed, and what `remote.ok` says while a fetch waits; first step: a test against a
    local remote that refuses, which shows that today a failed fetch is tried again on the next round, at the same
    interval, and that a mirror whose repository left the workspace is still there after the next refresh
  - **Verified by:** anyone
  - **Depends on:** nothing
  - **Not to do:** remove the mirror of a repository the workspace still has because its fetch failed
- [ ] SO14 **Validate on WSL and native Linux** (the e2e was on macOS): `AIDD_UID`/workspace permissions (umask 077
  leaves the container without read access), Docker autostart; a real PAT against GitHub (U5)
  - **Done when:** on WSL and on native Linux, `setup/install.sh` then `setup/install-check.sh` ends in "All checks
    passed" with a workspace made under umask 077, and again after a reboot with no manual start; `atlas_status` then
    lists a snapshot of every repository of that workspace, and answers `remote.ok` true for one of them, a GitHub
    repository fetched with a real read-only token
  - **Verified by:** the author (no CI job runs WSL or holds a real token)
  - **Depends on:** U5
- [ ] SO15 **Data flow / threat model** for adopters: what leaves the machine (what the LLM reads; telemetry off),
  where secrets live, what each container of the Atlas can touch. `mcp-neo4j` (debug profile) still has write Cypher
  on `127.0.0.1:3004` — for debugging only
  - **Sketch:** missing the page's place and a check that its claims match the compose file; first step: a table of each
    service of `docker-compose.yml`, with what it mounts, the ports it publishes and on which address, and the secrets
    it reads, by their variables' names
  - **Verified by:** anyone
  - **Depends on:** N10

## Installation and release

- [ ] SO16 The installer merges its entries into a repository's MCP configuration; today it replaces the whole file
  - **Done when:** the installer merges, by name, the entries of the template of the tree it installs, and never
    removes or edits another one; an entry of the same name with another address is kept, and the run says so; a run
    on a repository whose `.mcp.json` has another server keeps that entry
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N2
- [ ] SO17 A CI job checks the install; today a pull request that touches only `setup/`, the compose file or the
  gateway runs no check of them
  - **Done when:** the job `install` runs on every pull request, and its first step decides whether there is something
    to check: a change to `setup/`, `docker-compose.yml`, `gateway/`, `neo4j/`, a `Dockerfile`, `CHANGELOG.md`, a
    folder the installer copies, or the workflow itself. Then it checks the syntax of the scripts and of the compose
    file and runs the tests of `setup/`. `main` requires the job: the author adds it to the ruleset once it is on `main`
  - **Verified by:** anyone
  - **Depends on:** nothing
- [ ] SO18 A release is published by a pull request that moves the line of the entry script naming it
  - **Done when:** a pull request that changes the release the entry script names changes nothing else, and it either
    raises the line or takes it back to the value it had just before. Raising, its check refuses a name that is not a
    `vX.Y.Z` tag on the first-parent history of `main` or of a maintenance branch `maint/X.Y`, a version not above the
    one the line names, a version with no dated section in `CHANGELOG.md`, and a version that drops a service or
    changes the image of a service with a volume without an incompatible step. A release of an older line joins the
    list of published releases without moving the line. The check computes the build the tag gives and refuses a pull
    request that records another one. A workflow started by hand takes a version and a commit, runs those checks and
    the part of the rehearsal that fits a runner, computes the build and opens that pull request; the script it runs
    also runs on a machine. The tag is the author's, signed, and the merge is what publishes. `docs/indexer/method.md`
    says what a release is and who publishes one
  - **Verified by:** anyone
  - **Depends on:** N1, SO17
- [ ] SO19 The release a consumer checks; today `atlas_status` answers the indexer's version and build, not the release
  installed
  - **Done when:** `atlas_status` and `/healthz` answer the installed release under a name of its own, read from the
    environment; a test shows `indexer_build()` is the same with and without it; no command is added to `cli.py`;
    `install-check.sh` warns when the running build is not the one the release recorded; `indexer/pyproject.toml` and
    `INDEXER_VERSION` agree, and a test says so; `docs/atlas-interface.md` says what a consumer may rely on within one
    version line, which field to compare, and that the compose project name is the Atlas's
  - **Verified by:** anyone
  - **Depends on:** N1, F1.21
- [ ] SO20 The live validation closes before the merge, from an install made from a checkout of the pull request
  - **Done when:** `docs/indexer/method.md` §4.7 to §4.9 and §4.17, and the pull request template, describe the round
    with the install made from a checkout of the pull request, up to date with `main`, one pull request at a time; a
    new step of `validate.sh` passes when what an install reads (the folders the installer copies, the compose file and
    `setup/`) is the same in the merged tree and in the validated one, and otherwise says which paths differ and what
    the round then costs; one pull request was validated both ways, with the same counts; one command on the author's
    machine chains the checkout of `main`, the reinstall and the `after` step
  - **Verified by:** the author (the live validation runs on his install)
  - **Depends on:** N2
- [ ] SO21 A published image per release, which carries H4-D10's proposal into this repository. It starts when one of
  these holds: F3.1 or F3.2 starts; an install must not build; the build of a new release fails on real machines
  - **Sketch:** missing where the image is published, for which architectures, and how an install picks between
    pulling it and building it; first step: the compose file reads the indexer image from a variable, and the image
    carries its release and commit as labels
  - **Verified by:** the author (whether a trigger holds is his call)
  - **Depends on:** SO18
- [ ] SO22 The install rehearsed in CI: a job installs the tree on a runner and ends in "All checks passed", and runs
  the rehearsal when a pull request drops a service or moves the release the entry script names
  - **Sketch:** missing whether the stack installs on a hosted runner, and where the rehearsal runs if it does not;
    first step: find out whether the stack installs on a hosted runner
  - **Verified by:** anyone
  - **Depends on:** N1
- [ ] SO23 The rest of the supply chain, for the published image: an SBOM and a scan (Trivy or Grype) in CI, and
  dependency updates by deliberate pull requests (Renovate)
  - **Sketch:** missing which finding fails a release, where the SBOM is published, and what an update must pass before
    it merges; first step: one scanner run on the indexer image built from `main`, its findings counted by severity
  - **Verified by:** anyone
  - **Depends on:** SO21
