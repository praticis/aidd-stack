"""Mirrors the indexer owns (D15): the workspace is read, never written.

The developer's clones are mounted read-only. Each repo gets a bare mirror under `$AIDD_MIRROR_DIR`
(`<tenant>/<repo>.git`), and every git read of the planner and of `index --ref` goes to the mirror:

  1. local sync   — `git fetch <workspace repo>`: the developer's branches (`refs/heads/*`, unpushed
                    ones included) and remote-tracking refs (`refs/remotes/origin/*`). No network, no
                    credentials; the first sync copies the objects once.
  2. remote fetch — `git fetch origin` with the service credential (read-only PAT from
                    `AIDD_GIT_TOKEN_FILE` via `git-askpass.sh`; ssh remotes are fetched over https for
                    that one command). Without a token an ssh remote is not fetched at all: the mirror then
                    follows the developer's own fetches, which is what step 1 already copied.

Nothing touches the developer's repo: no `FETCH_HEAD`, no ref updates under their feet, no files owned
by the container user, no `cannot lock ref` racing their `git pull`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .gitinfo import remote_url

_SAFE = ["-c", "safe.directory=*"]


def mirror_root() -> Path | None:
    v = os.getenv("AIDD_MIRROR_DIR", "").strip()
    return Path(v) if v else None


def mirror_path(root: Path, tenant: str, name: str) -> Path:
    return root / tenant / f"{name}.git"


def token_available() -> bool:
    if any(k.startswith("AIDD_GIT_TOKEN") and k != "AIDD_GIT_TOKEN_FILE" and v for k, v in os.environ.items()):
        return True
    f = os.getenv("AIDD_GIT_TOKEN_FILE", "").strip()
    try:
        return bool(f) and Path(f).is_file() and Path(f).stat().st_size > 0
    except OSError:
        return False


def _ssh_host(url: str) -> str | None:
    if url.startswith("git@") and ":" in url:
        return url[len("git@"):].split(":", 1)[0]
    if url.startswith("ssh://git@"):
        return url[len("ssh://git@"):].split("/", 1)[0].split(":", 1)[0]
    return None


def https_rewrite(url: str) -> list[str]:
    """`-c url.https://host/.insteadOf=...` so an ssh remote is fetched over https with the PAT."""
    host = _ssh_host(url)
    if not host:
        return []
    return ["-c", f"url.https://{host}/.insteadOf=git@{host}:", "-c", f"url.https://{host}/.insteadOf=ssh://git@{host}/"]


def _git(args: list[str], timeout: int) -> tuple[int, str]:
    try:
        out = subprocess.run(["git", *_SAFE, *args], capture_output=True, text=True, timeout=timeout, check=False,
                             env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except FileNotFoundError:
        return 127, "git not found"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    msg = (out.stderr or out.stdout).strip().splitlines()
    return out.returncode, (msg[-1] if msg else "")


def sync(workspace_repo: Path, mirror: Path, remote: bool = True, timeout: int = 300) -> tuple[bool, str]:
    """Bring `mirror` up to date. Returns (remote_ok, message); the local sync never fails silently —
    it raises, because without it there is nothing to index."""
    if not (mirror / "HEAD").exists():
        mirror.mkdir(parents=True, exist_ok=True)
        rc, msg = _git(["init", "--bare", "--quiet", str(mirror)], 60)
        if rc != 0:
            raise RuntimeError(f"cannot create mirror {mirror}: {msg}")
    m = ["-C", str(mirror)]
    url = remote_url(workspace_repo)
    if url:
        _git([*m, "config", "remote.origin.url", url], 30)
    else:
        _git([*m, "config", "--unset", "remote.origin.url"], 30)

    # 1. local: whatever the developer has (their branches + their view of origin). The first copy
    #    of a large repo over Docker Desktop's file sharing can fail its connectivity check ("did not
    #    send all necessary objects") although the pack arrived; a second pass completes it.
    for attempt in (1, 2):
        rc, msg = _git([*m, "fetch", "--prune", "--no-tags", "--quiet", str(workspace_repo),
                        "+refs/heads/*:refs/heads/*", "+refs/remotes/origin/*:refs/remotes/origin/*",
                        "^refs/remotes/origin/HEAD"], timeout)
        if rc == 0:
            break
    if rc != 0:
        raise RuntimeError(f"cannot sync mirror from {workspace_repo}: {msg}")
    head = subprocess.run(["git", *_SAFE, "-C", str(workspace_repo), "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()
    if head:
        _git([*m, "symbolic-ref", "refs/remotes/origin/HEAD", head], 30)

    # 2. remote: what the team pushed (service credential only)
    if not remote:
        return False, "local only (--no-fetch)"
    if not url:
        return False, "local only (no origin remote)"
    rewrite: list[str] = []
    if token_available():
        rewrite = https_rewrite(url)
    elif _ssh_host(url):
        return False, "local only (ssh remote and no service token — the mirror follows your own fetches)"
    rc, msg = _git([*rewrite, *m, "fetch", "--prune", "--no-tags", "--quiet", "origin",
                    "+refs/heads/*:refs/remotes/origin/*"], timeout)
    if rc != 0:
        return False, f"remote fetch failed ({msg}) — indexed on local refs"
    return True, "ok"
