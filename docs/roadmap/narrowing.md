# Narrowing to the Atlas — roadmap

> This repository keeps only the Atlas (H10-D1). These items take out what leaves, behind a lock that tells a machine
> what it would lose before it loses it, and end in the first release of the reduced Atlas (H11-D1). The fields are
> H10-D2's; the map of the roadmap is `docs/ROADMAP.md`.

- [ ] N1 The lock before the first removal: a machine keeps what it has, or is told of every service that leaves,
  whichever install command it repeats
  - **Done when:**
    1. Piped from `main`, the entry script installs the release it names, or the one `--version` asks for, by handing
       over to that tag's own installer. It accepts only the name of a published `vX.Y.Z` release or `main`, fetches
       the tag by its ref, is read whole before it runs, and hands over with an explicit standard input. It stops when
       it names no release, when it cannot fetch the tag, or when the commit it fetched is not the one it lists for that
       release. With no `--version` it never installs a release below the installed one. The installer has a mode that
       stops after the handover and says what it received.
    2. On an upgrade, from the entry script or from a checkout, the installer stops with status 3 and
       `No changes made.` before its first write when the tree it installs lacks a service the machine has (the
       installed compose file, as Compose reads it, together with the containers of the project), or when its version
       is an incompatible step above the installed one. It names each service and port that leaves, what stays on disk
       and how to remove it, the installed and the incoming version, and the command that keeps the installed one. A
       machine with no record, or with a record that names no release, counts as the first release. With no terminal
       it answers no. It goes on only after a `y`, or with the accepting variable.
    3. A run records its intent before its first write and closes the record when it succeeds: the version, the
       commit, whether the tree was dirty, the source, the previous install, the build the release expects and the id
       of each image it built. A command of the wrapper prints it without Docker.
    4. An upgrade keeps the images that were running: under the installed version's name when the record says that
       version built them, and as the previous install otherwise. An installer that finds images kept under its own
       version, with the ids its record lists, uses them instead of building, unless it is asked to rebuild.
    5. `CHANGELOG.md` exists at the root with the dated section of `v0.3.0` and a ceiling of its own.
    6. The tag `v0.3.0` is on the merge commit of the pull request that completes this item's installer, put there
       after the rehearsal passed on that commit. A later pull request makes the entry script name the tag and that
       commit, removes the branch that installed the default branch, and adds the test of the line: it names a tag that
       can be fetched, at the commit it says. A ruleset lets nobody move or delete a `v*` tag, and that pull request
       shows it.
    7. That pull request carries the summary of the rehearsal on a throwaway machine: a new install; an upgrade to a
       tree with one service fewer, refused, accepted and taken back without a rebuild; the same upgrade over an install
       made by the installer of `7fc0984`, and its way back; and the upgrade from a checkout.
    8. The tests of `setup/` cover the guard on fixture compose files and on every version of `docker-compose.yml` in
       the history, the version name the entry script accepts, the comparison of two versions, and the handover to each
       published release in the mode that stops before installing.
  - **Verified by:** the author (the rehearsal runs on a throwaway machine of his, and the tag is his)
  - **Depends on:** N2, SO16
- [ ] N2 The installer decoupled from what leaves: today its tenant prompt sits in the skills step, and its checkout
  test looks for folders that leave
  - **Done when:** the tenant prompt is outside the skills step, and an upgrade keeps `AIDD_TENANT`; the entry script
    and the installer are two files, the entry script names the variables it hands over, and the installer takes the
    repository address, when it needs it, from the entry script, never from itself, and its install folder too
    (`~/.aidd` when none is given), reading `.env` only there; the checkout test looks at
    `indexer/` and
    `docker-compose.yml`; every question goes through one function that says what it does with no terminal, and an
    option answers each with its default. Four changes of behavior, and no other: the copy of a synced folder leaves
    under `~/.aidd` no file its source lacks, with or without `rsync`; no default answer deletes a volume; a new
    environment file over the project's old volumes stops before the first write and says the two ways out; the
    installer creates `~/.local/bin/aidd` only when nothing is there or it is a link into `$AIDD_DIR`
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** SO17
- [ ] N3 Remove the process skills: `setup/skills/` (`scan` and `refine-business`), the installer's skills step and its
  `--project` mode
  - **Done when:** the repository has no `skills/` folder, and the installer has no skills step and no `--project`
    mode; the installer removes each skill link it made (a link in a tool's skills folder that points into
    `$AIDD_DIR/processed_skills` or at a `SKILL.md` of this repository) and `~/.aidd/processed_skills`, and nothing else
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N1, N2
- [ ] N4 Remove `mcp-git`: `git/`, its service, port 3003 and its entries in the MCP configurations this repository
  ships
  - **Done when:** no `mcp-git`, no port 3003 and no `git/` folder in the repository, the compose file, the gateway,
    the installer (its list of folders to copy included) or its check, and no `git` entry in `setup/.mcp.json` or
    `antigravity/mcp_config.json`; every container mounts the workspace read-only
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N1, N2, N3, SO16
  - **Not to do:** touch the git the indexer uses: the mirrors (`core/mirror.py`), `git-askpass.sh`, the `git-token`
    secret
- [ ] N5 Remove the `knowledge` service: its package, tests and contract, its command and package extra, its image
  stage, its compose service, port 3006 and its entries in the MCP configurations this repository ships
  - **Done when:** no `knowledge` in the compose file, the gateway, the installer, its check or an MCP configuration
    this repository ships; none of the pieces above is left; nothing imports `aidd_indexer.knowledge`; the image has
    no FastEmbed
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N1, SO16
  - **Not to do:** delete the vault's or Qdrant's data
- [ ] N6 Remove the process policy: `core/policy.py`, `policy.example.yaml`, the `aidd policy` commands and their
  tests, `AIDD_POLICY` and the `policy.yaml` mounts, and the policy steps of the installer and its check
  - **Done when:** `core/policy.py` and `policy.example.yaml` are gone and nothing imports the module; no
    `AIDD_POLICY`, no `policy.yaml` mount and no `aidd policy` in the compose file, the installer, its check or
    `cli.py`; the refs policy of `atlas.yaml` (`RefPolicy`) is untouched; `cli.py` no longer names the host-only
    `aidd logs`; every live snapshot was re-indexed
  - **Verified by:** the author (it changes the build, and the live snapshots are his)
  - **Depends on:** N5
  - **Not to do:** delete a user's `~/.aidd/policy.yaml`
- [ ] N7 Remove the Obsidian vault and `mcp-obsidian`: `obsidian/`, its service, port 3001, its entries in the MCP
  configurations this repository ships, and the vault's settings in the installer and its check
  - **Done when:** no `obsidian` in the compose file, the gateway, the installer, its check or an MCP configuration this
    repository ships; the vault folder and its notes are left where they are
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N3, N5, SO16
- [ ] N8 Remove Qdrant and `mcp-qdrant`: `qdrant/`, the two services, the declaration of the `qdrant_data` volume, port
  3002, its entries in the MCP configurations this repository ships, and Qdrant's settings in the installer and its
  check
  - **Done when:** no `qdrant` in the compose file, the gateway, the installer, its check or an MCP configuration this
    repository ships; `neo4j/SCHEMA.md` names no Qdrant; after the upgrade, a machine that had the `qdrant_data`
    volume still has it
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N3, N5, SO16
  - **Not to do:** decide F1.5 here
- [ ] N9 The gateway serves the `atlas` port only. Each removal takes its own lines out of the gateway, or the compose
  file would not start; this item checks what is left
  - **Done when:** with no profile active, the compose file publishes, of the MCP ports, only 3005; the `debug`
    profile keeps 3004 (`mcp-neo4j`); the 403 for a foreign `Host` and `Origin` still holds
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N4, N5, N7, N8
  - **Not to do:** change the `Host` and `Origin` checks or the port 3005
- [ ] N10 The installer and its check reduced to the Atlas
  - **Done when:** `install-check.sh` checks Neo4j, `mcp-atlas`, the gateway and the refresher, and passes; nothing
    the user holds under `~/.aidd` was deleted; the example convention sits next to the mechanism, in
    `indexer/conventions/`; `setup/.mcp.json` and `antigravity/mcp_config.json` hold the `atlas` entry alone, at the
    gateway's port 3005; the installer removes from a `.mcp.json` each entry whose name and URL are exactly those an
    earlier template of the Atlas wrote (`obsidian` at port 3001, `qdrant` at 3002, `git` at 3003, `knowledge` at
    3006), and no other: the one exception to SO16; `AGENTS.md`, `README.md`, `indexer/README.md`, `neo4j/SCHEMA.md`
    and `docs/indexing-process.md` describe none of the removed pieces as present
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N6, N9, SO16
  - **Not to do:** drop the removal of the host schedulers of earlier versions, which stays up to `v0.4.0` included
- [ ] N11 The first release of the reduced Atlas, `v0.4.0`
  - **Done when:** the entry script names the release after its rehearsal showed, from an install of `v0.3.0` and from
    one made by the installer of `7fc0984`, the installer stopping with every removed service named and finishing once
    accepted; after the upgrade `aidd atlas status` answers and `~/.aidd/aidd` is gone, and after going back to
    `v0.3.0` `~/.aidd/aidd status` answers. Its section of `CHANGELOG.md` says, for each thing removed, what it was,
    that its data stays on disk, how to remove what stays and how to stay on `v0.3.0`; it names the MCP prompt that
    replaces the `scan` skill, says the old host command is gone with no forwarding, and says what `aidd --version`
    prints. The rehearsal runs in the `install` job or, if the stack does not install on a hosted runner, on a
    throwaway machine of the author's
  - **Verified by:** the author (the tag is his, and the rehearsal may run on his throwaway machine)
  - **Depends on:** N10, N13, N14, SO17, SO18, SO19, F1.22
- [ ] N12 The reference convention leaves the image and stays as a test fixture, once each of the author's installs
  reads its content by path
  - **Done when:** the image installs no convention package; `AGENTS.md` and the example configuration name none; the
    tests load the convention file by path; every tenant's snapshots re-index once, and a dry run with the convention
    by id against one by path gives the same records; the section of `CHANGELOG.md` of the release that carries it
    says that a convention named by `id` no longer loads, and how to name it by path. The fixtures and the convention's
    id in the tests take a neutral name
  - **Verified by:** the author (the snapshots that re-index are his tenants')
  - **Depends on:** N1, F1.23
- [ ] N13 The `aidd` command is a launcher, and the Atlas's command is `aidd atlas`
  - **Done when:** `setup/aidd` is a launcher for bash 3.2 and later whose marker line carries an integer version, and
    `setup/aidd.sums` lists each version with its checksum, one line each, and only grows. `aidd <subject> [args]` runs
    `aidd-<subject>` from the launcher's own folder, else from PATH, with the same arguments, terminal and exit status.
    `aidd`, `aidd help` and `aidd --help` list the subjects found (executable files, the first of each name). A subject
    that is not `[a-z][a-z0-9-]*`, is a reserved word or is not found exits non-zero with the list. `aidd --version`
    prints `aidd launcher <n>`. Today's host script is `setup/aidd-atlas`: with no command it prints its own usage, and
    `aidd-atlas X` and `aidd atlas X` behave the same. The installer puts both in `~/.local/bin`, creating it and
    saying how to put it on PATH when it is not there. It writes the launcher, through a temporary file renamed in
    place, only when none is there, when the one there is a link into the install folder, or when it carries the
    marker with a lower version. An equal version with another checksum, or a file without the marker, is left in
    place and named. It never removes the launcher while another `aidd-*` is there, and it removes `~/.aidd/aidd`. The
    installer and `install-check.sh` call `aidd-atlas` by its absolute path, and the check fails when it is missing. No
    script under `setup/` calls `~/.aidd/aidd`, and only the step that removes it names it; no string under
    `indexer/aidd_indexer/mcp/` names it or a host command without `atlas`; a test says so. The tests of `setup/` cover
    each rule, on a macOS runner too.
    `docs/atlas-interface.md` names the host commands as `aidd atlas …`. Nothing under `indexer/aidd_indexer/` outside
    `mcp/` changes, and the gates give `0 repo(s) differ`
  - **Verified by:** the author (it changes the installer, and no CI job installs the stack)
  - **Depends on:** N1, SO17
  - **Not to do:** rename the container's `aidd`; forward an old command; edit `cli.py` (N6 rewords its host hint);
    drop the removal of the host schedulers of earlier versions, which stays up to `v0.4.0` included
- [ ] N14 The install folder is modular: the Atlas's files move under `~/.aidd/atlas/`, so another tool installs beside it
  in `~/.aidd` and each one installs, upgrades and leaves on its own, as the launcher lets each bring its own command
  (N13)
  - **Sketch:** missing the layout, and where what N3 to N8 leave stays; how an upgrade from a flat install moves it,
    rewriting the absolute paths `.env` holds; how going back hands `v0.3.0`'s installer that folder; which paths change
    in the guard, the record, the launcher's link rule, `install-check.sh`, the live validation and the indexer's hints
    (those under `cli.py` and `core/` change the build); first step: the layout, with the folders other tools use under
    `~/.aidd`
  - **Verified by:** the author (no CI job installs the stack)
  - **Depends on:** N1, N13
  - **Not to do:** move or delete anything a user holds under `~/.aidd` without the guard naming it first; change the
    compose project's name or its volumes' names
